# utils.py
import math

# ---------- Trig helpers in degrees ----------
sin = lambda x: math.sin(math.radians(x))
cos = lambda x: math.cos(math.radians(x))
tan = lambda x: math.tan(math.radians(x))
asin = lambda x: math.degrees(math.asin(x))
acos = lambda x: math.degrees(math.acos(x))
atan = lambda x: math.degrees(math.atan(x))
atan2 = lambda y, x: math.degrees(math.atan2(y, x))

# ---------- VSOP87 evaluation ----------
def series_to_position(series, jd):
    """
    Evaluate VSOP87 series for given Julian Date.
    series: dict of {L, B, R} -> list of (A, B, C)
    Returns: ra_deg, dec_deg, r_au
    """
    T = (jd - 2451545.0) / 365250.0  # Julian millennia
    L = sum(A * math.cos(B + C * T) for A, B, C in series.get("L", []))
    B_ = sum(A * math.cos(B + C * T) for A, B, C in series.get("B", []))
    R = sum(A * math.cos(B + C * T) for A, B, C in series.get("R", []))
    
    # Simplified: convert ecliptic L,B to RA, Dec
    # More precise conversion can include obliquity of ecliptic
    ra = atan2(cos(B_) * sin(L), cos(L))
    dec = asin(sin(B_))
    return ra % 360, dec, R

# ---------- ELP82b Moon evaluation ----------
def elp_to_position(series, jd):
    """
    Evaluate lunar series for given Julian Date.
    series: list of tuples (A, B, C, D, ...) for ELP82b terms
    Returns: ra_deg, dec_deg, distance_km
    """
    # Simple placeholder; actual implementation sums series properly
    L = sum(A * math.cos(B + C * jd) for A, B, C in series)
    B_ = sum(A * math.sin(B + C * jd) for A, B, C in series)
    R = 384400  # approximate lunar distance in km

    ra = atan2(cos(B_) * sin(L), cos(L))
    dec = asin(sin(B_))
    return ra % 360, dec, R
