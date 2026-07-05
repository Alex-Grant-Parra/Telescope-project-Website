from datetime import datetime

from .convert import getRaDecAtTime


def _degrees_to_hms(ra_deg):
    total_hours = (ra_deg / 15.0) % 24.0
    hours = int(total_hours)
    minutes_float = (total_hours - hours) * 60.0
    minutes = int(minutes_float)
    seconds = round((minutes_float - minutes) * 60.0, 2)

    if seconds >= 60.0:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        hours = (hours + 1) % 24

    return [hours, minutes, seconds]


def _degrees_to_dms(dec_deg):
    sign = -1 if dec_deg < 0 else 1
    abs_degrees = abs(dec_deg)
    degrees = int(abs_degrees)
    minutes_float = (abs_degrees - degrees) * 60.0
    minutes = int(minutes_float)
    seconds = round((minutes_float - minutes) * 60.0, 2)

    if seconds >= 60.0:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        degrees += 1

    degrees *= sign
    return [degrees, minutes, seconds]


def getAllCelestialData(year, month, day, hour: int = 0, minute: int = 0, second: float = 0.0):
    whole_seconds = int(second)
    microseconds = int(round((second - whole_seconds) * 1_000_000))
    celestial_time = datetime(year, month, day, hour, minute, whole_seconds, microseconds)
    celestial_positions = getRaDecAtTime(celestial_time)
    formatted = {}

    for body_name, values in celestial_positions.items():
        ra_deg = values.get("ra_deg")
        dec_deg = values.get("dec_deg")
        if ra_deg is None or dec_deg is None:
            continue

        body_data = {
            "ra": _degrees_to_hms(ra_deg),
            "dec": _degrees_to_dms(dec_deg),
        }

        visual_mag = values.get("visual_mag")
        if visual_mag is not None:
            body_data["vmag"] = float(visual_mag)

        formatted[body_name.lower()] = body_data

    return formatted
