from .convert import convert
from .ephemeris import get_positions


def getAllCelestialData(year, month, day, hour: int = 0, minute: int = 0, second: float = 0.0):
    celestial_positions = get_positions(year, month, day, hour, minute, second)
    formatted = {}

    for body_name, values in celestial_positions.items():
        ra_deg = values.get("ra_deg")
        dec_deg = values.get("dec_deg")
        if ra_deg is None or dec_deg is None:
            continue

        body_data = {
            "ra": convert.DegreesToHMS(ra_deg),
            "dec": convert.DegreesToDMS(dec_deg),
        }

        visual_mag = values.get("visual_mag")
        if visual_mag is not None:
            body_data["vmag"] = float(visual_mag)

        formatted[body_name.lower()] = body_data

    return formatted
