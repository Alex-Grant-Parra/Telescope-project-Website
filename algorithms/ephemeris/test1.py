from loader import load_all

# Example Julian Date
jd = 2460963.25256  # adjust as needed

def test_planet(planets, name):
    planet = planets.get(name)
    if not planet:
        print(f"Planet '{name}' not found in loaded data.")
        return
    lat, long, r = planet.position(jd)
    

def test_moon(moon):
    lat, long, r = moon.position(jd)
    

if __name__ == "__main__":
    planets, moon = load_all()

    # Test a few planets
    test_planet(planets, "Earth")
    test_planet(planets, "Mars")
    test_planet(planets, "Jupiter")

    # Test the Moon
    test_moon(moon)
