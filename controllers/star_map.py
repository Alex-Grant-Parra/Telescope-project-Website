from flask import Blueprint, jsonify, render_template, request, session
from datetime import datetime
from models.tables import HDSTARtable, IndexTable, NGCtable

from algorithms.convert import convert
from algorithms2 import getAllCelestialData

star_map_bp = Blueprint("star_map", __name__)

def loadStarsFromTables(tables):
    all_stars = []
    for table in tables:
        stars = table.query.all()
        for star in stars:
            try:
                ra = float(star.RA) * 15 if star.RA is not None else 0
                dec = float(star.DEC) if star.DEC is not None else 0
                mag = getattr(star, "V-Mag", 0) or 0
                all_stars.append({
                    "name": getattr(star, "Name"),
                    "ra": ra,
                    "dec": dec,
                    "mag": mag,
                    "type": "star"
                })
            except Exception as e:
                print(f"Error processing star {getattr(star, 'Name', 'UNKNOWN')}: {e}")
    return all_stars


def get_all_celestial_objects():

    tables = [HDSTARtable, IndexTable, NGCtable]

    all_objects = loadStarsFromTables(tables)


    # Get celestial objects positions for current UTC date
    now = datetime.utcnow()
    celestial_data = getAllCelestialData(now.year, now.month, now.day)

    for obj_name, coords in celestial_data.items():
        ra_h, ra_m, ra_s = coords["ra"]
        dec_d, dec_m, dec_s = coords["dec"]
        mag = coords.get("vmag", 0) or 0

        ra_deg = convert.HrMinSecToDegrees(ra_h, ra_m, ra_s) * 15
        if dec_d < 0:
            dec_deg = dec_d - dec_m / 60 - dec_s / 3600
        else:
            dec_deg = dec_d + dec_m / 60 + dec_s / 3600

        all_objects.append({
            "name": obj_name.capitalize(),
            "ra": ra_deg,
            "dec": dec_deg,
            "mag": mag,
            "icon": f"/static/icons/planets/{obj_name.lower()}.png",
            "type": "planet"
        })

    return all_objects

@star_map_bp.route("/api/stars")
def get_stars():
    all_objects = get_all_celestial_objects()
    return jsonify(all_objects)

@star_map_bp.route("/StarMap")
def star_map():
    all_stars = []

    tables = [HDSTARtable, IndexTable, NGCtable]
    RenderStars = True
    RenderPlanets = True

    if RenderStars:
        all_stars = loadStarsFromTables(tables)


    now = datetime.utcnow()
    celestial_data = getAllCelestialData(now.year, now.month, now.day)

    if RenderPlanets:
        for obj_name, coords in celestial_data.items():
            ra_h, ra_m, ra_s = coords["ra"]
            dec_d, dec_m, dec_s = coords["dec"]
            mag = coords.get("vmag", 0) or 0

            ra_deg = convert.HrMinSecToDegrees(ra_h, ra_m, ra_s) * 15
            if dec_d < 0:
                dec_deg = dec_d - dec_m / 60 - dec_s / 3600
            else:
                dec_deg = dec_d + dec_m / 60 + dec_s / 3600

            all_stars.append({
                "name": obj_name.capitalize(),
                "ra": ra_deg,
                "dec": dec_deg,
                "mag": mag,
                "icon": f"/static/icons/planets/{obj_name.lower()}.png"
            })

    return render_template("star_map.html", stars=all_stars)

@star_map_bp.route("/star_info/<star_name>")
def star_info(star_name):
    tables = [HDSTARtable, IndexTable, NGCtable]

    for table in tables:
        result = table.query.filter_by(Name=star_name).first()
        if result:
            return jsonify({
                "name": result.Name,
                "ra": float(result.RA) if result.RA is not None else 0,
                "dec": float(result.DEC) if result.DEC is not None else 0,
                "mag": getattr(result, "V-Mag", 0) or 0,
                "type": "star"
            })

    celestial_data = getAllCelestialData(datetime.utcnow().year, datetime.utcnow().month, datetime.utcnow().day)
    obj_name_lower = star_name.lower()
    if obj_name_lower in celestial_data:
        coords = celestial_data[obj_name_lower]
        ra_h, ra_m, ra_s = coords["ra"]
        dec_d, dec_m, dec_s = coords["dec"]
        mag = coords.get("vmag", 0) or 0

        ra_deg = convert.HrMinSecToDegrees(ra_h, ra_m, ra_s) * 15
        if dec_d < 0:
            dec_deg = dec_d - dec_m / 60 - dec_s / 3600
        else:
            dec_deg = dec_d + dec_m / 60 + dec_s / 3600

        return jsonify({
            "name": star_name.capitalize(),
            "ra": ra_deg,
            "dec": dec_deg,
            "mag": mag,
            "type": "planet"
        })

    return jsonify({"error": "Star not found"}), 404

@star_map_bp.route("/track_star", methods=["POST"])
def track_star():
    data = request.get_json()
    ra = data.get("ra")
    dec = data.get("dec")
    name = data.get("name")
    mag = data.get("mag")

    if ra is None or dec is None:
        print("Missing RA/DEC in request")
        return jsonify({"error": "Missing RA/DEC"}), 400

    print(f"\n[TRACKING] {name} at RA: {ra}°, DEC: {dec}° with magnitude {mag}.\n", flush=True)

    session["selectedObject"] = {
        "name": name,
        "ra": ra,
        "dec": dec,
        "mag": mag
    }

    return jsonify({"status": "tracking", "ra": ra, "dec": dec})
