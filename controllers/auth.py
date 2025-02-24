from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, current_user, login_required
from utility.hash import hash_password, check_password
from models.user import User
from db import db
from flask_mail import Message

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and check_password(password, user.password):
            session['user_id'] = user.id  # Store user ID in session
            # Generate and send the 2FA code
            totp_code = user.generate_totp_code()
            print(f"TOTP code sent: {totp_code}")  # Debug statement
            msg = Message("Your 2FA Code", recipients=[user.get_email()])
            msg.body = f"Your 2FA code is {totp_code}. Please enter this code to complete your login."
            current_app.extensions['mail'].send(msg)
            flash('Check your email for the 2FA code to complete the login.', 'info')
            return redirect(url_for('auth.login_2fa'))
        else:
            flash('Invalid credentials, please try again.', 'danger')

    return render_template('login.html')

@auth_bp.route("/logout")
def logout():
    logout_user()
    flash('Logged out successfully', 'info')
    session.clear()  # Clear the session
    return redirect(url_for('home.home'))

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
            msg = Message("Password Reset Request", recipients=[email])
            msg.body = f"Click the following link to reset your password: {reset_url}"

            try:
                # Access mail object using current_app
                with current_app.app_context():
                    current_app.extensions['mail'].send(msg)
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
        if not user_id:
            flash('Session expired. Please log in again.', 'danger')
            return redirect(url_for('auth.login'))

        user = User.query.get(user_id)
        totp_code = request.form['totp']

        if user.verify_2fa_code(totp_code):
            login_user(user)
            flash('Login successful!', 'success')
            session.pop('user_id', None)  # Remove user_id from session
            return redirect(url_for('home.home'))
        else:
            flash('Invalid 2FA code. Please try again.', 'danger')

    return render_template('login_2fa.html')
