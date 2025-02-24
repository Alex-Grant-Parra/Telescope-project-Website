from flask import Blueprint, render_template

# Define the blueprint for error routes
error_bp = Blueprint('error', __name__)

@error_bp.app_errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@error_bp.app_errorhandler(500)
def internal_error(e):
    return render_template("500.html"), 500  # Customize the error page for 500 errors
