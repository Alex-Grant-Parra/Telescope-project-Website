import json
import numpy as np
from pathlib import Path

try:
    from .integrator import (
        computeAccelerations,
        computeGRCorrections,
        velocityVerletStep,
        yoshida4Step,
        adaptiveVerletStep,
    )
except ImportError:
    from integrator import (computeAccelerations, computeGRCorrections,
                            velocityVerletStep, yoshida4Step, adaptiveVerletStep)


# ============================================================================
# DIAGNOSTICS UTILITIES
# ============================================================================

G = 6.67430e-11


def totalEnergy(r, v, m):
    masses = np.asarray(m, dtype=np.float64)
    velocities = np.asarray(v, dtype=np.float64)
    positions = np.asarray(r, dtype=np.float64)

    kinetic = 0.5 * np.sum(masses * np.sum(velocities * velocities, axis=1, dtype=np.float64), dtype=np.float64)

    potential = np.float64(0.0)
    n = len(m)

    for i in range(n):
        for j in range(i + 1, n):
            diff = positions[j] - positions[i]
            dist = np.linalg.norm(diff)
            potential -= np.float64(G) * masses[i] * masses[j] / dist

    return np.float64(kinetic + potential)


def totalMomentum(v, m):
    masses = np.asarray(m, dtype=np.float64)
    velocities = np.asarray(v, dtype=np.float64)
    return np.sum(masses[:, None] * velocities, axis=0, dtype=np.float64)


def totalAngularMomentum(r, v, m):
    masses = np.asarray(m, dtype=np.float64)
    positions = np.asarray(r, dtype=np.float64)
    velocities = np.asarray(v, dtype=np.float64)
    return np.sum(masses[:, None] * np.cross(positions, velocities), axis=0, dtype=np.float64)


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
        "earth": 5.9722e24,
        "moon": 7.342e22,
        "mars": 6.417e23,
        "jupiter": 1.898e27,
        "saturn": 5.683e26,
        "uranus": 8.681e25,
        "neptune": 1.024e26
    }

    missing = [name for name in names if name not in massMap]
    if missing:
        raise KeyError(f"Missing mass entries for bodies: {', '.join(missing)}")

    return np.array([massMap[n] for n in names], dtype=np.float64)


