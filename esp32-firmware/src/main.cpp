#include <Arduino.h>
#include <ArduinoJson.h>

// Stepper motor specifications
#define STEPS_PER_REVOLUTION 1600  // 200 * 8 microsteps
#define PULSE_WIDTH_US 10          // Minimum for TMC2209

class Motor {
private:
  int stepPin;
  int dirPin;
  int enPin;
  bool enabled;
  bool moving;
  volatile bool stopRequested;
  uint32_t stepsPerRevolution;
  uint32_t stepDelayUs;

public:
  Motor(int step, int dir, int en, uint32_t stepsPerRev = STEPS_PER_REVOLUTION)
    : stepPin(step), dirPin(dir), enPin(en), enabled(false), moving(false),
      stopRequested(false), stepsPerRevolution(stepsPerRev), stepDelayUs(1250) {
  }

  void initialize() {
    pinMode(stepPin, OUTPUT);
    pinMode(dirPin, OUTPUT);
    pinMode(enPin, OUTPUT);
    digitalWrite(stepPin, LOW);
    digitalWrite(dirPin, LOW);
    digitalWrite(enPin, HIGH);  // Disabled by default
  }

  void cleanup() {
    // Set pins to safe states before deletion
    digitalWrite(enPin, HIGH);  // Disable driver
    digitalWrite(stepPin, LOW);
    digitalWrite(dirPin, LOW);
  }

  void setSpeed(uint32_t delayUs) {
    stepDelayUs = delayUs;
  }

  void engage() {
    digitalWrite(enPin, LOW);  // Active low
    enabled = true;
  }

  void disengage() {
    digitalWrite(enPin, HIGH);  // Disable
    enabled = false;
  }

  bool isEnabled() {
    return enabled;
  }

  bool isMoving() {
    return moving;
  }

  uint32_t getStepDelayUs() const {
    return stepDelayUs;
  }

  uint32_t getStepsPerRevolution() const {
    return stepsPerRevolution;
  }

  void stop() {
    if (!moving) {
      return;
    }

    stopRequested = true;
  }

  void turnDegrees(float degrees, bool forward = true) {
    if (!enabled) {
      Serial.println("ERROR: Motor is not engaged!");
      return;
    }

    stopRequested = false;
    moving = true;

    uint32_t stepsNeeded = (uint32_t)((degrees / 360.0) * stepsPerRevolution);

    digitalWrite(dirPin, forward ? HIGH : LOW);

    for (uint32_t i = 0; i < stepsNeeded; i++) {
      if (stopRequested) {
        break;
      }

      digitalWrite(stepPin, HIGH);
      delayMicroseconds(PULSE_WIDTH_US);
      digitalWrite(stepPin, LOW);
      delayMicroseconds(stepDelayUs - PULSE_WIDTH_US);

      if ((i + 1) % 1000 == 0) {
        // Progress callback hook reserved for future use.
      }
    }

    moving = false;
  }
};

constexpr int kLedPin = 2;
constexpr uint32_t kDefaultLedBlinkMs = 500;

struct MotorEntry {
  String id;
  Motor* motor;
  bool owned;
};

constexpr size_t kMaxMotors = 8;
MotorEntry g_motors[kMaxMotors];
String g_rxLine;
bool g_ledBlinkEnabled = false;
bool g_ledState = false;
uint32_t g_ledBlinkIntervalMs = kDefaultLedBlinkMs;
uint32_t g_lastLedToggleMs = 0;
uint32_t g_ledAutoOffAtMs = 0;

Motor* findMotor(const String& id) {
  for (size_t i = 0; i < kMaxMotors; i++) {
    if (g_motors[i].motor != nullptr && g_motors[i].id == id) {
      return g_motors[i].motor;
    }
  }
  return nullptr;
}

bool registerMotor(const String& id, Motor* motor, bool owned) {
  if (id.length() == 0 || motor == nullptr) {
    return false;
  }
  if (findMotor(id) != nullptr) {
    return false;
  }
  for (size_t i = 0; i < kMaxMotors; i++) {
    if (g_motors[i].motor == nullptr) {
      g_motors[i].id = id;
      g_motors[i].motor = motor;
      g_motors[i].owned = owned;
      return true;
    }
  }
  return false;
}

