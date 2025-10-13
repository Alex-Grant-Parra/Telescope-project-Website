from flask import Blueprint, jsonify, render_template, request, session
from datetime import datetime, timezone
from models.tables import HDSTARtable, IndexTable, NGCtable

from algorithms.convert import convert
from algorithms.astroTools import getAllCelestialData

star_map_bp = Blueprint("star_map", __name__)

def loadStarsFromTables(tables):
    all_stars = []
    for table in tables:
        stars = table.query.all()
        for star in stars:
            try:
                ra = float(star.RA) if star.RA is not None else 0
                dec = float(star.DEC) if star.DEC is not None else 0
                mag = getattr(star, "V-Mag", 30)
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


def get_all_celestial_objects(_dt: datetime | None = None):

    tables = [HDSTARtable, IndexTable, NGCtable]

    all_objects = loadStarsFromTables(tables)

    # Get celestial objects positions for current UTC date/time
    if _dt is None:
        _dt = datetime.utcnow()
    celestial_data = getAllCelestialData(_dt.year, _dt.month, _dt.day, _dt.hour, _dt.minute, _dt.second)

    for obj_name, coords in celestial_data.items():
        ra_h, ra_m, ra_s = coords["ra"]
        dec_d, dec_m, dec_s = coords["dec"]
        mag = coords.get("vmag", 30)

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
    # Optional datetime query parameter in ISO 8601 (UTC preferred)
    dt_str = request.args.get("datetime")
    _dt = None
    if dt_str:
        try:
            # Parse ISO format; if 'Z' present assume UTC
            _dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            # Normalize to UTC (timezone-aware)
            if _dt.tzinfo is not None:
                _dt = _dt.astimezone(timezone.utc)
        except Exception:
            _dt = None
    all_objects = get_all_celestial_objects(_dt)
    return jsonify(all_objects)

@star_map_bp.route("/api/planets")
def get_planets():
    # Returns only planets, sun, and moon; accepts optional datetime param
    dt_str = request.args.get("datetime")
    _dt = None
    if dt_str:
        try:
            _dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            if _dt.tzinfo is not None:
                _dt = _dt.astimezone(timezone.utc)
        except Exception:
            _dt = None
    if _dt is None:
        _dt = datetime.utcnow()

    celestial_data = getAllCelestialData(_dt.year, _dt.month, _dt.day, _dt.hour, _dt.minute, _dt.second)
    planets = []
    for obj_name, coords in celestial_data.items():
        ra_h, ra_m, ra_s = coords["ra"]
        dec_d, dec_m, dec_s = coords["dec"]
        mag = coords.get("vmag", 30)

        ra_deg = convert.HrMinSecToDegrees(ra_h, ra_m, ra_s) * 15
        if dec_d < 0:
            dec_deg = dec_d - dec_m / 60 - dec_s / 3600
        else:
            dec_deg = dec_d + dec_m / 60 + dec_s / 3600

        planets.append({
            "name": obj_name.capitalize(),
            "ra": ra_deg,
            "dec": dec_deg,
            "mag": mag,
            "icon": f"/static/icons/planets/{obj_name.lower()}.png",
            "type": "planet"
        })
    return jsonify(planets)

@star_map_bp.route("/StarMap")
def star_map():
    all_stars = []

    tables = [HDSTARtable, IndexTable, NGCtable]
    RenderStars = True
    RenderPlanets = True

    if RenderStars:
        all_stars = loadStarsFromTables(tables)

    _now = datetime.utcnow()
    celestial_data = getAllCelestialData(_now.year, _now.month, _now.day, _now.hour, _now.minute, _now.second)

    if RenderPlanets:
        for obj_name, coords in celestial_data.items():
            ra_h, ra_m, ra_s = coords["ra"]
            dec_d, dec_m, dec_s = coords["dec"]
            mag = coords.get("vmag", 30)

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
                "icon": f"/static/icons/planets/{obj_name.lower()}.png",
                "type": "planet"
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

    _now = datetime.utcnow()
    celestial_data = getAllCelestialData(_now.year, _now.month, _now.day, _now.hour, _now.minute, _now.second)
    obj_name_lower = star_name.lower()
    if obj_name_lower in celestial_data:
        coords = celestial_data[obj_name_lower]
        ra_h, ra_m, ra_s = coords["ra"]
        dec_d, dec_m, dec_s = coords["dec"]
        mag = coords.get("vmag", 30)

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
