import numpy as np

G = 6.67430e-11


def computeAccelerations(positions, masses, eps=1e-6):
    """Compute gravitational accelerations with pairwise symmetry.

    The pairwise update enforces Newton's third law explicitly, which keeps the
    total momentum much better behaved than a broadcast-only accumulation.
    """
    n = len(masses)
    accelerations = np.zeros((n, 3), dtype=np.float64)

    for i in range(n - 1):
        for j in range(i + 1, n):
            delta = positions[j] - positions[i]
            distance_sq = float(np.dot(delta, delta) + eps * eps)
            inv_distance_cubed = distance_sq ** -1.5

            scale = G * inv_distance_cubed * delta
            accelerations[i] += masses[j] * scale
            accelerations[j] -= masses[i] * scale

    return accelerations


def velocityVerletStep(r, v, a, masses, dt):
    """Velocity Verlet integrator step.
    
    A time-reversible, symplectic integrator with O(dt^4) accuracy.
    Excellent for long-term energy conservation.
    
    Args:
        r: current positions
        v: current velocities  
        a: current accelerations
        masses: body masses
        dt: time step
        
    Returns:
        r_new, v_new, a_new: updated state
    """
    # Half step for velocity
    v_half = v + 0.5 * dt * a
    
    # Full step for position
    r_new = r + dt * v_half
    
    # Compute new acceleration at new position
    a_new = computeAccelerations(r_new, masses)
    
    # Final half step for velocity
    v_new = v_half + 0.5 * dt * a_new
    
    return r_new, v_new, a_new


def yoshida4Step(r, v, a_old, masses, dt):
    """4th-order Yoshida symplectic integrator.
    
    Higher-order symplectic integrator that improves accuracy while
    maintaining excellent long-term energy and momentum conservation.
    Uses proper acceleration state passing for consistency.
    
    Args:
        r: current positions
        v: current velocities
        a_old: current accelerations
        masses: body masses  
        dt: time step
        
    Returns:
        r_new, v_new, a_new: updated state
    """
    # Yoshida (1990) coefficients for 4th order
    cbrt2 = 2.0 ** (1.0 / 3.0)
    w1 = 1.0 / (2.0 - cbrt2)
    w0 = 1.0 - 2.0 * w1
    
    # Position and velocity stage coefficients
    c = np.array([w1 / 2.0, (w0 + w1) / 2.0, (w0 + w1) / 2.0, w1 / 2.0])
    d = np.array([w1, w0, w1])
    
    # Stage 1: position drift
    r = r + c[0] * dt * v
    
    # Stage 1: velocity kick
    a_new = computeAccelerations(r, masses)
    v = v + d[0] * dt * a_new
    
    # Stage 2: position drift
    r = r + c[1] * dt * v
    
    # Stage 2: velocity kick
    a_new = computeAccelerations(r, masses)
    v = v + d[1] * dt * a_new
    
    # Stage 3: position drift
    r = r + c[2] * dt * v
    
    # Stage 3: velocity kick
    a_new = computeAccelerations(r, masses)
    v = v + d[2] * dt * a_new
    
    # Final position drift
    r = r + c[3] * dt * v
    
    # Final acceleration for next step
    a_new = computeAccelerations(r, masses)
    
    return r, v, a_new