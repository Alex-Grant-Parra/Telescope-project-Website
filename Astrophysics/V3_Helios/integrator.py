import numpy as np

G = 6.67430e-11


def computeAccelerations(positions, masses, eps=1e-9):
    # positions: (N,3)
    # masses: (N,)
    diff = positions[:, None, :] - positions[None, :, :]   # (N,N,3)

    distSq = np.sum(diff * diff, axis=2) + eps**2          # softening
    invDist3 = distSq ** -1.5                              # (N,N)

    # Zero out self-interaction
    np.fill_diagonal(invDist3, 0.0)

    # Multiply each j by its mass
    weighted = diff * (masses * invDist3)[:, :, None]      # (N,N,3)

    # Sum over j
    return G * np.sum(weighted, axis=1)


def velocityVerletStep(r, v, a, masses, dt):
    v_half = v + 0.5 * dt * a
    r_new = r + dt * v_half

    a_new = computeAccelerations(r_new, masses)

    v_new = v_half + 0.5 * dt * a_new

    return r_new, v_new, a_new