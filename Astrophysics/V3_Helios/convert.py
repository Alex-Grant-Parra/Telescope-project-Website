"""Convert ASTRA engine output positions into RA/DEC coordinates.

Usage (examples):
  # Convert an existing results file produced by numpy.savez
  python converty.py --input results.npz --observer earth_moon --out radec_output.npz

  # Run a quick simulation and convert (runs engine.runSimulation)
  python converty.py --run --steps 1000 --dt 900 --out radec_output.npz

The script outputs an .npz containing arrays of `ra_deg`, `dec_deg`, and `dist_m`
for each body (keys like `mercury_ra_deg`, `mercury_dec_deg`, `mercury_dist_m`).
"""

from pathlib import Path
import argparse
import numpy as np
import json
from typing import Dict, Any
import sys

# Ensure project root is on sys.path so we can import the engine reliably
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def ecliptic_to_equatorial(vecs: np.ndarray, epsilon_deg: float = 23.439291111) -> np.ndarray:
    """Rotate from ecliptic (ECLIPJ2000) to equatorial (ICRS-like) coordinates.

    vecs: (..., 3) array of Cartesian coordinates in meters.
    Returns array of same shape in equatorial frame.
    """
    eps = np.deg2rad(epsilon_deg)
    R = np.array([
        [1.0, 0.0, 0.0],
        [0.0, np.cos(eps), -np.sin(eps)],
        [0.0, np.sin(eps), np.cos(eps)],
    ], dtype=float)
    return vecs @ R.T


def cartesian_to_radec(vecs: np.ndarray) -> Dict[str, np.ndarray]:
    """Convert cartesian vectors (equatorial) to RA/DEC (radians) and distance (m).

    vecs: (N,3)
    returns dict with 'ra', 'dec', 'dist'
    """
    x = vecs[:, 0]
    y = vecs[:, 1]
    z = vecs[:, 2]
    r = np.linalg.norm(vecs, axis=1)
    # RA in [0,2pi)
    ra = np.arctan2(y, x) % (2.0 * np.pi)
    # DEC in [-pi/2, pi/2]
    dec = np.arcsin(np.clip(z / r, -1.0, 1.0))
    return {"ra": ra, "dec": dec, "dist": r}


def convert_results_to_radec(results: Dict[str, Any], observer_name: str = "earth_moon") -> Dict[str, Dict[str, np.ndarray]]:
    """Convert a simulation `results` dict (as returned by runSimulation) to RA/DEC.

    results must contain at least `names` (list of body names) and `rHistory`
    (shape: samples x n_bodies x 3) with positions in meters in ECLIPJ2000.
    observer_name selects which body is used as observer origin (default: `earth_moon`).
    Returns mapping body -> {'ra':..., 'dec':..., 'dist':...} with arrays length samples.
    """
    names = list(results["names"])
    rHist = np.asarray(results["rHistory"])  # (samples, n, 3)
    if rHist.ndim != 3:
        raise ValueError("rHistory must be a 3D array (samples, bodies, 3)")
    samples, n_bodies, _ = rHist.shape

    if observer_name not in names:
        raise ValueError(f"Observer '{observer_name}' not in names: {names}")

    obs_idx = names.index(observer_name)

    outputs: Dict[str, Dict[str, np.ndarray]] = {}

    for i, body in enumerate(names):
        if body == observer_name:
            continue

        # vectors from observer to body in ecliptic frame
        vecs = rHist[:, i, :] - rHist[:, obs_idx, :]

        # convert to equatorial frame
        eq = ecliptic_to_equatorial(vecs)

        # convert to RA/DEC
        sph = cartesian_to_radec(eq)

        outputs[body] = {
            "ra_rad": sph["ra"],
            "dec_rad": sph["dec"],
            "dist_m": sph["dist"],
            # convenience in degrees
            "ra_deg": np.degrees(sph["ra"]),
            "dec_deg": np.degrees(sph["dec"]),
        }

    return outputs


def _save_outputs_npz(outputs: Dict[str, Dict[str, np.ndarray]], out_path: Path):
    # Flatten to key arrays like mercury_ra_deg
    to_save: Dict[str, np.ndarray] = {}
    for body, data in outputs.items():
        base = body.replace(" ", "_")
        to_save[f"{base}_ra_deg"] = data["ra_deg"]
        to_save[f"{base}_dec_deg"] = data["dec_deg"]
        to_save[f"{base}_dist_m"] = data["dist_m"]

    np.savez_compressed(out_path, **to_save)


