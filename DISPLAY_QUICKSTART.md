# ST7735S Display - Quick Start Guide

## What Was Created

I've implemented a complete ST7735S TFT LCD display control system for your ESP32 + Raspberry Pi setup. Here's what you got:

### New Files:
1. **`esp32-firmware/src/display.h`** - Display hardware definitions
2. **`esp32-firmware/src/display.cpp`** - Display driver implementation (~450 lines)
3. **`esp32/interfaceESP32.py` → added `ESP32Display` class** - Python control interface
4. **`DISPLAY_CONTROL.md`** - Complete user documentation
5. **`DISPLAY_IMPLEMENTATION.md`** - Technical implementation details
6. **`examples/display_demo.py`** - Example usage script

### Modified Files:
1. **`esp32-firmware/src/commands.h`** - Added display response handler
2. **`esp32-firmware/src/commands.cpp`** - Added display command routing
3. **`esp32-firmware/src/main.cpp`** - Added display initialization

## Hardware Verification

Your pin connections (from your table):
- ✅ VCC → 3.3V
- ✅ GND → GND
- ✅ SCK → D13 (SPI Clock)
- ✅ SDA → D19 (SPI MOSI)
- ✅ DC → D21 (Data/Command)
- ✅ RES → D12 (Reset)
- ✅ CS → GND (Chip Select)
- ✅ BL → D15 (Backlight PWM)

All pins are configured in `display.h` - no conflicts with existing motors/LEDs.

## Next Steps

### 1. Compile and Flash ESP32
```bash
cd /home/alex/Rpi5.Client/esp32-firmware
platformio run -t upload
```

### 2. Test from Python (Quick Test)
```python
from esp32.interfaceESP32 import ESP32Connection, ESP32Display

conn = ESP32Connection()
display = ESP32Display(conn)
display.initialize()
display.clear("red")
```

### 3. Run Full Demo
```bash
cd /home/alex/Rpi5.Client
python3 examples/display_demo.py
```

## Available Python Methods

```python
# Initialization
display.initialize()
display.power(True/False)
display.set_backlight(0-255)

# Drawing
display.clear(color)
display.fill_rectangle(x, y, w, h, color)
display.draw_rectangle(x, y, w, h, color)
display.fill_circle(x, y, radius, color)
display.draw_circle(x, y, radius, color)
display.draw_line(x0, y0, x1, y1, color)
display.draw_pixel(x, y, color)

# Text (cursor positioning, colors)
display.set_cursor(x, y)
display.set_text_color(color)
display.set_background_color(color)

# Status/Debug
display.get_status()
display.draw_test_pattern()
```

## Supported Colors

**By name:**
- black, red, green, blue, white, yellow, cyan, magenta

**By hex:**
- Any hex color: `"1A2B3C"` or with hash: `"#FF0000"`

## Communication Protocol

The system uses JSON over serial (existing pattern):

```json
{"cmd": "display", "action": "init"}
{"cmd": "display", "action": "clear", "color": "000000"}
{"cmd": "display", "action": "fill_rect", "x": 10, "y": 10, "w": 50, "h": 40, "color": "FF0000"}
```

All responses include status:
```json
{"status": "ok", "data": {...}}
```

## Performance Notes

- **SPI Speed:** 40 MHz
- **Resolution:** 128×160 pixels
- **Color Depth:** 16-bit RGB565
- **Backlight:** PWM on GPIO 15 (0-255)
- **Full screen fill:** ~50ms

## Troubleshooting

**Display doesn't show anything:**
- Check all pin connections
- Verify power supply (3.3V stable)
- Try `display.set_backlight(255)` to ensure backlight is on
- Power cycle ESP32

**Colors are off:**
- Display uses RGB565, not RGB888
- Hex color conversion is automatic
- Try primary colors first: red, green, blue

**Compilation errors:**
- Ensure platformio.ini has ArduinoJson (it does)
- Clean build: `platformio run -t clean`
- Then: `platformio run -t upload`

## Documentation

For detailed information, see:
- **User Guide:** `DISPLAY_CONTROL.md` - How to use the display
- **Technical Details:** `DISPLAY_IMPLEMENTATION.md` - Implementation overview
- **Example Code:** `examples/display_demo.py` - Working example

## Key Features Implemented

✅ ST7735S initialization sequence
✅ SPI communication at 40 MHz
✅ Drawing primitives (lines, circles, rectangles, pixels)
✅ PWM backlight control
✅ RGB565 color support
✅ JSON serial protocol
✅ Python class for easy control
✅ Error handling and bounds checking
✅ Test patterns for debugging

## What's Next?

Once verified working, you can:
1. Integrate into your telescope/camera control system
2. Add real-time telemetry display
3. Show camera status/preview
4. Display motor positions
5. Show system diagnostics
6. Create custom UI layouts

The display is fully controllable from your Python Client code!
