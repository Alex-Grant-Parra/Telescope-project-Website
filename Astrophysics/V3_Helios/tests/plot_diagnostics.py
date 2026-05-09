import numpy as np
import matplotlib
matplotlib.use("Agg")  # IMPORTANT: headless backend

import matplotlib.pyplot as plt
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

OUTPUT_DIR = Path(__file__).resolve().parent

from engine import runSimulation


def plotEarthOrbit(results):
    r = results["rHistory"]
    names = results["names"]

    earthIndex = names.index("earth_moon")
    sunIndex = names.index("sun")

    earth = r[:, earthIndex, :]
    sun = r[:, sunIndex, :]

    rel = earth - sun

    plt.figure()
    plt.plot(rel[:, 0], rel[:, 1])
    plt.title("Earth Orbit (Sun-centred)")
    plt.xlabel("x (m)")
    plt.ylabel("y (m)")
    plt.axis("equal")

    plt.savefig(OUTPUT_DIR / "earth_orbit.png", dpi=200)
    plt.close()


def plotEnergy(results):
    E = results["energy"]

    plt.figure()
    plt.plot(E)
    plt.title("Total Energy vs Time")
    plt.xlabel("sample")
    plt.ylabel("Energy (J)")

    plt.savefig(OUTPUT_DIR / "energy.png", dpi=200)
    plt.close()


def plotEarthDistance(results):
    d = results["earthDistance"]

    plt.figure()
    plt.plot(d)
    plt.title("Earth–Sun Distance vs Time")
    plt.xlabel("sample")
    plt.ylabel("Distance (m)")

    plt.savefig(OUTPUT_DIR / "earth_distance.png", dpi=200)
    plt.close()


def plotMomentum(results):
    P = np.array(results["momentum"])

    plt.figure()
    plt.plot(P[:, 0], label="Px")
    plt.plot(P[:, 1], label="Py")
    plt.plot(P[:, 2], label="Pz")
    plt.title("Total Momentum vs Time")
    plt.legend()

    plt.savefig(OUTPUT_DIR / "momentum.png", dpi=200)
    plt.close()


if __name__ == "__main__":
    results = runSimulation()

    print("Generating diagnostic plots...")

    plotEarthOrbit(results)
    plotEnergy(results)
    plotEarthDistance(results)
    plotMomentum(results)

    print("Done. Plots saved:")
    print(" - earth_orbit.png")
    print(" - energy.png")
    print(" - earth_distance.png")
    print(" - momentum.png")