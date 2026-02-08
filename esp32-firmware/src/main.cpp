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
#include <SPIFFS.h>
#include <FS.h>

// Motor Controller Class
class Motor {
public:
    // Pin assignments
    const int stepPin;
    const int dirPin;
    const int ledPin;
    const int tmcUartTxPin;
    
    // UART & TMC
    HardwareSerial* tmcSerial;
    TMC2209Stepper* driver;
    static const float RSENSE;
    
    // Motion state
    volatile bool enabled;
    volatile bool runContinuous;
    volatile int64_t stepsRemaining;
    volatile bool dirForward;
    
    // Speed control
    volatile uint32_t stepIntervalMicros;
    volatile bool stepPinState;
    
    // Acceleration (simple linear ramp)
    float currentSpeed;
    float targetSpeed;
    float maxAccel;
    uint32_t lastSpeedUpdateMicros;
    
    // Local mirrors of TMC settings (avoid reading over UART when TX-only)
    uint16_t cfg_microsteps;
    uint16_t cfg_current_mA;
    bool cfg_stealth;
    
    // Constructor
    Motor(int step, int dir, int led, int tmcTx, HardwareSerial* serial, uint8_t tmcAddress = 0x00)
        : stepPin(step), dirPin(dir), ledPin(led), tmcUartTxPin(tmcTx),
          tmcSerial(serial),
          enabled(false), runContinuous(false), stepsRemaining(0), dirForward(true),
          stepIntervalMicros(0), stepPinState(false),
          currentSpeed(0.0f), targetSpeed(0.0f), lastSpeedUpdateMicros(0)
    {
        // Use default configuration values
        maxAccel = defaultConfig.max_accel;
        cfg_microsteps = defaultConfig.microsteps;
        cfg_current_mA = defaultConfig.current_mA;
        cfg_stealth = defaultConfig.stealth_mode;
        
        driver = new TMC2209Stepper(tmcSerial, RSENSE, tmcAddress);
    }
    
    void initializePins() {
        pinMode(stepPin, OUTPUT);
        pinMode(dirPin, OUTPUT);
        pinMode(ledPin, OUTPUT);
        digitalWrite(stepPin, LOW);
        digitalWrite(dirPin, LOW);
        digitalWrite(ledPin, LOW);
    }
    
    void initializeUART() {
        tmcSerial->begin(115200, SERIAL_8N1, -1, tmcUartTxPin);
    }
    
    void configureTMCDefaults() {
        driver->begin();
        driver->toff(0); // keep disabled until enabled
        driver->blank_time(24);
        driver->rms_current(cfg_current_mA);
        driver->microsteps(cfg_microsteps);
        driver->en_spreadCycle(!cfg_stealth);
        driver->pwm_autoscale(true);
        driver->pwm_autograd(true);
    }
    
    void setEnable(bool en) {
        enabled = en;
        digitalWrite(ledPin, en ? HIGH : LOW);
        driver->toff(en ? 5 : 0);
    }
    
    void setDirection(bool forward) {
        dirForward = forward;
        digitalWrite(dirPin, forward ? HIGH : LOW);
    }
    
    void applySpeed(float spd) {
        targetSpeed = max(0.0f, spd);
    }
    
    uint32_t speedToInterval(float speed) {
        if (speed <= 0.0f) return 0;
        float halfPeriod = 1e6f / (speed * 2.0f);
        if (halfPeriod < 2.0f) halfPeriod = 2.0f;
        return (uint32_t)halfPeriod;
    }
    
    void stepTimerISR() {
        if (!enabled || stepIntervalMicros == 0) return;
        stepPinState = !stepPinState;
        digitalWrite(stepPin, stepPinState ? HIGH : LOW);
        
        if (stepPinState) {
            if (!runContinuous) {
                if (stepsRemaining > 0) {
                    stepsRemaining--;
                    if (stepsRemaining == 0) {
                        enabled = false;
                    }
                }
            }
        }
    }
};

const float Motor::RSENSE = 0.11f;

