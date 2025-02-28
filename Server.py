from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_mail import Mail
import os
from db import db  # Import the db instance from db.py
import importlib
from dotenv import load_dotenv

# Initialize Flask app
app = Flask(__name__)
load_dotenv()

# Load configurations
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') 
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'Data.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DATABASE_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS') == 'True'
app.config['ENCRYPTION_KEY'] = os.getenv('ENCRYPTION_KEY')

# Email Configuration (Using Gmail SMTP)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

# Initialize Flask extensions
db.init_app(app)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Path to the controllers folder
controllers_dir = os.path.join(os.path.dirname(__file__), 'controllers')

# Function to dynamically import and register blueprints (From the controllers folder)
def register_blueprints():
    for filename in os.listdir(controllers_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = f"controllers.{filename[:-3]}"
            module = importlib.import_module(module_name)
            blueprint = getattr(module, f"{filename[:-3]}_bp", None)
            
            if blueprint:
                app.register_blueprint(blueprint)
                print(f"Registered Blueprint: {blueprint.name}")  # Debugging output


# Call the function to register all blueprints
register_blueprints()

# Print all registered routes for debugging
print("\nRegistered Routes:")
for rule in app.url_map.iter_rules():
    print(f"{rule} -> {rule.endpoint}")
print("")

# User loader for Flask-Login
from models.user import User
@login_manager.user_loader
def load_user(user_id):
    # Updated to use db.session.get to avoid deprecation warning in SQLAlchemy 2.0
    return db.session.get(User, int(user_id))

# Ensure tables exist in the database
with app.app_context():
    db.create_all() 

# Takes to homepage when just entering IP
@app.route("/")
def index():
    return redirect(url_for('home.home'))

# Run the app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=25566)
