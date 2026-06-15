from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from interfaceESP32 import ESP32Connection, ESP32Motor, ESP32SerialConfig, ESP32LED
import time
import random

# Auto-detect available USB port
conn = ESP32Connection()

# motor1 = ESP32Motor.create(
#     conn=conn,
#     motor_id="motor1",
#     step_pin=int(get_motor_board_by_id("motor1")["pins"]["step"]),
#     dir_pin=int(get_motor_board_by_id("motor1")["pins"]["dir"]),
#     en_pin=int(get_motor_board_by_id("motor1")["pins"]["en"]),
#     steps_per_rev=1600,
#     engage=True,
#     replace=True,
# )
# motor2 = ESP32Motor.create(
#     conn=conn,
#     motor_id="motor2",
#     step_pin=int(get_motor_board_by_id("motor2")["pins"]["step"]),
#     dir_pin=int(get_motor_board_by_id("motor2")["pins"]["dir"]),
#     en_pin=int(get_motor_board_by_id("motor2")["pins"]["en"]),
#     steps_per_rev=1600,
#     engage=True,
#     replace=True
# )


# motor1.turn_degrees(360, forward=True, waitUntilFinished=True)
# motor2.turn_degrees(180, forward=False, waitUntilFinished=True)
# print(motor1.get_position())
# print(motor2.get_position())


def flash_led_twice(led, on_time: float = 0.25, gap_time: float = 0.125) -> None:
	led.on()
	time.sleep(on_time)
	led.off()
	time.sleep(gap_time)
	led.on()
	time.sleep(on_time)
	led.off()


led_sequence = [
	ESP32LED.board,
	ESP32LED.yellow,
	ESP32LED.blue,
	ESP32LED.white,
	ESP32LED.green,
	ESP32LED.red,
]

while True:
    try:
        for led in led_sequence:
            flash_led_twice(led, on_time=0.25, gap_time=0.125)
            time.sleep(0.5)
    finally:
        for led in led_sequence:
            led.off()

