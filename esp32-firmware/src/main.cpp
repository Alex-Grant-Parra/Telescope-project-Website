#include <Arduino.h>

#include "led.h"
#include "display.h"
#include "serial_handler.h"

void setup() {
  initializeSerial();
  initializeLeds();
  // Display initialization is deferred - called via serial command
  // This prevents boot issues if display hardware has problems
}

void loop() {
  handleSerial();
  updateLedStates();
}
