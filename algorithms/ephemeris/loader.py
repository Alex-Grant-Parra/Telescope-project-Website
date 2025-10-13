import os
import pickle
from celestial import Planet, Moon

# Paths to pickled data
PICKLE_DIR = os.path.join("instance", "ephemerisData", "pickled")
VSOP_PICKLE = os.path.join(PICKLE_DIR, "vsop.pkl")
MOON_PICKLE = os.path.join(PICKLE_DIR, "moon.pkl")

def load_planets():
    # Load all planet objects from VSOP87 pickle.
    with open(VSOP_PICKLE, "rb") as f:
        vsop_data = pickle.load(f)
    # Convert raw series data into Planet objects
    planets = {name: Planet(name, series) for name, series in vsop_data.items()}
    return planets

def load_moon():
    # Load Moon object from ELP82b pickle.
    with open(MOON_PICKLE, "rb") as f:
        elp_data = pickle.load(f)
    moon = Moon(elp_data)
    return moon

# Optional convenience: load everything at once
def load_all():
    planets = load_planets()
    moon = load_moon()
    return planets, moon

# Test block
if __name__ == "__main__":
    planets, moon = load_all()
    print(f"Loaded planets: {list(planets.keys())}")
    print(f"Moon series length: {len(moon.series)}")
