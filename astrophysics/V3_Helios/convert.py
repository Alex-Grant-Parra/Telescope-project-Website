import calendar
from datetime import datetime, timezone
from time import struct_time
import sys

import numpy as np

try:
    from .chebyshev import evaluateAt, evaluateAtBatch, getEpochUTC
except ImportError:
    from chebyshev import evaluateAt, evaluateAtBatch, getEpochUTC


# London, UK (city center; WGS84 geodetic)
LONDON_LAT_DEG = 51.5074
LONDON_LON_DEG = -0.1278
LONDON_ALT_M = 35.0


def _ecl_to_equ(vec):
    eps = np.deg2rad(23.439291111)
    rot = np.array(
        [[1.0, 0.0, 0.0], [0.0, np.cos(eps), -np.sin(eps)], [0.0, np.sin(eps), np.cos(eps)]]
    )
    return vec @ rot.T


def _cart_to_radec(vec):
    x, y, z = vec
    radius = np.linalg.norm(vec)
    ra_deg = np.degrees(np.arctan2(y, x) % (2.0 * np.pi))
    dec_deg = np.degrees(np.arcsin(np.clip(z / radius, -1.0, 1.0)))
    return ra_deg, dec_deg, radius


def _julian_date(dt_utc):
    return dt_utc.timestamp() / 86400.0 + 2440587.5


def _gmst_radians(dt_utc):
    jd = _julian_date(dt_utc)
    t = (jd - 2451545.0) / 36525.0
    gmst_deg = (
        280.46061837
        + 360.98564736629 * (jd - 2451545.0)
        + 0.000387933 * t * t
        - (t * t * t) / 38710000.0
    )
    return np.deg2rad(gmst_deg % 360.0)


def _observer_eci_m(dt_utc, lat_deg, lon_deg, alt_m=0.0):
    # WGS84 geodetic observer position converted to ECI using GMST.
    lat = np.deg2rad(float(lat_deg))
    lon = np.deg2rad(float(lon_deg))
    alt = float(alt_m)

    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)

    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    n = a / np.sqrt(1.0 - e2 * sin_lat * sin_lat)

    x_ecef = (n + alt) * cos_lat * np.cos(lon)
    y_ecef = (n + alt) * cos_lat * np.sin(lon)
    z_ecef = ((1.0 - e2) * n + alt) * sin_lat

    theta = _gmst_radians(dt_utc)
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    x_eci = cos_t * x_ecef - sin_t * y_ecef
    y_eci = sin_t * x_ecef + cos_t * y_ecef

    return np.array([x_eci, y_eci, z_ecef], dtype=np.float64)


def _deg_to_hms(ra_deg):
    total_hours = ra_deg / 15.0
    hours = int(total_hours) % 24
    minutes = int((total_hours - hours) * 60.0)
    seconds = (total_hours - hours - minutes / 60.0) * 3600.0
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


def _deg_to_dms(dec_deg):
    sign = "+" if dec_deg >= 0 else "-"
    abs_deg = abs(dec_deg)
    degrees = int(abs_deg)
    minutes = int((abs_deg - degrees) * 60.0)
    seconds = (abs_deg - degrees - minutes / 60.0) * 3600.0
    return f"{sign}{degrees:02d}:{minutes:02d}:{seconds:05.2f}"