def runSimulation(steps=35040, dt=900, store_every=10, integrator="auto",
                  use_gr=False, adaptive=False, adaptive_tol=1e4, duration=None,
                  progress_callback=None):
    # 35040 steps * 900 seconds = 31,536,000 seconds = ~365 days (one Earth orbit)
    # dt=900s keeps the run practical while preserving acceptable accuracy
    # Velocity Verlet is used for its stability and simplicity
    names, r, v = loadInitialConditions()
    r = np.asarray(r, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    masses = np.asarray(getMasses(names), dtype=np.float64)

    # Remove net center-of-mass velocity to eliminate bulk drift
    total_mass = np.sum(masses)
    v_cm = np.sum(masses[:, None] * v, axis=0) / total_mass
    v = v - v_cm
    
    # Verify: total momentum should now be near zero
    initial_momentum = totalMomentum(v, masses)
    initial_energy = totalEnergy(r, v, masses)
    initial_angular_momentum = totalAngularMomentum(r, v, masses)

    a = computeAccelerations(r, masses)
    if use_gr:
        a = a + computeGRCorrections(r, v, masses)

    # diagnostic storage
    energyLog = []
    momentumLog = []
    angularMomentumLog = []
    earthDistanceLog = []

    # trajectory storage
    rHistory = []
    vHistory = []
    tHistory = []

    t_end = float(duration if duration is not None else steps * dt)

    # Select integrator automatically when integrator="auto":
    #   - adaptive=True  → always Verlet (adaptive step-doubling is Verlet-based)
    #   - duration <= 2 years → Verlet (accuracy already well below Chebyshev error)
    #   - duration >  2 years → Yoshida 4th order (higher-order accuracy compounds)
    _TWO_YEARS = 2 * 365.25 * 86400.0
    if integrator == "auto":
        if adaptive or t_end <= _TWO_YEARS:
            integrator = "verlet"
        else:
            integrator = "yoshida4"
    step_func = yoshida4Step if (integrator == "yoshida4" and not adaptive) else velocityVerletStep
    print(f"Integrator: {integrator}  adaptive={adaptive}  t_end={t_end/86400:.1f} days")

    if not adaptive:
        n_bodies = len(names)
        n_store = ((steps - 1) // store_every + 1) if steps > 0 else 0
        n_diag = ((steps - 1) // 5 + 1) if steps > 0 else 0

        rHistory = np.empty((n_store, n_bodies, 3), dtype=np.float64)
        vHistory = np.empty((n_store, n_bodies, 3), dtype=np.float64)
        tHistory = np.empty(n_store, dtype=np.float64)

        energyLog = np.empty(n_diag, dtype=np.float64)
        momentumLog = np.empty((n_diag, 3), dtype=np.float64)
        angularMomentumLog = np.empty((n_diag, 3), dtype=np.float64)
        earthDistanceLog = np.empty(n_diag, dtype=np.float64)

        store_idx = 0
        diag_idx = 0

        # ---- Fixed-step loop --------------------------------------------------
        for step in range(steps):
            r, v, a = step_func(r, v, a, masses, dt, use_gr=use_gr)

            if step % store_every == 0:
                rHistory[store_idx] = r
                vHistory[store_idx] = v
                tHistory[store_idx] = (step + 1) * float(dt)
                store_idx += 1

            if step % 5 == 0:
                energyLog[diag_idx] = totalEnergy(r, v, masses) - initial_energy
                momentumLog[diag_idx] = totalMomentum(v, masses) - initial_momentum
                angularMomentumLog[diag_idx] = totalAngularMomentum(r, v, masses) - initial_angular_momentum
                earthDistanceLog[diag_idx] = earthSunDistance(r)
                diag_idx += 1

            if step % 5000 == 0:
                p_mag = np.linalg.norm(momentumLog[diag_idx - 1]) if diag_idx > 0 else 0
                e_val = energyLog[diag_idx - 1] if diag_idx > 0 else 0
                baseline = np.linalg.norm(initial_momentum)
                p_drift_pct = (p_mag / baseline) * 100 if baseline > 0 else 0
                percent = 100 * step // steps
                if progress_callback is not None:
                    try:
                        progress_callback(step, steps, percent, e_val, p_mag, p_drift_pct)
                    except Exception:
                        pass
                else:
                    print(f"Step {step:6d}/{steps} ({percent:2d}%)  E={e_val:.3e} J  p={p_mag:.3e} kg*m/s  p_drift={p_drift_pct:.2f}%")

    else:
        # ---- Adaptive-step loop -----------------------------------------------
        t_sim = 0.0
        current_dt = float(dt)
        accepted = 0
        diag_interval = 5.0 * float(dt)
        diag_t_next = 0.0
        report_interval = 5000.0 * float(dt)
        report_t_next = 0.0

        while t_sim < t_end:
            step_dt = min(current_dt, t_end - t_sim)
            if step_dt <= 0.0:
                break

            r, v, a, dt_used, current_dt = adaptiveVerletStep(
                r, v, a, masses, step_dt, adaptive_tol, use_gr=use_gr
            )
            t_sim += dt_used
            accepted += 1

            if accepted % store_every == 0:
                rHistory.append(r.copy())
                vHistory.append(v.copy())
                tHistory.append(t_sim)

            if t_sim >= diag_t_next:
                energyLog.append(totalEnergy(r, v, masses) - initial_energy)
                momentumLog.append(totalMomentum(v, masses) - initial_momentum)
                angularMomentumLog.append(totalAngularMomentum(r, v, masses) - initial_angular_momentum)
                earthDistanceLog.append(earthSunDistance(r))
                diag_t_next = t_sim + diag_interval

            if t_sim >= report_t_next:
                p_mag = np.linalg.norm(momentumLog[-1]) if momentumLog else 0
                e_val = energyLog[-1] if energyLog else 0
                percent = int(100 * t_sim / t_end)
                if progress_callback is not None:
                    try:
                        progress_callback(accepted, int(t_end / dt), percent, e_val, p_mag, 0.0)
                    except Exception:
                        pass
                else:
                    print(f"t={t_sim:.0f}s ({percent:2d}%)  dt={current_dt:.1f}s  accepted={accepted}  E={e_val:.3e} J")
                report_t_next = t_sim + report_interval

    if adaptive:
        rHistory = np.array(rHistory, dtype=np.float64)
        vHistory = np.array(vHistory, dtype=np.float64)
        tHistory = np.array(tHistory, dtype=np.float64)
        energyLog = np.array(energyLog, dtype=np.float64)
        momentumLog = np.array(momentumLog, dtype=np.float64)
        angularMomentumLog = np.array(angularMomentumLog, dtype=np.float64)
        earthDistanceLog = np.array(earthDistanceLog, dtype=np.float64)
    
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
        "tHistory": tHistory,
        "energy": energyLog,
        "momentum": momentumLog,
        "angularMomentum": angularMomentumLog,
        "earthDistance": earthDistanceLog,
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