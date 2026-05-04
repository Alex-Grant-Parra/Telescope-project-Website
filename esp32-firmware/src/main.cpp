#include <Arduino.h>
#include <ArduinoJson.h>
 
// Stepper motor specifications
#define STEPS_PER_REVOLUTION 1600  // 200 * 8 microsteps
#define PULSE_WIDTH_US 10          // Minimum for TMC2209
 
class Motor {
private:
  bool enabled;
  volatile bool stopRequested;
  volatile int32_t position;  // Position tracker in steps (signed for direction)
 
public:
  int stepPin;
  int dirPin;
  int enPin;
  bool moving;
  uint32_t stepsPerRevolution;
  uint32_t stepDelayUs;
  TaskHandle_t stepTaskHandle;
 
  Motor(int step, int dir, int en, uint32_t stepsPerRev = STEPS_PER_REVOLUTION)
    : stepPin(step), dirPin(dir), enPin(en), enabled(false), moving(false),
      stopRequested(false), position(0), stepsPerRevolution(stepsPerRev), stepDelayUs(1250),
      stepTaskHandle(nullptr) {
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
    // Stop the motor task if running
    if (stepTaskHandle != nullptr) {
      stopRequested = true;
      vTaskDelete(stepTaskHandle);
      stepTaskHandle = nullptr;
    }
    // Set pins to safe states before deletion
    digitalWrite(enPin, HIGH);  // Disable driver
    digitalWrite(stepPin, LOW);
    digitalWrite(dirPin, LOW);
    moving = false;
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
 
  int32_t getPosition() const {
    return position;
  }
 
  void resetPosition() {
    position = 0;
  }
 
  void stop() {
    if (!moving) {
      return;
    }
 
    stopRequested = true;
  }
 
  void turnDegrees(float degrees, bool forward = true) {
    if (!enabled) {
      return;
    }
    if (moving) {
      return;  // Already moving, ignore
    }
 
    stopRequested = false;
    moving = true;
 
    uint32_t stepsNeeded = (uint32_t)((degrees / 360.0) * stepsPerRevolution);
    digitalWrite(dirPin, forward ? HIGH : LOW);
 
    // Run stepping in FreeRTOS task so serial can still be processed
    struct StepParams {
      Motor* motor;
      uint32_t stepsNeeded;
      bool forward;
    };
    
    StepParams* params = new StepParams{this, stepsNeeded, forward};
    
    xTaskCreatePinnedToCore(
      stepTask,           // Task function
      "MotorStep",        // Name
      2048,               // Stack size
      params,             // Parameters
      1,                  // Priority (0=lowest)
      &stepTaskHandle,    // Handle
      1                   // Core 1 (leave core 0 for serial)
    );
  }
 
  void startContinuous(bool forward = true) {
    if (!enabled) {
      return;
    }
    if (moving) {
      return;  // Already moving, ignore
    }
 
    stopRequested = false;
    moving = true;
 
    digitalWrite(dirPin, forward ? HIGH : LOW);
 
    // Run stepping in FreeRTOS task with continuous motion
    struct StepParams {
      Motor* motor;
      bool forward;
    };
    
    StepParams* params = new StepParams{this, forward};
    
    xTaskCreatePinnedToCore(
      continuousStepTask, // Task function
      "MotorContinuous",  // Name
      2048,               // Stack size
      params,             // Parameters
      1,                  // Priority (0=lowest)
      &stepTaskHandle,    // Handle
      1                   // Core 1 (leave core 0 for serial)
    );
  }
 
  static void stepTask(void* pvParameters) {
    struct StepParams {
      Motor* motor;
      uint32_t stepsNeeded;
      bool forward;
    };
    
    StepParams* params = (StepParams*)pvParameters;
    Motor* motor = params->motor;
    uint32_t stepsNeeded = params->stepsNeeded;
    bool forward = params->forward;
    delete params;
 
    // Determine position increment based on direction
    int32_t positionDelta = forward ? 1 : -1;
 
    for (uint32_t i = 0; i < stepsNeeded; i++) {
      if (motor->stopRequested) {
        break;
      }
 
      digitalWrite(motor->stepPin, HIGH);
      delayMicroseconds(PULSE_WIDTH_US);
      digitalWrite(motor->stepPin, LOW);
      delayMicroseconds(motor->stepDelayUs - PULSE_WIDTH_US);
      
      // Update position counter
      motor->position += positionDelta;
    }
 
    motor->moving = false;
    vTaskDelete(nullptr);
  }
 
  static void continuousStepTask(void* pvParameters) {
    struct StepParams {
      Motor* motor;
      bool forward;
    };
    
    StepParams* params = (StepParams*)pvParameters;
    Motor* motor = params->motor;
    delete params;
 
    // Determine position increment based on direction
    int32_t positionDelta = motor->position >= 0 ? 1 : -1;
 
    // Run continuously until stopRequested is set
    while (!motor->stopRequested) {
      digitalWrite(motor->stepPin, HIGH);
      delayMicroseconds(PULSE_WIDTH_US);
      digitalWrite(motor->stepPin, LOW);
      delayMicroseconds(motor->stepDelayUs - PULSE_WIDTH_US);
      
      // Update position counter
      motor->position += positionDelta;
    }
 
    motor->moving = false;
    vTaskDelete(nullptr);
  }
};
 
struct LedChannel {
  const char* name;
  int pin;
  bool state;
  bool blinkEnabled;
  uint32_t blinkIntervalMs;
  uint32_t lastToggleMs;
  uint32_t autoOffAtMs;
};

constexpr uint32_t kDefaultLedBlinkMs = 500;
constexpr size_t kLedCount = 6;
LedChannel g_leds[kLedCount] = {
  {"board", 2, false, false, kDefaultLedBlinkMs, 0, 0},
  {"yellow", 18, false, false, kDefaultLedBlinkMs, 0, 0},
  {"blue", 5, false, false, kDefaultLedBlinkMs, 0, 0},
  {"white", 17, false, false, kDefaultLedBlinkMs, 0, 0},
  {"green", 16, false, false, kDefaultLedBlinkMs, 0, 0},
  {"red", 4, false, false, kDefaultLedBlinkMs, 0, 0},
};
 
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

LedChannel* findLed(const String& id) {
  for (size_t i = 0; i < kLedCount; i++) {
    if (g_leds[i].name != nullptr && id == g_leds[i].name) {
      return &g_leds[i];
    }
  }
  return nullptr;
}

void applyLedState(LedChannel* led, bool on) {
  if (led == nullptr) {
    return;
  }
  led->blinkEnabled = false;
  led->state = on;
  led->autoOffAtMs = 0;
}

void startLedBlink(LedChannel* led, uint32_t intervalMs, uint32_t autoOffMs) {
  if (led == nullptr) {
    return;
  }
  led->blinkEnabled = true;
  led->blinkIntervalMs = intervalMs == 0 ? kDefaultLedBlinkMs : intervalMs;
  led->lastToggleMs = millis();
  led->autoOffAtMs = autoOffMs > 0 ? (led->lastToggleMs + autoOffMs) : 0;
}
 
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
  JsonDocument resp;
  resp["status"] = "error";
  resp["message"] = message;
  serializeJson(resp, Serial);
  Serial.println();
}
 
