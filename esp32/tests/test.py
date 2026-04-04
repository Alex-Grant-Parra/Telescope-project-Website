from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from interfaceESP32 import ESP32Connection, ESP32Motor, ESP32SerialConfig
import time
import random

# Auto-detect available USB port
conn = ESP32Connection()

motor1 = ESP32Motor.create(
    conn=conn,
    motor_id="motor1",
    step_pin=27,
    dir_pin=14,
    en_pin=26,
    steps_per_rev=1600,
    engage=True,
    replace=True,
)
motor2 = ESP32Motor.create(
    conn=conn,
    motor_id="motor2",
    step_pin=33,
    dir_pin=25,
    en_pin=32,
    steps_per_rev=1600,
    engage=True,
    replace=True
)


motor1.turn_degrees(360, forward=True, waitUntilFinished=True)
motor2.turn_degrees(180, forward=False, waitUntilFinished=True)
print(motor1.get_position())
print(motor2.get_position())