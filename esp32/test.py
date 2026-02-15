from interfaceESP32 import ESP32Connection, ESP32Motor, ESP32SerialConfig
import time

# Use /dev/ttyUSB1
cfg = ESP32SerialConfig(port="/dev/ttyUSB1")
conn = ESP32Connection(cfg)

motor = ESP32Motor.create(
    conn=conn,
    motor_id="motor1",
    step_pin=27,
    dir_pin=14,
    en_pin=26,
    steps_per_rev=1600,
    engage=True,
    replace=True,
)

motor.set_speed_sps(100)
motor.turn_degrees(360, forward=True)
motor.disengage()

