from math import sin as math_sin, cos as math_cos, tan as math_tan, \
    asin as math_asin, acos as math_acos, atan as math_atan, atan2 as math_atan2, radians, degrees, sqrt, pi, log10
from .timeUtils import SpaceTime
from .convert import convert

from utility.timer_utils import timer
from .ephemeris.ephemeris import get_positions as ephem_get_positions

# Lazy imports to avoid circular import issues
_app = None
_db = None
_PlanetsTable = None

def _get_app():
    global _app
    if _app is None:
        from Server import app as _temp_app
        _app = _temp_app
    return _app

def _get_db():
    global _db
    if _db is None:
        from app.db import db as _temp_db
        _db = _temp_db
    return _db

def _get_PlanetsTable():
    global _PlanetsTable
    if _PlanetsTable is None:
        from models.tables import PlanetsTable as _temp_table
        _PlanetsTable = _temp_table
    return _PlanetsTable

# Overriding trig functions to use degrees
sin = lambda x: math_sin(radians(x))
cos = lambda x: math_cos(radians(x))
tan = lambda x: math_tan(radians(x))

# Overriding inverse trig functions to return degrees
asin = lambda x: degrees(math_asin(x))
acos = lambda x: degrees(math_acos(x))
atan = lambda x: degrees(math_atan(x))
atan2 = lambda y, x: degrees(math_atan2(y, x))

class CelestialObject:

    def __init__(self, **kwargs):

        # Primary keplarian orbital parameters
        self.a = kwargs.get("SemiMajorAxis") # Semi-Major axis
        self.e = kwargs.get("Eccentricity") # Eccentricity
        self.i = kwargs.get("Inclination") # Inclination
        self.N = kwargs.get("AscNodeLong") # Longitude of ascending node
        self.w = kwargs.get("ArgPeri") # Arugument of periapsis
        self.M = kwargs.get("MeanAnomaly") # Mean anomaly

        self.T = SpaceTime.J2000_JD # Time at perihelion, epoch, currently julian date

        self.q = self.a * (1 - self.e) # Customary to give perihelion distance instead of a for hyperbolic orbits

        # Misc parameters
        self.l = kwargs.get("LongitudeAtEpoch") # Longitude at epoch, data is from Jan 1st 1990 for this epoch
        self.m = 8 # Mass of object
        self.V_mag = kwargs.get("V-Mag")
        

        # Secondary keplarian orbital parameters
        self.W = self.N + self.w # Longitude of periapsis
        self.q = self.a * (1 - self.e) # Perihelion distance
        self.Q = self.a * (1 + self.e) # Apehelion distance
        self.P = self.a**1.5# Orbital period in tropical years
        self.n = 360 / self.P # Daily motion
        self.t = self.T # Epoch
        # self.M = (self.t - self.T) * 360 / self.P # Mean anomaly
        self.L = self.M + self.w + self.N # Mean longitude

        self.E = solveKepler(self.M, self.e) # Eccentric anomaly
        self.v = None # True anomaly
        self.r = None # Heliocentric distance

def solveKepler(M_deg, e):
    # Solve Kepler's equation M = E - e*sin(E) for E (eccentric anomaly).
    # Input M in degrees, e dimensionless, returns E in degrees.

    import math
    if e < 0 or e >= 1:
        raise ValueError("Eccentricity must be in [0, 1)")
    # Convert to radians
    M = math.radians(M_deg % 360)
    # Initial guess
    E = M if e < 0.8 else math.pi
    tol = 1e-12
    for _ in range(50):
        f = E - e * math.sin(E) - M
        fp = 1 - e * math.cos(E)
        dE = -f / fp
        E += dE
        if abs(dE) < tol:
            break
    return math.degrees(E % (2*math.pi))
    
