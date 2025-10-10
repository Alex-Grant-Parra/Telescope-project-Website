from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models.user import User
from db import db
from models.user import AccountStatusHistory
from datetime import datetime
from security.ip_blacklist import get_blacklist
import logging

sec_logger = logging.getLogger('security')

# Define the blueprint for admin routes
admin_bp = Blueprint('admin', __name__)

# Import csrf for exemption
try:
    from flask_wtf.csrf import exempt
except ImportError:
    # Fallback if import fails
    def exempt(f):
        return f


@admin_bp.route("/admin")
@login_required
def admin():
    # Check if the current_user is an admin
    if current_user.is_admin:
        return render_template('admin.html')  # Render the admin page if the user is an admin

    # Redirect to login page with a flash message if the user is not an admin
    flash('You must be an admin to access this page.', 'warning')
    return redirect(url_for('auth.login'))  # Redirect to login if not an admin


def _admin_guard():
    """Helper to check admin privilege; returns (None) if OK or a Flask response to return."""
    if not current_user.is_authenticated or not current_user.is_admin:
        # If this was an AJAX request, return JSON so frontend can handle it
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'Admin access required.'}), 403
        flash('Admin access required.', 'danger')
        return redirect(url_for('profile.profile'))
    return None


@admin_bp.route('/admin/user/<int:user_id>/promote', methods=['POST'])
@login_required
def promote_user(user_id):
    guard = _admin_guard()
    if guard:
        return guard

    if current_user.id == user_id:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'You cannot change your own role.'}), 400
        flash('You cannot change your own role.', 'warning')
        return redirect(request.referrer or url_for('admin.admin'))

    user = User.query.get(user_id)
    if not user:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'User not found.'}), 404
        flash('User not found.', 'danger')
        return redirect(request.referrer or url_for('admin.admin'))

    user.AccountType = 'Administrator'
    db.session.commit()
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'success', 'message': f'User {user.username} promoted to Administrator.'})
    flash(f'User {user.username} promoted to Administrator.', 'success')
    return redirect(request.referrer or url_for('admin.admin'))


@admin_bp.route('/admin/user/<int:user_id>/demote', methods=['POST'])
@login_required
def demote_user(user_id):
    guard = _admin_guard()
    if guard:
        return guard

    if current_user.id == user_id:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'You cannot change your own role.'}), 400
        flash('You cannot change your own role.', 'warning')
        return redirect(request.referrer or url_for('admin.admin'))

    user = User.query.get(user_id)
    if not user:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'User not found.'}), 404
        flash('User not found.', 'danger')
        return redirect(request.referrer or url_for('admin.admin'))

    user.AccountType = 'Standard'
    db.session.commit()
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'success', 'message': f'User {user.username} demoted to Standard.'})
    flash(f'User {user.username} demoted to Standard.', 'success')
    return redirect(request.referrer or url_for('admin.admin'))


@admin_bp.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    guard = _admin_guard()
    if guard:
        return guard

    if current_user.id == user_id:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'You cannot delete your own account.'}), 400
        flash('You cannot delete your own account.', 'warning')
        return redirect(request.referrer or url_for('admin.admin'))

    user = User.query.get(user_id)
    if not user:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'User not found.'}), 404
        flash('User not found.', 'danger')
        return redirect(request.referrer or url_for('admin.admin'))

    try:
        db.session.delete(user)
        db.session.commit()
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'success', 'message': f'User {user.username} deleted.'})
        flash(f'User {user.username} deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': str(e)}), 500
        flash(f'Failed to delete user: {e}', 'danger')

    return redirect(request.referrer or url_for('admin.admin'))



@admin_bp.route('/admin/user/<int:user_id>/set_role', methods=['POST'])
@login_required
@exempt
def set_role(user_id):
    guard = _admin_guard()
    if guard:
        return guard

    if current_user.id == user_id:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'You cannot change your own role.'}), 400
        flash('You cannot change your own role.', 'warning')
        return redirect(request.referrer or url_for('admin.admin'))

    user = User.query.get(user_id)
    if not user:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'User not found.'}), 404
        flash('User not found.', 'danger')
        return redirect(request.referrer or url_for('admin.admin'))

    role = request.form.get('role')
    print(f"[DEBUG] Received role: '{role}', form data: {dict(request.form)}")
    print(f"[DEBUG] Role type: {type(role)}, repr: {repr(role)}")
    
    # Check if form data is empty (CSRF validation failure)
    if not request.form:
        print("[DEBUG] Empty form data - likely CSRF validation failure")
        flash('Security validation failed. Please try again.', 'danger')
        return redirect(request.referrer or url_for('admin.admin'))
    
    if role not in ['Administrator', 'Standard', 'Limited']:
        print(f"[DEBUG] Invalid role: '{role}' not in ['Administrator', 'Standard', 'Limited']")
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'Invalid role specified.'}), 400
        flash('Invalid role specified.', 'danger')
        return redirect(request.referrer or url_for('admin.admin'))

    user.AccountType = role
    db.session.commit()
    print(f"[DEBUG] Successfully set user.AccountType to: '{user.AccountType}'")
    
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'success', 'message': f'{user.username} role set to {role}.'})
    flash(f'{user.username} role set to {role}.', 'success')
    return redirect(request.referrer or url_for('admin.admin'))