void sendError(const char* message) {
  StaticJsonDocument<192> resp;
  resp["status"] = "error";
  resp["message"] = message;
  serializeJson(resp, Serial);
  Serial.println();
}

void sendOkEmpty() {
  StaticJsonDocument<64> resp;
  resp["status"] = "ok";
  serializeJson(resp, Serial);
  Serial.println();
}

void sendOkStatus(const String& motorId, Motor* motor) {
  StaticJsonDocument<192> resp;
  resp["status"] = "ok";
  JsonObject data = resp.createNestedObject("data");
  data["motor"] = motorId;
  data["enabled"] = motor->isEnabled();
  data["moving"] = motor->isMoving();
  data["step_delay_us"] = motor->getStepDelayUs();
  data["steps_per_rev"] = motor->getStepsPerRevolution();
  serializeJson(resp, Serial);
  Serial.println();
}

void sendOkMotorList() {
  StaticJsonDocument<256> resp;
  resp["status"] = "ok";
  JsonObject data = resp.createNestedObject("data");
  JsonArray motors = data.createNestedArray("motors");
  for (size_t i = 0; i < kMaxMotors; i++) {
    if (g_motors[i].motor != nullptr) {
      motors.add(g_motors[i].id);
    }
  }
  serializeJson(resp, Serial);
  Serial.println();
}