def getPlanetsData():
    app = _get_app()
    db = _get_db()
    PlanetsTable = _get_PlanetsTable()
    
    try:
        with app.app_context():
            planets = db.session.query(PlanetsTable).all()
            planets_data = {
                planet.Name.lower(): {column.name: getattr(planet, column.name, None) for column in planet.__table__.columns}
                for planet in planets
            }
            return planets_data
    except Exception as e:
        # Return empty dict if database access fails
        print(f"Warning: Could not load planets data: {e}")
        return {}

# Lazy initialization of data and planets to avoid circular imports
_initialized = False
data = {}
planets = {}

def _init_planets():
    global _initialized, data, planets
    if not _initialized:
        try:
            data = getPlanetsData()
            planets = {}
            for key, value in data.items():
                planets[key] = CelestialObject(**value)
            _initialized = True
        except Exception as e:
            print(f"Warning: Could not initialize planets: {e}")
            _initialized = True

def _ensure_planets_initialized():
    """Ensure planets data is initialized before use"""
    if not _initialized:
        _init_planets()

def findAxialTilt(julianDate):
    return SpaceTime.getMeanObliquityDeg(julianDate)

def findPlanet(year, month, day, planetChoice, hour: int = 0, minute: int = 0, second: float = 0.0):
    _ensure_planets_initialized()

    # Constants for J2000
    EarthPeriod = 1.00004
    EarthLongAtEpoch = 100.46435
    EarthLongOfPeri = 102.94719
    EarthEccentricity = 0.016713
    EarthSemiMajorAxis = 1

    currentJD = SpaceTime.getJD(year, month, day, hour, minute, second)
    J1990JD = 2447892.5
    JDdifference = currentJD - J1990JD + 1

    Np = (360/365.242191 * JDdifference/planets.get(planetChoice).P)%360
    Mp = Np + planets.get(planetChoice).l - planets.get(planetChoice).W
    l = (Np + 360/pi * planets.get(planetChoice).e * sin(Mp) + planets.get(planetChoice).l)%360
    vp = l - planets.get(planetChoice).W
    r = (planets.get(planetChoice).a * (1 - planets.get(planetChoice).e ** 2)) / (1 + planets.get(planetChoice).e * cos(vp))

    Ne = (360/365.242191 * JDdifference/EarthPeriod)%360
    Me = Ne + EarthLongAtEpoch - EarthLongOfPeri
    L = (Ne + 360/pi * EarthEccentricity * sin(Me) + EarthLongAtEpoch)%360
    ve = L - EarthLongOfPeri
    R = (EarthSemiMajorAxis * (1 - EarthEccentricity ** 2)) / (1 + EarthEccentricity * cos(ve))
    
    # Merged

    Psi = asin(sin(l - planets.get(planetChoice).N) * sin(planets.get(planetChoice).i))
    y = sin(l - planets.get(planetChoice).N) * cos(planets.get(planetChoice).i)
    x = cos(l - planets.get(planetChoice).N)
    lPrime = atan2(y, x) + planets.get(planetChoice).N
    rPrime = r * cos(Psi)
    A = atan((rPrime * sin(L - lPrime)) / (R - rPrime * cos(L - lPrime)))

    if planetChoice == "mercury" or planetChoice == "venus":
        # ecliptic lat and long for inner planets
        EclipLong = (180 + L + A)%360
        EclipLat = atan((rPrime * tan(Psi) * sin(EclipLong - lPrime)) / (R * sin(lPrime - L)))

    else:
        # ecliptic lat and long for outer planets
        EclipLong = (atan((R * sin(lPrime - L)) / (rPrime - R * cos (lPrime - L))) + lPrime)%360
        EclipLat = atan((rPrime * tan(Psi) * sin (EclipLong - lPrime)) / (R * sin(lPrime - L)))

    hmsLong = convert.DecimalToHrMinSec(EclipLat)
    hmsLat = convert.DecimalToHrMinSec(EclipLong)

    result = convert.EclipticToEquatorial(hmsLong, hmsLat, findAxialTilt(currentJD))

    return result
    
