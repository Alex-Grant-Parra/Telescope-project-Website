from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from utility.hash import hash_password, check_password
from models.user import User
from models.trusted_device import TrustedDevice
from db import db
from flask_mail import Message

profile_bp = Blueprint('profile', __name__)

@profile_bp.route("/profile")
@login_required
def profile():
    """Main profile page"""
    return render_template('profile.html')

@profile_bp.route("/profile/edit", methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit profile information (email, password)"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'change_email':
            new_email = request.form.get('email')
            current_password = request.form.get('current_password')
            
            # Verify current password
            if not check_password(current_password, current_user.password):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('profile.edit_profile'))
            
            # Check if email is already taken
            users = User.query.all()
            email_taken = any(u.get_email() == new_email and u.id != current_user.id for u in users)
            
            if email_taken:
                flash('This email is already in use by another account.', 'danger')
                return redirect(url_for('profile.edit_profile'))
            
            # Update email
            current_user.set_email(new_email)
            db.session.commit()
            flash('Email updated successfully!', 'success')
            return redirect(url_for('profile.profile'))
            
        elif action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # Verify current password
            if not check_password(current_password, current_user.password):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('profile.edit_profile'))
            
            # Check password confirmation
            if new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
                return redirect(url_for('profile.edit_profile'))
            
            # Check password strength (basic validation)
            if len(new_password) < 6:
                flash('Password must be at least 6 characters long.', 'danger')
                return redirect(url_for('profile.edit_profile'))
            
            # Update password
            current_user.password = hash_password(new_password)
            db.session.commit()
            
            # Send confirmation email
            try:
                msg = Message("Password Changed", recipients=[current_user.get_email()])
                msg.body = "Your password has been successfully changed. If you did not make this change, please contact support immediately."
                current_app.extensions['mail'].send(msg)
            except Exception as e:
                print(f"Failed to send password change confirmation email: {e}")
            
            flash('Password updated successfully!', 'success')
            return redirect(url_for('profile.profile'))
    
    return render_template('edit_profile.html')

@profile_bp.route("/profile/trusted_devices")
@login_required
def profile_trusted_devices():
    """Show trusted devices in profile context"""
    devices = TrustedDevice.get_user_trusted_devices(current_user.id)
    return render_template('profile_trusted_devices.html', devices=devices)

@profile_bp.route("/profile/revoke_device/<int:device_id>", methods=['POST'])
@login_required
def profile_revoke_device(device_id):
    """Revoke trust for a specific device from profile"""
    if TrustedDevice.revoke_device(current_user.id, device_id):
        flash('Device trust revoked successfully.', 'success')
    else:
        flash('Device not found or could not be revoked.', 'danger')
    return redirect(url_for('profile.profile_trusted_devices'))

@profile_bp.route("/profile/account_info")
@login_required
def account_info():
    """Show account information"""
    return render_template('account_info.html')


@profile_bp.route("/profile/admin/users")
@login_required
def admin_users():
    """Admin-only route to view all users"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('profile.profile'))
    
    users = User.query.all()
    user_stats = []
    
    for user in users:
        trusted_devices = TrustedDevice.get_user_trusted_devices(user.id)
        user_stats.append({
            'user': user,
            'trusted_devices_count': len(trusted_devices),
            'trusted_devices': trusted_devices
        })
    
    return render_template('admin_users.html', user_stats=user_stats)
