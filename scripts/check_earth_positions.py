from astrophysics.V2_VSOP87A.loader import load_planets
ps = load_planets()
if 'Earth' in ps:
    e = ps['Earth']
    print('Earth sample position at JD1:')
    print(e.position(2451545.0))
    print('Earth sample position at JD2:')
    print(e.position(2460000.5))
else:
    print('Earth not found')
