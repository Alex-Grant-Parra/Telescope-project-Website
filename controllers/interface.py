import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Blueprint, render_template, request, jsonify, session
from algorithms.convert import convert
# from camera.cameraController import Camera # Redundant import, using Cameralink instead

from datetime import datetime
import time

from telescopeLink import Cameralink

interface_bp = Blueprint("interface", __name__, url_prefix="/interface")

@interface_bp.route("/")
def interface():
    return render_template("interface.html")

@interface_bp.route("/update_camera", methods=["POST"])
def update_camera():
    data = request.json
    # print("Received Camera Settings:", data)
    response = {"status": "success", "message": "Settings updated"}

    # Set shutter speed if provided
    shutter_speed = data.get("shutterSpeed")
    iso = data.get("iso")

    print(shutter_speed, iso)
    if shutter_speed:
        try:
            # Set the shutter speed using Camera class
            print("Changing shutterspeed")
            Cameralink.setSettings(["/main/capturesettings/shutterspeed", shutter_speed])
        except Exception as e:
            response = {"status": "error", "message": f"Failed to set shutter speed: {e}"}
            print(response)
            return jsonify(response)

    # Handling ISO
    if iso:
        try:
            print("Changing iso")
            Cameralink.setSettings(["/main/imgsettings/iso", iso])
        except Exception as e:
            response = {"status": "error", "message": f"Failed to set ISO: {e}"}
            print(response)
            return jsonify(response)

    return jsonify(response)

@interface_bp.route("/search_object", methods=["POST"])
def search_object():
    from algorithms2 import getAllCelestialData
    from models.tables import HDSTARtable, IndexTable, NGCtable
    data = request.json
    search_value = data.get("searchValue", "").strip()

    print(f"Received search query: {search_value}")

    result = None

    searchableCelestials = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune"]
    try:
        # Determine the table based on prefix or content
        if search_value.startswith("HD"):
            # search_value = "HD" + search_value[2:]  # Ensure full name format
            print(f"Querying HDSTARtable for {search_value}")
            result = HDSTARtable.query_by_name(search_value)
            print(result)

        elif search_value.startswith("NGC"):
            print(f"Querying NGCtable for {search_value}")
            result = NGCtable.query_by_name(search_value)

        elif search_value.startswith("IC"):
            print(f"Querying IndexTable for {search_value}")
            result = IndexTable.query_by_name(search_value)

        elif search_value.upper().startswith("M") and len(search_value) > 1 and search_value[1:].isdigit():
            # Handle Messier objects (e.g., "M1", "m42", "M104")
            messier_designation = search_value.upper()
            print(f"Querying NGCtable for Messier object {messier_designation}")
            result = NGCtable.query_by_messier(messier_designation)

        elif search_value.lower() in searchableCelestials:
            search_value = search_value.lower()
            now = datetime.utcnow()
            CelestialData = getAllCelestialData(now.year, now.month, now.day)

            if search_value in CelestialData:
                formattedData = format_celestial_data(search_value, CelestialData[search_value])
                print(formattedData)
                result = formattedData
            else:
                print("Celestial object not found.")

        else:
            # Try searching by common name in NGCtable
            print(f"Searching for common name: {search_value}")
            result = NGCtable.query_by_common_name(search_value)
            
            if not result:
                print("Object not found by common name")
                return jsonify({"status": "error", "message": "Object not found"})

    except ValueError as e:
        print(f"Error during search: {e}")
        return jsonify({"status": "error", "message": "Invalid search format"})

    # If result is found, process the result and return as JSON
    if result:
        # Check if result is a dictionary
        if isinstance(result, dict):
            # If it's a dictionary, return it directly
            result_data = result
        else:
            # If it's an SQLAlchemy model instance, use dynamic reflection
            result_data = {column: getattr(result, column) for column in result.__table__.columns.keys()}

        name = result_data.get('Name', "Null")
        ra = float(result_data.get('RA', 0))  # Default to 0 if RA is missing or None
        dec = float(result_data.get('DEC', 0))  # Default to 0 if DEC is missing or None
        mag = result_data.get('V-Mag', 0)  # Default to 0 if V-Mag is missing or None

        # print(f"\n[TRACKING] {name} at RA: {ra}°, DEC: {dec}° with magnitude {mag}.\n", flush=True)

        # session["selectedObject"] = { # Adds to flask's session
        #     "name": name,
        #     "ra": ra,
        #     "dec": dec,
        #     "mag": mag
        # }

        return jsonify({"status": "success", "data": result_data})
    else:
        print("Object not found")
        return jsonify({"status": "error", "message": "Object not found"})
    


def format_celestial_data(name, data):
    return {
        "Name": name.capitalize(),
        "RA": convert.HrMinSecToDegrees(data['ra'][0], data['ra'][1], data['ra'][2]),  # Formatting RA
        "DEC": convert.HrMinSecToDegrees(data['dec'][0], data['dec'][1], data['dec'][2]),  # Formatting DEC
        "V-Mag": data["vmag"]
    }

