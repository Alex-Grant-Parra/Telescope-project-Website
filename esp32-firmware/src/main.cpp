// ESP32 firmware for controlling a TMC2209 over UART and a NEMA17 with STEP/DIR
// Features:
// - JSON over Serial (115200) commands (newline-delimited)
// - Configure TMC2209 (microsteps, current, stealthChop2/SpreadCycle, enable/disable)
// - Set target speed (steps/sec) with acceleration ramp
// - Movement type: continuous or move a set distance in steps
// - Status responses + basic error handling

#include <Arduino.h>
#include <HardwareSerial.h>
#include <TMCStepper.h>
#include <ArduinoJson.h>

// Pins (from user)
const int stepPin = 18;
const int dirPin  = 19;
const int ledPin  = 2;
const int tmcUartTxPin = 17; // TX only (Red wire)

// UART & TMC
// TMCStepper requires a Stream; we use a dedicated HardwareSerial port in TX-only mode.
HardwareSerial TMCSerial(2); // UART2 on ESP32
// TMC2209 configuration values (set defaults; address 0, sense resistor typical 0.11 Ohm)
static const float RSENSE = 0.11f;
TMC2209Stepper driver(&TMCSerial, RSENSE, 0x00);

// Motion state
volatile bool enabled = false;
volatile bool runContinuous = false;
volatile int64_t stepsRemaining = 0; // for distance moves
volatile bool dirForward = true;

// Speed control via hardware timer
hw_timer_t* stepTimer = nullptr;
portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t stepIntervalMicros = 0; // half-period for toggling pin high/low
volatile bool stepPinState = false;

// Acceleration (simple linear ramp)
float currentSpeed = 0.0f;      // steps/sec
float targetSpeed = 0.0f;       // steps/sec
float maxAccel = 1000.0f;       // steps/sec^2
uint32_t lastSpeedUpdateMicros = 0;

// Local mirrors of TMC settings (avoid reading over UART when TX-only)
uint16_t cfg_microsteps = 16;
uint16_t cfg_current_mA = 500;
bool cfg_stealth = true; // stealthChop2

// Utility: compute interval from speed
inline uint32_t speedToInterval(float speed) {
	if (speed <= 0.0f) return 0;
	// Each toggle occurs twice per step (high then low), but we implement one toggle per ISR
	// We'll generate one full step with two ISRs; interval represents half period
	float halfPeriod = 1e6f / (speed * 2.0f); // micros
	if (halfPeriod < 2.0f) halfPeriod = 2.0f; // limit
	return (uint32_t)halfPeriod;
}

// Timer ISR to produce step pulses
void IRAM_ATTR onStepTimer() {
	if (!enabled || stepIntervalMicros == 0) return;
	// Toggle step pin
	stepPinState = !stepPinState;
	digitalWrite(stepPin, stepPinState ? HIGH : LOW);

	// Count steps on rising edge only
	if (stepPinState) {
		if (!runContinuous) {
			if (stepsRemaining > 0) {
				stepsRemaining--;
				if (stepsRemaining == 0) {
					// stop
					enabled = false;
				}
			}
		}
	}
}

void setEnable(bool en) {
	enabled = en;
	digitalWrite(ledPin, en ? HIGH : LOW);
	driver.toff(en ? 5 : 0); // toff>0 enables driver; 0 disables
}

void setDirection(bool forward) {
	dirForward = forward;
	digitalWrite(dirPin, forward ? HIGH : LOW);
}

void applySpeed(float spd) {
	targetSpeed = max(0.0f, spd);
}