@admin_bp.route('/admin/user/<int:user_id>/toggle_enabled', methods=['POST'])
@login_required
def toggle_enabled(user_id):
    guard = _admin_guard()
    if guard:
        return guard

    if current_user.id == user_id:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'You cannot change your own enabled status.'}), 400
        flash('You cannot change your own enabled status.', 'warning')
        return redirect(request.referrer or url_for('admin.admin'))

    user = User.query.get(user_id)
    if not user:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'User not found.'}), 404
        flash('User not found.', 'danger')
        return redirect(request.referrer or url_for('admin.admin'))

    current_status = user.is_enabled()
    # Record the change in AccountStatusHistory
    entry = AccountStatusHistory(user_id=user.id, enabled=(not current_status), changed_by=current_user.id, reason='Toggled by admin')
    db.session.add(entry)
    db.session.commit()
    # Update persistent flag as well
    user.is_enabled_flag = not current_status
    db.session.commit()

    message = f'User {user.username} has been {("enabled" if not current_status else "disabled") }.'
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'success', 'message': message, 'enabled': not current_status})

    flash(message, 'success')
    return redirect(request.referrer or url_for('admin.admin'))


@admin_bp.route('/admin/security/logs')
@login_required
def security_logs():
    guard = _admin_guard()
    if guard:
        return guard

    # Fetch recent account status history
    logs = AccountStatusHistory.query.order_by(AccountStatusHistory.changed_at.desc()).limit(200).all()
    return render_template('security_logs.html', logs=logs)


@admin_bp.route('/admin/security')
@login_required
def admin_security_page():
    guard = _admin_guard()
    if guard:
        return guard

    blacklist = get_blacklist()
    # List files in security/logs directory
    import os
    logs_dir = os.path.join(os.path.dirname(__file__), '..', 'security', 'logs')
    logs_dir = os.path.abspath(logs_dir)
    files = []
    try:
        if os.path.exists(logs_dir):
            for fn in sorted(os.listdir(logs_dir)):
                if os.path.isfile(os.path.join(logs_dir, fn)):
                    files.append(fn)
    except Exception:
        files = []

    return render_template('admin_security.html', blacklist_stats=blacklist.get_stats(), blacklisted=sorted(list(blacklist.blacklisted_ips)), log_files=files)


@admin_bp.route('/admin/security/logfile/<path:filename>')
@login_required
def admin_security_logfile(filename):
    guard = _admin_guard()
    if guard:
        return guard

    import os
    from flask import abort
    # Prevent path traversal: only serve files from security/logs directory
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'security', 'logs'))
    requested = os.path.abspath(os.path.join(base_dir, filename))
    if not requested.startswith(base_dir) or not os.path.exists(requested):
        return jsonify({'error': 'File not found'}), 404

    # Return last 100 lines
    try:
        with open(requested, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-500:]
        return jsonify({'file': filename, 'lines': lines})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/blacklist/add', methods=['POST'])
@login_required
def admin_blacklist_add():
    guard = _admin_guard()
    if guard:
        return guard

    data = request.get_json() or request.form
    ip = data.get('ip') if isinstance(data, dict) else None
    if not ip:
        return jsonify({'status': 'error', 'message': 'IP required'}), 400

    blacklist = get_blacklist()
    if blacklist.add_manual_ip(ip):
        sec_logger.info(f"manual_blacklist_add: ip={ip}, by={current_user.id}")
        return jsonify({'status': 'success', 'message': f'Added {ip} to blacklist'})
    return jsonify({'status': 'error', 'message': 'Invalid IP'}), 400


