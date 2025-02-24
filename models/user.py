import os
import jwt  # Ensure you have jwt installed
import random
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from db import db  # Import the db instance

# Fetch the encryption key from environment variables (assuming it's set in Server.py)
encryption_key = os.getenv('ENCRYPTION_KEY').encode()  # Ensure it's in bytes format
fernet = Fernet(encryption_key)  # Initialize Fernet with the key

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    AccountType = db.Column(db.String(50), nullable=False)  # Ensure this matches your database column name
    totp_secret = db.Column(db.String(16))  # Add this field for TOTP secret
    current_2fa_code = db.Column(db.String(6))  # Add this field to store the current 2FA code

    @property
    def is_admin(self):
        return self.AccountType == "Administrator"

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
        return reset_token  # Return the token directly, no need to decode

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
