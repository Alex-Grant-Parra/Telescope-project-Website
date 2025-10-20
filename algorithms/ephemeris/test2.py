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
jd = 2460963.28744

# 1) Moon RA/Dec (handle either 3- or 4-value return from elp_to_position)
if moon is None:
    print("Moon not available")
else:
    vals = utils.elp_to_position(moon.series, jd)   # returns ra, dec, ... (varies)
    # unpack defensively
    ra_moon = vals[0]
    dec_moon = vals[1]
    # optional distances if present:
    moon_rest = vals[2:]   # may be [R_km] or [R_km, R_au] or empty
    print("Moon (raw) RA (deg):", ra_moon, "Dec (deg):", dec_moon, "extra:", moon_rest)

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