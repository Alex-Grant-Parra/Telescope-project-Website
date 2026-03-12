from algorithms.ephemeris.loader import load_all
from algorithms.timeUtils import SpaceTime
from algorithms.ephemeris import utils as ephem_utils

MAJOR = ["Mercury","Venus","Earth","Mars","Jupiter","Saturn","Uranus","Neptune"]


def get_positions(year, month, day, hour: int = 0, minute: int = 0, second: float = 0.0):
    """Return a mapping of celestial bodies to their positions.

    Each value is a dict with keys:
      - ra_deg: Right ascension in degrees
      - dec_deg: Declination in degrees
      - distance_km: optional distance in km (when available)
    """
    planets, moon = load_all()
    jd = SpaceTime.getJD(year, month, day, hour, minute, second)

    out = {}

    # Moon
    if moon is not None:
        vals = ephem_utils.elp_to_position(moon.series, jd)
        if vals:
            ra_deg = vals[0]
            dec_deg = vals[1]
            dist_km = vals[2] if len(vals) > 2 else None
            out['moon'] = {'ra_deg': ra_deg, 'dec_deg': dec_deg, 'distance_km': dist_km}

    # Sun (geocentric) -- Sun heliocentric vector is origin
    earth = planets.get('Earth')
    if earth is not None:
        try:
            earth_xyz = earth.cartesian(jd)
            sun_res = ephem_utils.heliocentric_to_geocentric((0.0, 0.0, 0.0, 0.0), earth_xyz)
            if sun_res:
                out['sun'] = {
                    'ra_deg': sun_res['ra_deg'],
                    'dec_deg': sun_res['dec_deg'],
                    'distance_km': sun_res.get('distance_km')
                }
        except Exception:
            pass

    # Major planets
    for name in MAJOR:
        b = planets.get(name)
        if not b:
            continue
        # Use planet.position(jd) if available (heliocentric RA/Dec)
        try:
            # Many Planet implementations provide .position(jd) -> (ra_deg, dec_deg, r_au)
            pos = None
            try:
                pos = b.position(jd)
            except Exception:
                pos = None
            # Prefer geocentric conversion for display (except Earth)
            if name != 'Earth':
                try:
                    geo = ephem_utils.heliocentric_to_geocentric(b.cartesian(jd), earth.cartesian(jd))
                    if geo:
                        ra_deg = geo['ra_deg']
                        dec_deg = geo['dec_deg']
                        dist_km = geo.get('distance_km')
                        out[name.lower()] = {'ra_deg': ra_deg, 'dec_deg': dec_deg, 'distance_km': dist_km}
                        continue
                except Exception:
                    # fallback to heliocentric pos
                    pass
            # fallback: use heliocentric values if geocentric not computed
            if pos:
                ra_deg, dec_deg = pos[0], pos[1]
                out[name.lower()] = {'ra_deg': ra_deg, 'dec_deg': dec_deg}
        except Exception:
            continue

    return out
