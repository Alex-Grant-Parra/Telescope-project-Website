
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
    # Time variable for VSOP-like series
    T = (jd - 2451545.0) / 365250.0

    # Case 1: X/Y/Z rectangular series already prepared
    if any(k in series for k in ("X", "Y", "Z")):
        def eval_list(terms):
            total = 0.0
            for term in terms:
                if len(term) < 3:
                    continue
                A, B, C = term[0], term[1], term[2]
                total += A * math.cos(B + C * T)
            return total
        X = eval_list(series.get("X", []))
        Y = eval_list(series.get("Y", []))
        Z = eval_list(series.get("Z", []))
        # Convert to RA (deg), Dec (deg), distance (AU) assuming heliocentric coords
        r = math.sqrt(X*X + Y*Y + Z*Z)
        # RA in degrees (0..360)
        ra = math.degrees(math.atan2(Y, X)) % 360.0
        # Dec in degrees
        dec = math.degrees(math.asin(Z / r)) if r != 0 else 0.0
        return ra, dec, r

    # Case 2: Summed L/B/R grouped series (fallback)
    def sum_group(prefix):
        total = 0.0
        for k, terms in series.items():
            if not k.upper().startswith(prefix.upper()):
                continue
            for term in terms:
                if len(term) < 3:
                    continue
                A, B, C = term[0], term[1], term[2]
                total += A * math.cos(B + C * T)
        return total
    L = sum_group('L')
    B_ = sum_group('B')
    R = sum_group('R')
    L_deg = math.degrees(L)
    B_deg = math.degrees(B_)
    ra = atan2(cos(B_deg) * sin(L_deg), cos(L_deg)) % 360
    dec = asin(sin(B_deg))
    return ra, dec, R

# ---------- ELP82b Moon evaluation ----------
def elp_to_position(series, jd):
    """
    Evaluate lunar series for given Julian Date.
    series: list of tuples (A, B, C, D, ...) for ELP82b terms
    Returns: ra_deg, dec_deg, distance_km
    """
    # Simple placeholder; actual implementation sums series properly.
    # The ELP82b terms may have variable-length tuples; each term's
    # first three values are expected to be (A, B, C) where C multiplies jd.
    L = 0.0
    B_ = 0.0
    for term in series:
        # unpack only the first three items; ignore any additional coefficients
        if len(term) < 3:
            continue
        A, B, C = term[0], term[1], term[2]
        L += A * math.cos(B + C * jd)
        B_ += A * math.sin(B + C * jd)
    R = 384400  # approximate lunar distance in km

    ra = atan2(cos(B_) * sin(L), cos(L))
    dec = asin(sin(B_))
    return ra % 360, dec, R