void sendOkEmpty() {
  JsonDocument resp;
  resp["status"] = "ok";
  serializeJson(resp, Serial);
  Serial.println();
}

void sendOkLedStatus(const LedChannel& led) {
  JsonDocument resp;
  resp["status"] = "ok";
  JsonObject data = resp["data"].to<JsonObject>();
  data["led"] = led.name;
  data["pin"] = led.pin;
  data["state"] = led.state;
  data["blink_enabled"] = led.blinkEnabled;
  data["blink_interval_ms"] = led.blinkIntervalMs;
  serializeJson(resp, Serial);
  Serial.println();
}
 
void sendOkStatus(const String& motorId, Motor* motor) {
  JsonDocument resp;
  resp["status"] = "ok";
  JsonObject data = resp["data"].to<JsonObject>();
  data["motor"] = motorId;
  data["enabled"] = motor->isEnabled();
  data["moving"] = motor->isMoving();
  data["step_delay_us"] = motor->getStepDelayUs();
  data["steps_per_rev"] = motor->getStepsPerRevolution();
  data["position"] = motor->getPosition();
  serializeJson(resp, Serial);
  Serial.println();
}
 
void sendOkMotorList() {
  JsonDocument resp;
  resp["status"] = "ok";
  JsonObject data = resp["data"].to<JsonObject>();
  JsonArray motors = data["motors"].to<JsonArray>();
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
 
  JsonDocument req;
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
    const char* ledName = req["led"] | "board";
    LedChannel* led = findLed(String(ledName));
    if (led == nullptr) {
      sendError("Unknown LED");
      return;
    }

    if (!req["mode"].isNull()) {
      const char* mode = req["mode"] | "";
      if (strcmp(mode, "on") == 0) {
        applyLedState(led, true);
      } else if (strcmp(mode, "off") == 0) {
        applyLedState(led, false);
      } else if (strcmp(mode, "blink") == 0) {
        uint32_t intervalMs = req["interval_ms"] | kDefaultLedBlinkMs;
        uint32_t autoOffMs = req["auto_off_ms"] | 0;
        startLedBlink(led, intervalMs, autoOffMs);
      } else if (strcmp(mode, "toggle") == 0) {
        applyLedState(led, !led->state);
      } else {
        sendError("Invalid LED mode");
        return;
      }
      sendOkLedStatus(*led);
      return;
    }
 
    if (!req["on"].isNull()) {
      bool on = req["on"] | false;
      applyLedState(led, on);
      sendOkLedStatus(*led);
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
    if (req["step"].isNull() || req["dir"].isNull() || req["en"].isNull()) {
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
    if (!req["speed_us"].isNull()) {
      speedUs = req["speed_us"].as<uint32_t>();
    } else if (!req["sps"].isNull()) {
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
    if (req["degrees"].isNull()) {
      sendError("Missing degrees");
      return;
    }
    float degrees = req["degrees"].as<float>();
    bool forward = req["forward"] | true;
    motor->turnDegrees(degrees, forward);
    sendOkEmpty();
    return;
  }
  if (strcmp(cmd, "start_continuous") == 0) {
    bool forward = req["forward"] | true;
    motor->startContinuous(forward);
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
  if (strcmp(cmd, "get_position") == 0) {
    JsonDocument resp;
    resp["status"] = "ok";
    JsonObject data = resp["data"].to<JsonObject>();
    data["motor"] = motorId;
    data["position"] = motor->getPosition();
    serializeJson(resp, Serial);
    Serial.println();
    return;
  }
  if (strcmp(cmd, "reset_position") == 0) {
    motor->resetPosition();
    sendOkEmpty();
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
 
  for (size_t i = 0; i < kLedCount; i++) {
    pinMode(g_leds[i].pin, OUTPUT);
    digitalWrite(g_leds[i].pin, LOW);
  }
}
 
void loop() {
  handleSerial();
 
  uint32_t now = millis();
  for (size_t i = 0; i < kLedCount; i++) {
    LedChannel& led = g_leds[i];
    if (led.blinkEnabled) {
      if (led.autoOffAtMs != 0 && (int32_t)(now - led.autoOffAtMs) >= 0) {
        led.blinkEnabled = false;
        led.state = false;
        led.autoOffAtMs = 0;
      } else if (now - led.lastToggleMs >= led.blinkIntervalMs) {
        led.state = !led.state;
        led.lastToggleMs = now;
      }
    }

    digitalWrite(led.pin, led.state ? HIGH : LOW);
  }
}
