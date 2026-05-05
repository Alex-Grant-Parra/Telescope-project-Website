#ifndef SERIAL_HANDLER_H
#define SERIAL_HANDLER_H

#include <Arduino.h>

// Serial communication management
extern String g_rxLine;

void handleSerial();
void initializeSerial();

#endif // SERIAL_HANDLER_H
