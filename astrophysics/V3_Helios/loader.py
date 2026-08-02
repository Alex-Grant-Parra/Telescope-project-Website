import spiceypy as spice
import json
from datetime import datetime, timezone
from pathlib import Path

base = Path(__file__).resolve().parent
dataPath = base / "data"
outputPath = base / "initial_conditions.json"

# Local SPICE kernel files bundled with the project.
tlsPath = dataPath / "naif0012.tls"
kernelPaths = [
    tlsPath,
    dataPath / "de440.bsp",
    dataPath / "mar099s.bsp",
    dataPath / "jup349.bsp",
    dataPath / "sat459.bsp",
    dataPath / "ura184_part-3.bsp",
    dataPath / "nep105.bsp",
    dataPath / "plu060.bsp",
]

print("TLS exists:", tlsPath.exists())

missingKernels = [path.name for path in kernelPaths if not path.exists()]
if missingKernels:
    raise FileNotFoundError(
        "Missing required SPICE kernels: " + ", ".join(missingKernels)
    )

spice.kclear()
for kernelPath in kernelPaths:
    spice.furnsh(str(kernelPath))

print("Loaded kernels:", spice.ktotal("ALL"))

now = datetime.now(timezone.utc)
utcStr = now.strftime("%Y-%m-%dT%H:%M:%S.%f")
et = spice.utc2et(utcStr)

print("Epoch ET:", et)

# Use a single scale factor for kilometer-to-meter conversion.
metersPerKilometer = 1000.0

# Bodies to sample from the Solar System barycenter in the chosen frame.
# Earth and Moon are kept as-is; the other planets now use body-center SPKs.
bodies = {
    "sun": "SUN",
    "mercury": "MERCURY",
    "venus": "VENUS",
    "earth": "EARTH",
    "moon": "MOON",
    "mars": "MARS",
    "jupiter": "JUPITER",
    "saturn": "SATURN",
    "uranus": "URANUS",
    "neptune": "NEPTUNE",
    "pluto": "PLUTO",
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