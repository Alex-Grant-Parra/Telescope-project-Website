from utils import series_to_position, elp_to_position

class CelestialBody:
    def __init__(self, name, series):
        self.name = name
        self.series = series

    def position(self, jd):
        """Compute RA, Dec, distance. To be implemented in subclass."""
        raise NotImplementedError


class Planet(CelestialBody):
    def position(self, jd):
        ra, dec, r = series_to_position(self.series, jd)
        return ra, dec, r

class Moon(CelestialBody):
    def position(self, jd):
        ra, dec, r = elp_to_position(self.series, jd)
        return ra, dec, r
