from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, current_user, login_required
import logging
sec_logger = logging.getLogger('security')
import json
from utility.hash import hash_password, check_password
from models.user import User
from models.trusted_device import TrustedDevice
from app.db import db
from utility.emailer import send_email


auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        trust_device = request.form.get('trust_device') == 'on'
        
        user = User.query.filter_by(username=username).first()
        if user and check_password(password, user.password):
            # Prevent disabled accounts from logging in
            try:
                if not user.is_enabled():
                    flash('This account has been disabled. Contact an administrator.', 'danger')
                    sec_logger.info(json.dumps({'event': 'login_disabled_attempt', 'user_id': user.id, 'username': username}))
                    return render_template('login.html')
            except Exception:
                # If is_enabled check fails for some reason, proceed cautiously
                pass
            # Check if the request is coming from localhost:8080 to bypass 2FA
            is_localhost = (request.host.startswith('localhost:8080'))
            
            # Check if this device is already trusted
            is_trusted, device_name = TrustedDevice.is_device_trusted(user.id)
            
            if is_localhost:
                # Skip 2FA for localhost:8080 connections
                login_user(user)
                flash('Login successful! (2FA bypassed for localhost)', 'success')
                sec_logger.info(json.dumps({'event': 'login_success', 'user_id': user.id, 'method': 'localhost_bypass'}))
                return redirect(url_for('home.home'))
            elif is_trusted:
                # Skip 2FA for trusted devices
                login_user(user)
                flash(f'Login successful! (Trusted device: {device_name})', 'success')
                sec_logger.info(json.dumps({'event': 'login_success', 'user_id': user.id, 'method': 'trusted_device', 'device': device_name}))
                return redirect(url_for('home.home'))
            else:
                # Regular 2FA flow for other connections
                session['user_id'] = user.id  # Store user ID in session
                session['trust_device'] = trust_device  # Store trust device preference
                
                # Generate and send the 2FA code
                totp_code = user.generate_totp_code()
                # print(f"TOTP code sent: {totp_code}")  # Debug statement
                # Auth-related email sender
                send_email(current_app, 'auth', [user.get_email()], "Your 2FA Code", f"Your 2FA code is {totp_code}. Please enter this code to complete your login.")
                flash('Check your email for the 2FA code to complete the login.', 'info')
                sec_logger.info(json.dumps({'event': 'login_2fa_required', 'user_id': user.id}))
                return redirect(url_for('auth.login_2fa'))
        else:
            flash('Invalid credentials, please try again.', 'danger')
            sec_logger.info(json.dumps({'event': 'login_failed', 'username': username}))

    return render_template('login.html')

@auth_bp.route("/logout")
def logout():
    resp = redirect(url_for('home.home'))
    try:
        sec_logger.info(json.dumps({'event': 'logout', 'user_id': current_user.get_id() if current_user else None}))
    except Exception:
        pass
    logout_user()
    # Note: Do NOT clear the trusted device cookie here.
    # Leaving the cookie intact allows the device to remain trusted across logouts,
    # which is the expected behavior for a "trusted device" 2FA bypass.
    # Users can explicitly revoke devices from their profile or via revoke routes.
    session.clear()  # Clear the session
    flash('Logged out successfully', 'info')
    return resp

@auth_bp.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        user_with_same_username = User.query.filter_by(username=username).first()
        users = User.query.all()
        email_taken = any(u.get_email() == email for u in users)

        if user_with_same_username and email_taken:
            flash('Username and email already taken. Please choose another two.', 'danger')
            return redirect(url_for('auth.register'))

        if user_with_same_username:
            flash('Username already taken. Please choose another one.', 'danger')
            return redirect(url_for('auth.register'))

        if email_taken:
            flash('Email already used. Please choose another one.', 'danger')
            return redirect(url_for('auth.register'))

        hashed_password = hash_password(password)
        new_user = User(username=username, email=email, password=hashed_password)
        new_user.set_email(email)
        new_user.set_totp_secret()  # Generate TOTP secret
        print(f"TOTP secret for new user: {new_user.totp_secret}")  # Debug statement
        
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash('Account created and logged in successfully!', 'success')
        session['_flashes'] = []  # Clear flash messages manually
        return redirect(url_for('home.home'))

    return render_template('register.html')


