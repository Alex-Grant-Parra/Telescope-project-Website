#include <Arduino.h>

#include "led.h"
#include "serial_handler.h"

void setup() {
  initializeSerial();
  initializeLeds();
}

void loop() {
  handleSerial();
  updateLedStates();
}
