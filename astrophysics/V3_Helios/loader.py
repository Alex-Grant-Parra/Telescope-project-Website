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
metersPerKilometer = 1000.0

# Bodies to sample from the Solar System barycenter in the chosen frame.
# Earth and Moon are queried separately so the N-body engine can integrate
# their mutual gravitational interaction explicitly.
bodies = {
    "sun": "SUN",
    "mercury": "MERCURY BARYCENTER",
    "venus": "VENUS BARYCENTER",
    "earth": "EARTH",
    "moon": "MOON",
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
    stateVec, _ = spice.spkezr(
        target,
        et,
        frame,
        "NONE",
        "SOLAR SYSTEM BARYCENTER"
    )

    positionM = [component * metersPerKilometer for component in stateVec[:3]]
    velocityMS = [component * metersPerKilometer for component in stateVec[3:6]]

    # SPICE returns kilometers and km/s; convert to meters for storage.
    state["bodies"][name] = {
        "position_m": positionM,
        "velocity_m_s": velocityMS
    }

    print(name, "extracted")

with open(outputPath, "w") as f:
    json.dump(state, f, indent=2)

print("Saved:", outputPath)

# Release loaded kernels before exiting.
spice.kclear()