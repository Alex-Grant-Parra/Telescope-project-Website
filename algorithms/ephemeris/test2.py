import os
import sys

# Ensure repository root is on sys.path so 'algorithms' package can be imported
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
	sys.path.insert(0, ROOT)

from algorithms.ephemeris.loader import load_all
from algorithms.convert import convert


def decimal_deg_to_dms(deg_val):
	"""Convert decimal degrees to [deg, minutes, seconds] triple used by convert.HrMinSecToDegrees."""
	sign = -1 if deg_val < 0 else 1
	v = abs(deg_val)
	d = int(v)
	m = int((v - d) * 60)
	s = (v - d - m/60) * 3600
	d = d * sign
	return [d, m, round(s, 2)]


planets, moon = load_all()
mars = planets.get("Mars")
earth = planets.get("Earth")
if mars is None or earth is None:
	raise SystemExit("Required planets not found (need Mars and Earth)")

# Example Julian date
jd = 2460963.28744
# Get celestial coordinates from planet.position
# The position function returns (lat_or_ra, long_or_dec, r)
ecl_lat, ecl_long, r = mars.position(jd)

# Convert decimal degrees to DMS triple expected by EclipticToEquatorial
long_dms = decimal_deg_to_dms(ecl_lat)
lat_dms = decimal_deg_to_dms(ecl_long)

# Use mean obliquity of the ecliptic (degrees)
axial_tilt = 23.4392911

ra_hms, dec_hms = convert.EclipticToEquatorial(lat_dms, long_dms, axial_tilt)

print(f"(Heliocentric) Mars ecliptic lat, long (deg): {ecl_lat:.6f}, {ecl_long:.6f}, r={r:.6f} AU")
print(f"(Heliocentric) Mars RA (H M S): {ra_hms}, Dec (D M S): {dec_hms}")

# Geocentric vector: Mars - Earth
from math import atan2, sqrt, degrees, asin
mars_xyz = mars.cartesian(jd)
earth_xyz = earth.cartesian(jd)
if mars_xyz and earth_xyz:
	Mx, My, Mz, Mr = mars_xyz
	Ex, Ey, Ez, Er = earth_xyz
	Gx, Gy, Gz = Mx-Ex, My-Ey, Mz-Ez
	Gr = sqrt(Gx*Gx + Gy*Gy + Gz*Gz)
	gra = (degrees(atan2(Gy, Gx)) + 360) % 360
	gdec = degrees(asin(Gz/Gr)) if Gr != 0 else 0.0
	# Convert gra (deg) to H M S
	g_hours = gra / 15.0
	g_h = int(g_hours)
	g_m_float = (g_hours - g_h)*60
	g_m = int(g_m_float)
	g_s = round((g_m_float - g_m)*60,2)
	# Convert declination degrees to D M S
	dec_sign = -1 if gdec < 0 else 1
	adec = abs(gdec)
	d_d = int(adec)
	d_m_float = (adec - d_d)*60
	d_m = int(d_m_float)
	d_s = round((d_m_float - d_m)*60,2)
	if dec_sign == -1:
		d_d *= -1
	print(f"(Geocentric) Mars RA: {g_h}h {g_m}m {g_s}s  Dec: {d_d}° {d_m}' {d_s}\"  Distance: {Gr*149597870.7:,.1f} km")
else:
	print("Geocentric cartesian data unavailable for Mars/Earth.")