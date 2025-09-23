#include <Arduino.h>

const int ledPin = 2; // GPIO pin for LED
const int dotDuration = 200; // milliseconds

String inputString = "";
bool inputReceived = false;

const String morseMap[36] = {
  ".-", "-...", "-.-.", "-..", ".", "..-.", "--.", "....", "..", ".---", // A-J
  "-.-", ".-..", "--", "-.", "---", ".--.", "--.-", ".-.", "...", "-",   // K-T
  "..-", "...-", ".--", "-..-", "-.--", "--..",                          // U-Z
  "-----", ".----", "..---", "...--", "....-", ".....", "-....", "--...", "---..", "----." // 0-9
};

void setup() {
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW);
  Serial.begin(115200);
  Serial.println("Enter a string to convert to Morse code:");
}

void loop() {
  if (Serial.available()) {
    inputString = Serial.readStringUntil('\n');
    inputString.trim();
    inputReceived = true;
  }

  if (inputReceived) {
    Serial.println("Flashing Morse code for: " + inputString);
    flashMorse(inputString);
    delay(dotDuration * 7); // Pause after flashing
    inputReceived = false; // Ready for new input
    Serial.println("Enter a string to convert to Morse code:");
  }
}

void flashMorse(String text) {
  text.toUpperCase();
  for (int i = 0; i < text.length(); i++) {
    char c = text.charAt(i);
    if (c == ' ') {
      delay(dotDuration * 7); // Word space
      continue;
    }

    String code = getMorseCode(c);
    if (code.length() == 0) {
      continue; // Skip unsupported characters
    }
    for (int j = 0; j < code.length(); j++) {
      if (code.charAt(j) == '.') {
        flashDot();
      } else if (code.charAt(j) == '-') {
        flashDash();
      }
      // Space between symbols, except after last symbol
      if (j < code.length() - 1) {
        delay(dotDuration);
      }
    }
    // Space between letters, except after last letter or if next char is space
    if (i < text.length() - 1 && text.charAt(i + 1) != ' ') {
      delay(dotDuration * 3);
    }
  }
}

String getMorseCode(char c) {
  if (c >= 'A' && c <= 'Z') {
    return morseMap[c - 'A'];
  } else if (c >= '0' && c <= '9') {
    return morseMap[26 + (c - '0')];
  } else {
    return "";
  }
}

void flashDot() {
  digitalWrite(ledPin, HIGH);
  delay(dotDuration);
  digitalWrite(ledPin, LOW);
}

void flashDash() {
  digitalWrite(ledPin, HIGH);
  delay(dotDuration * 3);
  digitalWrite(ledPin, LOW);
}
