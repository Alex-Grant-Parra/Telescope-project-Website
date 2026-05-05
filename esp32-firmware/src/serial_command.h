#ifndef SERIAL_COMMAND_H
#define SERIAL_COMMAND_H

#include <Arduino.h>

void handleCommand(const String& line);
void handleSerial();

#endif // SERIAL_COMMAND_H
