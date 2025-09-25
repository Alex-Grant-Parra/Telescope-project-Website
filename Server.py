commandPort = 4000
LiveViewPort = 8000
FlaskServerPort = 8080

from flask import Flask, request, jsonify, redirect, url_for, Response
from flask_login import LoginManager # type: ignore # type: ignore
from flask_mail import Mail # type: ignore
from dotenv import load_dotenv # type: ignore
import os
import importlib
import threading
from socket import gethostname
from db import db
import base64
import logging
import subprocess

# Get the base dir
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Startup caddy

caddyPath = os.path.join(BASE_DIR, "caddy_windows_amd64.exe") 
caddyProc = subprocess.Popen([caddyPath, "run"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
print("Caddy started in the background")

# Flask App Initialization
app = Flask(__name__)
load_dotenv()

# Flask Configuration
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")

DATABASE_PATH = f"sqlite:///{os.path.join(BASE_DIR, 'Data.db')}"
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_PATH 
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS") == "True"
app.config["ENCRYPTION_KEY"] = os.getenv("ENCRYPTION_KEY")

db.init_app(app)

# Email Configuration
app.config["MAIL_SERVER"] = "smtp.zoho.eu"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = not(app.config["MAIL_USE_TLS"])
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = app.config["MAIL_USERNAME"]

# Flask-Login & Email Configurations
login_manager = LoginManager()
login_manager.init_app(app)

mail = Mail(app)

# Register Blueprints
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

# User Loader for Flask-Login
from models.user import User # type: ignore

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Ensure Tables Exist in the Database
with app.app_context():
    db.create_all()

# Homepage Redirection
@app.route("/")
def index():
    return redirect(url_for("home.home"))

# Import websocket server functionality
from WebsocketServer import (
    start_websocket_servers,
    send_command_handler,
    liveview_handler,
    register_client_handler
)

# Flask routes that interface with websocket servers
@app.route('/sendCommand', methods=['POST'])
def send_command():
    return send_command_handler()

@app.route('/liveview/<client_id>')
def liveview(client_id):
    return liveview_handler(client_id)

@app.route('/client/register', methods=['POST'])
def register_client():
    return register_client_handler()

# Run Flask and WebSocket Server
if __name__ == '__main__':

    # from plateSolver.plateSolver import plateSolver 

    # # starDetector.getFaintStars()
    # result = plateSolver.processImageForView()
    # centroids = result["centroids"]
    # matches = plateSolver.identifyStars(detectedCentroids=centroids)
    # print(matches)

    # Start websocket servers using the new module
    start_websocket_servers()

    print(f"Starting Flask server on {gethostname()} at http://0.0.0.0:{FlaskServerPort}")
    app.run(host="0.0.0.0", port=FlaskServerPort, debug=False)

    