void updateSpeedRamp() {
	uint32_t now = micros();
	uint32_t dt = now - lastSpeedUpdateMicros;
	if (dt < 1000) return; // update ~1kHz max
	lastSpeedUpdateMicros = now;

	float dtSec = dt / 1e6f;
	float delta = targetSpeed - currentSpeed;
	float maxDelta = maxAccel * dtSec;
	if (delta > maxDelta) delta = maxDelta;
	else if (delta < -maxDelta) delta = -maxDelta;
	currentSpeed += delta;
	// Update timer interval
	uint32_t interval = speedToInterval(currentSpeed);
	portENTER_CRITICAL(&timerMux);
	stepIntervalMicros = interval;
	if (interval > 0) {
		// Reconfigure alarm period
		timerAlarmWrite(stepTimer, interval, true);
		timerAlarmEnable(stepTimer);
	} else {
		timerAlarmDisable(stepTimer);
	}
	portEXIT_CRITICAL(&timerMux);
}

// JSON helpers
StaticJsonDocument<512> doc;
String readLine;

void sendOk(const JsonDocument& payload) {
	StaticJsonDocument<256> out;
	out["status"] = "ok";
	out["data"] = payload.as<JsonVariantConst>();
	serializeJson(out, Serial);
	Serial.println();
}

void sendError(const char* msg) {
	StaticJsonDocument<192> out;
	out["status"] = "error";
	out["message"] = msg;
	serializeJson(out, Serial);
	Serial.println();
}

void reportStatus() {
	StaticJsonDocument<256> st;
	st["enabled"] = enabled;
	st["runContinuous"] = runContinuous;
	st["stepsRemaining"] = (int64_t)stepsRemaining;
	st["dirForward"] = dirForward;
	st["speedCurrent_sps"] = currentSpeed;
	st["speedTarget_sps"] = targetSpeed;
		st["microsteps"] = cfg_microsteps;
		st["rms_current_mA"] = cfg_current_mA;
		st["stealthChop"] = cfg_stealth;
	sendOk(st);
}

void configureTMCDefaults() {
	// UART already begun on TMCSerial in setup
	driver.begin();
	driver.toff(0); // keep disabled until enabled
	driver.blank_time(24);
		driver.rms_current(cfg_current_mA); // mA default, adjust for your motor
		driver.microsteps(cfg_microsteps);
	// TMC2209: stealthChop when spreadCycle disabled
	driver.en_spreadCycle(!cfg_stealth);
	driver.pwm_autoscale(true);
	driver.pwm_autograd(true);
}

