from datetime import datetime, timezone

def hour_angle(ra_deg, longitude_deg):
    now = datetime.now(timezone.utc)

    Y = now.year
    M = now.month
    D = now.day + now.hour/24 + now.minute/1440 + now.second/86400

    if M <= 2:
        Y -= 1
        M += 12

    A = Y // 100
    B = 2 - A + A // 4

    JD = int(365.25*(Y + 4716)) + int(30.6001*(M + 1)) + D + B - 1524.5

    T = (JD - 2451545.0) / 36525.0

    GMST = 280.46061837 + 360.98564736629 * (JD - 2451545) + 0.000387933 * T * T

    LST = (GMST + longitude_deg) % 360

    HA = (LST - ra_deg) % 360

    if HA > 180:
        HA -= 360

    return HA


# Example usage:
ra = 101.25       # Sirius
longitude = -1.5  # Example: UK-ish

print("Hour Angle:", hour_angle(ra, longitude), "degrees")