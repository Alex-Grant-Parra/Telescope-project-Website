import os
import sys

# Ensure repository root is on sys.path so 'algorithms' package can be imported
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
	sys.path.insert(0, ROOT)

from algorithms.ephemeris.loader import load_all
from algorithms.convert import convert
from algorithms.ephemeris import utils

planets, moon = load_all()
<<<<<<< HEAD
jd = 2460963.28744
=======
jd = 2460963.92002
>>>>>>> e544fe34d27fec99d7f146c2676bd5b4b385d46a

# 1) Moon RA/Dec (handle either 3- or 4-value return from elp_to_position)
if moon is None:
    print("Moon not available")
else:
<<<<<<< HEAD
    vals = utils.elp_to_position(moon.series, jd)   # returns ra, dec, ... (varies)
    # unpack defensively
    ra_moon = vals[0]
    dec_moon = vals[1]
    # optional distances if present:
    moon_rest = vals[2:]   # may be [R_km] or [R_km, R_au] or empty
    print("Moon (raw) RA (deg):", ra_moon, "Dec (deg):", dec_moon, "extra:", moon_rest)
=======
    vals = utils.elp_to_position(moon.series, jd)
    moon_coords = [vals[0], vals[1]]  # [ra, dec] in degrees
    moon_extra = tuple(vals[2:])

    # Raw output (degrees + extra values)
    print(f"Moon (raw) RA (deg): {moon_coords[0]} Dec (deg): {moon_coords[1]} extra: {moon_extra}")

    # Helpers: degrees -> HMS (int) and degrees -> DMS (int) with rollover
    def deg_to_hms_int(ra_deg):
        hours = (ra_deg / 15.0) % 24.0
        h = int(hours)
        min_f = (hours - h) * 60.0
        m = int(min_f)
        sec = round((min_f - m) * 60.0)
        if sec == 60:
            sec = 0
            m += 1
        if m == 60:
            m = 0
            h = (h + 1) % 24
        return [h, m, int(sec)]

    def deg_to_dms_int(dec_deg):
        sign = -1 if dec_deg < 0 else 1
        a = abs(dec_deg)
        d = int(a)
        min_f = (a - d) * 60.0
        m = int(min_f)
        sec = round((min_f - m) * 60.0)
        if sec == 60:
            sec = 0
            m += 1
        if m == 60:
            m = 0
            d += 1
        d *= sign
        return [d, m, int(sec)]

    ra_hms = deg_to_hms_int(moon_coords[0])
    dec_dms = deg_to_dms_int(moon_coords[1])

    # HMS/DMS output to match Sun/planet formatting
    print("Moon RA (H M S):", ra_hms, "Dec (D M S):", dec_dms)

    # Zero-padded output similar to examples
    moon_dist_km = moon_extra[0] if len(moon_extra) > 0 else None
    sign_str = '-' if dec_dms[0] < 0 else ''
    abs_deg = abs(dec_dms[0])
    print(
        f"  Moon (geocentric) RA_hms=[{ra_hms[0]:02d}, {ra_hms[1]:02d}, {ra_hms[2]:02d}] "
        f"Dec_dms=[{sign_str}{abs_deg:02d}, {dec_dms[1]:02d}, {dec_dms[2]:02d}] "
        + (f"Dist_km={moon_dist_km:,.1f}" if moon_dist_km is not None else "")
    )
>>>>>>> e544fe34d27fec99d7f146c2676bd5b4b385d46a

# 2) Sun RA/Dec:
# Approach: the Sun's heliocentric vector is (0,0,0); geocentric Sun vector = -Earth_heliocentric
earth = planets.get("Earth")
if earth is None:
    print("Earth data not available")
else:
    earth_xyz = earth.cartesian(jd)   # (X,Y,Z,r) in AU
    # Use the helper: object at origin -> heliocentric (0,0,0,0)
    sun_res = utils.heliocentric_to_geocentric((0.0, 0.0, 0.0, 0.0), earth_xyz)
    if sun_res:
        print("Sun RA (H M S):", sun_res['ra_hms'], "Dec (D M S):", sun_res['dec_dms'],
              "Distance (km):", sun_res['distance_km'])
    else:
        print("Could not compute Sun position")

# 3) Example: all major planets (heliocentric RA/Dec + geocentric RA/Dec)
major = ["Mercury","Venus","Earth","Mars","Jupiter","Saturn","Uranus","Neptune"]
for name in major:
    b = planets.get(name)
    if not b:
        print(f"{name}: not available")
        continue
    # heliocentric position (your Planet.position returns ra_deg, dec_deg, r)
    ra_deg, dec_deg, r_au = b.position(jd)
    print(f"{name} (heliocentric) RAdeg={ra_deg:.6f} Decdeg={dec_deg:.6f} r={r_au:.6f} AU")
    if name != "Earth":
        res = utils.heliocentric_to_geocentric(b.cartesian(jd), earth.cartesian(jd))
        if res:
            print(f"  {name} (geocentric) RA_hms={res['ra_hms']} Dec_dms={res['dec_dms']} Dist_km={res['distance_km']:,.1f}")