@auth_bp.route("/forgot_password", methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        
        # Search for the user by comparing the decrypted email
        users = User.query.all()  # Get all users from the database
        found_user = None
        for u in users:
            if u.get_email() == email:  # Decrypt email and compare
                found_user = u
                break

        if found_user:
            # Generate a reset token
            reset_token = found_user.get_reset_token()

            # Send an email with the token link
            reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
            try:
                send_email(current_app, 'auth', [email], "Password Reset Request", f"Click the following link to reset your password: {reset_url}")
                flash('A password reset link has been sent to your email.', 'info')
            except Exception as e:
                flash(f"Error sending email: {str(e)}", 'danger')
                return redirect(url_for('auth.forgot_password'))

            return redirect(url_for('auth.login'))
        else:
            flash('No account found with that email address.', 'danger')

    return render_template('forgot_password.html')


# Reset password route
@auth_bp.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_password(token):
    user = User.verify_reset_token(token)

    if not user:
        flash('That is an invalid or expired token.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    # Print statement to console
    print(f"Password reset link clicked for user ID: {user.id}")

    if request.method == 'POST':
        password = request.form['password']
        user.password = hash_password(password)  # Update password
        db.session.commit()
        flash('Your password has been updated!', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)


@auth_bp.route("/login/2FA", methods=['GET', 'POST'])
def login_2fa():
    if request.method == 'POST':
        user_id = session.get('user_id')
        trust_device = session.get('trust_device', False)
        
        if not user_id:
            flash('Session expired. Please log in again.', 'danger')
            return redirect(url_for('auth.login'))

        user = User.query.get(user_id)
        # Ensure account is still enabled before completing 2FA
        if user:
            try:
                if not user.is_enabled():
                    flash('This account has been disabled. Contact an administrator.', 'danger')
                    sec_logger.info(json.dumps({'event': 'login_2fa_disabled_attempt', 'user_id': user.id}))
                    session.pop('user_id', None)
                    session.pop('trust_device', None)
                    return redirect(url_for('auth.login'))
            except Exception:
                pass
        totp_code = request.form['totp']

        if user.verify_2fa_code(totp_code):
            # If user chose to trust this device, add it to trusted devices
            if trust_device:
                device_name, token = TrustedDevice.trust_device(user.id, trust_for_days=30)
                # Set a cookie that will persist for the trust period; httponly to reduce XSS risk
                resp = redirect(url_for('home.home'))
                resp.set_cookie('trusted_device_token', token, max_age=30*24*60*60, httponly=True, samesite='Lax')
                flash(f'Login successful! Device "{device_name}" is now trusted for 30 days.', 'success')
                login_user(user)
                session.pop('user_id', None)  # Remove user_id from session
                session.pop('trust_device', None)  # Remove trust_device from session
                return resp
            else:
                flash('Login successful!', 'success')
            
            login_user(user)
            session.pop('user_id', None)  # Remove user_id from session
            session.pop('trust_device', None)  # Remove trust_device from session
            return redirect(url_for('home.home'))
        else:
            flash('Invalid 2FA code. Please try again.', 'danger')

    return render_template('login_2fa.html')


@auth_bp.route("/trusted_devices")
@login_required
def trusted_devices():
    """Legacy route - redirect to profile-based trusted devices"""
    return redirect(url_for('profile.profile_trusted_devices'))


@auth_bp.route("/revoke_device/<int:device_id>", methods=['POST'])
@login_required
def revoke_device(device_id):
    """Revoke trust for a specific device"""
    if TrustedDevice.revoke_device(current_user.id, device_id):
        flash('Device trust revoked successfully.', 'success')
    else:
        flash('Device not found or could not be revoked.', 'danger')
    return redirect(url_for('auth.trusted_devices'))


@auth_bp.route("/device_info")
@login_required
def device_info():
    """Debug route to show device fingerprint information"""
    # Get device info from TrustedDevice
    fingerprint = TrustedDevice.generate_device_fingerprint()
    device_name = TrustedDevice.get_device_name()

    # Sanitize and normalize IP address header: prefer X-Forwarded-For but validate it
    xff = request.headers.get('X-Forwarded-For') or request.environ.get('HTTP_X_FORWARDED_FOR')
    if xff:
        # X-Forwarded-For can contain a comma-separated list; take the first valid-looking entry
        ip = xff.split(',')[0].strip()
    else:
        ip = request.remote_addr or request.environ.get('REMOTE_ADDR', 'Unknown')

    # Mask fingerprint to avoid leaking full device identifiers in debug view
    masked_fingerprint = None
    if fingerprint:
        # Show only first and last 4 chars (e.g. abcd...wxyz) to reduce info leakage
        fp = str(fingerprint)
        if len(fp) > 8:
            masked_fingerprint = f"{fp[:4]}...{fp[-4:]}"
        else:
            masked_fingerprint = fp

    # Render a template which uses Jinja2 auto-escaping to avoid XSS
    return render_template('device_info.html',
                           device_name=device_name,
                           fingerprint=masked_fingerprint,
                           user_agent=request.headers.get('User-Agent', 'Unknown'),
                           host=request.host)
