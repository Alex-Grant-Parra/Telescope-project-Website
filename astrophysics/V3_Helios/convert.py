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

AU_M = 149597870700.0


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


def _angle_deg(vec_a, vec_b):
    norm_a = float(np.linalg.norm(vec_a))
    norm_b = float(np.linalg.norm(vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    cosine = np.dot(vec_a, vec_b) / (norm_a * norm_b)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def _phase_angle_deg(body_pos, sun_pos, earth_pos):
    # Angle Sun-Body-Earth as measured at the body.
    body_to_sun = sun_pos - body_pos
    body_to_earth = earth_pos - body_pos
    return _angle_deg(body_to_sun, body_to_earth)


def _planet_visual_magnitude(body, r_au, delta_au, phase_deg):
    if r_au <= 0.0 or delta_au <= 0.0:
        return None

    common_term = 5.0 * np.log10(r_au * delta_au)
    phase = float(phase_deg)

    if body == "mercury":
        mag = -0.42 + 0.0380 * phase - 0.000273 * phase * phase + 0.000002 * phase**3
        return float(mag + common_term)
    if body == "venus":
        mag = -4.40 + 0.0009 * phase + 0.000239 * phase * phase - 0.00000065 * phase**3
        return float(mag + common_term)
    if body == "mars":
        mag = -1.52 + 0.016 * phase
        return float(mag + common_term)
    if body == "jupiter":
        mag = -9.395 + 0.005 * phase
        return float(mag + common_term)
    if body == "saturn":
        # Ring brightness is not modeled; this is a disk-only approximation.
        mag = -8.88 + 0.044 * phase
        return float(mag + common_term)
    if body == "uranus":
        mag = -7.19 + 0.001 * phase
        return float(mag + common_term)
    if body == "neptune":
        mag = -6.87
        return float(mag + common_term)

    return None


def _moon_visual_magnitude(earth_moon_distance_m, phase_angle_deg):
    distance_km = float(earth_moon_distance_m) / 1000.0
    if distance_km <= 0.0:
        return None

    alpha = float(phase_angle_deg)
    base_mag = -12.73 + 0.026 * alpha + 4.0e-9 * (alpha**4)
    distance_term = 5.0 * np.log10(distance_km / 384400.0)
    return float(base_mag + distance_term)


def _moon_phase_from_geometry(sun_pos, earth_pos, moon_pos):
    sun_geo = sun_pos - earth_pos
    moon_geo = moon_pos - earth_pos

    elongation_deg = _angle_deg(sun_geo, moon_geo)
    illum_frac = float((1.0 - np.cos(np.deg2rad(elongation_deg))) / 2.0)
    waxing = np.cross(sun_geo, moon_geo)[2] > 0.0

    if elongation_deg < 22.5:
        phase_name = "New Moon"
    elif elongation_deg < 67.5:
        phase_name = "Waxing Crescent" if waxing else "Waning Crescent"
    elif elongation_deg < 112.5:
        phase_name = "First Quarter" if waxing else "Last Quarter"
    elif elongation_deg < 157.5:
        phase_name = "Waxing Gibbous" if waxing else "Waning Gibbous"
    else:
        phase_name = "Full Moon"

    return {
        "moon_phase_name": phase_name,
        "moon_illumination_fraction": illum_frac,
        "moon_elongation_deg": float(elongation_deg),
    }


def _visual_magnitude_payload(body, positions, observer):
    if observer != "earth" or "sun" not in positions or "earth" not in positions:
        return {}

    sun_pos = positions["sun"]
    earth_pos = positions["earth"]
    body_pos = positions[body]

    if body == "moon":
        phase_deg = _phase_angle_deg(body_pos, sun_pos, earth_pos)
        dist_m = float(np.linalg.norm(body_pos - earth_pos))
        payload = {
            "visual_mag": _moon_visual_magnitude(dist_m, phase_deg),
            "phase_angle_deg": float(phase_deg),
        }
        payload.update(_moon_phase_from_geometry(sun_pos, earth_pos, body_pos))
        return payload

    if body in {"mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune"}:
        phase_deg = _phase_angle_deg(body_pos, sun_pos, earth_pos)
        r_au = float(np.linalg.norm(body_pos - sun_pos) / AU_M)
        delta_au = float(np.linalg.norm(body_pos - earth_pos) / AU_M)
        return {
            "visual_mag": _planet_visual_magnitude(body, r_au, delta_au, phase_deg),
            "phase_angle_deg": float(phase_deg),
        }

    return {}


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
        output[body].update(_visual_magnitude_payload(body, positions, observer))

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
        positions_at_t = {name: series[idx] for name, series in positions_by_body.items()}
        observer_pos = positions_at_t[observer]
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
            row[body].update(_visual_magnitude_payload(body, positions_at_t, observer))
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
    print(f"{'Body':<10}  {'RA':>13}  {'Dec':>14}  {'Dist':>16}  {'Vmag':>7}")
    print("-" * 72)
    for body, data in res.items():
        visual_mag = data.get("visual_mag")
        vmag_text = f"{visual_mag:7.3f}" if visual_mag is not None else f"{'-':>7}"
        print(
            f"{body:<10}  {data['ra_hms']:>13}  {data['dec_dms']:>14}  "
            f"{data['dist_m']/1e9:>13.6g} Mm  {vmag_text}"
        )

    moon = res.get("moon")
    if moon is not None:
        illum_pct = 100.0 * float(moon.get("moon_illumination_fraction", 0.0))
        phase_name = moon.get("moon_phase_name", "Unknown")
        print("\nMoon Phase")
        print("-" * 20)
        print(f"Illumination: {illum_pct:.2f}%")
        print(f"Phase: {phase_name}")