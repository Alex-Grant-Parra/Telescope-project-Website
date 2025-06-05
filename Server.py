from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_mail import Mail
from dotenv import load_dotenv

import os
import importlib
from socket import gethostname

from db import db

# Initialize Flask app
app = Flask(__name__)
load_dotenv()

# Load configurations
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Using a local db file
# As sqlite does not like accessing the file over the nas
print(f"Dir: {BASE_DIR}")
DATABASE_PATH = f"sqlite:///{os.path.join(BASE_DIR, 'Data.db')}" # Dynamic storage
# DATABASE_PATH = "sqlite:////home/alex/Data.db" # Local storage
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_PATH 
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS") == "True"
app.config["ENCRYPTION_KEY"] = os.getenv("ENCRYPTION_KEY")

# Initialize SQLAlchemy before any database interaction
db.init_app(app)


# Email Configuration
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = app.config["MAIL_USERNAME"]

# Initialize Flask extensions
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Register blueprints dynamically
controllers_dir = os.path.join(os.path.dirname(__file__), "controllers")

def register_blueprints():
    for filename in os.listdir(controllers_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = f"controllers.{filename[:-3]}"
            module = importlib.import_module(module_name)
            blueprint = getattr(module, f"{filename[:-3]}_bp", None)

            if blueprint:
                app.register_blueprint(blueprint)
                print(f"Registered Blueprint: {blueprint.name}")

register_blueprints()

# Debugging - Print all registered routes
print("\nRegistered Routes:")
for rule in app.url_map.iter_rules():
    print(f"{rule} -> {rule.endpoint}")
print("")

# User loader for Flask-Login
from models.user import User

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Ensure tables exist in the database
with app.app_context():
    db.create_all()

# Homepage redirection
@app.route("/")
def index():
    return redirect(url_for("home.home"))

print(f"Running on -> {gethostname()}")
# Run the app

debugMode = False
usePort80forAll = True

if __name__ == "__main__":
    if usePort80forAll:
        if gethostname() == "raspberrypi":
            app.run(host="0.0.0.0", port=8002, debug=debugMode)
        elif gethostname() == "AlexTower":
            app.run(host="0.0.0.0", port=25566, debug=debugMode)
        else:
            app.run(host="0.0.0.0", port=80, debug=debugMode)
    else:
        app.run(host="0.0.0.0", port=80, debug=debugMode)