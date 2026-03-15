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


motor2.set_speed_sps(1600)
motor2.turn_degrees(360)
# motor1.disengage()
# motor2.disengage()