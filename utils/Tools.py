from datetime import datetime, timezone

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
