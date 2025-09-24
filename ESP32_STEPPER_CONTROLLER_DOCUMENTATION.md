# ESP32 Stepper Controller Documentation

## Overview
The ESP32StepperController class provides a Python interface for controlling stepper motors via an ESP32 microcontroller with TMC2209 driver over UART communication. This documentation covers all available functions, their inputs, outputs, and usage examples.

## Table of Contents
1. [Installation & Setup](#installation--setup)
2. [Basic Connection](#basic-connection)
3. [Motor Control Functions](#motor-control-functions)
4. [Configuration Functions](#configuration-functions)
5. [Status & Monitoring](#status--monitoring)
6. [Advanced Movement Functions](#advanced-movement-functions)
7. [Error Handling](#error-handling)
8. [Usage Examples](#usage-examples)

---

## Installation & Setup

### Requirements
- ESP32 with uploaded firmware (TMC2209 UART on pin 17)
- USB connection to ESP32
- Python 3.6+ with `pyserial` library

### Import and Initialize
```python
from esp32link import ESP32StepperController

# Initialize controller
controller = ESP32StepperController(
    port='/dev/ttyUSB0',    # Serial port path
    baudrate=115200,        # Communication speed
    timeout=2.0             # Serial timeout in seconds
)
```

---

## Basic Connection

### `connect() -> bool`
Establishes serial connection to ESP32.

**Parameters:** None

**Returns:** 
- `True` - Connection successful
- `False` - Connection failed

**Example:**
```python
if controller.connect():
    print("Connected to ESP32")
else:
    print("Connection failed")
```

### `disconnect() -> None`
Closes connection and performs emergency stop.

**Parameters:** None

**Returns:** None

**Example:**
```python
controller.disconnect()  # Always call when finished
```

---

## Motor Control Functions

### `enable_motor() -> bool`
Enables the stepper motor (required before movement).

**Parameters:** None

**Returns:**
- `True` - Motor enabled successfully  
- `False` - Enable command failed

**Example:**
```python
if controller.enable_motor():
    print("Motor ready for movement")
```

### `disable_motor() -> bool`
Disables the stepper motor (stops all movement).

**Parameters:** None

**Returns:**
- `True` - Motor disabled successfully
- `False` - Disable command failed

**Example:**
```python
controller.disable_motor()  # Call when finished moving
```

### `move_steps(steps: int) -> bool`
Move motor by specified number of steps (relative movement).

**Parameters:**
- `steps` (int): Number of steps to move
  - Positive values = clockwise rotation
  - Negative values = counterclockwise rotation
  - Range: No specific limit (depends on application)

**Returns:**
- `True` - Movement command sent successfully
- `False` - Movement command failed

**Example:**
```python
# Move 200 steps clockwise
controller.move_steps(200)

# Move 100 steps counterclockwise  
controller.move_steps(-100)
```

### `goto_position(position: int) -> bool`
Move motor to absolute position.

**Parameters:**
- `position` (int): Target absolute position in steps

**Returns:**
- `True` - Movement command sent successfully
- `False` - Movement command failed

**Example:**
```python
# Go to position 500 steps from home
controller.goto_position(500)

# Return to home position
controller.goto_position(0)
```

### `emergency_stop() -> bool`
Immediately halt motor movement.

**Parameters:** None

**Returns:**
- `True` - Stop command sent successfully
- `False` - Stop command failed

**Example:**
```python
controller.emergency_stop()  # Immediate stop
```

---

## Configuration Functions

### `set_speed(microseconds: int) -> bool`
Set motor speed by adjusting step delay.

**Parameters:**
- `microseconds` (int): Delay between steps in microseconds
  - Range: 100-10000 μs
  - Lower values = faster speed
  - Higher values = slower speed

**Returns:**
- `True` - Speed set successfully
- `False` - Invalid speed value or command failed

**Speed Reference:**
- 100 μs = Very fast
- 1000 μs = Medium speed (default)
- 5000 μs = Slow
- 10000 μs = Very slow

**Example:**
```python
# Set fast speed
controller.set_speed(500)

# Set slow speed  
controller.set_speed(3000)
```

### `set_microsteps(microsteps: int) -> bool`
Set microstep resolution for smoother movement.

**Parameters:**
- `microsteps` (int): Microstep setting
  - Valid values: 1, 2, 4, 8, 16, 32, 64, 256
  - Higher values = smoother movement, lower torque
  - Lower values = higher torque, less smooth

**Returns:**
- `True` - Microsteps set successfully
- `False` - Invalid microstep value or command failed

**Microstep Reference:**
- 1 = Full steps (highest torque)
- 16 = Good balance of smoothness/torque
- 256 = Maximum smoothness (lowest torque)

**Example:**
```python
# Set to 16 microsteps (common setting)
controller.set_microsteps(16)

# Set to maximum smoothness
controller.set_microsteps(256)
```

### `set_movement_type(movement_type: str) -> bool`
Set movement type/mode for different applications.

**Parameters:**
- `movement_type` (str): Movement mode
  - `"STEALTH"` = stealthChop mode (quiet operation)
  - `"INTERPOLATED"` = 256 microstep interpolation
  - `"CONTINUOUS"` = Standard movement mode

**Returns:**
- `True` - Movement type set successfully
- `False` - Invalid movement type or command failed

**Movement Type Reference:**
- **STEALTH**: Quietest operation, good for noise-sensitive applications
- **INTERPOLATED**: Smoothest movement, best precision
- **CONTINUOUS**: Standard mode, good balance

**Example:**
```python
# Set quiet operation
controller.set_movement_type("STEALTH")

# Set smooth precision mode
controller.set_movement_type("INTERPOLATED")
```

### `home_position() -> bool`
Set current position as home (position 0).

**Parameters:** None

**Returns:**
- `True` - Home position set successfully
- `False` - Home command failed

**Example:**
```python
# Set current location as home
controller.home_position()
```

---

## Status & Monitoring

### `get_status() -> Optional[Dict[str, Any]]`
Get current motor status and configuration.

**Parameters:** None

**Returns:**
- `dict` - Status information dictionary
- `None` - Status request failed

**Status Dictionary Keys:**
- `'Enabled'` (bool): Motor enabled state
- `'Position'` (int): Current position in steps  
- `'Target'` (int): Target position in steps
- `'Speed'` (int): Current speed in microseconds
- `'Moving'` (bool): Whether motor is currently moving
- `'Microsteps'` (int): Current microstep setting
- `'Movement'` (str): Current movement type

**Example:**
```python
status = controller.get_status()
if status:
    print(f"Position: {status['Position']} steps")
    print(f"Moving: {status['Moving']}")
    print(f"Speed: {status['Speed']} μs")
    print(f"Microsteps: {status['Microsteps']}")
    print(f"Movement Type: {status['Movement']}")
```

### `wait_for_movement_complete(check_interval=0.1, timeout=30.0) -> bool`
Wait for current movement to complete.

**Parameters:**
- `check_interval` (float): How often to check status in seconds (default: 0.1)
- `timeout` (float): Maximum time to wait in seconds (default: 30.0)

**Returns:**
- `True` - Movement completed successfully
- `False` - Movement timed out or error occurred

**Example:**
```python
# Start movement
controller.move_steps(1000)

# Wait for completion (up to 30 seconds)
if controller.wait_for_movement_complete():
    print("Movement finished")
else:
    print("Movement timed out")

# Custom timeout
controller.move_steps(500)
if controller.wait_for_movement_complete(timeout=10.0):
    print("Quick movement finished")
```

---

## Advanced Movement Functions

### `move_degrees(degrees: float, steps_per_revolution=200) -> bool`
Move motor by specified degrees.

**Parameters:**
- `degrees` (float): Degrees to rotate
  - Positive = clockwise
  - Negative = counterclockwise
- `steps_per_revolution` (int): Steps per full rotation (default: 200 for NEMA17)

**Returns:**
- `True` - Movement command sent successfully
- `False` - Movement command failed

**Example:**
```python
# Rotate 90 degrees clockwise
controller.move_degrees(90)

# Rotate 45 degrees counterclockwise
controller.move_degrees(-45)

# Custom motor with 400 steps per revolution
controller.move_degrees(180, steps_per_revolution=400)
```

### `move_revolutions(revolutions: float, steps_per_revolution=200) -> bool`
Move motor by specified number of revolutions.

**Parameters:**
- `revolutions` (float): Number of full rotations
  - Positive = clockwise
  - Negative = counterclockwise
- `steps_per_revolution` (int): Steps per full rotation (default: 200)

**Returns:**
- `True` - Movement command sent successfully
- `False` - Movement command failed

**Example:**
```python
# Rotate 2.5 revolutions clockwise
controller.move_revolutions(2.5)

# Rotate 1 revolution counterclockwise
controller.move_revolutions(-1.0)
```

---

## Error Handling

### Common Error Scenarios

1. **Connection Errors**
   - Wrong port or ESP32 not connected
   - ESP32 not responding

2. **Parameter Errors**
   - Invalid speed values (outside 100-10000 μs)
   - Invalid microstep values
   - Invalid movement types

3. **Movement Errors**
   - Motor not enabled before movement
   - Movement timeout

### Error Handling Examples

```python
# Connection with error handling
try:
    controller = ESP32StepperController('/dev/ttyUSB0')
    if not controller.connect():
        raise ConnectionError("Could not connect to ESP32")
    
    # Your code here
    
except ConnectionError as e:
    print(f"Connection failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    controller.disconnect()

# Parameter validation example  
def safe_set_speed(controller, speed):
    if 100 <= speed <= 10000:
        return controller.set_speed(speed)
    else:
        print(f"Invalid speed: {speed}. Must be 100-10000 μs")
        return False

# Movement with timeout handling
controller.move_steps(1000)
if not controller.wait_for_movement_complete(timeout=15.0):
    print("Movement timed out - stopping motor")
    controller.emergency_stop()
```

---

## Usage Examples

### Basic Movement Sequence
```python
from esp32link import ESP32StepperController
import time

controller = ESP32StepperController()

try:
    # Connect and setup
    controller.connect()
    controller.enable_motor()
    controller.set_speed(1000)  # 1ms between steps
    controller.set_microsteps(16)  # Smooth movement
    
    # Move in sequence
    controller.move_steps(200)  # 1 revolution clockwise
    controller.wait_for_movement_complete()
    
    time.sleep(1)  # Pause
    
    controller.move_steps(-100)  # Half revolution back
    controller.wait_for_movement_complete()
    
    # Return home
    controller.goto_position(0)
    controller.wait_for_movement_complete()
    
finally:
    controller.disable_motor()
    controller.disconnect()
```

### Context Manager Usage
```python
# Automatic connection handling
with ESP32StepperController('/dev/ttyUSB0') as controller:
    controller.enable_motor()
    controller.set_speed(500)  # Fast movement
    
    # Perform movements
    controller.move_revolutions(1.0)
    controller.wait_for_movement_complete()
    
    status = controller.get_status()
    print(f"Final position: {status['Position']}")
    
# Automatic disconnection when leaving context
```

### Precision Control Application
```python
def precision_positioning(controller, target_degrees, tolerance=0.5):
    """Move to target with high precision."""
    
    # Configure for precision
    controller.set_microsteps(256)  # Maximum smoothness
    controller.set_movement_type("INTERPOLATED")
    controller.set_speed(2000)  # Slower for precision
    
    # Move to target
    controller.move_degrees(target_degrees)
    controller.wait_for_movement_complete()
    
    # Verify position
    status = controller.get_status()
    current_degrees = (status['Position'] / 200.0) * 360.0
    error = abs(current_degrees - target_degrees)
    
    return error <= tolerance

# Usage
controller = ESP32StepperController()
controller.connect()
controller.enable_motor()

if precision_positioning(controller, 45.0):
    print("Positioned accurately at 45 degrees")
```

### Speed Testing Application
```python
def test_speeds(controller, test_steps=100):
    """Test different speeds and measure performance."""
    
    speeds = [100, 500, 1000, 2000, 5000, 10000]  # μs
    results = {}
    
    controller.enable_motor()
    controller.home_position()
    
    for speed in speeds:
        controller.set_speed(speed)
        
        start_time = time.time()
        controller.move_steps(test_steps)
        controller.wait_for_movement_complete()
        end_time = time.time()
        
        duration = end_time - start_time
        actual_speed = test_steps / duration  # steps per second
        
        results[speed] = {
            'duration': duration,
            'steps_per_second': actual_speed
        }
        
        print(f"Speed {speed}μs: {duration:.2f}s ({actual_speed:.1f} steps/s)")
        
        # Return to start position
        controller.move_steps(-test_steps)
        controller.wait_for_movement_complete()
    
    return results
```

---

## Hardware Configuration

### TMC2209 Wiring (ESP32 Pin 17)
- ESP32 Pin 17 → TMC2209 PDN_UART pin
- Add 1kΩ resistor between ESP32 Pin 17 and TMC2209 PDN_UART
- Standard stepper motor wiring to TMC2209 A1, A2, B1, B2
- Power supply to TMC2209 VM and GND

### Supported Motors
- NEMA17 stepper motors (200 steps/revolution)
- NEMA14, NEMA23 compatible with parameter adjustment
- Microstepping from 1 to 256 steps per full step

---

## Troubleshooting

### Connection Issues
- Check USB cable and port permissions
- Verify ESP32 is programmed with correct firmware
- Try different baud rates if connection fails

### Movement Issues
- Ensure motor is enabled before movement commands
- Check power supply to TMC2209 driver
- Verify stepper motor wiring connections

### Performance Issues
- Lower microstep settings for higher torque
- Increase speed values (μs) for slower, more reliable movement
- Use appropriate movement types for application requirements

---

This documentation covers all functions available in the ESP32StepperController class. For additional support or advanced usage, refer to the source code comments and example implementations.