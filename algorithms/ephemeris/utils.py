
import math
from algorithms.convert import convert
from algorithms.timeUtils import SpaceTime

AU_KM = 149597870.7


def _eval_triples(terms, tval):
    total = 0.0
    for term in terms:
        if len(term) < 3:
            continue
        A, B, C = term[0], term[1], term[2]
        total += A * math.cos(B + C * tval)
    return total


def _ecliptic_xyz_to_equatorial_xyz(x_ecl, y_ecl, z_ecl, cos_eps, sin_eps):
    y_eq = y_ecl * cos_eps - z_ecl * sin_eps
    z_eq = y_ecl * sin_eps + z_ecl * cos_eps
    return x_ecl, y_eq, z_eq


def _xyz_to_radec_distance(x, y, z):
    r = math.sqrt(x * x + y * y + z * z)
    if r == 0:
        return 0.0, 0.0, 0.0
    ra = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    dec = math.degrees(math.asin(max(-1.0, min(1.0, z / r))))
    return ra, dec, r


def _lbr_to_ecliptic_xyz(L, B_, R):
    cos_b = math.cos(B_)
    x_ecl = R * cos_b * math.cos(L)
    y_ecl = R * cos_b * math.sin(L)
    z_ecl = R * math.sin(B_)
    return x_ecl, y_ecl, z_ecl

# VSOP87 evaluation
def series_to_position(series, jd):
    # Evaluate VSOP87 series for given Julian Date; return ra_deg, dec_deg, r_au
    # Time variable for VSOP like series
    T = (jd - SpaceTime.J2000_JD) / 365250.0

    eps = SpaceTime.getMeanObliquityRad(jd)
    cos_eps = math.cos(eps)
    sin_eps = math.sin(eps)

    # Case A: X/Y/Z rectangular series already prepared
    if any(k in series for k in ("X", "Y", "Z")):
        X_ecl = _eval_triples(series.get("X", []), T)
        Y_ecl = _eval_triples(series.get("Y", []), T)
        Z_ecl = _eval_triples(series.get("Z", []), T)
        X_eq, Y_eq, Z_eq = _ecliptic_xyz_to_equatorial_xyz(X_ecl, Y_ecl, Z_ecl, cos_eps, sin_eps)
        ra, dec, r = _xyz_to_radec_distance(X_eq, Y_eq, Z_eq)
        return ra, dec, r

    # Evaluate as sums of A * cos(B + C*T)
    if any(k in series for k in ("L", "B", "R")):
        L = _eval_triples(series.get("L", []), T)
        B_ = _eval_triples(series.get("B", []), T)
        R = _eval_triples(series.get("R", []), T)
        X_ecl, Y_ecl, Z_ecl = _lbr_to_ecliptic_xyz(L, B_, R)
        X_eq, Y_eq, Z_eq = _ecliptic_xyz_to_equatorial_xyz(X_ecl, Y_ecl, Z_ecl, cos_eps, sin_eps)
        ra, dec, r = _xyz_to_radec_distance(X_eq, Y_eq, Z_eq)
        return ra, dec, r

    # Unknown series shape
    return None


def series_to_equatorial_xyz(series, jd):
    # Return equatorial rectangular (X,Y,Z) and distance r (AU) for a VSOP X/Y/Z series
    T = (jd - SpaceTime.J2000_JD) / 365250.0
    if not any(k in series for k in ("X", "Y", "Z")):
        return None
    eps = SpaceTime.getMeanObliquityRad(jd)
    cos_eps = math.cos(eps)
    sin_eps = math.sin(eps)
    X_ecl = _eval_triples(series.get("X", []), T)
    Y_ecl = _eval_triples(series.get("Y", []), T)
    Z_ecl = _eval_triples(series.get("Z", []), T)
    X_eq, Y_eq, Z_eq = _ecliptic_xyz_to_equatorial_xyz(X_ecl, Y_ecl, Z_ecl, cos_eps, sin_eps)
    _, _, r = _xyz_to_radec_distance(X_eq, Y_eq, Z_eq)
    return X_eq, Y_eq, Z_eq, r


def heliocentric_to_geocentric(object_xyz, earth_xyz):
    # Convert heliocentric equatorial Cartesian coordinates to geocentric RA/Dec and distance
    if not object_xyz or not earth_xyz:
        return None
    Ox, Oy, Oz, _ = object_xyz
    Ex, Ey, Ez, _ = earth_xyz
    Gx, Gy, Gz = Ox - Ex, Oy - Ey, Oz - Ez
    ra_deg, dec_deg, Gr = _xyz_to_radec_distance(Gx, Gy, Gz)
    # Distance in km (AU -> km)
    distance_km = Gr * AU_KM

    return {
        'ra_deg': ra_deg,
        'dec_deg': dec_deg,
        'distance_km': distance_km,
        'ra_hms': convert.DegreesToHMS(ra_deg),
        'dec_dms': convert.DegreesToDMS(dec_deg)
    }


def heliocentric_to_geocentric_for_body(body_xyz, earth_xyz):
    # Wrapper
    if not body_xyz or not earth_xyz:
        return None
    return heliocentric_to_geocentric(body_xyz, earth_xyz)

# ELP82b Moon evaluation 
def elp_to_position(series, jd):
    # Currently unused as not working
    T = (jd - SpaceTime.J2000_JD) / 365250.0
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
    eps = SpaceTime.getMeanObliquityRad(jd)
    cos_eps = math.cos(eps)
    sin_eps = math.sin(eps)
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
