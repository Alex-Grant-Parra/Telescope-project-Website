#include "serial_handler.h"
#include "commands.h"
#include "display.h"

String g_rxLine;
static bool g_displayBlitActive = false;
static bool g_displayBlitBuffered = false;
static uint32_t g_displayBlitRemaining = 0;
// Buffer for streaming mode (small fixed chunk)
static uint8_t g_displayStreamBuffer[256];
// Pointer-based buffer for buffered (full-frame) mode
static uint8_t* g_displayBlitBuffer = nullptr;
static uint32_t g_displayBlitIndex = 0;
static uint16_t g_displayBlitX = 0;
static uint16_t g_displayBlitY = 0;
static uint16_t g_displayBlitW = 0;
static uint16_t g_displayBlitH = 0;

bool beginDisplayBlit(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint32_t byteCount) {
  // Backwards-compatible existing behavior: start immediate streaming blit if
  // no buffered mode is used. This keeps legacy callers working.
  if (g_displayBlitActive || byteCount == 0) {
    return false;
  }

  displayBeginBlit(x, y, w, h);
  g_displayBlitActive = true;
  g_displayBlitRemaining = byteCount;
  return true;
}

bool beginDisplayBlitBuffered(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint32_t byteCount) {
  if (g_displayBlitActive || g_displayBlitBuffered || byteCount == 0) {
    return false;
  }

  // Try to allocate a buffer for the incoming frame. If allocation fails,
  // fall back to streaming mode by returning false.
  uint8_t* buf = (uint8_t*)malloc(byteCount);
  if (buf == nullptr) {
    return false;
  }

  g_displayBlitBuffer = buf;
  g_displayBlitIndex = 0;
  g_displayBlitRemaining = byteCount;
  g_displayBlitBuffered = true;
  g_displayBlitX = x;
  g_displayBlitY = y;
  g_displayBlitW = w;
  g_displayBlitH = h;
  return true;
}

void initializeSerial() {
  Serial.begin(2000000);
}

void handleSerial() {
  while (Serial.available() > 0) {
    if (g_displayBlitBuffered) {
      // Read into the allocated buffer until full, then perform a single
      // bulk SPI write to update the display atomically.
      size_t toRead = Serial.available();
      if (toRead > g_displayBlitRemaining) {
        toRead = g_displayBlitRemaining;
      }

      size_t readCount = Serial.readBytes(reinterpret_cast<char*>(g_displayBlitBuffer + g_displayBlitIndex), toRead);
      if (readCount == 0) {
        return;
      }

      g_displayBlitIndex += static_cast<uint32_t>(readCount);
      g_displayBlitRemaining -= static_cast<uint32_t>(readCount);

      if (g_displayBlitRemaining == 0) {
        // Now that we've fully received the frame, perform a single bulk
        // SPI write: set window, RAMWR, then write all bytes at once.
        displayBeginBlit(g_displayBlitX, g_displayBlitY, g_displayBlitW, g_displayBlitH);
        // Use the public API to write the received blit buffer in one go.
        displayWriteBlitData(g_displayBlitBuffer, g_displayBlitIndex);
        displayEndBlit();

        // Free buffer and clear state
        free(g_displayBlitBuffer);
        g_displayBlitBuffer = nullptr;
        g_displayBlitBuffered = false;
        g_displayBlitIndex = 0;
        g_displayBlitRemaining = 0;

        sendOkEmpty();
      }
      continue;
    }

    if (g_displayBlitActive) {
      size_t toRead = Serial.available();
      if (toRead > sizeof(g_displayStreamBuffer)) {
        toRead = sizeof(g_displayStreamBuffer);
      }
      if (toRead > g_displayBlitRemaining) {
        toRead = g_displayBlitRemaining;
      }

      size_t readCount = Serial.readBytes(reinterpret_cast<char*>(g_displayStreamBuffer), toRead);
      if (readCount == 0) {
        return;
      }

      displayWriteBlitData(g_displayStreamBuffer, readCount);
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
