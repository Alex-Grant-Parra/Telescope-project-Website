from flask import Blueprint, render_template, request, jsonify, session

interface_bp = Blueprint("interface", __name__, url_prefix="/interface")

@interface_bp.route("/")
def interface():
    return render_template("interface.html")

@interface_bp.route("/update_camera", methods=["POST"])
def update_camera():
    data = request.json
    print("Received Camera Settings:", data)
    shutter_speed = data.get("shutterSpeed", "Unknown")
    print(f"Shutter Speed: {shutter_speed}")
    return jsonify({"status": "success", "message": "Settings updated"})

@interface_bp.route("/search_object", methods=["POST"])
def search_object():
    from models.tables import HDSTARtable, IndexTable, NGCtable
    data = request.json
    search_value = data.get("searchValue", "").strip()

    print(f"Received search query: {search_value}")

    result = None

    try:
        # Determine the table based on prefix
        if search_value.startswith("HD"):
            # search_value = "HD" + search_value[2:]  # Ensure full name format
            print(f"Querying HDSTARtable for {search_value}")
            result = HDSTARtable.query_by_name(search_value)

        elif search_value.startswith("NGC"):
            print(f"Querying NGCtable for {search_value}")
            result = NGCtable.query_by_name(search_value)

        elif search_value.startswith("IC"):
            print(f"Querying IndexTable for {search_value}")
            result = IndexTable.query_by_name(search_value)

        else:
            return jsonify({"status": "error", "message": "Invalid prefix"})

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

        print(f"\n[TRACKING] {name} at RA: {ra}°, DEC: {dec}° with magnitude {mag}.\n", flush=True)

        session["selectedObject"] = { # Adds to flask's session
            "name": name,
            "ra": ra,
            "dec": dec,
            "mag": mag
        }

        return jsonify({"status": "success", "data": result_data})
    else:
        print("Object not found")
        return jsonify({"status": "error", "message": "Object not found"})
    


