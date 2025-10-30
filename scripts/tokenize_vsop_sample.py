fn='instance/ephemerisData/raw/VSOP87A.ear'
with open(fn,'r') as f:
    for i in range(20):
        line=f.readline()
        if not line:
            break
        toks=line.strip().split()
        print(i+1, toks)
