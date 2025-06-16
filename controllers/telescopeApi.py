from flask import Blueprint, request, jsonify
import time
from db import db
from models.telescope import Telescope  # adjust import path if needed

telescopeApi_bp = Blueprint('telescopeApi', __name__, url_prefix='/api')

@telescopeApi_bp.route('/registerTelescope', methods=['POST'])
def registerTelescope():
    data = request.json
    requiredFields = ["telescopeId", "ipAddress", "firmwareVersion"]
    if not all(field in data for field in requiredFields):
        return jsonify({"error": "Missing required fields"}), 400

    telescopeId = data["telescopeId"]
    capabilities = ','.join(data.get("capabilities", []))  # store as CSV string
    now = time.time()

    # Query existing telescope
    telescope = Telescope.query.filter_by(telescopeId=telescopeId).first()

    if telescope:
        # Update existing telescope
        telescope.ipAddress = data["ipAddress"]
        telescope.firmwareVersion = data["firmwareVersion"]
        telescope.capabilities = capabilities
        telescope.lastSeen = now
    else:
        # Create new telescope entry
        telescope = Telescope(
            telescopeId=telescopeId,
            ipAddress=data["ipAddress"],
            firmwareVersion=data["firmwareVersion"],
            capabilities=capabilities,
            lastSeen=now
        )
        db.session.add(telescope)

    db.session.commit()
    return jsonify({"status": "success", "message": f"Telescope '{telescopeId}' registered"})

@telescopeApi_bp.route('/listTelescopes', methods=['GET'])
def listTelescopes():
    telescopes = Telescope.query.all()
    # Convert each telescope object to dict with list of capabilities
    result = {
        t.telescopeId: {
            "ipAddress": t.ipAddress,
            "firmwareVersion": t.firmwareVersion,
            "capabilities": t.capabilities.split(",") if t.capabilities else [],
            "lastSeen": t.lastSeen
        }
        for t in telescopes
    }
    return jsonify(result)

@telescopeApi_bp.route('/deregisterTelescope', methods=['POST'])
def deregisterTelescope():
    data = request.json
    telescopeId = data.get("telescopeId")
    if not telescopeId:
        return jsonify({"error": "Missing telescopeId"}), 400

    telescope = Telescope.query.filter_by(telescopeId=telescopeId).first()
    if not telescope:
        return jsonify({"error": "Invalid telescopeId"}), 400

    db.session.delete(telescope)
    db.session.commit()
    return jsonify({"status": "success", "message": f"Telescope '{telescopeId}' deregistered"})

def cleanupStaleTelescopes(timeoutSeconds=60):
    now = time.time()
    staleTelescopes = Telescope.query.filter(Telescope.lastSeen < now - timeoutSeconds).all()
    for t in staleTelescopes:
        db.session.delete(t)
    if staleTelescopes:
        db.session.commit()
