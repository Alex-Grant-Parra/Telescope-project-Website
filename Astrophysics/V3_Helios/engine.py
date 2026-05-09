import json
import numpy as np
from pathlib import Path
from integrator import computeAccelerations, velocityVerletStep, yoshida4Step


# ============================================================================
# DIAGNOSTICS UTILITIES
# ============================================================================

G = 6.67430e-11


def totalEnergy(r, v, m):
    masses = np.asarray(m, dtype=np.longdouble)
    velocities = np.asarray(v, dtype=np.longdouble)
    positions = np.asarray(r, dtype=np.longdouble)

    kinetic = 0.5 * np.sum(masses * np.sum(velocities * velocities, axis=1, dtype=np.longdouble), dtype=np.longdouble)

    potential = np.longdouble(0.0)
    n = len(m)

    for i in range(n):
        for j in range(i + 1, n):
            diff = positions[j] - positions[i]
            dist = np.linalg.norm(diff)
            potential -= np.longdouble(G) * masses[i] * masses[j] / dist

    return np.longdouble(kinetic + potential)


def totalMomentum(v, m):
    masses = np.asarray(m, dtype=np.longdouble)
    velocities = np.asarray(v, dtype=np.longdouble)
    return np.sum(masses[:, None] * velocities, axis=0, dtype=np.longdouble)


def totalAngularMomentum(r, v, m):
    masses = np.asarray(m, dtype=np.longdouble)
    positions = np.asarray(r, dtype=np.longdouble)
    velocities = np.asarray(v, dtype=np.longdouble)
    return np.sum(masses[:, None] * np.cross(positions, velocities), axis=0, dtype=np.longdouble)


def earthSunDistance(r, earthIndex=3, sunIndex=0):
    return np.linalg.norm(r[earthIndex] - r[sunIndex])


# ============================================================================
# SIMULATION ENGINE
# ============================================================================


def loadInitialConditions(path=None):
    if path is None:
        path = Path(__file__).resolve().parent / "initial_conditions.json"

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


def runSimulation(steps=35040, dt=900, store_every=10, integrator="verlet", progress_callback=None):
    # 35040 steps * 900 seconds = 31,536,000 seconds = ~365 days (one Earth orbit)
    # dt=900s keeps the run practical while preserving acceptable accuracy
    # Velocity Verlet is used for its stability and simplicity
    names, r, v = loadInitialConditions()
    r = np.asarray(r, dtype=np.longdouble)
    v = np.asarray(v, dtype=np.longdouble)
    masses = np.asarray(getMasses(names), dtype=np.longdouble)

    # Remove net center-of-mass velocity to eliminate bulk drift
    total_mass = np.sum(masses)
    v_cm = np.sum(masses[:, None] * v, axis=0) / total_mass
    v = v - v_cm
    
    # Verify: total momentum should now be near zero
    initial_momentum = totalMomentum(v, masses)
    initial_energy = totalEnergy(r, v, masses)
    initial_angular_momentum = totalAngularMomentum(r, v, masses)

    a = computeAccelerations(r, masses)

    # diagnostic storage
    energyLog = []
    momentumLog = []
    angularMomentumLog = []
    earthDistanceLog = []

    # trajectory storage 
    rHistory = []
    vHistory = []

    # Use Velocity Verlet - proven symplectic integrator with excellent stability
    step_func = yoshida4Step

    for step in range(steps):

        # Pass acceleration state explicitly for proper symplectic integration
        r, v, a = step_func(r, v, a, masses, dt)

        # Project back to the conserved total momentum to suppress roundoff drift.
        current_momentum = totalMomentum(v, masses)
        momentum_correction = (current_momentum - initial_momentum) / total_mass
        v = v - momentum_correction

        # store trajectory
        if step % store_every == 0:
            rHistory.append(r.copy())
            vHistory.append(v.copy())

        # diagnostics every 5 steps = every 25 minutes
        if step % 5 == 0:
            energyLog.append(totalEnergy(r, v, masses) - initial_energy)
            momentumLog.append(totalMomentum(v, masses) - initial_momentum)
            angularMomentumLog.append(totalAngularMomentum(r, v, masses) - initial_angular_momentum)
            earthDistanceLog.append(earthSunDistance(r))

        # Progress reporting & diagnostics
        if step % 5000 == 0:
            p_mag = np.linalg.norm(momentumLog[-1]) if momentumLog else 0
            e_val = energyLog[-1] if energyLog else 0
            baseline = np.linalg.norm(initial_momentum)
            p_drift_pct = (p_mag / baseline) * 100 if baseline > 0 else 0
            percent = 100 * step // steps
            if progress_callback is not None:
                try:
                    progress_callback(step, steps, percent, e_val, p_mag, p_drift_pct)
                except Exception:
                    # ignore callback errors to avoid breaking the simulation
                    pass
            else:
                print(f"Step {step:6d}/{steps} ({percent:2d}%)  E={e_val:.3e} J  p={p_mag:.3e} kg*m/s  p_drift={p_drift_pct:.2f}%")

    rHistory = np.array(rHistory)
    vHistory = np.array(vHistory)
    
    # Final diagnostics for conservation laws
    final_momentum = totalMomentum(v, masses)
    final_energy = totalEnergy(r, v, masses)
    final_angular_momentum = totalAngularMomentum(r, v, masses)
    
    print(f"\n{'='*60}")
    print(f"CONSERVATION LAW DIAGNOSTICS")
    print(f"{'='*60}")
    print(f"Initial momentum magnitude:  {np.linalg.norm(initial_momentum):.3e} kg*m/s")
    print(f"Final momentum magnitude:    {np.linalg.norm(final_momentum):.3e} kg*m/s")
    print(f"Initial energy: {initial_energy:.6e} J")
    print(f"Final energy:   {final_energy:.6e} J")
    energy_drift = abs(final_energy - initial_energy) / abs(initial_energy) if initial_energy != 0 else 0
    print(f"Energy drift:   {energy_drift*100:.6f}%")
    momentum_drift = np.linalg.norm(final_momentum - initial_momentum)
    print(f"Momentum drift: {momentum_drift:.6e} kg*m/s")
    angular_drift = np.linalg.norm(final_angular_momentum - initial_angular_momentum)
    print(f"Angular momentum drift: {angular_drift:.6e} kg*m^2/s")
    print(f"{'='*60}\n")

    return {
        "names": names,
        "rHistory": rHistory,
        "vHistory": vHistory,
        "energy": np.array(energyLog),
        "momentum": np.array(momentumLog),
        "angularMomentum": np.array(angularMomentumLog),
        "earthDistance": np.array(earthDistanceLog),
        "initialEnergy": initial_energy,
        "initialMomentum": initial_momentum,
        "totalMass": total_mass
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