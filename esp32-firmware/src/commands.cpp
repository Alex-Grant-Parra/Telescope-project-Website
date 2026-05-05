#include "commands.h"
#include "motor.h"
#include "led.h"
#include <ArduinoJson.h>

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

static void handleLedCommand(const JsonDocument& req) {
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
}

static void handleMotorCreateCommand(const JsonDocument& req) {
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
}

static void handleMotorDeleteCommand(const JsonDocument& req) {
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
}

static void handleMotorMotionCommand(const String& cmd, const JsonDocument& req, Motor* motor) {
  if (cmd == "engage") {
    motor->engage();
    sendOkEmpty();
  } else if (cmd == "disengage") {
    motor->disengage();
    sendOkEmpty();
  } else if (cmd == "enable") {
    bool on = req["value"] | false;
    if (on) {
      motor->engage();
    } else {
      motor->disengage();
    }
    sendOkEmpty();
  } else if (cmd == "set_speed") {
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
  } else if (cmd == "turn_degrees") {
    if (req["degrees"].isNull()) {
      sendError("Missing degrees");
      return;
    }
    float degrees = req["degrees"].as<float>();
    bool forward = req["forward"] | true;
    motor->turnDegrees(degrees, forward);
    sendOkEmpty();
  } else if (cmd == "start_continuous") {
    bool forward = req["forward"] | true;
    motor->startContinuous(forward);
    sendOkEmpty();
  } else if (cmd == "stop") {
    motor->stop();
    sendOkEmpty();
  } else if (cmd == "status") {
    String motorId = req["motor"] | "";
    sendOkStatus(motorId, motor);
  } else if (cmd == "get_position") {
    JsonDocument resp;
    resp["status"] = "ok";
    JsonObject data = resp["data"].to<JsonObject>();
    data["motor"] = req["motor"];
    data["position"] = motor->getPosition();
    serializeJson(resp, Serial);
    Serial.println();
  } else if (cmd == "reset_position") {
    motor->resetPosition();
    sendOkEmpty();
  } else {
    sendError("Unknown motor command");
  }
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

  // LED commands
  if (strcmp(cmd, "led") == 0) {
    handleLedCommand(req);
    return;
  }

  // Motor creation/deletion commands
  if (strcmp(cmd, "create_motor") == 0) {
    handleMotorCreateCommand(req);
    return;
  }

  if (strcmp(cmd, "list_motors") == 0) {
    sendOkMotorList();
    return;
  }

  if (strcmp(cmd, "delete_motor") == 0) {
    handleMotorDeleteCommand(req);
    return;
  }

  // Motor operation commands (require valid motor_id)
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

  handleMotorMotionCommand(cmd, req, motor);
}
