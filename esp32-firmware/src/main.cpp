#include <Arduino.h>

#include "led.h"
#include "display.h"
#include "serial_handler.h"

void setup() {
  initializeSerial();
  initializeLeds();
  initializeDisplay();
}

void loop() {
  handleSerial();
  updateLedStates();
}
