import numpy as np

G = 6.67430e-11


def computeAccelerations(positions, masses, eps=1e-9):
    # positions: (N,3)
    # masses: (N,)
    diff = positions[:, None, :] - positions[None, :, :]   # (N,N,3)
    # diff[i,j] = r_i - r_j (vector from body j to body i)

    distSq = np.sum(diff * diff, axis=2) + eps**2          # softening
    invDist3 = distSq ** -1.5                              # (N,N)

    # Zero out self-interaction
    np.fill_diagonal(invDist3, 0.0)

    # For each body i, sum the gravitational acceleration due to all j
    # a_i = -G * sum_j (m_j / |r_ij|^3) * (r_i - r_j)  [negative for attraction]
    # = G * sum_j (m_j / |r_ij|^3) * (r_j - r_i)
    # Must multiply by masses[j] (broadcasted along axis 1, not axis 0)
    weighted = -diff * (masses[None, :] * invDist3)[:, :, None]  # (N,N,3)

    # Sum over j
    return G * np.sum(weighted, axis=1)


def velocityVerletStep(r, v, a, masses, dt):
    v_half = v + 0.5 * dt * a
    r_new = r + dt * v_half

    a_new = computeAccelerations(r_new, masses)

    v_new = v_half + 0.5 * dt * a_new

    return r_new, v_new, a_new