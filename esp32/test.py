from interfaceESP32 import ESP32Connection, ESP32Motor, ESP32SerialConfig
import time
import random

# Auto-detect available USB port
conn = ESP32Connection()

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

motor.stop()
motor.set_speed_sps(2800)
motor.turn_degrees(720, forward=True)
motor.turn_degrees(720, forward=False)
