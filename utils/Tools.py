from datetime import datetime, timezone
from typing import Union

def motor_steps_to_degrees(steps: int, steps_per_rev: int = 1600, gear_ratio: float = 360.0) -> float:
	# Convert motor steps to angular degrees for a polar-aligned telescope.
	# 
	# Args:
	#	steps: Signed integer representing motor position in steps
	#	steps_per_rev: Number of steps per motor revolution (default: 1600)
	#	gear_ratio: Gear reduction ratio mapping motor rev to sky degrees (default: 360 for RA)
	# 
	# Returns:
	#	Angular deviation in degrees (negative = behind target, positive = ahead)
	# 
	# Example:
	#	A 400-step deviation with default RA gearing = 90 arcseconds error
	degrees_per_step = gear_ratio / steps_per_rev
	return steps * degrees_per_step


def motor_steps_to_arcminutes(steps: int, steps_per_rev: int = 1600, gear_ratio: float = 360.0) -> float:
	# Convert motor steps to arcminutes (useful for fine alignment).
	# 
	# Args:
	#	steps: Signed integer representing motor position in steps
	#	steps_per_rev: Number of steps per motor revolution (default: 1600)
	#	gear_ratio: Gear reduction ratio mapping motor rev to sky degrees (default: 360 for RA)
	# 
	# Returns:
	#	Angular deviation in arcminutes
	degrees = motor_steps_to_degrees(steps, steps_per_rev, gear_ratio)
	return degrees * 60


def motor_steps_to_arcseconds(steps: int, steps_per_rev: int = 1600, gear_ratio: float = 360.0) -> float:
	# Convert motor steps to arcseconds (highest precision).
	# 
	# Args:
	#	steps: Signed integer representing motor position in steps
	#	steps_per_rev: Number of steps per motor revolution (default: 1600)
	#	gear_ratio: Gear reduction ratio mapping motor rev to sky degrees (default: 360 for RA)
	# 
	# Returns:
	#	Angular deviation in arcseconds
	arcmin = motor_steps_to_arcminutes(steps, steps_per_rev, gear_ratio)
	return arcmin * 60


def hour_angle(ra_deg, longitude_deg):
    now = datetime.now(timezone.utc)

    D = now.day + now.hour/24 + now.minute/1440 + now.second/86400
    Y, M = now.year, now.month
    if M <= 2:
        Y -= 1
        M += 12

    A = Y // 100
    B = 2 - A + A // 4

    JD = int(365.25*(Y + 4716)) + int(30.6001*(M + 1)) + D + B - 1524.5

    GMST = 280.46061837 + 360.98564736629 * (JD - 2451545)

    LST = (GMST + longitude_deg) % 360

    HA = (LST - ra_deg + 180) % 360 - 180

    return HA
