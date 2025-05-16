from math import sin as math_sin, cos as math_cos, tan as math_tan, \
    asin as math_asin, acos as math_acos, atan as math_atan, atan2 as math_atan2, radians, degrees, sqrt, pi
from Server import app
from db import db
from models.tables import PlanetsTable  
from algorithms.timeUtils import SpaceTime
from algorithms.convert import convert

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

        self.T = 2451545.0 # Time at perihelion, epoch, currently julian date

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

def solveKepler(M, e):
    if e < 0.1:
        E0 = M
        LR_E0 = E0  # Initialize
        tolerance = 10**-6
        while True:
            E1 = E0 - (E0 - e*sin(E0)-M) / (1 - e*cos(E0))
            if abs(LR_E0 - E1) < tolerance:
                break
            LR_E0 = E1
        return E1
    else:
        print("Eccentricity of orbit must be between 0 and 0.1")
        return -1
    
def getPlanetsData():
    with app.app_context():
        planets = db.session.query(PlanetsTable).all()
        planets_data = {
            planet.Name.lower(): {column.name: getattr(planet, column.name, None) for column in planet.__table__.columns}
            for planet in planets
        }
        return planets_data

data, planets = getPlanetsData(), {}
for key, value in data.items():
    planets[key] = CelestialObject(**value)

# example usage to get data
# print(planets.get("mars").a) # returns 1.523688
# print(planets.get("mars").e) # returns 0.093405
# print(planets.get("mars").i) # returns 0.093405
# print(planets.get("mars").N) # returns 1.8497
# print(planets.get("mars").W) 
# print(planets.get("mars").M) # returns 18.6021
# print(planets.get("mars").P) # returns 18.6021

def findAxialTilt(LR_julianDate):
    LR_JD = LR_julianDate-2451545.0 # The constant is the JD for J2000 1.5
    LR_T = LR_JD/36525.0 # Days in a centuary
    LR_ChangeInTilt = ((46.815*LR_T)+(0.0006*LR_T**2)-(0.00181*LR_T**3))/3600
    LR_Tilt = 23.439292-LR_ChangeInTilt
    return LR_Tilt

def findPlanet(year, month, day, planetChoice):

    # # Constants for J1990
    # EarthPeriod = 1.00004
    # EarthLongAtEpoch = 99.403308
    # EarthLongOfPeri = 102.768413
    # EarthEccentricity = 0.016713
    # EarthSemiMajorAxis = 1

    # Constants for J2000
    EarthPeriod = 1.00004
    EarthLongAtEpoch = 100.46435
    EarthLongOfPeri = 102.94719
    EarthEccentricity = 0.016713
    EarthSemiMajorAxis = 1

    currentJD = SpaceTime.getJD(year, month, day)
    J1990JD = 2447892.5
    JDdifference = currentJD - J1990JD + 1

    # For the planet:
    Np = (360/365.242191 * JDdifference/planets.get(planetChoice).P)%360
    Mp = Np + planets.get(planetChoice).l - planets.get(planetChoice).W
    l = (Np + 360/pi * planets.get(planetChoice).e * sin(Mp) + planets.get(planetChoice).l)%360
    vp = l - planets.get(planetChoice).W
    r = (planets.get(planetChoice).a * (1 - planets.get(planetChoice).e ** 2)) / (1 + planets.get(planetChoice).e * cos(vp))

    # For the earth
    Ne = (360/365.242191 * JDdifference/EarthPeriod)%360
    Me = Ne + EarthLongAtEpoch - EarthLongOfPeri
    L = (Ne + 360/pi * EarthEccentricity * sin(Me) + EarthLongAtEpoch)%360
    ve = L - EarthLongOfPeri
    R = (EarthSemiMajorAxis * (1 - EarthEccentricity ** 2)) / (1 + EarthEccentricity * cos(ve)) # correct up to here
    
    # Merged

    Psi = asin(sin(l - planets.get(planetChoice).N) * sin(planets.get(planetChoice).i))
    y = sin(l - planets.get(planetChoice).N) * cos(planets.get(planetChoice).i)
    x = cos(l - planets.get(planetChoice).N)
    lPrime = atan2(y, x) + planets.get(planetChoice).N
    rPrime = r * cos(Psi)
    A = atan((rPrime * sin(L - lPrime)) / (R - rPrime * cos(L - lPrime)))
    EclipLong = (180 + L + A)%360
    EclipLat = atan((rPrime * tan(Psi) * sin(EclipLong - lPrime)) / (R * sin(lPrime - L)))

    print(EclipLong, EclipLat)

    # Convert ecliptic to equatorial coordinates # the converter is brocken, the ecliptic outputs are correct
    hmsLong = convert.DecimalToHrMinSec(EclipLat)
    hmsLat = convert.DecimalToHrMinSec(EclipLong)

    result = convert.EclipticToEquatorial(hmsLat, hmsLong, findAxialTilt(currentJD))

    return result


print(findPlanet(1988, 11, 22, "mercury"))