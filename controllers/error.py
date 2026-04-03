from flask import Blueprint, render_template, abort, flash, redirect, url_for
from flask_login import login_required, current_user
import os

# Define the blueprint for error routes
error_bp = Blueprint('error', __name__)

# List of valid error codes that have templates
VALID_ERROR_CODES = [400, 401, 403, 404, 500, 502, 503, 504]

def _admin_guard():
    if not current_user.is_authenticated or not current_user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('home.home'))
    return None

# Testing routes for manually triggering error pages
@error_bp.route('/errors/<int:code>')
@login_required
def test_error(code):
    # Manually trigger error pages for testing purposes - Admin only
    
    guard = _admin_guard()
    if guard:
        return guard
    
    # Check if the error code is valid and has a template
    if code not in VALID_ERROR_CODES:
        abort(404)  # If invalid code, show 404
    
    # Check if the template file exists
    template_path = f'errors/{code}.html'
    template_file = os.path.join(os.path.dirname(__file__), '..', 'templates', template_path)
    
    if not os.path.exists(template_file):
        abort(404)  # If template doesn't exist, show 404
    
    # Render the error template directly
    return render_template(template_path), code

@error_bp.route('/errors')
@login_required
def error_list():
    # Show a list of available error pages for testing - Admin only
    
    guard = _admin_guard()
    if guard:
        return guard
        
    return render_template('error_list.html', error_codes=VALID_ERROR_CODES)

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
