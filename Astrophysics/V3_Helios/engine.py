import json
import numpy as np
from integrator import computeAccelerations, velocityVerletStep

from diagnostics import (
    totalEnergy,
    totalMomentum,
    totalAngularMomentum,
    earthSunDistance
)


def loadInitialConditions(path="Astrophysics/V3_Helios/initial_conditions.json"):
    with open(path, "r") as f:
        data = json.load(f)

    names = list(data["bodies"].keys())

    r = np.array([data["bodies"][n]["position_m"] for n in names], dtype=np.float64)
    v = np.array([data["bodies"][n]["velocity_m_s"] for n in names], dtype=np.float64)

    return names, r, v


def getMasses(names):
    massMap = {
        "sun": 1.9885e30,
        "mercury": 3.301e23,
        "venus": 4.867e24,
        "earth_moon": 5.972e24,
        "mars": 6.417e23,
        "jupiter": 1.898e27,
        "saturn": 5.683e26,
        "uranus": 8.681e25,
        "neptune": 1.024e26
    }

    return np.array([massMap[n] for n in names], dtype=np.float64)


def runSimulation(steps=35040, dt=900):
    # 35040 steps * 900 seconds = 31,536,000 seconds = ~365 days (one Earth orbit)
    # dt=900s provides 2x better accuracy than dt=1800s for energy conservation
    names, r, v = loadInitialConditions()
    masses = getMasses(names)

    a = computeAccelerations(r, masses)

    # diagnostic storage
    energyLog = []
    momentumLog = []
    angularMomentumLog = []
    earthDistanceLog = []

    # trajectory storage 
    rHistory = []

    for step in range(steps):

        r, v, a = velocityVerletStep(r, v, a, masses, dt)

        # store trajectory
        if step % 10 == 0:
            rHistory.append(r.copy())

        # diagnostics
        if step % 5 == 0:
            energyLog.append(totalEnergy(r, v, masses))
            momentumLog.append(totalMomentum(v, masses))
            angularMomentumLog.append(totalAngularMomentum(r, v, masses))
            earthDistanceLog.append(earthSunDistance(r))

        if step % 50 == 0:
            print(f"Step {step}")

    rHistory = np.array(rHistory)

    return {
        "names": names,
        "rHistory": rHistory,
        "energy": np.array(energyLog),
        "momentum": np.array(momentumLog),
        "angularMomentum": np.array(angularMomentumLog),
        "earthDistance": np.array(earthDistanceLog)
    }


if __name__ == "__main__":
    results = runSimulation()

    print("\nSimulation complete")

    print("Bodies:", results["names"])
    print("Trajectory shape:", results["rHistory"].shape)

    print("\nDiagnostics:")
    print("Energy samples:", len(results["energy"]))
    print("Momentum samples:", len(results["momentum"]))
    print("Earth distance samples:", len(results["earthDistance"]))