#include <Arduino.h>

// Pin definitions
const int ledPins[] = {
  18, // Yellow
  5, // Blue
  17, // White
  16,  // Green
  4  // Red
};

const int numLeds = sizeof(ledPins) / sizeof(ledPins[0]);

void flashLed(int pin) {
  // First flash (0.25s)
  digitalWrite(pin, HIGH);
  delay(250);

  digitalWrite(pin, LOW);
  delay(125);

  // Second flash (0.25s)
  digitalWrite(pin, HIGH);
  delay(250);

  digitalWrite(pin, LOW);

  // Wait before next LED
  delay(1000);
}

void setup() {
  // Set all pins as outputs
  for (int i = 0; i < numLeds; i++) {
    pinMode(ledPins[i], OUTPUT);
    digitalWrite(ledPins[i], LOW);
  }
}

void loop() {
  for (int i = 0; i < numLeds; i++) {
    flashLed(ledPins[i]);
  }
}