def findSun(year, month, day, usedForMoon=False, hour: int = 0, minute: int = 0, second: float = 0.0):

    LR_julianDate = SpaceTime.getJD(year, month, day, hour, minute, second)

    GD_SUNDATA = {
    "Ecliptic longitude (epoch)": 279.403303,
    "Ecliptic longitude (perigee)":282.768422,
    "Eccentricity":0.016713,
    "Semi-major axis":1.495985*10**8,
    "Angular diameter": 0.533128
    }
    
    LR_e = GD_SUNDATA.get("Eccentricity")
    LR_daysBetween = LR_julianDate - SpaceTime.getJD(1990, 1, 0, 0, 0, 0.0)
    LR_N = ((360/365.242191)*LR_daysBetween)%360
    # Mean anomaly in degrees
    LR_M = LR_N + GD_SUNDATA.get("Ecliptic longitude (epoch)") - GD_SUNDATA.get("Ecliptic longitude (perigee)")
    # Solve kepler's equation for eccentric anomaly E
    LR_E = solveKepler(LR_M, GD_SUNDATA.get("Eccentricity"))
    # True anomaly atan returns degrees due to overrides
    LR_V = 2 * atan(((1 + LR_e) / (1 - LR_e))**0.5 * tan(LR_E / 2))
    LR_EclLong = (LR_V + GD_SUNDATA.get("Ecliptic longitude (perigee)"))%360 
    if usedForMoon == False:
        return convert.EclipticToEquatorial(convert.DecimalToHrMinSec(0), convert.DecimalToHrMinSec(LR_EclLong), findAxialTilt(LR_julianDate))
    else:
        return (LR_M, LR_EclLong)



def findMoon(year, month, day, hour: int = 0, minute: int = 0, second: float = 0.0):

    GD_MOONDATA = {
    "Ecliptic mean longitude": 318.351648,
    "Ecliptic longitude (perigee)": 36.340410,
    "Ecliptic longitude node (epoch)": 318.510107,
    "Inclination": 5.145396,
    "Eccentricity": 0.054900,
    "Semi-major axis": 3.84401*10**5,
    }

    currentJD = SpaceTime.getJD(year, month, day, hour, minute, second)
    D = currentJD - SpaceTime.getJD(1990, 1, 0) 

    sunLocationData = findSun(year, month, day, usedForMoon=True, hour=hour, minute=minute, second=second)
    M = sunLocationData[0]
    LongSun = sunLocationData[1]
    
    l = (13.1763966 * D + GD_MOONDATA["Ecliptic mean longitude"])%360
    Mm = (l - 0.1114041 * D - GD_MOONDATA["Ecliptic longitude (perigee)"])%360
    N = (GD_MOONDATA["Ecliptic longitude node (epoch)"] - 0.0529539 * D)%360
    C = l - LongSun
    Ev = 1.2739 * sin(2 * C - Mm)
    Ae = 0.1858 * sin(M)
    A3 = 0.37 * sin(M)
    MPrimem = Mm + Ev - Ae - A3
    Ec = 6.2886 * sin(MPrimem)
    A4 = 0.214 * sin(2 * MPrimem)
    lPrime = l + Ev + Ec - Ae + A4
    V = 0.6583 * sin(2 * (lPrime - LongSun))
    lPrimePrime = lPrime + V
    NPrime = N - 0.16 * sin(M)
    y = sin(lPrimePrime - NPrime) * cos(GD_MOONDATA["Inclination"])
    x = cos(lPrimePrime - NPrime)

    LongMoon = atan2(y, x) + NPrime
    LatMoon = asin(sin(lPrimePrime - NPrime) * sin(GD_MOONDATA["Inclination"]))
    
    hmsLongMoon = convert.DecimalToHrMinSec(LongMoon)
    hmsLatMoon = convert.DecimalToHrMinSec(LatMoon)
    
    return convert.EclipticToEquatorial(hmsLatMoon, hmsLongMoon, findAxialTilt(currentJD))


def ra_dec_to_vector(ra, dec):
    return (
    cos(dec) * cos(ra),
    cos(dec) * sin(ra),
    sin(dec)
    )

