import numpy as np

G = 6.67430e-11


def totalEnergy(r, v, m):
    kinetic = 0.5 * np.sum(m * np.sum(v * v, axis=1))

    potential = 0.0
    n = len(m)

    for i in range(n):
        for j in range(i + 1, n):
            diff = r[j] - r[i]
            dist = np.linalg.norm(diff)
            potential -= G * m[i] * m[j] / dist

    return kinetic + potential


def totalMomentum(v, m):
    return np.sum(m[:, None] * v, axis=0)


def totalAngularMomentum(r, v, m):
    return np.sum(m[:, None] * np.cross(r, v), axis=0)


def earthSunDistance(r, earthIndex=3, sunIndex=0):
    return np.linalg.norm(r[earthIndex] - r[sunIndex])