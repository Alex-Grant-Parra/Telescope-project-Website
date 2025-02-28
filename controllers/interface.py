from flask import Blueprint, render_template, request, jsonify

# Define blueprint with URL prefix
interface_bp = Blueprint('interface', __name__, url_prefix='/interface')

# Route for the interface page
@interface_bp.route('/')
def interface():
    return render_template('interface.html')

# Route for camera settings update
@interface_bp.route('/update_camera', methods=['POST'])
def update_camera():
    data = request.json
    print("Received Camera Settings:", data)  # Debugging output
    shutter_speed = data.get('shutterSpeed', 'Unknown')  # Get the shutter speed from the request
    print(f"Shutter Speed: {shutter_speed}")  # Debugging output
    return jsonify({"status": "success", "message": "Settings updated"})
