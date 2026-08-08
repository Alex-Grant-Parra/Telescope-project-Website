from .V1_Keplarian.astroTools import getAllCelestialData as _get_v1_celestial_data
from .V2_VSOP87A import getAllCelestialData as _get_v2_celestial_data
from .V3_Helios import getAllCelestialData as _get_v3_celestial_data

# Change this value to "v1", "v2", or "v3" to switch the planetary model.
PLANETARY_MODEL = "v3"

_MODEL_LOADERS = {
    "v1": _get_v1_celestial_data,
    "v2": _get_v2_celestial_data,
    "v3": _get_v3_celestial_data,
}


def getAllCelestialData(year, month, day, hour: int = 0, minute: int = 0, second: float = 0.0):
    loader = _MODEL_LOADERS.get(PLANETARY_MODEL)
    if loader is None:
        raise ValueError(f"Unsupported planetary model: {PLANETARY_MODEL}")
    return loader(year, month, day, hour, minute, second)