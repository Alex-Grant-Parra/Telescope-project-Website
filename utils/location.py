"""
GPS Location Module
Retrieves GPS coordinates (latitude and longitude) and stores them in config/location.json
Supports both hardware GPS (via gpsd) and IP-based geolocation as fallback
"""

import os
import json
from datetime import datetime


def get_gps_from_hardware():
    """
    Attempt to get GPS coordinates from hardware GPS module using gpsd
    Returns: dict with lat, lon, timestamp if successful, None otherwise
    """
    try:
        from gps import gps, WATCH_ENABLE
        
        # Connect to gpsd
        session = gps(mode=WATCH_ENABLE)
        
        # Try to get a fix (timeout after a few attempts)
        for _ in range(10):
            report = session.next()
            if report['class'] == 'TPV':
                if hasattr(report, 'lat') and hasattr(report, 'lon'):
                    return {
                        'latitude': report.lat,
                        'longitude': report.lon,
                        'altitude': getattr(report, 'alt', None),
                        'timestamp': datetime.utcnow().isoformat(),
                        'source': 'hardware_gps'
                    }
        return None
    except ImportError:
        # gps library not installed
        return None
    except Exception as e:
        print(f"[location] Hardware GPS error: {e}")
        return None


def get_gps_from_ip():
    """
    Get approximate location from IP address using ip-api.com (free service)
    Returns: dict with lat, lon, timestamp if successful, None otherwise
    """
    try:
        import urllib.request
        import urllib.error
        
        # Using ip-api.com free service (no API key required)
        url = "http://ip-api.com/json/"
        
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            
            if data.get('status') == 'success':
                return {
                    'latitude': data.get('lat'),
                    'longitude': data.get('lon'),
                    'city': data.get('city'),
                    'region': data.get('regionName'),
                    'country': data.get('country'),
                    'isp': data.get('isp'),
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'ip_geolocation'
                }
        return None
    except Exception as e:
        print(f"[location] IP geolocation error: {e}")
        return None


def update_location_config():
    """
    Update the location configuration file with current GPS coordinates
    Tries hardware GPS first, falls back to IP geolocation
    """
    config_dir = "config"
    config_path = os.path.join(config_dir, "location.json")
    
    # Ensure config directory exists
    os.makedirs(config_dir, exist_ok=True)
    
    print("[location] Attempting to retrieve GPS coordinates...")
    
    # Try hardware GPS first
    location_data = get_gps_from_hardware()
    
    # Fallback to IP-based geolocation
    if location_data is None:
        print("[location] Hardware GPS not available, using IP geolocation...")
        location_data = get_gps_from_ip()
    
    if location_data is None:
        print("[location] Failed to retrieve location data")
        return False
    
    # Add metadata
    location_data['last_updated'] = datetime.utcnow().isoformat()
    
    # Save to file
    try:
        with open(config_path, 'w') as f:
            json.dump(location_data, f, indent=2)
        
        source = location_data.get('source', 'unknown')
        lat = location_data.get('latitude', 'N/A')
        lon = location_data.get('longitude', 'N/A')
        print(f"[location] Location updated successfully via {source}: {lat}, {lon}")
        return True
    except Exception as e:
        print(f"[location] Failed to save location data: {e}")
        return False


def get_current_location():
    """
    Read the current location from the config file
    Returns: dict with location data if file exists, None otherwise
    """
    config_path = os.path.join("config", "location.json")
    
    if not os.path.exists(config_path):
        return None
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[location] Failed to read location data: {e}")
        return None


if __name__ == "__main__":
    # Test the location module
    print("Testing location module...")
    update_location_config()
    
    location = get_current_location()
    if location:
        print(f"Current location: {json.dumps(location, indent=2)}")
    else:
        print("No location data available")
