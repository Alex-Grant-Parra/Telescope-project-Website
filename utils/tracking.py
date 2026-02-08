from utils.location import get_current_location
from utils.Tools import hour_angle


def trackCoordinates(name, ra, dec, mag):
    print(f"Tracking object: {name}, RA: {ra}, Dec: {dec}, Mag: {mag}")
    
    # Get current location from config
    location = get_current_location()
    if location is None:
        print("[tracking] Warning: Location data not available. Cannot calculate hour angle.")
        return
    
    longitude = location.get('longitude')
    latitude = location.get('latitude')

    # Convert RA to hour angle using current location
    ha = hour_angle(ra, longitude)