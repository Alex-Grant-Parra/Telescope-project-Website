import os
import jwt
import random
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from flask_login import UserMixin, login_required, current_user
from db import db
from dotenv import load_dotenv  # Import load_dotenv
from flask import Blueprint, jsonify

# Load environment variables from .env file
load_dotenv()

# Fetch the encryption key from environment variables
encryption_key = os.getenv('ENCRYPTION_KEY')
if encryption_key is None:
    raise ValueError("ENCRYPTION_KEY environment variable is not set")
encryption_key = encryption_key.encode()  # Ensure it's in bytes format
fernet = Fernet(encryption_key)  # Initialize Fernet with the key

class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    AccountType = db.Column(db.String(32), nullable=False, default="Standard")  # "Standard", "Administrator", "Limited", or "None"
    totp_secret = db.Column(db.String(16))
    current_2fa_code = db.Column(db.String(6))
    night_mode = db.Column(db.Boolean, default=False, nullable=False)  # Night mode preference

    @property
    def is_admin(self):
        return self.AccountType == "Administrator"

    @property
    def is_standard(self):
        return self.AccountType == "Standard"

    @property
    def is_limited(self):
        return self.AccountType == "Limited"

    @property
    def is_none(self):
        return self.AccountType == "None"

    # Encrypt email before storing in the database
    def set_email(self, email):
        self.email = fernet.encrypt(email.encode()).decode()

    # Decrypt email when accessing the user email
    def get_email(self):
        return fernet.decrypt(self.email.encode()).decode()

    # Generate a reset token using JWT
    def get_reset_token(self, expires_sec=1800):
        reset_token = jwt.encode(
            {'reset_password': self.id, 'exp': datetime.utcnow() + timedelta(seconds=expires_sec)},
            os.getenv('FLASK_SECRET_KEY', 'default_secret_key'),  # Secret key for JWT (ensure it is in environment)
            algorithm='HS256'
        )
        return reset_token

    # Verify the reset token
    @staticmethod
    def verify_reset_token(token):
        try:
            user_id = jwt.decode(token, os.getenv('FLASK_SECRET_KEY', 'default_secret_key'), algorithms=['HS256'])['reset_password']
        except Exception as e:
            return None
        return User.query.get(user_id)

    # Flask-Login properties
    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    # TOTP setup
    def set_totp_secret(self):
        self.totp_secret = ''.join(random.choices('0123456789abcdef', k=16))
        print(f"TOTP secret set: {self.totp_secret}")

    def generate_totp_code(self):
        self.current_2fa_code = ''.join(random.choices('0123456789abcdef', k=6))
        db.session.commit()  # Save the generated code to the database
        print(f"Generated 2FA code: {self.current_2fa_code}")
        return self.current_2fa_code

    def verify_2fa_code(self, code):
        result = self.current_2fa_code == code
        print(f"Verification result: {result} for code: {code}")
        if result:
            self.current_2fa_code = None  # Clear the 2FA code after successful verification
            db.session.commit()
        return result

    def get_account_type(self):
        return self.AccountType

    # Night mode preference methods
    def set_night_mode(self, is_night_mode):
        """Set the user's night mode preference"""
        self.night_mode = bool(is_night_mode)
        db.session.commit()

    def get_night_mode(self):
        """Get the user's night mode preference"""
        return bool(self.night_mode) if self.night_mode is not None else False


user_bp = Blueprint("user", __name__)

@user_bp.route("/user/account_type")
@login_required
def get_account_type_route():
    return jsonify({"account_type": current_user.get_account_type()})

@user_bp.route("/user/night_mode", methods=["GET"])
@login_required
def get_night_mode():
    """Get the current user's night mode preference"""
    try:
        night_mode = current_user.get_night_mode()
        return jsonify({"status": "success", "night_mode": night_mode})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@user_bp.route("/user/night_mode", methods=["POST"])
@login_required
def set_night_mode():
    """Set the current user's night mode preference"""
    try:
        from flask import request
        data = request.get_json()
        night_mode = data.get('night_mode', False)
        
        current_user.set_night_mode(night_mode)
        
        return jsonify({
            "status": "success", 
            "message": f"Night mode {'enabled' if night_mode else 'disabled'}",
            "night_mode": night_mode
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
