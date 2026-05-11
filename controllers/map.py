import os
from flask import Blueprint, render_template

map_bp = Blueprint("map", __name__)


@map_bp.route("/map")
def map_page():
    return render_template(
        "map.html",
        open_meteo_tile_url=os.getenv("OPEN_METEO_TILE_URL", ""),
        open_meteo_attribution=os.getenv("OPEN_METEO_ATTRIBUTION", ""),
        bortle_tile_url=os.getenv("BORTLE_TILE_URL", ""),
        bortle_wms_url=os.getenv(
            "BORTLE_WMS_URL",
            "https://deneb.lightpollutionmap.info/geoserver/ows",
        ),
        bortle_wms_layer=os.getenv("BORTLE_WMS_LAYER", "PostGIS:VIIRS_2019"),
        bortle_wms_time=os.getenv("BORTLE_WMS_TIME", ""),
        bortle_fixed_url=os.getenv("BORTLE_FIXED_URL", ""),
        bortle_attribution=os.getenv(
            "BORTLE_ATTRIBUTION",
            "© <a href='https://www.lightpollutionmap.info' target='_blank'>Light Pollution Map Contributors</a>",
        ),
        satellite_tile_url=os.getenv("SATELLITE_TILE_URL", ""),
        satellite_attribution=os.getenv("SATELLITE_ATTRIBUTION", ""),
    )
