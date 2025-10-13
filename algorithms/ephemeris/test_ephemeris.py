from loader import load_all

# Example Julian Date
jd = 2460000.5  # adjust as needed

def test_planet(planets, name):
    planet = planets.get(name)
    if not planet:
        print(f"Planet '{name}' not found in loaded data.")
        return
    ra, dec, r = planet.position(jd)
    print(f"{name} -> RA: {ra}, Dec: {dec}, Dist: {r}")

def test_moon(moon):
    ra, dec, r = moon.position(jd)
    print(f"Moon -> RA: {ra}, Dec: {dec}, Dist: {r}")

if __name__ == "__main__":
    planets, moon = load_all()

    # Test a few planets
    test_planet(planets, "Earth")
    test_planet(planets, "Mars")
    test_planet(planets, "Jupiter")

    # Test the Moon
    test_moon(moon)