void handleCommand(JsonDocument& cmd) {
	const char* action = cmd["cmd"] | "";
	if (strcmp(action, "enable") == 0) {
		bool en = cmd["value"].as<bool>();
		setEnable(en);
		StaticJsonDocument<64> d; d["enabled"] = enabled; sendOk(d);
	} else if (strcmp(action, "set_dir") == 0) {
		bool forward = cmd["forward"].as<bool>();
		setDirection(forward);
		StaticJsonDocument<64> d; d["dirForward"] = dirForward; sendOk(d);
	} else if (strcmp(action, "start") == 0) {
		// Start continuous rotation at a given speed; optional direction
		// Payload: { cmd: "start", sps: <float>, forward?: <bool> }
		if (cmd["forward"].is<bool>()) {
			setDirection(cmd["forward"].as<bool>());
		}
		float sps = cmd["sps"].as<float>();
		applySpeed(sps);
		runContinuous = true;
		setEnable(true);
		StaticJsonDocument<128> d;
		d["enabled"] = enabled;
		d["continuous"] = runContinuous;
		d["dirForward"] = dirForward;
		d["target_sps"] = targetSpeed;
		sendOk(d);
	} else if (strcmp(action, "set_speed") == 0) {
		float sps = cmd["sps"].as<float>();
		applySpeed(sps);
		runContinuous = true;
		StaticJsonDocument<96> d; d["target_sps"] = targetSpeed; d["continuous"] = runContinuous; sendOk(d);
		} else if (strcmp(action, "move_steps") == 0) {
			int64_t steps = cmd["steps"].as<int64_t>();
			bool forward = cmd["forward"].is<bool>() ? cmd["forward"].as<bool>() : (steps >= 0);
			setDirection(forward);
		runContinuous = false;
			stepsRemaining = llabs(steps);
		setEnable(true);
		if (targetSpeed <= 0) applySpeed(cmd["sps"].as<float>());
		StaticJsonDocument<128> d; d["queued_steps"] = (int64_t)stepsRemaining; sendOk(d);
	} else if (strcmp(action, "stop") == 0) {
		applySpeed(0);
		runContinuous = false;
		stepsRemaining = 0;
		setEnable(false);
		StaticJsonDocument<32> d; d["stopped"] = true; sendOk(d);
		} else if (strcmp(action, "set_microsteps") == 0) {
		uint16_t ms = cmd["value"].as<uint16_t>();
		if (ms == 0) { sendError("microsteps must be >0"); return; }
			driver.microsteps(ms);
			cfg_microsteps = ms;
			StaticJsonDocument<64> d; d["microsteps"] = cfg_microsteps; sendOk(d);
	} else if (strcmp(action, "set_current") == 0) {
		uint16_t mA = cmd["mA"].as<uint16_t>();
			driver.rms_current(mA);
			cfg_current_mA = mA;
			StaticJsonDocument<64> d; d["rms_current_mA"] = cfg_current_mA; sendOk(d);
	} else if (strcmp(action, "set_mode") == 0) {
			const char* mode = cmd["mode"] | "stealth";
			bool stealth = (strcmp(mode, "stealth") == 0) || (strcmp(mode, "stealthChop") == 0) || (strcmp(mode, "stealthChop2") == 0);
			// stealthChop when spreadCycle disabled
			driver.en_spreadCycle(!stealth);
			if (!stealth) {
			// SpreadCycle tuning: ensure toff > 0; classic chopper
			driver.toff(5);
		}
			cfg_stealth = stealth;
			StaticJsonDocument<64> d; d["stealthChop"] = cfg_stealth; sendOk(d);
	} else if (strcmp(action, "set_accel") == 0) {
		float a = cmd["sps2"].as<float>();
		if (a > 0) maxAccel = a;
		StaticJsonDocument<64> d; d["maxAccel"] = maxAccel; sendOk(d);
	} else if (strcmp(action, "status") == 0) {
		reportStatus();
	} else {
		sendError("unknown cmd");
	}
}

void setup() {
	pinMode(stepPin, OUTPUT);
	pinMode(dirPin, OUTPUT);
	pinMode(ledPin, OUTPUT);
	digitalWrite(stepPin, LOW);
	digitalWrite(dirPin, LOW);
	digitalWrite(ledPin, LOW);

	Serial.begin(115200);
	while (!Serial) { delay(10); }

	// UART2 TX only: set RX to -1, TX to tmcUartTxPin
	TMCSerial.begin(115200, SERIAL_8N1, -1, tmcUartTxPin);

	configureTMCDefaults();

	// Hardware timer at microsecond resolution
	stepTimer = timerBegin(0, 80, true); // 80 prescaler -> 1MHz ticks
	timerAttachInterrupt(stepTimer, &onStepTimer, true);
	timerAlarmWrite(stepTimer, 1000, true); // default 1kHz half period
	timerAlarmDisable(stepTimer);

	lastSpeedUpdateMicros = micros();
	StaticJsonDocument<64> boot; boot["boot"] = true; sendOk(boot);
}

void loop() {
	// Read newline-delimited JSON
	while (Serial.available()) {
		char c = (char)Serial.read();
		if (c == '\n') {
			DeserializationError err = deserializeJson(doc, readLine);
			readLine = "";
			if (err) {
				sendError("json parse error");
			} else {
				handleCommand(doc);
				doc.clear();
			}
		} else if (c != '\r') {
			readLine += c;
			if (readLine.length() > 480) {
				readLine = "";
				sendError("line too long");
			}
		}
	}

	// Update speed ramp
	updateSpeedRamp();

	// Auto-enable timer when running
	if (enabled && stepIntervalMicros > 0) {
		timerAlarmEnable(stepTimer);
	}
}