void handleCommand(const String& line) {
  if (line.length() == 0) {
    return;
  }

  StaticJsonDocument<384> req;
  DeserializationError err = deserializeJson(req, line);
  if (err) {
    sendError("Invalid JSON");
    return;
  }

  const char* cmd = req["cmd"] | "";
  if (strlen(cmd) == 0) {
    sendError("Missing cmd");
    return;
  }

  if (strcmp(cmd, "led") == 0) {
    if (req.containsKey("mode")) {
      const char* mode = req["mode"] | "";
      if (strcmp(mode, "on") == 0) {
        g_ledBlinkEnabled = false;
        g_ledState = true;
      } else if (strcmp(mode, "off") == 0) {
        g_ledBlinkEnabled = false;
        g_ledState = false;
      } else if (strcmp(mode, "blink") == 0) {
        g_ledBlinkEnabled = true;
        uint32_t intervalMs = req["interval_ms"] | kDefaultLedBlinkMs;
        g_ledBlinkIntervalMs = intervalMs == 0 ? kDefaultLedBlinkMs : intervalMs;
        g_lastLedToggleMs = millis();
        if (req.containsKey("auto_off_ms")) {
          uint32_t autoOffMs = req["auto_off_ms"] | 0;
          g_ledAutoOffAtMs = autoOffMs > 0 ? (g_lastLedToggleMs + autoOffMs) : 0;
        } else {
          g_ledAutoOffAtMs = 0;
        }
      } else {
        sendError("Invalid LED mode");
        return;
      }
      sendOkEmpty();
      return;
    }

    if (req.containsKey("on")) {
      bool on = req["on"] | false;
      g_ledBlinkEnabled = false;
      g_ledState = on;
      sendOkEmpty();
      return;
    }

    sendError("Missing LED mode");
    return;
  }

  if (strcmp(cmd, "create_motor") == 0) {
    const char* motorId = req["motor"] | "";
    if (strlen(motorId) == 0) {
      sendError("Missing motor id");
      return;
    }
    if (findMotor(motorId) != nullptr) {
      sendError("Motor already exists");
      return;
    }
    if (!req.containsKey("step") || !req.containsKey("dir") || !req.containsKey("en")) {
      sendError("Missing motor pins");
      return;
    }
    int stepPin = req["step"].as<int>();
    int dirPin = req["dir"].as<int>();
    int enPin = req["en"].as<int>();
    uint32_t stepsPerRev = req["steps_per_rev"] | STEPS_PER_REVOLUTION;
    Motor* motor = new Motor(stepPin, dirPin, enPin, stepsPerRev);
    motor->initialize();
    uint32_t speedUs = req["speed_us"] | motor->getStepDelayUs();
    if (speedUs <= PULSE_WIDTH_US) {
      speedUs = PULSE_WIDTH_US + 1;
    }
    motor->setSpeed(speedUs);
    bool engage = req["engage"] | false;
    if (engage) {
      motor->engage();
    }
    if (!registerMotor(motorId, motor, true)) {
      delete motor;
      sendError("Motor registry full");
      return;
    }
    sendOkEmpty();
    return;
  }

  if (strcmp(cmd, "list_motors") == 0) {
    sendOkMotorList();
    return;
  }

  if (strcmp(cmd, "delete_motor") == 0) {
    const char* motorId = req["motor"] | "";
    if (strlen(motorId) == 0) {
      sendError("Missing motor id");
      return;
    }
    for (size_t i = 0; i < kMaxMotors; i++) {
      if (g_motors[i].motor != nullptr && g_motors[i].id == motorId) {
        g_motors[i].motor->cleanup();
        if (g_motors[i].owned) {
          delete g_motors[i].motor;
        }
        g_motors[i].motor = nullptr;
        g_motors[i].id = "";
        g_motors[i].owned = false;
        sendOkEmpty();
        return;
      }
    }
    sendError("Motor not found");
    return;
  }

  const char* motorId = req["motor"] | "";
  if (strlen(motorId) == 0) {
    sendError("Missing motor id");
    return;
  }
  Motor* motor = findMotor(motorId);
  if (motor == nullptr) {
    sendError("Unknown motor id");
    return;
  }

  if (strcmp(cmd, "engage") == 0) {
    motor->engage();
    sendOkEmpty();
    return;
  }
  if (strcmp(cmd, "disengage") == 0) {
    motor->disengage();
    sendOkEmpty();
    return;
  }
  if (strcmp(cmd, "enable") == 0) {
    bool on = req["value"] | false;
    if (on) {
      motor->engage();
    } else {
      motor->disengage();
    }
    sendOkEmpty();
    return;
  }
  if (strcmp(cmd, "set_speed") == 0) {
    uint32_t speedUs = motor->getStepDelayUs();
    if (req.containsKey("speed_us")) {
      speedUs = req["speed_us"].as<uint32_t>();
    } else if (req.containsKey("sps")) {
      float sps = req["sps"].as<float>();
      if (sps <= 0.0f) {
        sendError("Invalid sps");
        return;
      }
      float delay = 1000000.0f / sps;
      if (delay < (PULSE_WIDTH_US + 1)) {
        delay = PULSE_WIDTH_US + 1;
      }
      speedUs = static_cast<uint32_t>(delay);
    } else {
      sendError("Missing speed value");
      return;
    }
    if (speedUs <= PULSE_WIDTH_US) {
      speedUs = PULSE_WIDTH_US + 1;
    }
    motor->setSpeed(speedUs);
    sendOkEmpty();
    return;
  }
  if (strcmp(cmd, "turn_degrees") == 0) {
    if (!req.containsKey("degrees")) {
      sendError("Missing degrees");
      return;
    }
    float degrees = req["degrees"].as<float>();
    bool forward = req["forward"] | true;
    motor->turnDegrees(degrees, forward);
    sendOkEmpty();
    return;
  }
  if (strcmp(cmd, "stop") == 0) {
    motor->stop();
    sendOkEmpty();
    return;
  }
  if (strcmp(cmd, "status") == 0) {
    sendOkStatus(motorId, motor);
    return;
  }

  sendError("Unknown command");
}

void handleSerial() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == '\n') {
      handleCommand(g_rxLine);
      g_rxLine = "";
    } else if (c != '\r') {
      if (g_rxLine.length() < 256) {
        g_rxLine += c;
      }
    }
  }
}

void setup() {
  // Initialize serial communication
  Serial.begin(115200);

  pinMode(kLedPin, OUTPUT);
  digitalWrite(kLedPin, LOW);
}

void loop() {
  handleSerial();

  if (g_ledBlinkEnabled) {
    uint32_t now = millis();
    if (g_ledAutoOffAtMs != 0 && (int32_t)(now - g_ledAutoOffAtMs) >= 0) {
      g_ledBlinkEnabled = false;
      g_ledState = false;
      g_ledAutoOffAtMs = 0;
    } else if (now - g_lastLedToggleMs >= g_ledBlinkIntervalMs) {
      g_ledState = !g_ledState;
      g_lastLedToggleMs = now;
    }
  }

  digitalWrite(kLedPin, g_ledState ? HIGH : LOW);
}
