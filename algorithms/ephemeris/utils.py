
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
    # Helper to evaluate lists of (A,B,C) terms; many VSOP-derived pickles
    # created by the pickler use triples (A, B, C) representing A*cos(B + C*T)
    def eval_triples(terms, scale_T=True):
        total = 0.0
        for term in terms:
            if len(term) < 3:
                continue
            A, B, C = term[0], term[1], term[2]
            tval = T if scale_T else jd
            total += A * math.cos(B + C * tval)
        return total

    # Case A: X/Y/Z rectangular series already prepared
    if any(k in series for k in ("X", "Y", "Z")):
        X_ecl = eval_triples(series.get("X", []))
        Y_ecl = eval_triples(series.get("Y", []))
        Z_ecl = eval_triples(series.get("Z", []))
        # Rotate from ecliptic to equatorial frame using obliquity
        X_eq = X_ecl
        Y_eq = Y_ecl * math.cos(OBLIQUITY_EPS) - Z_ecl * math.sin(OBLIQUITY_EPS)
        Z_eq = Y_ecl * math.sin(OBLIQUITY_EPS) + Z_ecl * math.cos(OBLIQUITY_EPS)
        r = math.sqrt(X_eq*X_eq + Y_eq*Y_eq + Z_eq*Z_eq)
        ra = (math.degrees(math.atan2(Y_eq, X_eq)) + 360.0) % 360.0 if r != 0 else 0.0
        dec = math.degrees(math.asin(Z_eq / r)) if r != 0 else 0.0
        return ra, dec, r

    # Case B: Series given as L (lambda), B (beta), R (radius) lists
    # Evaluate as sums of A * cos(B + C*T). This is a simplified evaluator
    # and assumes the pickler has bundled polynomial-in-T terms into triples.
    if any(k in series for k in ("L", "B", "R")):
        L = eval_triples(series.get("L", []))
        B_ = eval_triples(series.get("B", []))
        R = eval_triples(series.get("R", []))
        # Convert to rectangular ecliptic coordinates
        X_ecl = R * math.cos(B_) * math.cos(L)
        Y_ecl = R * math.cos(B_) * math.sin(L)
        Z_ecl = R * math.sin(B_)
        # Rotate to equatorial
        X_eq = X_ecl
        Y_eq = Y_ecl * math.cos(OBLIQUITY_EPS) - Z_ecl * math.sin(OBLIQUITY_EPS)
        Z_eq = Y_ecl * math.sin(OBLIQUITY_EPS) + Z_ecl * math.cos(OBLIQUITY_EPS)
        r = math.sqrt(X_eq*X_eq + Y_eq*Y_eq + Z_eq*Z_eq)
        ra = (math.degrees(math.atan2(Y_eq, X_eq)) + 360.0) % 360.0 if r != 0 else 0.0
        dec = math.degrees(math.asin(Z_eq / r)) if r != 0 else 0.0
        return ra, dec, r

    # Unknown series shape
    return None


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


def heliocentric_to_geocentric(object_xyz, earth_xyz):
    """Convert heliocentric equatorial Cartesian coordinates to geocentric RA/Dec and distance.

    Inputs:
        object_xyz: (Ox, Oy, Oz, Or) in AU
        earth_xyz: (Ex, Ey, Ez, Er) in AU

    Returns:
        dict with keys: ra_deg, dec_deg, distance_km, ra_hms, dec_dms
    """
    if not object_xyz or not earth_xyz:
        return None
    Ox, Oy, Oz, Or = object_xyz
    Ex, Ey, Ez, Er = earth_xyz
    Gx, Gy, Gz = Ox - Ex, Oy - Ey, Oz - Ez
    Gr = math.sqrt(Gx*Gx + Gy*Gy + Gz*Gz)
    # RA/Dec in degrees (equatorial)
    ra_deg = (math.degrees(math.atan2(Gy, Gx)) + 360.0) % 360.0 if Gr != 0 else 0.0
    dec_deg = math.degrees(math.asin(Gz / Gr)) if Gr != 0 else 0.0
    # Distance in km (AU -> km)
    AU_KM = 149597870.7
    distance_km = Gr * AU_KM

    # RA to H:M:S
    hours = ra_deg / 15.0
    h = int(hours)
    m = int((hours - h) * 60)
    s = round(((hours - h) * 60 - m) * 60, 2)

    # Dec to D:M:S
    sign = -1 if dec_deg < 0 else 1
    adec = abs(dec_deg)
    d = int(adec)
    dm = int((adec - d) * 60)
    ds = round(((adec - d) * 60 - dm) * 60, 2)
    if sign < 0:
        d = -d

    return {
        'ra_deg': ra_deg,
        'dec_deg': dec_deg,
        'distance_km': distance_km,
        'ra_hms': [h, m, s],
        'dec_dms': [d, dm, ds]
    }


def heliocentric_to_geocentric_for_body(body_xyz, earth_xyz):
    """Generic wrapper: convert any body's heliocentric equatorial (X,Y,Z,r)
    to geocentric RA/Dec and distance. Accepts body_xyz or None.

    body_xyz: (X, Y, Z, r) in AU
    earth_xyz: (Ex, Ey, Ez, er) in AU
    """
    if not body_xyz or not earth_xyz:
        return None
    return heliocentric_to_geocentric(body_xyz, earth_xyz)

# convert expects [deg, min, sec]
def d2dms(v):
	sign = -1 if v < 0 else 1
	a = abs(v)
	d = int(a)
	m = int((a - d) * 60)
	s = round((a - d - m/60) * 3600, 2)
	return [d * sign, m, s]

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
    # Use scaled time variable similar to VSOP: small T variable
    T = (jd - 2451545.0) / 365250.0
    L = 0.0
    B_ = 0.0
    for term in series:
        # unpack only the first three items; ignore any additional coefficients
        if len(term) < 3:
            continue
        A, B, C = term[0], term[1], term[2]
        # assume C multiplies the VSOP-like T; fallback to using T
        L += A * math.cos(B + C * T)
        B_ += A * math.sin(B + C * T)
    # approximate lunar distance in km and AU
    R_km = 384400
    R_au = R_km / 149597870.7

    # Treat L as ecliptic longitude, B_ as latitude (placeholder assumptions)
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
    return ra, dec, R_km, R_au
