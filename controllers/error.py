from flask import Blueprint, render_template

# Define the blueprint for error routes
error_bp = Blueprint('error', __name__)

@error_bp.app_errorhandler(404)
def page_not_found(e):
    return render_template("errors/404.html"), 404

@error_bp.app_errorhandler(500)
def internal_error(e):
    return render_template("errors/500.html"), 500

@error_bp.app_errorhandler(403)
def forbidden(e):
    return render_template("errors/403.html"), 403

@error_bp.app_errorhandler(401)
def unauthorized(e):
    return render_template("errors/401.html"), 401

@error_bp.app_errorhandler(502)
def bad_gateway(e):
    return render_template("errors/502.html"), 502

@error_bp.app_errorhandler(503)
def service_unavailable(e):
    return render_template("errors/503.html"), 503

@error_bp.app_errorhandler(504)
def gateway_timeout(e):
    return render_template("errors/504.html"), 504

@error_bp.app_errorhandler(400)
def bad_request(e):
    return render_template("errors/400.html"), 400
