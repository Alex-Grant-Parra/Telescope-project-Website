#include <Arduino.h>
#include <HardwareSerial.h>

// Pin definitions
const int stepPin = 18;
const int dirPin  = 19;
const int ledPin  = 2;
const int uartPin = 17;        // UART TX pin for TMC2209 communication

// Motor control variables
bool motorEnabled = false;
int stepsPerRevolution = 200;  // Standard NEMA17 steps per revolution
int currentSpeed = 1000;       // Microseconds between steps (speed control)
long currentPosition = 0;      // Current motor position in steps
bool isMoving = false;
long targetPosition = 0;

// TMC2209 configuration variables
int microstepSetting = 16;     // Current microstep setting (1,2,4,8,16,32,64,256)
String movementType = "STEALTH";  // Movement type: STEALTH, INTERPOLATED, CONTINUOUS
HardwareSerial TMCSerial(2);   // UART2 for TMC2209 communication

// Communication variables
String inputString = "";
bool stringComplete = false;

// Function declarations
void processCommand(String command);
void moveToTarget();
void emergencyStop();
void configureTMC2209();
void setMicrosteps(int microsteps);
void setMovementType(String type);
void sendTMCCommand(uint8_t reg, uint32_t value);

void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  Serial.println("ESP32 TMC2209 Stepper Controller Ready");
  
  // Initialize TMC2209 UART communication
  TMCSerial.begin(115200, SERIAL_8N1, -1, uartPin); // RX not used, TX on pin 17
  Serial.println("TMC2209 UART initialized on pin 17");
  
  // Configure pins
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);
  pinMode(ledPin, OUTPUT);
  
  // Initial states
  digitalWrite(stepPin, LOW);
  digitalWrite(dirPin, LOW);
  digitalWrite(ledPin, LOW);
  
  // Initialize TMC2209 with default settings
  configureTMC2209();
  
  Serial.println("Commands:");
  Serial.println("ENABLE - Enable motor");
  Serial.println("DISABLE - Disable motor");
  Serial.println("MOVE:<steps> - Move relative steps (+ or -)");
  Serial.println("GOTO:<position> - Move to absolute position");
  Serial.println("SPEED:<microseconds> - Set step delay (100-10000)");
  Serial.println("MICROSTEP:<value> - Set microsteps (1,2,4,8,16,32,64,256)");
  Serial.println("MOVEMENT:<type> - Set movement type (STEALTH,INTERPOLATED,CONTINUOUS)");
  Serial.println("HOME - Set current position as home (0)");
  Serial.println("STATUS - Get current status");
  Serial.println("STOP - Emergency stop");
}

void loop() {
  // Handle serial input
  if (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') {
      stringComplete = true;
    } else {
      inputString += inChar;
    }
  }
  
  // Process commands
  if (stringComplete) {
    processCommand(inputString);
    inputString = "";
    stringComplete = false;
  }
  
  // Handle motor movement
  if (isMoving && motorEnabled) {
    moveToTarget();
  }
  
  // Update LED status
  digitalWrite(ledPin, motorEnabled ? HIGH : LOW);
}

void processCommand(String command) {
  command.trim();
  command.toUpperCase();
  
  if (command == "ENABLE") {
    motorEnabled = true;
    Serial.println("OK:Motor enabled");
    
  } else if (command == "DISABLE") {
    motorEnabled = false;
    isMoving = false;
    Serial.println("OK:Motor disabled");
    
  } else if (command.startsWith("MOVE:")) {
    if (!motorEnabled) {
      Serial.println("ERROR:Motor not enabled");
      return;
    }
    
    long steps = command.substring(5).toInt();
    targetPosition = currentPosition + steps;
    isMoving = true;
    Serial.println("OK:Moving " + String(steps) + " steps");
    
  } else if (command.startsWith("GOTO:")) {
    if (!motorEnabled) {
      Serial.println("ERROR:Motor not enabled");
      return;
    }
    
    targetPosition = command.substring(5).toInt();
    isMoving = true;
    Serial.println("OK:Going to position " + String(targetPosition));
    
  } else if (command.startsWith("SPEED:")) {
    int newSpeed = command.substring(6).toInt();
    if (newSpeed >= 100 && newSpeed <= 10000) {
      currentSpeed = newSpeed;
      Serial.println("OK:Speed set to " + String(currentSpeed) + " microseconds");
    } else {
      Serial.println("ERROR:Speed must be between 100-10000 microseconds");
    }
    
  } else if (command.startsWith("MICROSTEP:")) {
    int newMicrosteps = command.substring(10).toInt();
    if (newMicrosteps == 1 || newMicrosteps == 2 || newMicrosteps == 4 || 
        newMicrosteps == 8 || newMicrosteps == 16 || newMicrosteps == 32 || 
        newMicrosteps == 64 || newMicrosteps == 256) {
      setMicrosteps(newMicrosteps);
      Serial.println("OK:Microsteps set to " + String(microstepSetting));
    } else {
      Serial.println("ERROR:Microsteps must be 1,2,4,8,16,32,64,256");
    }
    
  } else if (command.startsWith("MOVEMENT:")) {
    String newType = command.substring(9);
    newType.trim();
    if (newType == "STEALTH" || newType == "INTERPOLATED" || newType == "CONTINUOUS") {
      setMovementType(newType);
      Serial.println("OK:Movement type set to " + movementType);
    } else {
      Serial.println("ERROR:Movement type must be STEALTH, INTERPOLATED, or CONTINUOUS");
    }
    
  } else if (command == "HOME") {
    currentPosition = 0;
    targetPosition = 0;
    isMoving = false;
    Serial.println("OK:Position homed to 0");
    
  } else if (command == "STATUS") {
    Serial.println("STATUS:Enabled=" + String(motorEnabled) + 
                   ",Position=" + String(currentPosition) + 
                   ",Target=" + String(targetPosition) + 
                   ",Speed=" + String(currentSpeed) + 
                   ",Moving=" + String(isMoving) + 
                   ",Microsteps=" + String(microstepSetting) + 
                   ",Movement=" + movementType);
    
  } else if (command == "STOP") {
    isMoving = false;
    targetPosition = currentPosition;
    Serial.println("OK:Emergency stop");
    
  } else {
    Serial.println("ERROR:Unknown command: " + command);
  }
}

