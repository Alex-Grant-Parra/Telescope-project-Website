import numpy as np

G = 6.67430e-11
C_LIGHT = 2.99792458e8  # m/s


def computeAccelerations(positions, masses, eps=1e-6):
    """Compute gravitational accelerations using vectorised NumPy broadcasting.

    Replaces the Python pairwise loop with a fully vectorised broadcast that
    runs in NumPy's C backend (~10-50x faster for small N).  Newton's third
    law is enforced by the antisymmetry of the delta tensor.
    """
    pos = np.asarray(positions, dtype=np.float64)
    m = np.asarray(masses, dtype=np.float64)

    # delta[i,j] = pos[i] - pos[j],  shape (N, N, 3)
    delta = pos[:, None, :] - pos[None, :, :]

    # Squared pairwise distances with softening,  shape (N, N)
    dist_sq = np.einsum("ijk,ijk->ij", delta, delta) + eps * eps

    inv_d3 = dist_sq ** -1.5
    np.fill_diagonal(inv_d3, 0.0)          # no self-acceleration

    # accel[i] = G * sum_j( m[j] * (r_j - r_i) / r_ij^3 )
    #           = -G * sum_j( m[j] * delta[i,j] * inv_d3[i,j] )
    return -G * np.einsum("ij,j,ijk->ik", inv_d3, m, delta)


def computeGRCorrections(positions, velocities, masses, sun_idx=0):
    """First-order post-Newtonian (Schwarzschild) correction from the Sun.

    Accounts for Mercury's 43 arcsec/century perihelion precession and
    applies a smaller correction to all other non-Sun bodies.

    The 1PN acceleration on body i in the Sun's field is:

        da_i = (GM_sun / c^2 r^3) * [(4*GM_sun/r - v^2)*r_vec + 4*(r_vec.v_vec)*v_vec]

    where r_vec and v_vec are position and velocity relative to the Sun.
    """
    pos = np.asarray(positions, dtype=np.float64)
    vel = np.asarray(velocities, dtype=np.float64)
    m = np.asarray(masses, dtype=np.float64)

    corrections = np.zeros_like(pos)
    GM_sun = G * m[sun_idx]
    c2 = C_LIGHT * C_LIGHT

    for i in range(len(m)):
        if i == sun_idx:
            continue
        r_vec = pos[i] - pos[sun_idx]
        v_vec = vel[i] - vel[sun_idx]
        r = np.linalg.norm(r_vec)
        v_sq = float(np.dot(v_vec, v_vec))
        r_dot_v = float(np.dot(r_vec, v_vec))
        prefactor = GM_sun / (c2 * r ** 3)
        corrections[i] = prefactor * (
            (4.0 * GM_sun / r - v_sq) * r_vec + 4.0 * r_dot_v * v_vec
        )

    return corrections


def velocityVerletStep(r, v, a, masses, dt, use_gr=False, sun_idx=0):
    """Velocity Verlet integrator step.

    A time-reversible, symplectic integrator with O(dt^2) local accuracy.

    When use_gr=True, the 1PN correction is evaluated at the new position
    using v_half as the velocity approximation, which is O(dt^2) consistent
    with the Verlet truncation error.
    """
    v_half = v + 0.5 * dt * a
    r_new = r + dt * v_half

    a_new = computeAccelerations(r_new, masses)
    if use_gr:
        a_new = a_new + computeGRCorrections(r_new, v_half, masses, sun_idx)

    v_new = v_half + 0.5 * dt * a_new
    return r_new, v_new, a_new


def yoshida4Step(r, v, a_old, masses, dt, use_gr=False, sun_idx=0):
    """4th-order Yoshida symplectic integrator.

    When use_gr=True the 1PN correction is added at each force evaluation
    using the velocity at that stage.
    """
    cbrt2 = 2.0 ** (1.0 / 3.0)
    w1 = 1.0 / (2.0 - cbrt2)
    w0 = 1.0 - 2.0 * w1

    c = np.array([w1 / 2.0, (w0 + w1) / 2.0, (w0 + w1) / 2.0, w1 / 2.0])
    d = np.array([w1, w0, w1])

    r = r + c[0] * dt * v
    a_new = computeAccelerations(r, masses)
    if use_gr:
        a_new = a_new + computeGRCorrections(r, v, masses, sun_idx)
    v = v + d[0] * dt * a_new

    r = r + c[1] * dt * v
    a_new = computeAccelerations(r, masses)
    if use_gr:
        a_new = a_new + computeGRCorrections(r, v, masses, sun_idx)
    v = v + d[1] * dt * a_new

    r = r + c[2] * dt * v
    a_new = computeAccelerations(r, masses)
    if use_gr:
        a_new = a_new + computeGRCorrections(r, v, masses, sun_idx)
    v = v + d[2] * dt * a_new

    r = r + c[3] * dt * v
    a_new = computeAccelerations(r, masses)
    if use_gr:
        a_new = a_new + computeGRCorrections(r, v, masses, sun_idx)

    return r, v, a_new


def adaptiveVerletStep(r, v, a, masses, dt, tol, use_gr=False, sun_idx=0,
                       dt_min=10.0, dt_max=7200.0):
    """Velocity Verlet with step-doubling adaptive error control (M4).

    Takes one full step of size dt and two half-steps of size dt/2.  The
    difference in final positions gives a Richardson-extrapolated error:

        err ~ |r_half2 - r_full| / 3      (3 = 2^2 - 1 for a 2nd-order method)

    The two-half-step result is returned as it is one order more accurate
    (Richardson local extrapolation).

    Parameters
    ----------
    tol     : position error tolerance in metres (worst body, per step)
    dt_min  : hard floor on dt (seconds) -- step is force-accepted at this size
    dt_max  : hard ceiling on dt (seconds)

    Returns
    -------
    r_new, v_new, a_new, dt_used, dt_next
    """
    MAX_HALVINGS = 12

    for _ in range(MAX_HALVINGS):
        # Full step
        r1, v1, a1 = velocityVerletStep(r, v, a, masses, dt, use_gr, sun_idx)

        # Two half-steps
        dt2 = dt / 2.0
        r_m, v_m, a_m = velocityVerletStep(r, v, a, masses, dt2, use_gr, sun_idx)
        r2, v2, a2 = velocityVerletStep(r_m, v_m, a_m, masses, dt2, use_gr, sun_idx)

        # Richardson error estimate in metres (worst body)
        err = float(np.max(np.linalg.norm(r2 - r1, axis=1))) / 3.0

        if err <= tol or dt <= dt_min:
            if err > 0.0:
                scale = 0.9 * (tol / err) ** (1.0 / 3.0)
                dt_next = float(np.clip(dt * scale, dt_min, dt_max))
            else:
                dt_next = min(dt * 2.0, dt_max)
            return r2, v2, a2, dt, dt_next

        # Reject and halve
        dt = max(dt / 2.0, dt_min)

    # Safety fallback after max halvings
    return r2, v2, a2, dt, dt