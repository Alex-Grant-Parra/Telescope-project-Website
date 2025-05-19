from math import sin as math_sin, cos as math_cos, tan as math_tan, \
    asin as math_asin, acos as math_acos, atan as math_atan, atan2 as math_atan2, radians, degrees, sqrt, pi
from Server import app
from db import db
from models.tables import PlanetsTable  
from algorithms.timeUtils import SpaceTime
from algorithms.convert import convert
from models.tables import PlanetsTable

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

def findAxialTilt(julianDate):
    JD = julianDate-2451545.0 # The constant is the JD for J2000 1.5
    T = JD/36525.0 # Days in a centuary
    ChangeInTilt = ((46.815*T)+(0.0006*T**2)-(0.00181*T**3))/3600
    Tilt = 23.439292-ChangeInTilt
    return Tilt

def findPlanet(year, month, day, planetChoice):

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

    if planetChoice == "mercury" or planetChoice == "venus":
        # ecliptic lat and long for inner planets
        EclipLong = (180 + L + A)%360
        EclipLat = atan((rPrime * tan(Psi) * sin(EclipLong - lPrime)) / (R * sin(lPrime - L)))

    else:
        # ecliptic lat and long for outer planets
        EclipLong = (atan((R * sin(lPrime - L)) / (rPrime - R * cos (lPrime - L))) + lPrime)%360
        EclipLat = atan((rPrime * tan(Psi) * sin (EclipLong - lPrime)) / (R * sin(lPrime - L)))

    # Convert ecliptic to equatorial coordinates # the converter is brocken, the ecliptic outputs are correct
    hmsLong = convert.DecimalToHrMinSec(EclipLat)
    hmsLat = convert.DecimalToHrMinSec(EclipLong)

    result = convert.EclipticToEquatorial(hmsLong, hmsLat, findAxialTilt(currentJD))
    # result = convert.EclipticToEquatorial(hmsLong, hmsLat, 23.435992)

    return result
    
def findSun(year, month, day, usedForMoon=False):

    LR_julianDate = SpaceTime.getJD(year, month, day)

    GD_SUNDATA = {
    "Ecliptic longitude (epoch)": 279.403303,
    "Ecliptic longitude (perigee)":282.768422,
    "Eccentricity":0.016713,
    "Semi-major axis":1.495985*10**8,
    "Angular diameter": 0.533128
    }
    
    LR_e = GD_SUNDATA.get("Eccentricity")
    LR_daysBetween = LR_julianDate - SpaceTime.getJD(1990, 1, 0)
    LR_N = ((360/365.242191)*LR_daysBetween)%360
    LR_M = LR_N + GD_SUNDATA.get("Ecliptic longitude (epoch)") - GD_SUNDATA.get("Ecliptic longitude (perigee)")
    LR_M = radians(LR_M)
    LR_E = solveKepler(LR_M, GD_SUNDATA.get("Eccentricity"))
    LR_V = degrees(atan(((1+LR_e)/(1-LR_e))**(1/2)*tan(LR_E/2))*2)
    LR_EclLong = (LR_V + GD_SUNDATA.get("Ecliptic longitude (perigee)"))%360 
    if usedForMoon == False:
        return convert.EclipticToEquatorial(convert.DecimalToHrMinSec(0), convert.DecimalToHrMinSec(LR_EclLong), findAxialTilt(LR_julianDate))
    else:
        return (degrees(LR_M), LR_EclLong)



def findMoon(year, month, day):

    GD_MOONDATA = {
    "Ecliptic mean longitude": 318.351648,
    "Ecliptic longitude (perigee)": 36.340410,
    "Ecliptic longitude node (epoch)": 318.510107,
    "Inclination": 5.145396,
    "Eccentricity": 0.054900,
    "Semi-major axis": 3.84401*10**5,
    }

    currentJD = SpaceTime.getJD(year, month, day)
    D = currentJD - SpaceTime.getJD(1990, 1, 0) 

    sunLocationData = findSun(year, month, day, usedForMoon=True)
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




def get_vmag_for_object(name):
    data = PlanetsTable.query_by_name(name.capitalize())
    if name.lower() == "moon":
        # Calculating brightness for the Moon using phase angle could be done later
        V = -12.73
        return V
    if data and "V-Mag" in data:
        return data["V-Mag"]
    return None



def getAllCelestialData(year, month, day):
    results = {}

    # Exclude sun and moon from planets loop
    for planet_name in planets.keys():
        if planet_name.lower() in ["sun", "moon"]:
            continue
        ra, dec = findPlanet(year, month, day, planet_name)
        vmag = get_vmag_for_object(planet_name)
        results[planet_name] = {"ra": ra, "dec": dec, "vmag": vmag}

    # Calculate Sun separately
    ra, dec = findSun(year, month, day)
    vmag = get_vmag_for_object("sun")
    results["sun"] = {"ra": ra, "dec": dec, "vmag": vmag}

    # Calculate Moon separately
    ra, dec = findMoon(year, month, day)
    vmag = get_vmag_for_object("moon")
    results["moon"] = {"ra": ra, "dec": dec, "vmag": vmag}

    return results
