import json
import numpy as np
from integrator import computeAccelerations, velocityVerletStep


def loadInitialConditions(path="initial_conditions.json"):
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


def runSimulation(steps=1000, dt=3600):
    names, r, v = loadInitialConditions()
    masses = getMasses(names)

    a = computeAccelerations(r, masses)

    history = []

    for step in range(steps):
        r, v, a = velocityVerletStep(r, v, a, masses, dt)

        if step % 10 == 0:
            history.append(r.copy())

        if step % 50 == 0:
            print(f"Step {step}")

    history = np.array(history)

    return names, history


if __name__ == "__main__":
    names, history = runSimulation()

    print("Simulation complete")
    print("Bodies:", names)
    print("Trajectory shape:", history.shape)