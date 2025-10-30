from flask import Blueprint, jsonify, render_template, request, session
from datetime import datetime, timezone
from typing import Optional
from models.tables import HDSTARtable, IndexTable, NGCtable
from app.db import db
from sqlalchemy import func

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


def get_all_celestial_objects(_dt: Optional[datetime] = None):

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
    # Parameters and defaults
    dt_str = request.args.get("datetime")
    min_mag = request.args.get("minMag", type=float)
    max_mag = request.args.get("maxMag", type=float)
    mag_limit = request.args.get("mag", type=float)  # backward compatibility
    limit = request.args.get("limit", type=int)
    include_planets = request.args.get("include_planets", default="false").lower() in ("1", "true", "yes")

    if min_mag is None:
        # Include negative magnitudes for very bright stars (e.g., Sirius ~ -1.46)
        min_mag = -2.0
    if max_mag is None:
        max_mag = 20.0
    if mag_limit is not None and mag_limit < max_mag:
        max_mag = mag_limit

    _dt = None
    if dt_str:
        try:
            _dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            if _dt.tzinfo is not None:
                _dt = _dt.astimezone(timezone.utc)
        except Exception:
            _dt = None

    # If include_planets, compute planets for given or current UTC
    planets = []
    if include_planets:
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

            planets.append({
                "name": obj_name.capitalize(),
                "ra": ra_deg,
                "dec": dec_deg,
                "mag": mag,
                "icon": f"/static/icons/planets/{obj_name.lower()}.png",
                "type": "planet"
            })

    # Build stars result, using DB-side filters when possible
    def query_table_stars(table, limit_override: Optional[int] = None):
        stars_list = []
        try:
            col_map = table.__table__.c
            q = db.session.query(table)
            # Apply magnitude filter at DB level if column exists and sort by brightness
            if 'V-Mag' in col_map:
                q = q.filter(col_map['V-Mag'] >= min_mag, col_map['V-Mag'] <= max_mag)
                try:
                    q = q.order_by(col_map['V-Mag'].asc())
                except Exception:
                    pass
            # Apply limit if provided
            eff_limit = limit_override if (limit_override is not None and limit_override > 0) else limit
            if eff_limit is not None and eff_limit > 0:
                q = q.limit(eff_limit)
            rows = q.all()
            for star in rows:
                try:
                    ra = float(getattr(star, 'RA')) if getattr(star, 'RA', None) is not None else 0
                    dec = float(getattr(star, 'DEC')) if getattr(star, 'DEC', None) is not None else 0
                    mag_val = getattr(star, 'V-Mag', None)
                    try:
                        magv = float(mag_val) if mag_val is not None else 30
                    except Exception:
                        magv = 30
                    # If DB-side filter not possible, enforce min/max in Python
                    if 'V-Mag' not in col_map and (magv < min_mag or magv > max_mag):
                        continue
                    stars_list.append({
                        "name": getattr(star, 'Name', None),
                        "ra": ra,
                        "dec": dec,
                        "mag": magv,
                        "type": "star"
                    })
                except Exception as e:
                    print(f"Error processing star {getattr(star, 'Name', 'UNKNOWN')}: {e}")
        except Exception as e:
            print(f"Query failed for table {getattr(table, '__tablename__', 'unknown')}: {e}")
        return stars_list

    tables = [HDSTARtable, IndexTable, NGCtable]
    all_stars = []
    # Distribute per-table limits when a limit is provided to avoid exceeding total
    per_table_limit = None
    if limit is not None and limit > 0:
        per_table_limit = max(1, limit // len(tables))
    for table in tables:
        subset = query_table_stars(table, limit_override=per_table_limit)
        all_stars.extend(subset)

    # Trim to limit if necessary
    if limit is not None and len(all_stars) > limit:
        all_stars = all_stars[:limit]

    if include_planets:
        return jsonify(all_stars + planets)
    else:
        return jsonify(all_stars)

@star_map_bp.route("/api/stars_meta")
def get_stars_meta():
    """
    Return overall magnitude extremes across star tables.
    Includes only objects with a 'V-Mag' column. Planets are excluded here (client will merge).
    Response: {"minMag": float, "maxMag": float}
    """
    tables = [HDSTARtable, IndexTable, NGCtable]
    overall_min = None
    overall_max = None
    for table in tables:
        try:
            col_map = table.__table__.c
            if 'V-Mag' not in col_map:
                continue
            col = col_map['V-Mag']
            mn, mx = db.session.query(func.min(col), func.max(col)).first()
            # Normalize types
            try:
                if mn is not None:
                    mn = float(mn)
            except Exception:
                mn = None
            try:
                if mx is not None:
                    mx = float(mx)
            except Exception:
                mx = None
            if mn is not None:
                overall_min = mn if (overall_min is None or mn < overall_min) else overall_min
            if mx is not None:
                overall_max = mx if (overall_max is None or mx > overall_max) else overall_max
        except Exception as e:
            print(f"stars_meta aggregation failed for table {getattr(table, '__tablename__', 'unknown')}: {e}")

    if overall_min is None:
        overall_min = -2.0
    if overall_max is None:
        overall_max = 12.0
    return jsonify({"minMag": overall_min, "maxMag": overall_max})

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
    # For fast initial load, render without embedding the entire star dataset
    # The client will fetch stars and planets via APIs progressively
    return render_template("star_map.html", stars=[])

def extract_friendly_common_name(common_names_field: str) -> str:
    """
    Extract the first friendly name from commonNames field.
    commonNames format: 'Sirius, HD 48915, HD48915' or 'Andromeda Galaxy, M31, NGC 224'
    Returns: 'Sirius' or 'Andromeda Galaxy' or '' if no friendly name found.
    Skips catalog designations like HD, NGC, IC, M (Messier).
    """
    if not common_names_field:
        return ''
    parts = [p.strip() for p in common_names_field.split(',')]
    for name in parts:
        name_upper = name.upper()
        # Skip catalog designations (HD, NGC, IC, M followed by number)
        if (name_upper.startswith('HD') or 
            name_upper.startswith('NGC') or 
            name_upper.startswith('IC') or 
            (name_upper.startswith('M') and len(name) > 1 and name[1:].strip().replace(' ', '').isdigit())):
            continue
        # Found a friendly name
        return name
    return ''

@star_map_bp.route("/star_info/<star_name>")
def star_info(star_name):
    tables = [HDSTARtable, IndexTable, NGCtable]

    for table in tables:
        result = table.query.filter_by(Name=star_name).first()
        if result:
            response_data = {
                "name": result.Name,
                "ra": float(result.RA) if result.RA is not None else 0,
                "dec": float(result.DEC) if result.DEC is not None else 0,
                "mag": getattr(result, "V-Mag", 0) or 0,
                "type": "star"
            }
            # Add friendly common name if available
            # Try both 'commonNames' (HDSTARtable) and 'Common names' (NGCtable)
            common_names_raw = getattr(result, 'commonNames', None) or getattr(result, 'Common names', None)
            if common_names_raw:
                friendly_name = extract_friendly_common_name(common_names_raw)
                if friendly_name:
                    response_data['friendlyName'] = friendly_name
            return jsonify(response_data)

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