@interface_bp.route("/get_camera_choices")
def get_camera_choices():
    # # Map setting names to gphoto2 config paths
    # settings = {
    #     "shutterSpeed": "/main/capturesettings/shutterspeed",
    #     "iso": "/main/imgsettings/iso",
    #     # Add more settings as needed
    # }
    # choices = {}
    # start = time.time()
    # for label, path in settings.items():
    #     result = Camera.getSettingChoices(label, path)
    #     choices[label] = result if result else []
    # print(f"get_camera_choices took {time.time() - start:.2f} seconds")
    choices = Cameralink.getSettings()
    return jsonify(choices)

@interface_bp.route("/take_photo", methods=["POST"])
def take_photo():
    # Set your camera photos folder path here
    # photos_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "camera_photos")
    # os.makedirs(photos_folder, exist_ok=True)
    try:
        from flask_login import current_user
        if current_user.is_authenticated:
            currentId = current_user.get_id()
            print(f"User ID: {currentId}")

            try:
                print(Cameralink.capturePhoto(currentId))

                return jsonify({"status": "success"})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)})
        else:
            return jsonify({"status": "error", "message": "Must be logged in to take photos"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    

@interface_bp.route("/get_telescopes", methods=["GET"])
def get_telescopes():
    """
    Get all available telescopes from the database
    """
    try:
        from models.tables import Telescope
        telescopes = Telescope.get_all_telescopes()
        
        telescope_list = []
        for telescope in telescopes:
            telescope_data = {column: getattr(telescope, column) for column in telescope.__table__.columns.keys()}
            
            # Add online status
            telescope_data['online'] = Telescope.is_telescope_online(telescope_data.get('telescopeId', ''))
            telescope_list.append(telescope_data)
        
        return jsonify({"status": "success", "telescopes": telescope_list})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to get telescopes: {str(e)}"})

@interface_bp.route("/select_telescope", methods=["POST"])
def select_telescope():
    """
    Set the selected telescope in the user's session
    """
    try:
        data = request.json
        telescope_id = data.get("telescopeId")
        
        if not telescope_id:
            return jsonify({"status": "error", "message": "Telescope ID is required"})
        
        from models.tables import Telescope
        telescope = Telescope.get_telescope_by_id(telescope_id)
        
        if not telescope:
            return jsonify({"status": "error", "message": "Telescope not found"})
        
        # Store selected telescope in session
        session['selected_telescope'] = {
            'telescopeId': telescope.get('telescopeId'),
            'ipAddress': telescope.get('ipAddress'),
            'firmwareVersion': telescope.get('firmwareVersion'),
            'capabilities': telescope.get('capabilities'),
            'online': Telescope.is_telescope_online(telescope.get('telescopeId', ''))
        }
        
        return jsonify({
            "status": "success", 
            "message": f"Selected telescope: {telescope_id}",
            "telescope": session['selected_telescope']
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to select telescope: {str(e)}"})

@interface_bp.route("/get_selected_telescope", methods=["GET"])
def get_selected_telescope():
    """
    Get the currently selected telescope from session
    """
    selected_telescope = session.get('selected_telescope')
    if selected_telescope:
        return jsonify({"status": "success", "telescope": selected_telescope})
    else:
        return jsonify({"status": "success", "telescope": None, "message": "No telescope selected"})

@interface_bp.route("/add_telescope", methods=["POST"])
def add_telescope():
    """
    Add a new telescope to the database
    """
    try:
        data = request.json
        telescope_id = data.get("telescopeId")
        ip_address = data.get("ipAddress")
        firmware_version = data.get("firmwareVersion")
        capabilities = data.get("capabilities")
        
        # Validate required fields
        if not all([telescope_id, ip_address, firmware_version, capabilities]):
            return jsonify({
                "status": "error", 
                "message": "All fields are required: telescopeId, ipAddress, firmwareVersion, capabilities"
            })
        
        from models.tables import Telescope
        result = Telescope.add_telescope(telescope_id, ip_address, firmware_version, capabilities)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to add telescope: {str(e)}"})

@interface_bp.route("/remove_telescope", methods=["POST"])
def remove_telescope():
    """
    Remove a telescope from the database
    """
    try:
        data = request.json
        telescope_id = data.get("telescopeId")
        
        if not telescope_id:
            return jsonify({"status": "error", "message": "Telescope ID is required"})
        
        from models.tables import Telescope
        result = Telescope.remove_telescope(telescope_id)
        
        # If we removed the currently selected telescope, clear the session
        if result.get("status") == "success" and session.get('selected_telescope', {}).get('telescopeId') == telescope_id:
            session.pop('selected_telescope', None)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to remove telescope: {str(e)}"})

@interface_bp.route("/update_telescope_heartbeat", methods=["POST"])
def update_telescope_heartbeat():
    """
    Update the last seen timestamp for a telescope (heartbeat)
    """
    try:
        data = request.json
        telescope_id = data.get("telescopeId")
        
        if not telescope_id:
            return jsonify({"status": "error", "message": "Telescope ID is required"})
        
        from models.tables import Telescope
        result = Telescope.update_last_seen(telescope_id)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to update telescope heartbeat: {str(e)}"})