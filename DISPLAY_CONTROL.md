# ST7735S TFT Display Control

This document explains how to use the ST7735S TFT LCD display connected to your ESP32, controlled from the Raspberry Pi.

## Hardware Setup

The display is connected to the ESP32 with the following pin configuration:

| TFT Pin | ESP32 Pin | Description |
| --- | --- | --- |
| VCC | 3.3V | Power supply |
| GND | GND | Ground |
| SCK | D13 | SPI Clock |
| SDA | D19 | SPI MOSI (Data) |
| DC | D21 | Data/Command select |
| RES | D12 | Reset pin |
| CS | GND | Chip Select (tied to ground) |
| BL | D15 | Backlight control (PWM) |

**Display Specifications:**
- Resolution: 128×160 pixels
- Color depth: 16-bit RGB565
- Communication: SPI at 40 MHz

## Python Interface

### Basic Usage

```python
from esp32.interfaceESP32 import ESP32Connection, ESP32Display

# Connect to ESP32
conn = ESP32Connection()

# Create display controller
display = ESP32Display(conn)

# Initialize the display
display.initialize()

# Set backlight brightness (0-255)
display.set_backlight(255)

# Clear screen with black
display.clear("black")

# Draw a filled rectangle
display.fill_rectangle(10, 10, 50, 30, "red")

# Draw a circle outline
display.draw_circle(64, 80, 15, "blue")

# Get display status
status = display.get_status()
print(status)
```

### Available Colors

Pre-defined colors are available by name:
- `"black"` (000000)
- `"red"` (FF0000)
- `"green"` (00FF00)
- `"blue"` (0000FF)
- `"white"` (FFFFFF)
- `"yellow"` (FFFF00)
- `"cyan"` (00FFFF)
- `"magenta"` (FF00FF)

You can also use any custom hex color: `"1A2B3C"` or `"#FF0000"`

### Drawing Operations

#### Basic Shapes

```python
# Clear display
display.clear("black")

# Fill rectangle
display.fill_rectangle(x=10, y=10, width=50, height=40, color="red")

# Draw rectangle outline
display.draw_rectangle(x=10, y=10, width=50, height=40, color="white")

# Draw filled circle
display.fill_circle(x=64, y=80, radius=20, color="blue")

# Draw circle outline
display.draw_circle(x=64, y=80, radius=20, color="white")

# Draw line
display.draw_line(x0=0, y0=0, x1=127, y1=159, color="green")

# Draw single pixel
display.draw_pixel(x=50, y=50, color="white")
```

#### Coordinate System

- **X-axis:** 0-127 (left to right)
- **Y-axis:** 0-159 (top to bottom)
- **Origin (0, 0):** Top-left corner

### Text and Cursor Control

```python
# Set cursor position (for future text drawing)
display.set_cursor(x=0, y=0)

# Set text color
display.set_text_color("white")

# Set background color
display.set_background_color("black")

# Print text (not yet fully implemented - reserved for future use)
# display.print_text("Hello")
```

### Display Control

```python
# Turn display on/off
display.power(True)   # Turn on
display.power(False)  # Turn off

# Set backlight brightness (0-255, where 0 is off, 255 is full brightness)
display.set_backlight(128)  # 50% brightness
display.set_backlight(255)  # Full brightness

# Get display status
status = display.get_status()
# Returns: {
#   'initialized': True,
#   'powered': True,
#   'brightness': 255,
#   'width': 128,
#   'height': 160,
#   'cursor_x': 0,
#   'cursor_y': 0,
#   'text_color': 'FFFFFF',
#   'background_color': '000000'
# }
```

### Test Pattern

```python
# Draw a test pattern (useful for debugging/verification)
display.draw_test_pattern()
# This draws:
# - Colored rectangles (red, green, blue, yellow)
# - Colored circles (cyan, magenta)
# - Grid lines (white)
```

## C++ Serial Protocol

The display is controlled via JSON commands sent over serial. The Python interface handles this automatically, but here are the available commands for reference:

### Display Initialization

```json
{"cmd": "display", "action": "init"}
```

### Display Power

```json
{"cmd": "display", "action": "power", "on": true}
```

### Backlight Control

```json
{"cmd": "display", "action": "backlight", "brightness": 255}
```

Parameters:
- `brightness`: 0-255 PWM value

### Clear Screen

```json
{"cmd": "display", "action": "clear", "color": "000000"}
```

Parameters:
- `color`: Optional hex color (default: "000000" black)

### Draw Shapes

**Rectangle (filled):**
```json
{"cmd": "display", "action": "fill_rect", "x": 10, "y": 10, "w": 50, "h": 40, "color": "FF0000"}
```

**Rectangle (outline):**
```json
{"cmd": "display", "action": "draw_rect", "x": 10, "y": 10, "w": 50, "h": 40, "color": "FFFFFF"}
```

**Line:**
```json
{"cmd": "display", "action": "draw_line", "x0": 0, "y0": 0, "x1": 127, "y1": 159, "color": "00FF00"}
```

**Circle (filled):**
```json
{"cmd": "display", "action": "fill_circle", "x": 64, "y": 80, "r": 15, "color": "0000FF"}
```

**Circle (outline):**
```json
{"cmd": "display", "action": "draw_circle", "x": 64, "y": 80, "r": 15, "color": "FFFFFF"}
```

### Cursor and Text

**Set cursor position:**
```json
{"cmd": "display", "action": "set_cursor", "x": 0, "y": 0}
```

**Set text color:**
```json
{"cmd": "display", "action": "set_text_color", "color": "FFFFFF"}
```

**Set background color:**
```json
{"cmd": "display", "action": "set_bg_color", "color": "000000"}
```

### Get Display Status

```json
{"cmd": "display", "action": "status"}
```

Response includes initialization state, power status, brightness, and cursor position.

## Example Programs

### Animated Color Test

```python
from esp32.interfaceESP32 import ESP32Connection, ESP32Display
import time

conn = ESP32Connection()
display = ESP32Display(conn)
display.initialize()

colors = ["red", "green", "blue", "yellow", "cyan", "magenta"]

for color in colors:
    display.clear(color)
    time.sleep(0.5)

display.clear("black")
```

### Draw Dashboard

```python
display.clear("black")

# Title area (blue header)
display.fill_rectangle(0, 0, 128, 20, "blue")

# Status indicators
display.fill_circle(10, 30, 5, "green")   # Online
display.fill_circle(118, 30, 5, "yellow")  # Warning

# Data boxes
display.draw_rectangle(5, 50, 118, 50, "white")
display.draw_rectangle(5, 110, 118, 45, "white")

# Bottom bar
display.fill_rectangle(0, 150, 128, 10, "cyan")
```

### Loading Animation

```python
for i in range(0, 128, 4):
    display.clear("black")
    display.fill_rectangle(0, 75, i, 10, "blue")
    time.sleep(0.05)
```

## Troubleshooting

### Display doesn't initialize
- Verify all pin connections match the hardware setup
- Check SPI bus speed (40 MHz default)
- Ensure power supply is stable 3.3V
- Try power cycling the ESP32

### Colors look wrong
- Display uses RGB565 format, not RGB888
- Hex color values are converted automatically
- Check if the "color_invert" setting is enabled (not implemented yet)

### Drawing is slow
- SPI communication happens at 40 MHz
- Complex scenes with many operations will take time
- Batch multiple operations where possible

## Future Enhancements

Potential features to implement:
- Text rendering with various font sizes
- Image blitting from stored buffers
- Animation support
- Display rotation/mirroring
- Gamma correction
- Touch screen support (if added)
- DMA acceleration for faster transfers
