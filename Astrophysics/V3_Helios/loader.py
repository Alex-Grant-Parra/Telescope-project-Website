import spiceypy as spice
import json
from datetime import datetime, timezone
from pathlib import Path

base = Path(__file__).resolve().parent
dataPath = base / "data"
outputPath = base / "initial_conditions.json"

# Local SPICE kernel files bundled with the project.
tlsPath = dataPath / "naif0012.tls"
bspPath = dataPath / "de440.bsp"

print("TLS exists:", tlsPath.exists())
print("BSP exists:", bspPath.exists())

spice.kclear()
spice.furnsh(str(tlsPath))
spice.furnsh(str(bspPath))

print("Loaded kernels:", spice.ktotal("ALL"))

now = datetime.now(timezone.utc)
utcStr = now.strftime("%Y-%m-%dT%H:%M:%S.%f")
et = spice.utc2et(utcStr)

print("Epoch ET:", et)

# Use a single scale factor for kilometer-to-meter conversion.
meters_per_kilometer = 1000.0

# Bodies to sample from the Solar System barycenter in the chosen frame.
bodies = {
    "sun": "SUN",
    "mercury": "MERCURY BARYCENTER",
    "venus": "VENUS BARYCENTER",
    "earth_moon": "EARTH BARYCENTER",
    "mars": "MARS BARYCENTER",
    "jupiter": "JUPITER BARYCENTER",
    "saturn": "SATURN BARYCENTER",
    "uranus": "URANUS BARYCENTER",
    "neptune": "NEPTUNE BARYCENTER"
}

frame = "ECLIPJ2000"

# Build the JSON payload that downstream code can load directly.
state = {
    "epoch_et": et,
    "epoch_utc": utcStr,
    "frame": frame,
    "bodies": {}
}

for name, target in bodies.items():
    state_vec, _ = spice.spkezr(
        target,
        et,
        frame,
        "NONE",
        "SOLAR SYSTEM BARYCENTER"
    )

    position_m = [component * meters_per_kilometer for component in state_vec[:3]]
    velocity_m_s = [component * meters_per_kilometer for component in state_vec[3:6]]

    # SPICE returns kilometers and km/s; convert to meters for storage.
    state["bodies"][name] = {
        "position_m": position_m,
        "velocity_m_s": velocity_m_s
    }

    print(name, "extracted")

with open(outputPath, "w") as f:
    json.dump(state, f, indent=2)

print("Saved:", outputPath)

# Release loaded kernels before exiting.
spice.kclear()