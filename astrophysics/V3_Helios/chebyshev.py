"""
Chebyshev polynomial ephemeris cache for V3 Helios.

Workflow
--------
Build once (takes as long as the N-body simulation):

    python astrophysics/V3_Helios/chebyshev.py

This will:
  1. Run the N-body engine and cache the raw trajectory to rHistory.npz.
     (If rHistory.npz already exists and initial_conditions.json has not
     changed, the simulation is skipped.)
  2. Fit degree-DEGREE Chebyshev polynomials over SEGMENT_DAYS-day segments
     for every body and axis.
  3. Write cheb_table.npz.

After that, every call to evaluateAt() is a microsecond polynomial lookup
with no simulation involved.

Rebuild whenever initial_conditions.json changes (i.e. after running
loader.py for a new epoch):

    python astrophysics/V3_Helios/chebyshev.py
"""

import json
import sys
import numpy as np
from pathlib import Path

_BASE = Path(__file__).resolve().parent
_IC_PATH = _BASE / "initial_conditions.json"
_RHISTORY_PATH = _BASE / "rHistory.npz"
_CHEB_TABLE_PATH = _BASE / "cheb_table.npz"

# ---------------------------------------------------------------------------
# Fitting parameters — adjust for accuracy vs table size trade-off.
# Degree 16 over 32-day segments gives ~1 km accuracy for inner planets.
# ---------------------------------------------------------------------------
SEGMENT_DAYS = 32
DEGREE = 16

# Must match engine.py defaults.
_SIM_DT = 900.0          # integrator timestep (seconds)
_SIM_STORE_EVERY = 10    # trajectory stored every N steps
_DT_STORED = _SIM_DT * _SIM_STORE_EVERY   # 9 000 s between stored samples


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_newer(path: Path, reference: Path) -> bool:
    """Return True if *path* exists and is at least as new as *reference*."""
    return path.exists() and path.stat().st_mtime >= reference.stat().st_mtime


def _ensure_importable() -> None:
    """Add the project root to sys.path so package imports work."""
    project_root = str(_BASE.parents[2])   # …/Server
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def _run_simulation():
    """Run the N-body engine and return (names, rHistory ndarray)."""
    _ensure_importable()
    try:
        from astrophysics.V3_Helios.engine import runSimulation
    except ImportError:
        from engine import runSimulation

    print("Running N-body simulation (this happens once) …")
    results = runSimulation()
    return list(results["names"]), np.asarray(results["rHistory"])


def _get_rhistory():
    """Return (names, rHistory) from disk cache or by running the simulation."""
    if _is_newer(_RHISTORY_PATH, _IC_PATH):
        print(f"Loading cached trajectory from {_RHISTORY_PATH.name} …")
        data = np.load(_RHISTORY_PATH, allow_pickle=True)
        return list(data["names"]), data["rHistory"]

    names, rHistory = _run_simulation()
    np.savez_compressed(_RHISTORY_PATH, names=np.array(names), rHistory=rHistory)
    print(f"Trajectory cached → {_RHISTORY_PATH.name}")
    return names, rHistory


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def buildTable() -> None:
    """
    Fit Chebyshev polynomials to the simulated trajectory and save
    cheb_table.npz.  Safe to re-run; reuses rHistory.npz when fresh.
    """
    names, rHistory = _get_rhistory()

    ic = json.loads(_IC_PATH.read_text())
    epoch_utc = ic["epoch_utc"]

    n_samples, n_bodies, _ = rHistory.shape
    total_seconds = float(n_samples * _DT_STORED)

    # Uniform time grid for the stored trajectory (seconds from epoch)
    t_uniform = np.arange(n_samples, dtype=np.float64) * _DT_STORED

    segment_seconds = float(SEGMENT_DAYS * 86400)
    n_segments = int(np.ceil(total_seconds / segment_seconds))

    # Shape: (n_bodies, 3 axes, n_segments, DEGREE+1 coefficients)
    coefficients = np.zeros((n_bodies, 3, n_segments, DEGREE + 1), dtype=np.float64)
    seg_t_a = np.zeros(n_segments, dtype=np.float64)
    seg_t_b = np.zeros(n_segments, dtype=np.float64)

    for seg in range(n_segments):
        t_a = seg * segment_seconds
        t_b = min(t_a + segment_seconds, total_seconds)
        seg_t_a[seg] = t_a
        seg_t_b[seg] = t_b

        # Samples that fall within this segment (inclusive on both ends)
        mask = (t_uniform >= t_a) & (t_uniform <= t_b)

        # Guard: ensure enough points to fit the polynomial
        if mask.sum() < DEGREE + 1:
            idx_end = int(np.searchsorted(t_uniform, t_b, side="right"))
            idx_start = max(0, idx_end - (DEGREE + 2))
            mask = np.zeros(n_samples, dtype=bool)
            mask[idx_start:idx_end] = True

        # Map sample times to τ ∈ [-1, 1] over this segment
        tau = (2.0 * t_uniform[mask] - (t_a + t_b)) / (t_b - t_a)

        for body_idx in range(n_bodies):
            for axis in range(3):
                # Cast to float64 — longdouble (float128) is not supported by
                # numpy's linalg backend, and float64 is sufficient for fitting.
                vals = rHistory[mask, body_idx, axis].astype(np.float64)
                coefficients[body_idx, axis, seg, :] = (
                    np.polynomial.chebyshev.chebfit(tau, vals, DEGREE)
                )

    np.savez_compressed(
        _CHEB_TABLE_PATH,
        names=np.array(names),
        epoch_utc=np.array(epoch_utc),
        segment_seconds=np.array(segment_seconds),
        seg_t_a=seg_t_a,
        seg_t_b=seg_t_b,
        coefficients=coefficients,
        total_seconds=np.array(total_seconds),
    )
    print(
        f"Chebyshev table saved → {_CHEB_TABLE_PATH.name}\n"
        f"  Bodies: {n_bodies}   Segments: {n_segments}   "
        f"Degree: {DEGREE}   Span: {total_seconds / 86400:.1f} days"
    )