// Motor configuration structure for clear instantiation
struct MotorConfig {
    String id;
    int stepPin;
    int dirPin;
    int ledPin;
    int tmcUartTxPin;
    HardwareSerial* serial;
    uint8_t tmcAddress;
    bool enabled;
    String description;
};

// Dynamic motor configuration - loaded from file
MotorConfig* motorConfigs = nullptr;
int NUM_MOTORS = 0;

// Default configuration values
struct DefaultConfig {
    uint16_t microsteps = 16;
    uint16_t current_mA = 500;
    bool stealth_mode = true;
    float max_accel = 1000.0f;
} defaultConfig;

// Global motor instances and timer
Motor** motors = nullptr; // Dynamically allocated array
hw_timer_t* stepTimer = nullptr;
portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;
int activeMotorIndex = 0; // Currently active motor for timer ISR

// Helper function to get HardwareSerial instance by port number
HardwareSerial* getSerialPort(int portNum) {
    switch(portNum) {
        case 0: return &Serial;
        case 1: return &Serial1;
        case 2: return &Serial2;
        default: return &Serial2; // Default fallback
    }
}

// Helper function to find motor by ID
Motor* findMotor(const char* motorId) {
    for (int i = 0; i < NUM_MOTORS; i++) {
        if (motorConfigs[i].id.equals(motorId)) {
            return motors[i];
        }
    }
    return nullptr;
}

// Load motor configuration from SPIFFS
bool loadMotorConfig() {
    if (!SPIFFS.begin(true)) {
        Serial.println("[CONFIG] Failed to mount SPIFFS");
        return false;
    }
    
    if (!SPIFFS.exists("/motor_config.json")) {
        Serial.println("[CONFIG] motor_config.json not found, using defaults");
        return false;
    }
    
    File configFile = SPIFFS.open("/motor_config.json", "r");
    if (!configFile) {
        Serial.println("[CONFIG] Failed to open motor_config.json");
        return false;
    }
    
    size_t size = configFile.size();
    if (size == 0) {
        Serial.println("[CONFIG] motor_config.json is empty");
        configFile.close();
        return false;
    }
    
    // Allocate buffer for JSON
    std::unique_ptr<char[]> buf(new char[size]);
    configFile.readBytes(buf.get(), size);
    configFile.close();
    
    // Parse JSON
    StaticJsonDocument<2048> doc;
    DeserializationError error = deserializeJson(doc, buf.get());
    
    if (error) {
        Serial.printf("[CONFIG] Failed to parse JSON: %s\n", error.c_str());
        return false;
    }
    
    // Load defaults
    if (doc.containsKey("defaults")) {
        JsonObject defaults = doc["defaults"];
        defaultConfig.microsteps = defaults["microsteps"] | 16;
        defaultConfig.current_mA = defaults["current_mA"] | 500;
        defaultConfig.stealth_mode = defaults["stealth_mode"] | true;
        defaultConfig.max_accel = defaults["max_accel"] | 1000.0f;
    }
    
    // Count enabled motors
    JsonArray motorsArray = doc["motors"];
    int enabledCount = 0;
    for (JsonObject motor : motorsArray) {
        if (motor["enabled"] | false) {
            enabledCount++;
        }
    }
    
    if (enabledCount == 0) {
        Serial.println("[CONFIG] No enabled motors found in configuration");
        return false;
    }
    
    // Allocate memory for motor configs
    NUM_MOTORS = enabledCount;
    motorConfigs = new MotorConfig[NUM_MOTORS];
    
    // Load motor configurations
    int configIndex = 0;
    for (JsonObject motor : motorsArray) {
        if (!(motor["enabled"] | false)) {
            continue; // Skip disabled motors
        }
        
        if (configIndex >= NUM_MOTORS) {
            break; // Safety check
        }
        
        MotorConfig& config = motorConfigs[configIndex];
        config.id = motor["id"] | ("motor" + String(configIndex + 1));
        config.stepPin = motor["stepPin"] | 18;
        config.dirPin = motor["dirPin"] | 19;
        config.ledPin = motor["ledPin"] | 2;
        config.tmcUartTxPin = motor["tmcUartTxPin"] | 17;
        
        int serialPort = motor["serialPort"] | 2;
        config.serial = getSerialPort(serialPort);
        
        // Parse TMC address (handle both string hex and integer)
        if (motor["tmcAddress"].is<const char*>()) {
            const char* addrStr = motor["tmcAddress"];
            config.tmcAddress = (uint8_t)strtol(addrStr, nullptr, 16);
        } else {
            config.tmcAddress = motor["tmcAddress"] | 0x00;
        }
        
        config.enabled = motor["enabled"] | true;
        config.description = motor["description"] | "Motor";
        
        Serial.printf("[CONFIG] Loaded motor %s: step=%d, dir=%d, led=%d, uart=%d, addr=0x%02X\n",
                     config.id.c_str(), config.stepPin, config.dirPin, 
                     config.ledPin, config.tmcUartTxPin, config.tmcAddress);
        
        configIndex++;
    }
    
    Serial.printf("[CONFIG] Successfully loaded %d motor configurations\n", NUM_MOTORS);
    return true;
}

