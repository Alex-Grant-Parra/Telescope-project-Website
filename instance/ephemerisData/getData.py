import urllib.request

# VSOP87A planet files
vsop = [
    "https://ftp.imcce.fr/pub/ephem/planets/vsop87/VSOP87A.mer",
    "https://ftp.imcce.fr/pub/ephem/planets/vsop87/VSOP87A.ven",
    "https://ftp.imcce.fr/pub/ephem/planets/vsop87/VSOP87A.ear",
    "https://ftp.imcce.fr/pub/ephem/planets/vsop87/VSOP87A.mar",
    "https://ftp.imcce.fr/pub/ephem/planets/vsop87/VSOP87A.jup",
    "https://ftp.imcce.fr/pub/ephem/planets/vsop87/VSOP87A.sat",
    "https://ftp.imcce.fr/pub/ephem/planets/vsop87/VSOP87A.ura",
    "https://ftp.imcce.fr/pub/ephem/planets/vsop87/VSOP87A.nep"
]

# ELP Moon files
elp = [f"https://ftp.imcce.fr/pub/ephem/moon/elp82b/ELP{i}" for i in range(1, 37)]
elp += [
    "https://ftp.imcce.fr/pub/ephem/moon/elp82b/elp82b_1",
    "https://ftp.imcce.fr/pub/ephem/moon/elp82b/elp82b_2"
]

# Download VSOP files
for url in vsop:
    print("Downloading", url.split("/")[-1])
    urllib.request.urlretrieve(url, url.split("/")[-1])

# Download and merge ELP files
with open("ELP82B.moon", "wb") as out:
    for url in elp:
        print("Merging", url.split("/")[-1])
        tmp_file = url.split("/")[-1]
        urllib.request.urlretrieve(url, tmp_file)
        with open(tmp_file, "rb") as f:
            out.write(f.read())
