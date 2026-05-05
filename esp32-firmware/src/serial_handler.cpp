#include "serial_handler.h"
#include "commands.h"

String g_rxLine;

void initializeSerial() {
  Serial.begin(115200);
}

void handleSerial() {
  while (Serial.available() > 0) {
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
