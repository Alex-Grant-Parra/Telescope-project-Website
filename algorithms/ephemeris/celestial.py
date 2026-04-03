from .utils import series_to_position, elp_to_position, series_to_equatorial_xyz

class CelestialBody:
    def __init__(self, name, series):
        self.name = name
        self.series = series

    def position(self, jd):
        # Compute RA, Dec, distance
        raise NotImplementedError

class Planet(CelestialBody):
    def position(self, jd):
        ra, dec, r = series_to_position(self.series, jd)
        return ra, dec, r
    def cartesian(self, jd):
        xyz = series_to_equatorial_xyz(self.series, jd)
        return xyz  # (X,Y,Z,r) or None

class Moon(CelestialBody):
    def position(self, jd):
        ra, dec, r = elp_to_position(self.series, jd)
        return ra, dec, r
