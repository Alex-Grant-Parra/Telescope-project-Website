import os
import pickle

RAW_DIR = r"instance\ephemerisData\raw"
PICKLE_DIR = r"instance\ephemerisData\pickled"
os.makedirs(PICKLE_DIR, exist_ok=True)

def parse_vsop87(file_path):
    # Parse a VSOP87A raw file into X/Y/Z series terms (simplified A,B,C triples)
    series = {"X": [], "Y": [], "Z": []}
    current_key = None
    with open(file_path, "r") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("VSOP87") and "VARIABLE" in line:
                # Identify variable number
                parts = line.split()
                try:
                    var_index = int(parts[parts.index("VARIABLE") + 1])
                except Exception:
                    current_key = None
                    continue
                current_key = {1: "X", 2: "Y", 3: "Z"}.get(var_index)
                continue
            # skip non-data lines
            if current_key is None:
                continue
            parts = line.split()
            # Need at least 5 trailing float columns, attempt to parse last 5
            if len(parts) < 5:
                continue
            tail = parts[-5:]
            try:
                f1, f2, f3, phase, freq = map(float, tail)
            except ValueError:
                continue
            # Use f3 as amplitude (A) producing non-zero contributions
            A = f3
            B = phase
            C = freq
            series[current_key].append((A, B, C))
    return series

def parse_elp82b(raw_dir):
    data = {}
    for fn in sorted(os.listdir(raw_dir)):
        if not fn.startswith("ELP"):
            continue
        series = os.path.splitext(fn)[0]
        data[series] = []
        with open(os.path.join(raw_dir, fn), "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 3:
                    continue
                try:
                    data[series].append(tuple(map(float, parts[:3])))
                except ValueError:
                    continue
    return data

def save_pickle(data, file_name):
    with open(os.path.join(PICKLE_DIR, file_name), "wb") as f:
        pickle.dump(data, f)

def main():
    # Map common file extensions to planet names
    ext_to_name = {
        'mer': 'Mercury',
        'ven': 'Venus',
        'ear': 'Earth',
        'mar': 'Mars',
        'jup': 'Jupiter',
        'sat': 'Saturn',
        'ura': 'Uranus',
        'nep': 'Neptune',
    }

    vsop = {}
    for fn in sorted(os.listdir(RAW_DIR)):
        parts = fn.split('.')
        if len(parts) < 2:
            continue
        ext = parts[-1].lower()
        if ext in ext_to_name:
            planet_name = ext_to_name[ext]
            vsop[planet_name] = parse_vsop87(os.path.join(RAW_DIR, fn))
    save_pickle(vsop, "vsop.pkl")
    print("VSOP87 pickled.")

    moon = parse_elp82b(RAW_DIR)
    save_pickle(moon, "moon.pkl")
    print("Moon data pickled.")

if __name__ == "__main__":
    main()
