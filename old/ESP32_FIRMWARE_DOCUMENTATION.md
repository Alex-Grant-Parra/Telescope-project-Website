# ESP32 TMC2209 Stepper Motor Firmware Documentation

## Overview
This documentation covers the ESP32 firmware that controls stepper motors via TMC2209 driver with UART communication. The firmware provides a serial command interface for motor control, configuration, and status monitoring.

## Table of Contents
1. [Hardware Configuration](#hardware-configuration)
2. [Pin Definitions](#pin-definitions)
3. [Global Variables](#global-variables)
4. [Setup & Initialization](#setup--initialization)
5. [Serial Command Interface](#serial-command-interface)
6. [Motor Control Functions](#motor-control-functions)
7. [TMC2209 UART Functions](#tmc2209-uart-functions)
8. [Command Reference](#command-reference)
9. [Status Reporting](#status-reporting)
10. [Error Handling](#error-handling)
11. [Hardware Wiring](#hardware-wiring)
12. [Troubleshooting](#troubleshooting)

---

## Hardware Configuration

### Microcontroller
- **ESP32** development board
- **115200 baud** serial communication
- **Arduino framework** with PlatformIO

### Stepper Driver
- **TMC2209** stepper motor driver
- **UART communication** on pin 17
- **Microstep resolution**: 1-256 steps
- **Silent operation** modes available

### Stepper Motor
- **NEMA17** recommended (200 steps/revolution)
- **Bipolar stepper motor** configuration
- **12-24V power supply** for TMC2209

---

## Pin Definitions

```cpp
const int stepPin = 18;    // Step pulse output to TMC2209
const int dirPin  = 19;    // Direction output to TMC2209  
const int ledPin  = 2;     // Status LED (motor enabled indicator)
const int uartPin = 17;    // UART TX for TMC2209 communication
```

### Pin Functions
- **Pin 18 (STEP)**: Generates step pulses to move motor
- **Pin 19 (DIR)**: Controls rotation direction (HIGH=clockwise, LOW=counterclockwise)
- **Pin 2 (LED)**: Visual indicator of motor enable status
- **Pin 17 (UART TX)**: One-way communication to TMC2209 for configuration

---

## Global Variables

### Motor Control Variables
```cpp
bool motorEnabled = false;          // Motor enable state
int stepsPerRevolution = 200;       // NEMA17 standard
int currentSpeed = 1000;            // Microseconds between steps
long currentPosition = 0;           // Current position in steps
bool isMoving = false;              // Movement state flag
long targetPosition = 0;            // Target position for movement
```

### TMC2209 Configuration Variables
```cpp
int microstepSetting = 16;          // Current microstep resolution
String movementType = "STEALTH";    // Movement mode
HardwareSerial TMCSerial(2);        // UART2 instance for TMC2209
```

### Communication Variables
```cpp
String inputString = "";            // Serial input buffer
bool stringComplete = false;        // Command ready flag
```

---

## Setup & Initialization

### `setup()` Function
Initializes all hardware and communication interfaces.

**Initialization Sequence:**
1. **Serial Communication**: 115200 baud for PC interface
2. **TMC2209 UART**: 115200 baud on pin 17 (TX only)
3. **Pin Configuration**: Set pin modes for step/dir/LED
4. **Initial States**: All outputs LOW, motor disabled
5. **TMC2209 Configuration**: Apply default settings via UART
6. **Command Help**: Display available commands

**Code Structure:**
```cpp
void setup() {
  Serial.begin(115200);
  TMCSerial.begin(115200, SERIAL_8N1, -1, uartPin);
  
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);
  pinMode(ledPin, OUTPUT);
  
  digitalWrite(stepPin, LOW);
  digitalWrite(dirPin, LOW);
  digitalWrite(ledPin, LOW);
  
  configureTMC2209();  // Initialize driver
}
```

---

## Serial Command Interface

### Main Loop (`loop()`)
Handles continuous operation with three main tasks:

1. **Serial Input Processing**: Read and buffer incoming commands
2. **Command Execution**: Process complete commands
3. **Motor Movement**: Execute step-by-step movement
4. **Status Updates**: Update LED and system state

**Loop Structure:**
```cpp
void loop() {
  // Handle serial input character by character
  if (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') {
      stringComplete = true;  // Command ready
    } else {
      inputString += inChar;  // Buffer characters
    }
  }
  
  // Process complete commands
  if (stringComplete) {
    processCommand(inputString);
    inputString = "";
    stringComplete = false;
  }
  
  // Execute motor movement
  if (isMoving && motorEnabled) {
    moveToTarget();
  }
  
  // Update status LED
  digitalWrite(ledPin, motorEnabled ? HIGH : LOW);
}
```

---

## Motor Control Functions

### `processCommand(String command)`
Main command parser and dispatcher.

**Parameters:**
- `command` (String): Input command string

**Command Processing Steps:**
1. **Trim and Uppercase**: Clean input string
2. **Parse Command Type**: Identify command category
3. **Validate Parameters**: Check parameter ranges
4. **Execute Command**: Call appropriate function
5. **Send Response**: Confirm success or report error

**Supported Command Categories:**
- Motor enable/disable commands
- Movement commands (relative/absolute)
- Configuration commands (speed, microsteps, movement type)
- Status and utility commands

### `moveToTarget()`
Executes single step toward target position.

**Algorithm:**
1. **Check Completion**: If at target, stop movement
2. **Direction Control**: Set DIR pin based on target vs current
3. **Generate Step Pulse**: 10μs HIGH pulse on STEP pin
4. **Update Position**: Increment/decrement position counter
5. **Step Delay**: Wait specified microseconds before next step

**Code Implementation:**
```cpp
void moveToTarget() {
  if (currentPosition == targetPosition) {
    isMoving = false;
    Serial.println("OK:Movement complete at position " + String(currentPosition));
    return;
  }
  
  bool clockwise = (targetPosition > currentPosition);
  digitalWrite(dirPin, clockwise ? HIGH : LOW);
  
  // Generate step pulse (minimum 10μs width)
  digitalWrite(stepPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(stepPin, LOW);
  
  currentPosition += clockwise ? 1 : -1;
  delayMicroseconds(currentSpeed);
}
```

### `emergencyStop()`
Immediate motor stop and disable.

**Actions:**
1. Set `isMoving = false`
2. Set `motorEnabled = false`  
3. Turn off status LED
4. Send emergency notification

---

## TMC2209 UART Functions

### `configureTMC2209()`
Initializes TMC2209 driver with default settings.

**Configuration Sequence:**
1. **Initialization Delay**: Wait for TMC2209 startup
2. **GCONF Register**: Enable UART and internal sense resistors
3. **Microstep Configuration**: Apply default microstep setting
4. **Movement Type**: Apply default movement mode
5. **Communication Verification**: Test UART communication

**GCONF Register Setup:**
```cpp
sendTMCCommand(0x00, 0x00000001); // Enable UART, internal sense resistors
```

### `setMicrosteps(int microsteps)`
Configure microstep resolution via CHOPCONF register.

**Parameters:**
- `microsteps` (int): Microstep value (1,2,4,8,16,32,64,256)

**CHOPCONF Register Configuration:**
```cpp
uint32_t chopconf_value = 0x10000053; // Base configuration

// MRES field mapping (bits 24-27)
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

sendTMCCommand(0x6C, chopconf_value); // Write to CHOPCONF
```

### `setMovementType(String type)`
Configure driver operation mode.

**Parameters:**
- `type` (String): Movement type ("STEALTH", "INTERPOLATED", "CONTINUOUS")

**Movement Type Configurations:**

1. **STEALTH Mode**:
   ```cpp
   gconf_value |= 0x00000004; // Enable stealthChop
   sendTMCCommand(0x00, gconf_value);
   sendTMCCommand(0x10, 0x00001F0A); // TPWMTHRS threshold
   ```

2. **INTERPOLATED Mode**:
   ```cpp
   gconf_value |= 0x00000200; // Enable interpolation to 256
   sendTMCCommand(0x00, gconf_value);
   ```

3. **CONTINUOUS Mode**:
   ```cpp
   // Standard operation - no special flags
   sendTMCCommand(0x00, gconf_value);
   ```

### `sendTMCCommand(uint8_t reg, uint32_t value)`
Send UART command to TMC2209 register.

**Parameters:**
- `reg` (uint8_t): TMC2209 register address
- `value` (uint32_t): 32-bit register value

**UART Protocol Frame:**
```cpp
uint8_t cmd[8];
cmd[0] = 0x05;           // Sync byte
cmd[1] = 0x00;           // Slave address
cmd[2] = reg | 0x80;     // Register + write flag
cmd[3] = (value >> 24) & 0xFF; // Data byte 3 (MSB)
cmd[4] = (value >> 16) & 0xFF; // Data byte 2
cmd[5] = (value >> 8) & 0xFF;  // Data byte 1  
cmd[6] = value & 0xFF;         // Data byte 0 (LSB)
cmd[7] = 0x00;          // CRC (placeholder)
```

---

## Command Reference

### Motor Control Commands

#### `ENABLE`
**Function**: Enable stepper motor for movement
**Parameters**: None
**Response**: `OK:Motor enabled`
**Example**: `ENABLE`

#### `DISABLE`  
**Function**: Disable stepper motor (stops all movement)
**Parameters**: None
**Response**: `OK:Motor disabled`
**Example**: `DISABLE`

#### `MOVE:<steps>`
**Function**: Relative movement by specified steps
**Parameters**: 
- `steps` (int): Step count (positive=clockwise, negative=counterclockwise)
**Response**: `OK:Moving <steps> steps`
**Examples**: 
- `MOVE:200` (1 revolution clockwise)
- `MOVE:-100` (half revolution counterclockwise)

#### `GOTO:<position>`
**Function**: Absolute movement to target position
**Parameters**:
- `position` (int): Target absolute position
**Response**: `OK:Going to position <position>`
**Examples**:
- `GOTO:500` (move to position 500)
- `GOTO:0` (return to home)

#### `STOP`
**Function**: Emergency stop - halt movement immediately
**Parameters**: None
**Response**: `OK:Emergency stop`
**Example**: `STOP`

### Configuration Commands

#### `SPEED:<microseconds>`
**Function**: Set step timing (speed control)
**Parameters**:
- `microseconds` (int): Delay between steps (100-10000)
**Response**: `OK:Speed set to <value> microseconds`
**Speed Reference**:
- 100μs = Very fast
- 1000μs = Medium (default)
- 5000μs = Slow  
- 10000μs = Very slow
**Examples**:
- `SPEED:500` (fast movement)
- `SPEED:2000` (slow movement)

#### `MICROSTEP:<value>`
**Function**: Set microstep resolution
**Parameters**:
- `value` (int): Microstep setting (1,2,4,8,16,32,64,256)
**Response**: `OK:Microsteps set to <value>`
**Resolution Reference**:
- 1 = Full steps (highest torque)
- 16 = Good balance (default)
- 256 = Maximum smoothness
**Examples**:
- `MICROSTEP:16` (balanced setting)
- `MICROSTEP:256` (smoothest operation)

#### `MOVEMENT:<type>`
**Function**: Set movement/operation mode
**Parameters**:
- `type` (String): Movement type (STEALTH, INTERPOLATED, CONTINUOUS)
**Response**: `OK:Movement type set to <type>`
**Mode Reference**:
- **STEALTH**: Quiet operation via stealthChop
- **INTERPOLATED**: 256-step interpolation for smoothness
- **CONTINUOUS**: Standard operation mode
**Examples**:
- `MOVEMENT:STEALTH` (quiet operation)
- `MOVEMENT:INTERPOLATED` (smooth precision)

### Utility Commands

#### `HOME`
**Function**: Set current position as home (0)
**Parameters**: None
**Response**: `OK:Position homed to 0`
**Example**: `HOME`

#### `STATUS`
**Function**: Get comprehensive system status
**Parameters**: None
**Response**: `STATUS:Enabled=<bool>,Position=<int>,Target=<int>,Speed=<int>,Moving=<bool>,Microsteps=<int>,Movement=<string>`
**Example Response**: `STATUS:Enabled=true,Position=150,Target=200,Speed=1000,Moving=true,Microsteps=16,Movement=STEALTH`

---

## Status Reporting

### Status Fields
The STATUS command returns a comma-separated list of key-value pairs:

- **Enabled** (boolean): Motor enable state
- **Position** (integer): Current position in steps from home
- **Target** (integer): Target position for current movement
- **Speed** (integer): Current step delay in microseconds
- **Moving** (boolean): Whether motor is currently moving
- **Microsteps** (integer): Current microstep resolution
- **Movement** (string): Current movement mode

### Movement Completion Notification
When a movement finishes, the system automatically sends:
```
OK:Movement complete at position <final_position>
```

---

## Error Handling

### Error Response Format
All errors return messages in format: `ERROR:<description>`

### Common Error Conditions

#### Motor Not Enabled
**Trigger**: Movement commands when motor disabled
**Response**: `ERROR:Motor not enabled`
**Solution**: Send `ENABLE` command first

#### Invalid Speed Range
**Trigger**: Speed outside 100-10000 microsecond range
**Response**: `ERROR:Speed must be between 100-10000 microseconds`
**Solution**: Use valid speed range

#### Invalid Microstep Value
**Trigger**: Microstep not in [1,2,4,8,16,32,64,256]
**Response**: `ERROR:Microsteps must be 1,2,4,8,16,32,64,256`
**Solution**: Use valid microstep values

#### Invalid Movement Type
**Trigger**: Movement type not STEALTH/INTERPOLATED/CONTINUOUS
**Response**: `ERROR:Movement type must be STEALTH, INTERPOLATED, or CONTINUOUS`
**Solution**: Use valid movement type names

#### Unknown Command
**Trigger**: Unrecognized command string
**Response**: `ERROR:Unknown command: <command>`
**Solution**: Check command spelling and format

---

## Hardware Wiring

### ESP32 to TMC2209 Connections
```
ESP32 Pin 18  →  TMC2209 STEP
ESP32 Pin 19  →  TMC2209 DIR  
ESP32 Pin 17  →  TMC2209 PDN_UART (via 1kΩ resistor)
ESP32 GND     →  TMC2209 GND
ESP32 3.3V    →  TMC2209 VDD
```

### TMC2209 to Stepper Motor
```
TMC2209 A1    →  Motor Coil A+
TMC2209 A2    →  Motor Coil A-
TMC2209 B1    →  Motor Coil B+
TMC2209 B2    →  Motor Coil B-
```

### Power Supply
```
12-24V DC     →  TMC2209 VM
Power GND     →  TMC2209 GND
```

### Critical Wiring Notes
1. **UART Resistor**: 1kΩ resistor required between ESP32 Pin 17 and TMC2209 PDN_UART
2. **MS1/MS2 Pins**: Leave floating for UART control mode
3. **Power Supply**: Separate 12-24V supply for motor power (VM)
4. **Ground Connection**: Common ground between ESP32, TMC2209, and power supply

---

## Troubleshooting

### Motor Not Moving
**Symptoms**: Motor enabled but no movement on MOVE commands
**Possible Causes**:
- TMC2209 not receiving UART commands
- MS1/MS2 pins incorrectly wired (should be floating)
- Insufficient motor power supply
- Motor wiring incorrect

**Solutions**:
1. Verify 1kΩ resistor on UART connection
2. Check MS1/MS2 are floating (not connected)
3. Verify 12-24V power supply to VM pin
4. Test motor wiring with multimeter

### UART Communication Issues
**Symptoms**: Motor works but microstep/movement commands ignored
**Possible Causes**:
- Missing 1kΩ resistor on UART line
- Wrong TMC2209 UART address
- Electrical noise on UART line

**Solutions**:
1. Add/verify 1kΩ resistor on Pin 17
2. Check ground connections
3. Use shorter wires for UART connection
4. Add decoupling capacitors near TMC2209

### Serial Communication Problems
**Symptoms**: No response from ESP32
**Possible Causes**:
- Wrong baud rate setting
- USB cable issues
- ESP32 not properly programmed

**Solutions**:
1. Verify 115200 baud rate in serial monitor
2. Try different USB cable/port
3. Re-flash ESP32 firmware
4. Check ESP32 power LED

### Movement Too Fast/Slow
**Symptoms**: Motor moves but at wrong speed
**Solutions**:
1. Adjust SPEED command (100-10000μs range)
2. Check microstep setting (higher = slower apparent speed)
3. Verify power supply voltage (low voltage = slow movement)

### Noisy Operation
**Symptoms**: Motor makes excessive noise
**Solutions**:
1. Use STEALTH movement mode
2. Increase microstep resolution
3. Adjust current settings via TMC2209 hardware
4. Check motor mounting and coupling

---

## Development Notes

### Register Addresses (TMC2209)
- **0x00**: GCONF - General configuration
- **0x10**: TPWMTHRS - StealthChop threshold
- **0x6C**: CHOPCONF - Chopper configuration

### Future Enhancements
1. **CRC Calculation**: Implement proper CRC for UART commands
2. **Current Control**: Add UART current limiting commands  
3. **Sensorless Homing**: Implement stallGuard-based homing
4. **Multiple Motors**: Support for multiple TMC2209 drivers
5. **Acceleration**: Add ramping for smooth acceleration/deceleration

### Performance Specifications
- **Maximum Step Rate**: ~20 kHz (limited by delayMicroseconds precision)
- **Position Resolution**: 1 step minimum, up to ±2,147,483,647 steps
- **Speed Range**: 100-10000 microseconds per step
- **Microstep Range**: 1x to 256x microstepping

This firmware provides a robust foundation for stepper motor control with TMC2209 drivers, offering both basic movement capabilities and advanced driver configuration through UART communication.