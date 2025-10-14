import pickle
import pprint
from pathlib import Path

P = Path("instance") / "ephemerisData" / "pickled" / "moon.pkl"
if not P.exists():
    raise SystemExit(f"Pickle not found: {P}")

with open(P, "rb") as f:
    data = pickle.load(f)

print("TYPE:", type(data))
if isinstance(data, dict):
    print("LEN:", len(data))
    print("\nDICT KEYS (up to 10):")
    for k in list(data.keys())[:10]:
        v = data[k]
        print(f"Key: {k!r} -> type={type(v)}, len={len(v) if hasattr(v,'__len__') else '?'}")
        if hasattr(v, '__len__') and len(v) > 0:
            print('  First item sample:')
            pprint.pprint(v[0])
        print('---')
else:
    try:
        print('LEN:', len(data))
    except Exception:
        pass
    print('\nSAMPLE (first 5 items):')
    for i, item in enumerate(data[:5]):
        print(f'[{i}] type={type(item)}, len={len(item) if hasattr(item, "__len__") else "?"}')
        pprint.pprint(item)
        print('---')

    if len(data) > 0:
        first = data[0]
        print('\nFirst item field types:')
        for idx, field in enumerate(first):
            print(idx, type(field), repr(field)[:120])
