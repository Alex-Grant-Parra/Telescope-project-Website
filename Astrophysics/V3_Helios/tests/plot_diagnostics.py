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
    E = np.asarray(results["energy"])
    initial_energy = float(results.get("initialEnergy", 1.0))
    baseline = abs(initial_energy) if initial_energy != 0 else 1.0

    plt.figure()
    plt.plot(100.0 * E / baseline, color="tab:blue")
    plt.axhline(0, color="black", linewidth=0.8, alpha=0.5)
    plt.title("Energy Drift vs Time")
    plt.xlabel("sample")
    plt.ylabel("ΔE / E₀ (%)")

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
    total_mass = float(results.get("totalMass", 1.0))

    # Convert momentum drift to equivalent center-of-mass velocity drift.
    V = P / total_mass

    plt.figure()
    plt.plot(V[:, 0], label="ΔVx")
    plt.plot(V[:, 1], label="ΔVy")
    plt.plot(V[:, 2], label="ΔVz")
    plt.axhline(0, color="black", linewidth=0.8, alpha=0.5)
    plt.title("Center-of-Mass Velocity Drift vs Time")
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