from flask import Blueprint, render_template, request, jsonify

# Define constants for valid ranges
ISO_MIN = 50
ISO_MAX = 12800
SHUTTER_MIN = 1 / 4000
SHUTTER_MAX = 30
APERTURE_MIN = 1.0
APERTURE_MAX = 22.0
WB_MIN = 2500
WB_MAX = 10000
FOCUS_MIN = 1
FOCUS_MAX = 1000

# Define the blueprint for interface routes
interface_bp = Blueprint('interface', __name__)

# Route to render the interface
@interface_bp.route("/interface")
def interface():
    # Pass the constants to the template
    return render_template("interface.html", 
                           ISO_MIN=ISO_MIN, ISO_MAX=ISO_MAX, 
                           SHUTTER_MIN=SHUTTER_MIN, SHUTTER_MAX=SHUTTER_MAX,
                           APERTURE_MIN=APERTURE_MIN, APERTURE_MAX=APERTURE_MAX,
                           WB_MIN=WB_MIN, WB_MAX=WB_MAX,
                           FOCUS_MIN=FOCUS_MIN, FOCUS_MAX=FOCUS_MAX)

# Route to handle AJAX requests and update camera settings
@interface_bp.route("/update_camera_setting", methods=["POST"])
def update_camera_setting():
    data = request.get_json()  # Get the data from the frontend (camera setting and new value)
    setting = data.get('setting')
    value = data.get('value')

    # Update the camera setting here as per your application's logic
    # For example, you might want to save it to a database or update a variable
    print(f"Updated {setting} to {value}")

    # Respond with a message
    return jsonify({"message": f"{setting} updated to {value}"})
