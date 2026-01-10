# ESP32 TMC2209 Serial Control

This firmware exposes a newline-delimited JSON protocol over USB Serial (115200 baud) to control a TMC2209 stepper driver and NEMA17 via STEP/DIR.

Pins:
- stepPin: 18
- dirPin: 19
- ledPin: 2
- tmcUartTxPin: 17 (TX only)

## Commands
Send each as a single line JSON, terminated with \n. Responses are JSON objects with `status: ok|error`.

- {"cmd":"enable","value":true}
- {"cmd":"set_dir","forward":true}
- {"cmd":"set_speed","sps":800}
- {"cmd":"move_steps","steps":1600,"sps":1000,"forward":true}
- {"cmd":"stop"}
- {"cmd":"set_microsteps","value":16}
- {"cmd":"set_current","mA":500}
- {"cmd":"set_mode","mode":"stealth"}  // or "spread"
- {"cmd":"set_accel","sps2":1500}
- {"cmd":"status"}

## Build & Flash
Use PlatformIO:
- Build: `platformio run`
- Flash: `platformio run -t upload`
- Monitor: `platformio device monitor -b 115200`

If you prefer, use the convenience script `flash.sh`.
