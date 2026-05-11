#include "serial_handler.h"
#include "commands.h"
#include "display.h"

String g_rxLine;

static bool g_displayBlitActive = false;
static uint32_t g_displayBlitRemaining = 0;
static uint8_t g_displayBlitBuffer[256];

bool beginDisplayBlit(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint32_t byteCount) {
  if (g_displayBlitActive || byteCount == 0) {
    return false;
  }

  displayBeginBlit(x, y, w, h);
  g_displayBlitActive = true;
  g_displayBlitRemaining = byteCount;
  return true;
}

void initializeSerial() {
  Serial.begin(2000000);
}

void handleSerial() {
  while (Serial.available() > 0) {
    if (g_displayBlitActive) {
      size_t toRead = Serial.available();
      if (toRead > sizeof(g_displayBlitBuffer)) {
        toRead = sizeof(g_displayBlitBuffer);
      }
      if (toRead > g_displayBlitRemaining) {
        toRead = g_displayBlitRemaining;
      }

      size_t readCount = Serial.readBytes(reinterpret_cast<char*>(g_displayBlitBuffer), toRead);
      if (readCount == 0) {
        return;
      }

      displayWriteBlitData(g_displayBlitBuffer, readCount);
      g_displayBlitRemaining -= static_cast<uint32_t>(readCount);

      if (g_displayBlitRemaining == 0) {
        g_displayBlitActive = false;
        displayEndBlit();
        sendOkEmpty();
      }
      continue;
    }

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