def _normalize_time_input(time_input):
    if time_input is None:
        return datetime.fromtimestamp(sys.modules["time"].time(), tz=timezone.utc)

    if isinstance(time_input, datetime):
        return time_input if time_input.tzinfo is not None else time_input.replace(tzinfo=timezone.utc)

    if isinstance(time_input, struct_time):
        # struct_time values passed to this module are expected to be UTC
        # (for example from time.gmtime()), so use timegm rather than mktime.
        return datetime.fromtimestamp(calendar.timegm(time_input), tz=timezone.utc)

    if isinstance(time_input, (int, float)):
        # Numeric input is interpreted as Unix epoch seconds (time.time()).
        return datetime.fromtimestamp(float(time_input), tz=timezone.utc)

    text = str(time_input)
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def get_radec_at_time(time_input=None, observer_lat_deg=None, observer_lon_deg=None, observer_alt_m=0.0):
    """Return RA/DEC for every planet at a requested time.

    Accepts:
    - None: uses the current time from the time library
    - time.time() epoch seconds
    - datetime
    - time.struct_time
    - ISO8601 string

        Optional observer parameters:
        - observer_lat_deg / observer_lon_deg: when both are provided, return
            topocentric RA/Dec for that geodetic location.
        - observer_alt_m: observer height in meters (default 0.0).

    Requires cheb_table.npz to exist. Build it once with:
        python astrophysics/V3_Helios/chebyshev.py
    """
    req_time = _normalize_time_input(time_input)
    epoch = getEpochUTC()
    t_sec = (req_time - epoch).total_seconds()

    positions = evaluateAt(t_sec)
    names = list(positions.keys())

    observer = "earth" if "earth" in names else names[0]
    observer_pos = positions[observer]
    observer_offset = None
    if observer_lat_deg is not None and observer_lon_deg is not None:
        observer_offset = _observer_eci_m(req_time, observer_lat_deg, observer_lon_deg, observer_alt_m)

    output = {}
    for body, pos in positions.items():
        if body == observer:
            continue

        vector = pos - observer_pos
        vector_equ = _ecl_to_equ(vector)
        if observer_offset is not None:
            # observer_offset is in equatorial J2000 (ECI), so apply it in
            # the same frame as the target vector.
            vector_equ = vector_equ - observer_offset
        ra_deg, dec_deg, distance_m = _cart_to_radec(vector_equ)
        output[body] = {
            "ra_hms": _deg_to_hms(ra_deg),
            "dec_dms": _deg_to_dms(dec_deg),
            "ra_deg": ra_deg,
            "dec_deg": dec_deg,
            "dist_m": distance_m,
        }

    return output


def get_radec_at_times(time_inputs, observer_lat_deg=None, observer_lon_deg=None, observer_alt_m=0.0):
    """Return RA/Dec for each body across multiple requested times.

    Parameters
    ----------
    time_inputs : sequence
        Sequence of accepted time inputs for get_radec_at_time.

    Returns
    -------
    list[dict]
        A list with one output dict per requested time.
    """
    req_times = [_normalize_time_input(value) for value in time_inputs]
    epoch = getEpochUTC()
    t_seconds = np.array([(value - epoch).total_seconds() for value in req_times], dtype=np.float64)
    positions_by_body = evaluateAtBatch(t_seconds)
    names = list(positions_by_body.keys())
    observer = "earth" if "earth" in names else names[0]

    observer_offsets = None
    if observer_lat_deg is not None and observer_lon_deg is not None:
        observer_offsets = np.array(
            [_observer_eci_m(value, observer_lat_deg, observer_lon_deg, observer_alt_m) for value in req_times],
            dtype=np.float64,
        )

    output_per_time = []
    for idx in range(len(req_times)):
        observer_pos = positions_by_body[observer][idx]
        row = {}
        for body, pos_series in positions_by_body.items():
            if body == observer:
                continue

            vector = pos_series[idx] - observer_pos
            vector_equ = _ecl_to_equ(vector)
            if observer_offsets is not None:
                vector_equ = vector_equ - observer_offsets[idx]

            ra_deg, dec_deg, distance_m = _cart_to_radec(vector_equ)
            row[body] = {
                "ra_hms": _deg_to_hms(ra_deg),
                "dec_dms": _deg_to_dms(dec_deg),
                "ra_deg": ra_deg,
                "dec_deg": dec_deg,
                "dist_m": distance_m,
            }
        output_per_time.append(row)

    return output_per_time


if __name__ == "__main__":
    from time import gmtime

    res = get_radec_at_time(
        gmtime(),
        observer_lat_deg=LONDON_LAT_DEG,
        observer_lon_deg=LONDON_LON_DEG,
        observer_alt_m=LONDON_ALT_M,
    )
    print(f"{'Body':<10}  {'RA':>13}  {'Dec':>14}  {'Dist':>16}")
    print("-" * 60)
    for body, data in res.items():
        print(f"{body:<10}  {data['ra_hms']:>13}  {data['dec_dms']:>14}  {data['dist_m']/1e9:>13.6g} Mm")