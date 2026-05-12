#include "commands.h"
#include "motor.h"
#include "led.h"
#include "display.h"
#include "serial_handler.h"
#include <ArduinoJson.h>
#include <LittleFS.h>

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

void sendOkDisplayStatus() {
  JsonDocument resp;
  resp["status"] = "ok";
  JsonObject data = resp["data"].to<JsonObject>();
  data["initialized"] = g_display_state.initialized;
  data["powered"] = g_display_state.powered;
  data["brightness"] = g_display_state.brightness;
  data["width"] = DISPLAY_WIDTH;
  data["height"] = DISPLAY_HEIGHT;
  data["cursor_x"] = g_display_state.cursor_x;
  data["cursor_y"] = g_display_state.cursor_y;
  data["text_color"] = colorToHex(g_display_state.text_color);
  data["background_color"] = colorToHex(g_display_state.background_color);
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

static void handleDisplayCommand(const JsonDocument& req) {
  const char* action = req["action"] | "";
  if (strlen(action) == 0) {
    sendError("Missing display action");
    return;
  }

  if (strcmp(action, "init") == 0) {
    initializeDisplay();
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "power") == 0) {
    bool on = req["on"] | true;
    displayPower(on);
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "backlight") == 0) {
    uint8_t brightness = req["brightness"] | 255;
    displayBacklight(brightness);
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "clear") == 0) {
    uint16_t color = 0x0000;  // Black
    if (!req["color"].isNull()) {
      const char* colorHex = req["color"] | "000000";
      color = hexToColor(String(colorHex));
    }
    displayFillScreen(color);
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "fill_rect") == 0) {
    uint16_t x = req["x"] | 0;
    uint16_t y = req["y"] | 0;
    uint16_t w = req["w"] | 10;
    uint16_t h = req["h"] | 10;
    const char* colorHex = req["color"] | "FFFFFF";
    uint16_t color = hexToColor(String(colorHex));
    displayFillRectangle(x, y, w, h, color);
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "draw_rect") == 0) {
    uint16_t x = req["x"] | 0;
    uint16_t y = req["y"] | 0;
    uint16_t w = req["w"] | 10;
    uint16_t h = req["h"] | 10;
    const char* colorHex = req["color"] | "FFFFFF";
    uint16_t color = hexToColor(String(colorHex));
    displayDrawRectangle(x, y, w, h, color);
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "draw_line") == 0) {
    uint16_t x0 = req["x0"] | 0;
    uint16_t y0 = req["y0"] | 0;
    uint16_t x1 = req["x1"] | 127;
    uint16_t y1 = req["y1"] | 159;
    const char* colorHex = req["color"] | "FFFFFF";
    uint16_t color = hexToColor(String(colorHex));
    displayDrawLine(x0, y0, x1, y1, color);
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "draw_circle") == 0) {
    uint16_t x = req["x"] | 64;
    uint16_t y = req["y"] | 80;
    uint16_t r = req["r"] | 10;
    const char* colorHex = req["color"] | "FFFFFF";
    uint16_t color = hexToColor(String(colorHex));
    displayDrawCircle(x, y, r, color);
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "fill_circle") == 0) {
    uint16_t x = req["x"] | 64;
    uint16_t y = req["y"] | 80;
    uint16_t r = req["r"] | 10;
    const char* colorHex = req["color"] | "FFFFFF";
    uint16_t color = hexToColor(String(colorHex));
    displayFillCircle(x, y, r, color);
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "set_cursor") == 0) {
    uint16_t x = req["x"] | 0;
    uint16_t y = req["y"] | 0;
    displaySetCursor(x, y);
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "set_text_color") == 0) {
    const char* colorHex = req["color"] | "FFFFFF";
    uint16_t color = hexToColor(String(colorHex));
    displaySetTextColor(color);
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "set_bg_color") == 0) {
    const char* colorHex = req["color"] | "000000";
    uint16_t color = hexToColor(String(colorHex));
    displaySetBackgroundColor(color);
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "status") == 0) {
    sendOkDisplayStatus();
    return;
  }

  if (strcmp(action, "format_storage") == 0) {
    if (!LittleFS.begin(true)) {
      sendError("Storage mount failed");
      return;
    }
    if (!LittleFS.format()) {
      sendError("Storage format failed");
      return;
    }
    sendOkEmpty();
    return;
  }

  if (strcmp(action, "blit") == 0) {
    uint16_t x = req["x"] | 0;
    uint16_t y = req["y"] | 0;
    uint16_t w = req["w"] | 0;
    uint16_t h = req["h"] | 0;
    const char* format = req["format"] | "RGB565";
    uint32_t length = req["length"] | 0;

    if (w == 0 || h == 0) {
      sendError("Invalid blit size");
      return;
    }

    if (strcmp(format, "RGB565") != 0) {
      sendError("Unsupported blit format");
      return;
    }

    if (length != static_cast<uint32_t>(w) * static_cast<uint32_t>(h) * 2U) {
      sendError("Invalid blit length");
      return;
    }

    // Try buffered blit first (preferred) and fall back to streaming blit if
    // buffering isn't available or allocation fails.
    if (!beginDisplayBlitBuffered(x, y, w, h, length)) {
      if (!beginDisplayBlit(x, y, w, h, length)) {
        sendError("Unable to start display blit");
        return;
      }
    }

    // Response is sent after the binary payload is fully received.
    return;
  }

  if (strcmp(action, "store_begin") == 0) {
    const char* name = req["name"] | "";
    uint32_t length = req["length"] | 0;
    if (strlen(name) == 0 || length == 0) {
      sendError("Missing name or length");
      return;
    }

    if (!beginFileUpload(name, length)) {
      sendError("Unable to start file upload");
      return;
    }

    sendOkEmpty();
    return;
  }

  if (strcmp(action, "store") == 0) {
    const char* name = req["name"] | "";
    uint32_t length = req["length"] | 0;
    if (strlen(name) == 0 || length == 0) {
      sendError("Missing name or length");
      return;
    }

    if (!beginFileUpload(name, length)) {
      sendError("Unable to start file upload");
      return;
    }

    // Response will be sent after upload completes
    return;
  }

  if (strcmp(action, "play") == 0) {
    const char* name = req["name"] | "";
    if (strlen(name) == 0) {
      sendError("Missing name");
      return;
    }

    uint16_t x = req["x"] | 0;
    uint16_t y = req["y"] | 0;
    uint16_t w = req["w"] | DISPLAY_WIDTH;
    uint16_t h = req["h"] | DISPLAY_HEIGHT;

    displayPlayFile(name, x, y, w, h);
    sendOkEmpty();
    return;
  }

  sendError("Unknown display action");
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

  // Display commands
  if (strcmp(cmd, "display") == 0) {
    handleDisplayCommand(req);
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
