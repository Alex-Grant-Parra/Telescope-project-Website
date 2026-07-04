from pathlib import Path
import json
from datetime import datetime, timezone, timedelta
from time import struct_time
import sys

import numpy as np


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


def _load_epoch():
    data = json.loads((Path(__file__).parent / "initial_conditions.json").read_text())
    epoch = data["epoch_utc"]
    if epoch.endswith("Z"):
        epoch = epoch.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(epoch)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _normalize_time_input(time_input):
    if time_input is None:
        return datetime.fromtimestamp(sys.modules["time"].time(), tz=timezone.utc)

    if isinstance(time_input, datetime):
        return time_input if time_input.tzinfo is not None else time_input.replace(tzinfo=timezone.utc)

    if isinstance(time_input, struct_time):
        return datetime.fromtimestamp(sys.modules["time"].mktime(time_input), tz=timezone.utc)

    if isinstance(time_input, (int, float)):
        return _load_epoch() + timedelta(seconds=float(time_input))

    text = str(time_input)
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def get_radec_at_time(time_input=None):
    """Return RA/DEC for every planet at a requested time.

    Accepts:
    - None: uses the current time from the time library
    - time.time() epoch seconds
    - datetime
    - time.struct_time
    - ISO8601 string

    Requires cheb_table.npz to exist. Build it once with:
        python astrophysics/V3_Helios/chebyshev.py
    """
    req_time = _normalize_time_input(time_input)
    epoch = _load_epoch()
    t_sec = (req_time - epoch).total_seconds()

    project_root = str(Path(__file__).resolve().parents[2])  # …/Server
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    try:
        from astrophysics.V3_Helios.chebyshev import evaluateAt
    except ImportError:
        from chebyshev import evaluateAt

    positions = evaluateAt(t_sec)
    names = list(positions.keys())

    observer = "earth_moon" if "earth_moon" in names else names[0]
    observer_pos = positions[observer]

    output = {}
    for body, pos in positions.items():
        if body == observer:
            continue

        vector = pos - observer_pos
        ra_deg, dec_deg, distance_m = _cart_to_radec(_ecl_to_equ(vector))
        output[body] = {
            "ra_hms": _deg_to_hms(ra_deg),
            "dec_dms": _deg_to_dms(dec_deg),
            "ra_deg": ra_deg,
            "dec_deg": dec_deg,
            "dist_m": distance_m,
        }

    return output


if __name__ == "__main__":
    from time import gmtime

    res = get_radec_at_time(gmtime())
    print(res)