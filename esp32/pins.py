from __future__ import annotations

from typing import Any, Dict


# Single source of truth for ESP32-side hardware assignments used by the Python client.
ESP32_HARDWARE: Dict[str, Any] = {
    "leds": {
        "board": {"channel": "board", "pin": 2},
        "yellow": {"channel": "yellow", "pin": 18},
        "blue": {"channel": "blue", "pin": 5},
        "white": {"channel": "white", "pin": 17},
        "green": {"channel": "green", "pin": 16},
        "red": {"channel": "red", "pin": 4},
    },
    "display": {
        "width": 128,
        "height": 160,
        "pins": {
            "sck": 13,
            "sda": 19,
            "dc": 21,
            "res": 12,
            "cs": -1,
            "bl": 15,
        },
    },
    "motor_boards": {
        "ra": {
            "motor_id": "motor1",
            "label": "RA motor",
            "pins": {"step": 27, "dir": 14, "en": 26},
            "steps_per_rev": 1600,
            "engage": True,
            "replace": True,
            "required": True,
        },
        "dec": {
            "motor_id": "motor2",
            "label": "DEC motor",
            "pins": {"step": 33, "dir": 25, "en": 32},
            "steps_per_rev": 1600,
            "engage": True,
            "replace": True,
            "required": False,
        },
    },
}


def get_led_channels() -> Dict[str, Dict[str, int | str]]:
    return ESP32_HARDWARE["leds"]


def get_display_config() -> Dict[str, Any]:
    return ESP32_HARDWARE["display"]


def get_motor_boards() -> Dict[str, Dict[str, Any]]:
    return ESP32_HARDWARE["motor_boards"]


def get_motor_board_by_id(motor_id: str) -> Dict[str, Any] | None:
    for board in ESP32_HARDWARE["motor_boards"].values():
        if board.get("motor_id") == motor_id:
            return board
    return None