def _save_outputs_json(outputs: Dict[str, Dict[str, np.ndarray]], out_path: Path):
    json_out = {}
    for body, data in outputs.items():
        json_out[body] = {
            "ra_deg": data["ra_deg"].tolist(),
            "dec_deg": data["dec_deg"].tolist(),
            "dist_m": data["dist_m"].tolist(),
        }
    with open(out_path, "w") as f:
        json.dump(json_out, f)


def main():
    parser = argparse.ArgumentParser(description="Convert ASTRA engine output to RA/DEC time series")
    parser.add_argument("--input", "-i", help=".npz results file produced by engine (optional)")
    parser.add_argument("--out", "-o", default=None, help="output .npz or .json path (omit to print to stdout)")
    parser.add_argument("--format", "-f", choices=["npz", "json"], default="npz")
    parser.add_argument("--print", action="store_true", help="print RA/DEC to stdout as CSV and do not write files")
    parser.add_argument("--final", action="store_true", help="print only the final sample's RA/DEC (or the sample given by --index)")
    parser.add_argument("--index", type=int, default=None, help="print the RA/DEC at a specific sample index (0-based). Overrides --final if provided.")
    parser.add_argument("--body", type=str, default=None, help="restrict output to a single body name")
    parser.add_argument("--observer", default="earth_moon", help="observer body name (default: earth_moon)")
    parser.add_argument("--run", action="store_true", help="run engine.runSimulation() if no input file provided")
    parser.add_argument("--steps", type=int, default=None, help="pass to runSimulation steps")
    parser.add_argument("--dt", type=float, default=None, help="pass to runSimulation dt")

    args = parser.parse_args()

    results = None

    if args.input:
        data = np.load(args.input, allow_pickle=True)
        # Expect arrays and possibly names; try to reconstruct results dict
        if "names" in data:
            # saved full results
            results = {k: data[k] for k in data.files}
        else:
            raise ValueError("Input .npz must be a full engine results archive containing 'names' and 'rHistory'")

    # If no input provided, run the engine by default (convenience)
    if not args.input and not args.run:
        args.run = True

    if results is None and args.run:
        # Import engine from package path after ensuring PROJECT_ROOT is on sys.path
        try:
            from Astrophysics.V3_Helios import engine as engine_module
        except Exception:
            # fallback to plain module import when running from package root
            import engine as engine_module

        kwargs = {}
        if args.steps is not None:
            kwargs["steps"] = args.steps
        if args.dt is not None:
            kwargs["dt"] = args.dt

        results = engine_module.runSimulation(**kwargs)

    if results is None:
        parser.error("No input provided and --run not specified. Provide --input or --run.")

    outputs = convert_results_to_radec(results, observer_name=args.observer)

    # If user requested printing or did not supply an output path, print CSV to stdout
    if args.print or not args.out:
        samples = None
        for body, data in outputs.items():
            if samples is None:
                samples = len(data["ra_deg"])

        # Determine target sample index
        if args.index is not None:
            idx = args.index
            if idx < 0 or idx >= samples:
                raise SystemExit(f"Requested index {idx} out of range (0..{samples-1})")
            single_sample_mode = True
        elif args.final:
            idx = samples - 1
            single_sample_mode = True
        else:
            idx = None
            single_sample_mode = False

        # If body filter provided, validate
        selected_bodies = list(outputs.keys())
        if args.body:
            if args.body not in outputs:
                raise SystemExit(f"Requested body '{args.body}' not found. Available: {list(outputs.keys())}")
            selected_bodies = [args.body]

        # Single-sample print (final or index)
        if single_sample_mode:
            print("body,ra_deg,dec_deg,dist_m")
            for body in selected_bodies:
                data = outputs[body]
                print(f"{body},{data['ra_deg'][idx]:.8f},{data['dec_deg'][idx]:.8f},{data['dist_m'][idx]:.6e}")
        else:
            # full time-series CSV
            print("sample_index,body,ra_deg,dec_deg,dist_m")
            for i in range(samples):
                for body in selected_bodies:
                    data = outputs[body]
                    print(f"{i},{body},{data['ra_deg'][i]:.8f},{data['dec_deg'][i]:.8f},{data['dist_m'][i]:.6e}")
    else:
        out_path = Path(args.out)
        if args.format == "npz":
            _save_outputs_npz(outputs, out_path)
        else:
            _save_outputs_json(outputs, out_path)

        print(f"Wrote RA/DEC output to {out_path}")


if __name__ == "__main__":
    main()
