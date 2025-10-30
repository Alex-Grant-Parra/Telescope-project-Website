import os
import pickle
try:
    # Prefer absolute package import
    from algorithms.ephemeris.celestial import Planet, Moon
except ImportError:
    # Fallback to local import if package context not set
    from celestial import Planet, Moon  # type: ignore

# Paths to pickled data
PICKLE_DIR = os.path.join("instance", "ephemerisData", "pickled")
VSOP_PICKLE = os.path.join(PICKLE_DIR, "vsop.pkl")
MOON_PICKLE = os.path.join(PICKLE_DIR, "moon.pkl")

def load_planets():
    # Load all planet objects from VSOP87 pickle.
    with open(VSOP_PICKLE, "rb") as f:
        vsop_data = pickle.load(f)
    # The VSOP pickle may have several shapes. Common forms:
    # - {'Mercury': {...}, 'Venus': {...}, ...}
    # - {'VSOP87A': {'Mercury': {...}, ...}}
    # If nested under a top-level key, descend one level.
    if isinstance(vsop_data, dict) and len(vsop_data) == 1:
        # check if the single value is another dict of planets
        first_val = next(iter(vsop_data.values()))
        if isinstance(first_val, dict) and any(isinstance(v, dict) for v in first_val.values()):
            vsop_data = first_val

    if not isinstance(vsop_data, dict) or len(vsop_data) == 0:
        print(f"[loader.load_planets] No planet series found in {VSOP_PICKLE}")
        return {}

    # Convert raw series data into Planet objects
    planets = {name: Planet(name, series) for name, series in vsop_data.items()}
    return planets

def load_moon():
    # Load Moon object from ELP82b pickle.
    with open(MOON_PICKLE, "rb") as f:
        elp_data = pickle.load(f)
    # The pickled ELP data may be a dict (e.g. {'ELP82B': [...]}) or
    # already the series list. If it's a dict, extract the first value.
    if isinstance(elp_data, dict):
        # take the first series list available
        series_list = next(iter(elp_data.values()))
    else:
        series_list = elp_data

    # The CelestialBody base class expects (name, series).
    moon = Moon("Moon", series_list)
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
