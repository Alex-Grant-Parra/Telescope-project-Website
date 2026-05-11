#ifndef SERIAL_HANDLER_H
#define SERIAL_HANDLER_H

#include <Arduino.h>

// Serial communication management
extern String g_rxLine;

void handleSerial();
void initializeSerial();
bool beginDisplayBlit(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint32_t byteCount);

#endif // SERIAL_HANDLER_H
