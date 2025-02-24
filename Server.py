from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_mail import Mail, Message
import os
from db import db  # Import the db instance from db.py

# Initialize Flask app
app = Flask(__name__)

# Manually load the environment variables for secret and encryption keys
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')  # Default if the environment variable isn't set

# Set the path to the database relative to the project folder
BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # Get the base directory of the current script
DATABASE_PATH = os.path.join(BASE_DIR, 'Data.db')  # Path to Data.db in the same folder
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DATABASE_PATH}"  # Set the SQLAlchemy URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS', 'False') == 'True'  # Ensuring boolean conversion for 'True' or 'False'
app.config['ENCRYPTION_KEY'] = os.getenv('ENCRYPTION_KEY')

# Email Configuration (Using Gmail SMTP)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

# Initialize Flask extensions
db.init_app(app)  # Initialize db with app
mail = Mail(app)  # Initialize Flask-Mail
login_manager = LoginManager()
login_manager.init_app(app)

# Import routes
from controllers.auth import auth_bp
from controllers.admin import admin_bp
from controllers.home import home_bp
from controllers.error import error_bp

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(home_bp)
app.register_blueprint(error_bp)

# User loader for Flask-Login
from models.user import User
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Ensure tables exist in the database
with app.app_context():
    db.create_all()  # Ensures all tables are created or checked for existence

# Takes to homepage when just entering IP
@app.route("/")
def index():
    return redirect(url_for('home.home'))

# Run the app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=25566)
