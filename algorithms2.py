from math import sin as math_sin, cos as math_cos, tan as math_tan, \
    asin as math_asin, acos as math_acos, atan as math_atan, atan2 as math_atan2, radians, degrees, sqrt

# Overriding trig functions to use degrees
sin = lambda x: math_sin(radians(x))
cos = lambda x: math_cos(radians(x))
tan = lambda x: math_tan(radians(x))

# Overriding inverse trig functions to return degrees
asin = lambda x: degrees(math_asin(x))
acos = lambda x: degrees(math_acos(x))
atan = lambda x: degrees(math_atan(x))
atan2 = lambda y, x: degrees(math_atan2(y, x))

class object:

    def __init__(self):

        # Primary keplarian orbital parameters
        self.a = 1 # Semi-Major axis
        self.e = 2 # Eccentricity
        self.T = 3 # Time at perihelion
        self.q = 4 # Perihelion distance
        self.i = 5 # Inclination
        self.N = 6 # Longitude of ascending node
        self.w = 7 # Angle of ascending node to perihelion

        # Misc parameters
        self.m = 8 # Mass of object

        # Secondary keplarian orbital parameters
        self.q = self.a * (1 - self.e)
        self.Q = self.a * (1 + self.e)
        self.P = 365.256898326 * self.a**1.5/sqrt(1+self.m)
        self.n = 360 / self.P # Daily motion
        self.t = self.T # Epoch
        self.M = (self.t - self.T) * 360 / self.P # Mean anomaly
        self.L = self.M + self.w + self.N # Mean longitude
        self.E = None
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
    


from Server import app
from db import db
from models.tables import PlanetsTable  

def check_table_data():
    """
    Check if the PlanetsTable has data and retrieve all entries.
    """
    with app.app_context():
        planet_count = db.session.query(PlanetsTable).count()
        print(f"Total planets in database: {planet_count}")
        planets = db.session.query(PlanetsTable).all()

        if planet_count == 0:
            print("No planets found in database.")
            return {}

        print("Columns in PlanetsTable:", PlanetsTable.__table__.columns.keys())

        # Extract the data correctly
        planets_data = {
            planet.Name.lower(): {column.name: getattr(planet, column.name, None) for column in planet.__table__.columns}
            for planet in planets
        }

        return planets_data

if __name__ == "__main__":
    planets_dict = check_table_data()
    print("Planets Data:", planets_dict)

