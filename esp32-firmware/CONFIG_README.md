# ESP32 Motor Controller Configuration

This firmware now supports dynamic motor configuration via JSON files stored in SPIFFS.

## Configuration File: motor_config.json

The motor configuration is defined in `motor_config.json` with the following structure:

```json
{
  "motors": [
    {
      "id": "motor1",
      "stepPin": 18,
      "dirPin": 19,
      "ledPin": 2,
      "tmcUartTxPin": 17,
      "serialPort": 2,
      "tmcAddress": "0x00",
      "enabled": true,
      "description": "Main azimuth motor"
    }
  ],
  "defaults": {
    "microsteps": 16,
    "current_mA": 500,
    "stealth_mode": true,
    "max_accel": 1000.0
  }
}
```

### Motor Parameters:
- `id`: Unique identifier for the motor (used in JSON commands)
- `stepPin`: GPIO pin for STEP signal
- `dirPin`: GPIO pin for DIR signal  
- `ledPin`: GPIO pin for status LED
- `tmcUartTxPin`: GPIO pin for TMC2209 UART TX (single-wire)
- `serialPort`: Hardware serial port number (0, 1, or 2)
- `tmcAddress`: TMC2209 UART address (hex string or integer)
- `enabled`: Whether this motor should be initialized
- `description`: Human-readable description

### Default Parameters:
- `microsteps`: Default microstepping setting
- `current_mA`: Default motor current in milliamps
- `stealth_mode`: Default chopper mode (true=stealthChop, false=spreadCycle)
- `max_accel`: Default acceleration in steps/sec²

## Uploading Configuration

### Method 1: PlatformIO Upload
1. Edit `motor_config.json` with your pin assignments
2. Run: `pio run --target uploadfs`

### Method 2: Copy to Data Directory
1. Edit `motor_config.json` 
2. Run: `python upload_config.py`
3. Run: `pio run --target uploadfs`

## Pin Assignment Examples

### Single Motor Setup:
```json
{
  "motors": [
    {
      "id": "motor1",
      "stepPin": 18,
      "dirPin": 19,
      "ledPin": 2,
      "tmcUartTxPin": 17,
      "serialPort": 2,
      "tmcAddress": "0x00",
      "enabled": true,
      "description": "Single motor"
    }
  ]
}
```

### Dual Motor Setup:
```json
{
  "motors": [
    {
      "id": "azimuth",
      "stepPin": 18,
      "dirPin": 19,
      "ledPin": 2,
      "tmcUartTxPin": 17,
      "serialPort": 2,
      "tmcAddress": "0x00",
      "enabled": true,
      "description": "Azimuth motor"
    },
    {
      "id": "altitude", 
      "stepPin": 21,
      "dirPin": 22,
      "ledPin": 4,
      "tmcUartTxPin": 16,
      "serialPort": 1,
      "tmcAddress": "0x01",
      "enabled": true,
      "description": "Altitude motor"
    }
  ]
}
```

## Usage with JSON Commands

Commands now support motor targeting:

```json
{
  "cmd": "start",
  "motor": "motor1",
  "sps": 800,
  "forward": true
}
```

If no motor is specified, commands default to "motor1" for backwards compatibility.

## Fallback Behavior

If `motor_config.json` is not found or cannot be parsed, the firmware will:
1. Create a default single motor configuration
2. Use pin assignments: step=18, dir=19, led=2, uart=17
3. Log the fallback to serial output

## Debugging

Monitor serial output during boot to see:
- Configuration loading status
- Pin assignments for each motor
- Any parsing errors
- Fallback notifications

Example boot output:
```
[BOOT] ESP32 Motor Controller starting...
[CONFIG] Loaded motor motor1: step=18, dir=19, led=2, uart=17, addr=0x00
[CONFIG] Successfully loaded 1 motor configurations
[BOOT] Initializing motor1 (Main azimuth motor)
[BOOT] Motor controller ready with 1 motors
```