@admin_bp.route('/admin/blacklist/remove', methods=['POST'])
@login_required
def admin_blacklist_remove():
    guard = _admin_guard()
    if guard:
        return guard

    data = request.get_json() or request.form
    ip = data.get('ip') if isinstance(data, dict) else None
    if not ip:
        return jsonify({'status': 'error', 'message': 'IP required'}), 400

    blacklist = get_blacklist()
    if blacklist.remove_ip(ip):
        sec_logger.info(f"manual_blacklist_remove: ip={ip}, by={current_user.id}")
        return jsonify({'status': 'success', 'message': f'Removed {ip} from blacklist'})
    return jsonify({'status': 'error', 'message': 'IP not found'}), 404


@admin_bp.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('profile.profile'))

    from models.trusted_device import TrustedDevice
    users = User.query.all()
    user_stats = []

    for user in users:
        trusted_devices = TrustedDevice.get_user_trusted_devices(user.id)
        user_stats.append({
            'user': user,
            'is_enabled': user.is_enabled(),
            'trusted_devices_count': len(trusted_devices),
            'trusted_devices': trusted_devices
        })

    return render_template('admin_users.html', user_stats=user_stats)


@admin_bp.route('/admin/security/logs')
@login_required
def admin_security_logs():
    guard = _admin_guard()
    if guard:
        return guard

    import os
    logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'security', 'logs'))
    print(f"[DEBUG] logs_dir resolved to: {logs_dir}")
    files = []
    try:
        if os.path.exists(logs_dir):
            print(f"[DEBUG] logs_dir exists. Contents: {os.listdir(logs_dir)}")
            for fn in sorted(os.listdir(logs_dir)):
                file_path = os.path.join(logs_dir, fn)
                print(f"[DEBUG] Checking file: {file_path} isfile={os.path.isfile(file_path)}")
                if os.path.isfile(file_path):
                    files.append(fn)
        else:
            print(f"[DEBUG] logs_dir does not exist.")
    except Exception as e:
        print(f"[DEBUG] Exception while listing logs: {e}")
        files = []
    return {'logs': files}


# Token management routes (moved from security controller)
@admin_bp.route('/admin/security/tokens')
@login_required
def admin_security_tokens():
    guard = _admin_guard()
    if guard:
        return guard

    import security.manage_tokens as token_utils
    tokens = token_utils.load_tokens()
    # Build mapping of identifier -> (token, info)
    view_tokens = []
    for token, info in tokens.items():
        view_tokens.append({
            'id': token,  # Full token for identification
            'truncated': token[:12] + '...',  # Truncated for display
            'name': info.get('name'),
            'client_type': info.get('client_type'),
            'created': info.get('created')
        })

    return render_template('security_tokens.html', tokens=view_tokens)


@admin_bp.route('/admin/security/tokens/generate', methods=['POST'])
@login_required
def admin_generate_token():
    guard = _admin_guard()
    if guard:
        return guard

    import security.manage_tokens as token_utils
    name = request.form.get('name') or 'unnamed'
    client_type = request.form.get('client_type') or 'observer'
    
    # Check for duplicate names
    tokens = token_utils.load_tokens()
    for token, info in tokens.items():
        if info.get('name') == name:
            flash(f'Token with name "{name}" already exists. Please choose a different name.', 'danger')
            return redirect(url_for('admin.admin_security_tokens'))
    
    token = token_utils.add_token(name, client_type)
    sec_logger.info(f"token_generated: token={token[:12]}..., name={name}, by={current_user.id}")
    flash(f'Generated token for {name}: {token} (store securely)', 'success')
    return redirect(url_for('admin.admin_security_tokens'))


@admin_bp.route('/admin/security/tokens/revoke', methods=['POST'])
@login_required
def admin_revoke_token():
    guard = _admin_guard()
    if guard:
        return guard

    import security.manage_tokens as token_utils
    identifier = request.form.get('token')
    if not identifier:
        flash('No token specified.', 'danger')
        return redirect(url_for('admin.admin_security_tokens'))

    tokens = token_utils.load_tokens()
    if identifier in tokens:
        token_utils.revoke_token(identifier)
        sec_logger.info(f"token_revoked: token={identifier[:12]}..., by={current_user.id}")
        flash('Token revoked.', 'success')
    else:
        flash('Token not found.', 'danger')

    return redirect(url_for('admin.admin_security_tokens'))


@admin_bp.route('/admin/security/tokens/show', methods=['POST'])
@login_required
def admin_show_token():
    guard = _admin_guard()
    if guard:
        return guard

    import security.manage_tokens as token_utils
    token_id = request.json.get('token_id') if request.is_json else request.form.get('token_id')
    if not token_id:
        return jsonify({'error': 'Token ID required'}), 400

    tokens = token_utils.load_tokens()
    if token_id in tokens:
        return jsonify({'token': token_id})
    else:
        return jsonify({'error': 'Token not found'}), 404
