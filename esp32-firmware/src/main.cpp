#include <Arduino.h>
#include <TMCStepper.h>

// Pin definitions
const int stepPin = 18;
const int dirPin  = 19;
const int ledPin  = 2;
const int uartPin = 17; // TX only

const float R_SENSE = 0.11f; // Sense resistor value

TMC2209Stepper driver(&Serial2, R_SENSE, 0x00);

const int stepsPerRev = 200; // NEMA 17 full steps
int microsteps = 16;         // Microstepping value

void setup() {
  Serial.begin(115200); // ✅ Start USB serial once

  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);
  pinMode(ledPin, OUTPUT);

  digitalWrite(dirPin, HIGH); // Set direction

  Serial2.begin(115200, SERIAL_8N1, -1, uartPin); // TX only, RX disabled
  driver.begin();               // Initialize driver
  driver.microsteps(microsteps); // Set microstepping
  driver.rms_current(600);       // Set motor current
  driver.toff(5);                // Enable driver

  digitalWrite(ledPin, HIGH);    // LED on to show setup complete
  delay(500);
  digitalWrite(ledPin, LOW);

  // ✅ Print microsteps once after setup
  Serial.print("Microsteps set: ");
  Serial.println(driver.microsteps());
}

void loop() {
  float degrees = 90.0; // Desired rotation
  int totalSteps = (degrees / 360.0) * stepsPerRev * microsteps;

  for (int i = 0; i < totalSteps; i++) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(500);
    digitalWrite(stepPin, LOW);
    delayMicroseconds(500);
  }

  delay(5000); // Wait before next move
}