def _load_table():
    """Load and validate the Chebyshev table from disk."""
    if not _CHEB_TABLE_PATH.exists():
        raise FileNotFoundError(
            "Chebyshev table not found. Build it first:\n"
            "    python astrophysics/V3_Helios/chebyshev.py"
        )
    if not _is_newer(_CHEB_TABLE_PATH, _IC_PATH):
        raise RuntimeError(
            "Chebyshev table is stale — initial_conditions.json is newer. "
            "Rebuild with:\n    python astrophysics/V3_Helios/chebyshev.py"
        )
    return np.load(_CHEB_TABLE_PATH, allow_pickle=True)


def evaluateAt(t_sec: float) -> dict:
    """
    Return Cartesian positions (metres, ECLIPJ2000 frame) for all bodies
    at *t_sec* seconds after the simulation epoch.

    Parameters
    ----------
    t_sec : float
        Seconds elapsed since the epoch stored in initial_conditions.json.

    Returns
    -------
    dict
        Maps body name (str) → np.ndarray shape (3,) with [x, y, z] in metres.

    Raises
    ------
    ValueError
        If t_sec is outside the simulated time span.
    FileNotFoundError / RuntimeError
        If the Chebyshev table is missing or stale.
    """
    table = _load_table()
    names = list(table["names"])
    coefficients = table["coefficients"]     # (n_bodies, 3, n_segs, DEGREE+1)
    seg_t_a = table["seg_t_a"]
    seg_t_b = table["seg_t_b"]
    total_seconds = float(table["total_seconds"])
    segment_seconds = float(table["segment_seconds"])

    if t_sec < 0.0 or t_sec > total_seconds:
        raise ValueError(
            f"t_sec={t_sec:.0f} s is outside the simulated range "
            f"[0, {total_seconds:.0f}] s  ({total_seconds / 86400:.1f} days from epoch)."
        )

    # Locate the correct segment
    seg = min(int(t_sec / segment_seconds), len(seg_t_a) - 1)

    t_a = float(seg_t_a[seg])
    t_b = float(seg_t_b[seg])
    tau = float(np.clip((2.0 * t_sec - (t_a + t_b)) / (t_b - t_a), -1.0, 1.0))

    return {
        name: np.array([
            np.polynomial.chebyshev.chebval(tau, coefficients[body_idx, axis, seg, :])
            for axis in range(3)
        ])
        for body_idx, name in enumerate(names)
    }


if __name__ == "__main__":
    buildTable()
