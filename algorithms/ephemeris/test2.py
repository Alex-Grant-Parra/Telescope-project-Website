import os
import sys

# Ensure repository root is on sys.path so 'algorithms' package can be imported
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
	sys.path.insert(0, ROOT)

from algorithms.ephemeris.loader import load_all
from algorithms.convert import convert
from algorithms.ephemeris import utils

planets, _ = load_all()
major = ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]
jd = 2460963.28744

for name in major:
	body = planets.get(name)
	if not body:
		print(f"{name}: not available")
		continue
	lat, lon, r = body.position(jd)
	ra_hms, dec_hms = convert.EclipticToEquatorial(utils.d2dms(lat), utils.d2dms(lon), 23.4392911)
	print(f"{name} (Heliocentric) lat, long: {lat:.6f}, {lon:.6f}, r={r:.6f} AU")
	print(f"{name} (Heliocentric) RA: {ra_hms} Dec: {dec_hms}")
	if name != "Earth":
		res = utils.heliocentric_to_geocentric(body.cartesian(jd), planets["Earth"].cartesian(jd))
		if res:
			rh, rd = res['ra_hms'], res['dec_dms']
			print(f"{name} (Geocentric) RA: {rh[0]}h {rh[1]}m {rh[2]}s  Dec: {rd[0]}° {rd[1]}' {rd[2]}\"  Distance: {res['distance_km']:,.1f} km")
		else:
			print(f"{name} (Geocentric): cartesian data unavailable")
	print()