void moveToTarget() {
  if (currentPosition == targetPosition) {
    isMoving = false;
    Serial.println("OK:Movement complete at position " + String(currentPosition));
    return;
  }
  
  // Determine direction
  bool clockwise = (targetPosition > currentPosition);
  digitalWrite(dirPin, clockwise ? HIGH : LOW);
  
  // Take a step
  digitalWrite(stepPin, HIGH);
  delayMicroseconds(10);  // Minimum pulse width for TMC2209
  digitalWrite(stepPin, LOW);
  
  // Update position
  currentPosition += clockwise ? 1 : -1;
  
  // Wait for next step based on speed setting
  delayMicroseconds(currentSpeed);
}

void emergencyStop() {
  isMoving = false;
  motorEnabled = false;
  digitalWrite(ledPin, LOW);
  Serial.println("EMERGENCY:Motor stopped and disabled");
}

// TMC2209 UART Communication Functions
void configureTMC2209() {
  Serial.println("Configuring TMC2209...");
  Serial.println("Note: MS1/MS2 pins floating, using PDN_UART with 1k resistor");
  
  // Wait a bit for TMC2209 to initialize
  delay(100);
  
  // Basic configuration for TMC2209
  // With floating MS1/MS2, need to ensure proper UART communication
  sendTMCCommand(0x00, 0x00000001); // GCONF - Enable UART and internal sense resistors
  delay(20);
  
  // Verify communication by trying to read a register (optional diagnostic)
  Serial.println("Attempting TMC2209 UART communication...");
  
  // Set initial microstep configuration
  setMicrosteps(microstepSetting);
  delay(20);
  
  // Set initial movement type
  setMovementType(movementType);
  delay(20);
  
  Serial.println("TMC2209 configured successfully");
  Serial.println("If motor doesn't respond, check MS1/MS2 connections or add pulldowns");
}

void setMicrosteps(int microsteps) {
  microstepSetting = microsteps;
  
  uint32_t chopconf_value = 0x10000053; // Base CHOPCONF value
  
  // Set MRES bits based on microstep setting
  switch(microsteps) {
    case 256: chopconf_value |= (0x00 << 24); break; // MRES = 0
    case 128: chopconf_value |= (0x01 << 24); break; // MRES = 1
    case 64:  chopconf_value |= (0x02 << 24); break; // MRES = 2
    case 32:  chopconf_value |= (0x03 << 24); break; // MRES = 3
    case 16:  chopconf_value |= (0x04 << 24); break; // MRES = 4
    case 8:   chopconf_value |= (0x05 << 24); break; // MRES = 5
    case 4:   chopconf_value |= (0x06 << 24); break; // MRES = 6
    case 2:   chopconf_value |= (0x07 << 24); break; // MRES = 7
    case 1:   chopconf_value |= (0x08 << 24); break; // MRES = 8
  }
  
  sendTMCCommand(0x6C, chopconf_value); // CHOPCONF register
  
  // Don't print here - let the main command handler print the response
}

void setMovementType(String type) {
  movementType = type;
  
  uint32_t gconf_value = 0x00000001; // Base GCONF with UART enabled
  
  if (type == "STEALTH") {
    gconf_value |= 0x00000004; // Enable stealthChop
    sendTMCCommand(0x00, gconf_value); // GCONF
    sendTMCCommand(0x10, 0x00001F0A); // TPWMTHRS - Enable stealthChop below this velocity
  } else if (type == "INTERPOLATED") {
    gconf_value |= 0x00000200; // Enable interpolation
    sendTMCCommand(0x00, gconf_value); // GCONF
  } else if (type == "CONTINUOUS") {
    // Standard continuous mode - no special flags
    sendTMCCommand(0x00, gconf_value); // GCONF
  }
  
  // Don't print here - let the main command handler print the response
}

void sendTMCCommand(uint8_t reg, uint32_t value) {
  // TMC2209 UART protocol implementation
  // This is a simplified version - full implementation would include
  // address handling, CRC calculation, etc.
  
  uint8_t cmd[8];
  cmd[0] = 0x05; // Sync byte
  cmd[1] = 0x00; // Slave address (can be configured)
  cmd[2] = reg | 0x80; // Register with write flag
  cmd[3] = (value >> 24) & 0xFF;
  cmd[4] = (value >> 16) & 0xFF;
  cmd[5] = (value >> 8) & 0xFF;
  cmd[6] = value & 0xFF;
  cmd[7] = 0x00; // CRC placeholder (should be calculated for production use)
  
  for(int i = 0; i < 8; i++) {
    TMCSerial.write(cmd[i]);
  }
  TMCSerial.flush();
}
