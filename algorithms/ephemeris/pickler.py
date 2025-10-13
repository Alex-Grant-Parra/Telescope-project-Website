import os
import pickle

RAW_DIR = r"instance\ephemerisData\raw"
PICKLE_DIR = r"instance\ephemerisData\pickled"
os.makedirs(PICKLE_DIR, exist_ok=True)

def parse_vsop87(file_path):
    data = {}
    current_series = None
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # detect series header like L0, L1, B0, etc.
            if line.startswith(("L", "B", "R")) and line[1].isdigit():
                current_series = line
                data[current_series] = []
                continue
            parts = line.split()
            if len(parts) < 3 or current_series is None:
                continue
            try:
                data[current_series].append(tuple(map(float, parts[:3])))
            except ValueError:
                continue
    return data

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
    vsop = {}
    for fn in os.listdir(RAW_DIR):
        if fn.endswith(".mer"):
            planet = os.path.splitext(fn)[0]
            vsop[planet] = parse_vsop87(os.path.join(RAW_DIR, fn))
    save_pickle(vsop, "vsop.pkl")
    print("VSOP87 pickled.")

    moon = parse_elp82b(RAW_DIR)
    save_pickle(moon, "moon.pkl")
    print("Moon data pickled.")

if __name__ == "__main__":
    main()