def dot(v1, v2):
    return sum(a * b for a, b in zip(v1, v2))

def magnitude(v):
    return sum(x**2 for x in v) ** 0.5

def phase_angle(ra_moon, dec_moon, ra_sun, dec_sun):
    v_moon = ra_dec_to_vector(ra_moon, dec_moon)
    v_sun = ra_dec_to_vector(ra_sun, dec_sun)
    return acos(dot(v_moon, v_sun) / (magnitude(v_moon) * magnitude(v_sun)))



def get_vmag_for_object(name, phaseDeg=None):
    # Return V magnitude for a body without hitting the DB on every call
    _ensure_planets_initialized()
    
    name_l = name.lower()

    if name_l == "moon":
        if phaseDeg is not None:
            illumination_fraction = (1 + cos(phaseDeg)) / 2
            if illumination_fraction <= 0:
                return float('inf')  # Invisible at new Moon
            return -12.7 + 2.5 * log10(illumination_fraction)
        else:
            # Default full Moon magnitude
            magnitude = -12.73
        return str(magnitude)

    # Use static table loaded once at import
    rec = data.get(name_l)
    if rec and "V-Mag" in rec:
        return rec["V-Mag"]

    return None

@timer
def getAllCelestialData(year, month, day, hour: int = 0, minute: int = 0, second: float = 0.0):
    _ensure_planets_initialized()
    
    # Primary implementation now delegates to ephemeris.get_positions; map results to controller format
    results = {}

    try:
        pos = ephem_get_positions(year, month, day, hour, minute, second)
    except Exception as e:
        print(f"ephem_get_positions failed: {e}")
        pos = {}

    # Map ephem output into expected shape
    for key, val in pos.items():
        try:
            ra = val.get('ra_deg')
            dec = val.get('dec_deg')
            v = val.get('distance_km')
            if ra is None or dec is None:
                continue
            ra_hms = convert.DegreesToHMS(ra)
            dec_dms = convert.DegreesToDMS(dec)
            vmag = get_vmag_for_object(key) if key in planets else None
            results[key.lower()] = {"ra": ra_hms, "dec": dec_dms, "vmag": vmag}
        except Exception as e:
            print(f"mapping ephem position failed for {key}: {e}")

    # Calculate moon position using findMoon() from astroTools.py
    # This overrides any ephemeris moon data with our own calculation
    try:
        ra_moon, dec_moon = findMoon(year, month, day, hour=hour, minute=minute, second=second)
        
        # Calculate moon phase angle for magnitude calculation
        if "sun" in results:
            # Convert sun's ra/dec back to degrees for phase calculation
            sun_ra_h, sun_ra_m, sun_ra_s = results["sun"]["ra"]
            sun_dec_d, sun_dec_m, sun_dec_s = results["sun"]["dec"]
            ra_sun_deg = convert.HrMinSecToDegrees(sun_ra_h, sun_ra_m, sun_ra_s) * 15
            dec_sun_deg = convert.HrMinSecToDegrees(sun_dec_d, sun_dec_m, sun_dec_s)
            
            # Convert moon's ra/dec to degrees
            moon_ra_h, moon_ra_m, moon_ra_s = ra_moon
            moon_dec_d, moon_dec_m, moon_dec_s = dec_moon
            ra_moon_deg = convert.HrMinSecToDegrees(moon_ra_h, moon_ra_m, moon_ra_s) * 15
            dec_moon_deg = convert.HrMinSecToDegrees(moon_dec_d, moon_dec_m, moon_dec_s)
            
            # Calculate phase angle
            phaseDeg = phase_angle(ra_moon_deg, dec_moon_deg, ra_sun_deg, dec_sun_deg)
            vmag_moon = get_vmag_for_object("moon", phaseDeg=phaseDeg)
        else:
            vmag_moon = get_vmag_for_object("moon")
        
        results["moon"] = {"ra": ra_moon, "dec": dec_moon, "vmag": vmag_moon}
    except Exception as e:
        print(f"findMoon calculation failed: {e}")

    return results