// Create default configuration if file doesn't exist
void createDefaultConfig() {
    Serial.println("[CONFIG] Creating default motor configuration");
    
    NUM_MOTORS = 1;
    motorConfigs = new MotorConfig[NUM_MOTORS];
    
    motorConfigs[0] = {
        "motor1",    // id
        18,          // stepPin
        19,          // dirPin
        2,           // ledPin
        17,          // tmcUartTxPin
        &Serial2,    // serial
        0x00,        // tmcAddress
        true,        // enabled
        "Default motor" // description
    };
    
    Serial.println("[CONFIG] Using default single motor configuration");
}

// Timer ISR to produce step pulses (handles active motor)
void IRAM_ATTR onStepTimer() {
    if (activeMotorIndex >= 0 && activeMotorIndex < NUM_MOTORS) {
        motors[activeMotorIndex]->stepTimerISR();
    }
}

void updateSpeedRamp() {
	// Update speed ramp for all motors
	for (int i = 0; i < NUM_MOTORS; i++) {
		Motor* motor = motors[i];
		uint32_t now = micros();
		uint32_t dt = now - motor->lastSpeedUpdateMicros;
		if (dt < 1000) continue; // update ~1kHz max
		motor->lastSpeedUpdateMicros = now;

		float dtSec = dt / 1e6f;
		float delta = motor->targetSpeed - motor->currentSpeed;
		float maxDelta = motor->maxAccel * dtSec;
		if (delta > maxDelta) delta = maxDelta;
		else if (delta < -maxDelta) delta = -maxDelta;
		motor->currentSpeed += delta;
		
		// Update timer interval
		uint32_t interval = motor->speedToInterval(motor->currentSpeed);
		portENTER_CRITICAL(&timerMux);
		motor->stepIntervalMicros = interval;
		
		// Set active motor for timer (prioritize enabled motors)
		if (motor->enabled && interval > 0) {
			activeMotorIndex = i;
			timerAlarmWrite(stepTimer, interval, true);
			timerAlarmEnable(stepTimer);
		}
		portEXIT_CRITICAL(&timerMux);
	}
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

void reportStatus(const char* motorId = nullptr) {
	if (motorId == nullptr) {
		// Return status of all motors
		StaticJsonDocument<512> allStatus;
		for (int i = 0; i < NUM_MOTORS; i++) {
			StaticJsonDocument<256> st;
			Motor* motor = motors[i];
			st["enabled"] = motor->enabled;
			st["runContinuous"] = motor->runContinuous;
			st["stepsRemaining"] = (int64_t)motor->stepsRemaining;
			st["dirForward"] = motor->dirForward;
			st["speedCurrent_sps"] = motor->currentSpeed;
			st["speedTarget_sps"] = motor->targetSpeed;
			st["microsteps"] = motor->cfg_microsteps;
			st["rms_current_mA"] = motor->cfg_current_mA;
			st["stealthChop"] = motor->cfg_stealth;
			allStatus[motorConfigs[i].id.c_str()] = st;
		}
		sendOk(allStatus);
	} else {
		Motor* motor = findMotor(motorId);
		if (!motor) {
			sendError("motor not found");
			return;
		}
		StaticJsonDocument<256> st;
		st["motorId"] = motorId;
		st["enabled"] = motor->enabled;
		st["runContinuous"] = motor->runContinuous;
		st["stepsRemaining"] = (int64_t)motor->stepsRemaining;
		st["dirForward"] = motor->dirForward;
		st["speedCurrent_sps"] = motor->currentSpeed;
		st["speedTarget_sps"] = motor->targetSpeed;
		st["microsteps"] = motor->cfg_microsteps;
		st["rms_current_mA"] = motor->cfg_current_mA;
		st["stealthChop"] = motor->cfg_stealth;
		sendOk(st);
	}
}

void handleCommand(JsonDocument& cmd) {
	const char* action = cmd["cmd"] | "";
	const char* motorId = cmd["motor"] | "motor1"; // Default to motor1 for backwards compatibility
	
	// Find the motor
	Motor* motor = findMotor(motorId);
	if (!motor && strcmp(action, "status") != 0) {
		sendError("motor not found");
		return;
	}
	
	if (strcmp(action, "enable") == 0) {
		bool en = cmd["value"].as<bool>();
		motor->setEnable(en);
		StaticJsonDocument<64> d; 
		d["motorId"] = motorId;
		d["enabled"] = motor->enabled; 
		sendOk(d);
	} else if (strcmp(action, "set_dir") == 0) {
		bool forward = cmd["forward"].as<bool>();
		motor->setDirection(forward);
		StaticJsonDocument<64> d; 
		d["motorId"] = motorId;
		d["dirForward"] = motor->dirForward; 
		sendOk(d);
	} else if (strcmp(action, "start") == 0) {
		// Start continuous rotation at a given speed; optional direction
		// Payload: { cmd: "start", motor: "motor1", sps: <float>, forward?: <bool> }
		if (cmd["forward"].is<bool>()) {
			motor->setDirection(cmd["forward"].as<bool>());
		}
		float sps = cmd["sps"].as<float>();
		motor->applySpeed(sps);
		motor->runContinuous = true;
		motor->setEnable(true);
		StaticJsonDocument<128> d;
		d["motorId"] = motorId;
		d["enabled"] = motor->enabled;
		d["continuous"] = motor->runContinuous;
		d["dirForward"] = motor->dirForward;
		d["target_sps"] = motor->targetSpeed;
		sendOk(d);
	} else if (strcmp(action, "set_speed") == 0) {
		float sps = cmd["sps"].as<float>();
		motor->applySpeed(sps);
		motor->runContinuous = true;
		StaticJsonDocument<96> d; 
		d["motorId"] = motorId;
		d["target_sps"] = motor->targetSpeed; 
		d["continuous"] = motor->runContinuous; 
		sendOk(d);
	} else if (strcmp(action, "move_steps") == 0) {
		int64_t steps = cmd["steps"].as<int64_t>();
		bool forward = cmd["forward"].is<bool>() ? cmd["forward"].as<bool>() : (steps >= 0);
		motor->setDirection(forward);
		motor->runContinuous = false;
		motor->stepsRemaining = llabs(steps);
		motor->setEnable(true);
		if (motor->targetSpeed <= 0) motor->applySpeed(cmd["sps"].as<float>());
		StaticJsonDocument<128> d; 
		d["motorId"] = motorId;
		d["queued_steps"] = (int64_t)motor->stepsRemaining; 
		sendOk(d);
	} else if (strcmp(action, "stop") == 0) {
		motor->applySpeed(0);
		motor->runContinuous = false;
		motor->stepsRemaining = 0;
		motor->setEnable(false);
		StaticJsonDocument<32> d; 
		d["motorId"] = motorId;
		d["stopped"] = true; 
		sendOk(d);
	} else if (strcmp(action, "set_microsteps") == 0) {
		uint16_t ms = cmd["value"].as<uint16_t>();
		if (ms == 0) { sendError("microsteps must be >0"); return; }
		motor->driver->microsteps(ms);
		motor->cfg_microsteps = ms;
		StaticJsonDocument<64> d; 
		d["motorId"] = motorId;
		d["microsteps"] = motor->cfg_microsteps; 
		sendOk(d);
	} else if (strcmp(action, "set_current") == 0) {
		uint16_t mA = cmd["mA"].as<uint16_t>();
		motor->driver->rms_current(mA);
		motor->cfg_current_mA = mA;
		StaticJsonDocument<64> d; 
		d["motorId"] = motorId;
		d["rms_current_mA"] = motor->cfg_current_mA; 
		sendOk(d);
	} else if (strcmp(action, "set_mode") == 0) {
		const char* mode = cmd["mode"] | "stealth";
		bool stealth = (strcmp(mode, "stealth") == 0) || (strcmp(mode, "stealthChop") == 0) || (strcmp(mode, "stealthChop2") == 0);
		// stealthChop when spreadCycle disabled
		motor->driver->en_spreadCycle(!stealth);
		if (!stealth) {
			// SpreadCycle tuning: ensure toff > 0; classic chopper
			motor->driver->toff(5);
		}
		motor->cfg_stealth = stealth;
		StaticJsonDocument<64> d; 
		d["motorId"] = motorId;
		d["stealthChop"] = motor->cfg_stealth; 
		sendOk(d);
	} else if (strcmp(action, "set_accel") == 0) {
		float a = cmd["sps2"].as<float>();
		if (a > 0) motor->maxAccel = a;
		StaticJsonDocument<64> d; 
		d["motorId"] = motorId;
		d["maxAccel"] = motor->maxAccel; 
		sendOk(d);
	} else if (strcmp(action, "status") == 0) {
		reportStatus(cmd["motor"].is<const char*>() ? motorId : nullptr);
	} else {
		sendError("unknown cmd");
	}
}

void setup() {
	Serial.begin(115200);
	while (!Serial) { delay(10); }

	Serial.println("[BOOT] ESP32 Motor Controller starting...");

	// Load motor configuration from file
	if (!loadMotorConfig()) {
		Serial.println("[BOOT] Failed to load config, using defaults");
		createDefaultConfig();
	}

	// Allocate memory for motor instances
	motors = new Motor*[NUM_MOTORS];

	// Initialize all motors from configuration
	for (int i = 0; i < NUM_MOTORS; i++) {
		MotorConfig& config = motorConfigs[i];
		Serial.printf("[BOOT] Initializing %s (%s)\n", config.id.c_str(), config.description.c_str());
		
		motors[i] = new Motor(config.stepPin, config.dirPin, config.ledPin, 
		                     config.tmcUartTxPin, config.serial, config.tmcAddress);
		
		// Initialize each motor
		motors[i]->initializePins();
		motors[i]->initializeUART();
		motors[i]->configureTMCDefaults();
		motors[i]->lastSpeedUpdateMicros = micros();
	}

	// Hardware timer at microsecond resolution
	stepTimer = timerBegin(0, 80, true); // 80 prescaler -> 1MHz ticks
	timerAttachInterrupt(stepTimer, &onStepTimer, true);
	timerAlarmWrite(stepTimer, 1000, true); // default 1kHz half period
	timerAlarmDisable(stepTimer);

	StaticJsonDocument<256> boot; 
	boot["boot"] = true;
	boot["motors"] = NUM_MOTORS;
	boot["config_loaded"] = (motorConfigs != nullptr);
	JsonArray motorList = boot.createNestedArray("motorIds");
	for (int i = 0; i < NUM_MOTORS; i++) {
		motorList.add(motorConfigs[i].id.c_str());
	}
	sendOk(boot);
	
	Serial.printf("[BOOT] Motor controller ready with %d motors\n", NUM_MOTORS);
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

	// Update speed ramp for all motors
	updateSpeedRamp();

	// Auto-enable timer when any motor is running
	bool anyMotorRunning = false;
	for (int i = 0; i < NUM_MOTORS; i++) {
		if (motors[i]->enabled && motors[i]->stepIntervalMicros > 0) {
			anyMotorRunning = true;
			break;
		}
	}
	if (anyMotorRunning) {
		timerAlarmEnable(stepTimer);
	}
}

