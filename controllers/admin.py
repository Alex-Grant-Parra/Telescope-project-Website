from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

# Define the blueprint for admin routes
admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/admin")
@login_required
def admin():
    # Check if the current_user is an admin
    if current_user.is_admin:
        return render_template('admin.html')  # Render the admin page if the user is an admin
    
    # Redirect to login page with a flash message if the user is not an admin
    flash('You must be an admin to access this page.', 'warning')
    return redirect(url_for('auth.login'))  # Redirect to login if not an admin
