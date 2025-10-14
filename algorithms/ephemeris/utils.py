
# utils.py
import math

# Mean obliquity of the ecliptic (J2000) in radians
OBLIQUITY_EPS = math.radians(23.4392911)

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
        # Heliocentric ecliptic rectangular coordinates (approximate AU)
        X_ecl = eval_list(series.get("X", []))
        Y_ecl = eval_list(series.get("Y", []))
        Z_ecl = eval_list(series.get("Z", []))
        # Rotate from ecliptic to equatorial frame using obliquity
        X_eq = X_ecl
        Y_eq = Y_ecl * math.cos(OBLIQUITY_EPS) - Z_ecl * math.sin(OBLIQUITY_EPS)
        Z_eq = Y_ecl * math.sin(OBLIQUITY_EPS) + Z_ecl * math.cos(OBLIQUITY_EPS)
        r = math.sqrt(X_eq*X_eq + Y_eq*Y_eq + Z_eq*Z_eq)
        ra = (math.degrees(math.atan2(Y_eq, X_eq)) + 360.0) % 360.0 if r != 0 else 0.0
        dec = math.degrees(math.asin(Z_eq / r)) if r != 0 else 0.0
        return ra, dec, r

def series_to_equatorial_xyz(series, jd):
    """Return equatorial rectangular (X,Y,Z) and distance r (AU) for a VSOP X/Y/Z series.
    This uses the simplified parsing currently implemented.
    """
    T = (jd - 2451545.0) / 365250.0
    if not any(k in series for k in ("X", "Y", "Z")):
        return None
    def eval_list(terms):
        total = 0.0
        for term in terms:
            if len(term) < 3:
                continue
            A, B, C = term[0], term[1], term[2]
            total += A * math.cos(B + C * T)
        return total
    X_ecl = eval_list(series.get("X", []))
    Y_ecl = eval_list(series.get("Y", []))
    Z_ecl = eval_list(series.get("Z", []))
    X_eq = X_ecl
    Y_eq = Y_ecl * math.cos(OBLIQUITY_EPS) - Z_ecl * math.sin(OBLIQUITY_EPS)
    Z_eq = Y_ecl * math.sin(OBLIQUITY_EPS) + Z_ecl * math.cos(OBLIQUITY_EPS)
    r = math.sqrt(X_eq*X_eq + Y_eq*Y_eq + Z_eq*Z_eq)
    return X_eq, Y_eq, Z_eq, r

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
    L = sum_group('L')  # longitude (radians)
    B_ = sum_group('B')  # latitude (radians)
    R = sum_group('R')
    # Apply ecliptic (λ,β) -> equatorial (α,δ)
    # α = atan2( sinλ cosε - tanβ sinε, cosλ )
    # δ = asin( sinβ cosε + cosβ sinε sinλ )
    lam = L
    beta = B_
    cos_eps = math.cos(OBLIQUITY_EPS)
    sin_eps = math.sin(OBLIQUITY_EPS)
    sin_lam = math.sin(lam)
    cos_lam = math.cos(lam)
    tan_beta = math.tan(beta)
    sin_beta = math.sin(beta)
    cos_beta = math.cos(beta)
    alpha = math.atan2(sin_lam * cos_eps - tan_beta * sin_eps, cos_lam)
    delta = math.asin(sin_beta * cos_eps + cos_beta * sin_eps * sin_lam)
    ra = (math.degrees(alpha) + 360.0) % 360.0
    dec = math.degrees(delta)
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

    # Treat L as ecliptic longitude, B_ as latitude (already in radians?) —
    # current placeholder uses raw sums; for now convert assuming radians.
    lam = L
    beta = B_
    cos_eps = math.cos(OBLIQUITY_EPS)
    sin_eps = math.sin(OBLIQUITY_EPS)
    sin_lam = math.sin(lam)
    cos_lam = math.cos(lam)
    tan_beta = math.tan(beta)
    sin_beta = math.sin(beta)
    cos_beta = math.cos(beta)
    alpha = math.atan2(sin_lam * cos_eps - tan_beta * sin_eps, cos_lam)
    delta = math.asin(sin_beta * cos_eps + cos_beta * sin_eps * sin_lam)
    ra = (math.degrees(alpha) + 360.0) % 360.0
    dec = math.degrees(delta)
    return ra, dec, R
