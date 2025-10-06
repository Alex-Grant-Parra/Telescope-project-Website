FlaskServerPort = 8080

from flask import Flask, request, jsonify, redirect, url_for, Response
from flask_login import LoginManager
from flask_mail import Mail 
from dotenv import load_dotenv
import os
import importlib
from socket import gethostname
from db import db
import subprocess
import atexit
from waitress import serve
# Import security components
from security import SecurityMiddleware, register_security_error_handlers

# Get the base dir
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Startup caddy
caddyPath = os.path.join(BASE_DIR, "caddy_windows_amd64.exe") 
caddyProc = subprocess.Popen([caddyPath, "run"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
print("Caddy started in the background")

# Startup Cloudflare Tunnel
cloudflaredPath = os.path.join(BASE_DIR, "cloudflared.exe")
configPath = os.path.join(BASE_DIR, "config.yml")
cloudflaredProc = subprocess.Popen([cloudflaredPath, "tunnel", "--config", configPath, "run", "telescope-websockets"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
print("Cloudflare Tunnel started in the background")

# Cleanup function for shutting down processes
def cleanup_processes():
    """Clean up Caddy and Cloudflare Tunnel processes on exit"""
    try:
        if 'caddyProc' in globals() and caddyProc.poll() is None:
            print("Terminating Caddy process...")
            caddyProc.terminate()
    except Exception as e:
        print(f"Error terminating Caddy: {e}")
    
    try:
        if 'cloudflaredProc' in globals() and cloudflaredProc.poll() is None:
            print("Terminating Cloudflare Tunnel process...")
            cloudflaredProc.terminate()
    except Exception as e:
        print(f"Error terminating Cloudflare Tunnel: {e}")

# Register cleanup function
atexit.register(cleanup_processes)

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

# Initialize Security Middleware
security_middleware = SecurityMiddleware()
security_middleware.init_app(app)

# Register security error handlers
register_security_error_handlers(app)

print("Security middleware initialized - IP blacklist active")

# HTTPS Enforcement Middleware
@app.before_request
def force_https():
    if not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
        # Allow localhost for development/testing
        if request.host.startswith('127.0.0.1') or request.host.startswith('localhost'):
            return None
        return redirect(request.url.replace('http://', 'https://'), code=301)

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

# Register user blueprint from models
from models.user import user_bp
app.register_blueprint(user_bp)
print(f"Registered Blueprint: {user_bp.name}")

# Debugging - Print all registered routes
print("\nRegistered Routes:")
for rule in app.url_map.iter_rules():
    print(f"{rule} -> {rule.endpoint}")
print("")

# User Loader for Flask-Login
from models.user import User
from models.trusted_device import TrustedDevice  # Import to register the model

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Initialize database tables
with app.app_context():
    db.create_all()
    print("Database tables created/verified")
    
    # Cleanup expired trusted devices
    from models.trusted_device import TrustedDevice
    expired_count = TrustedDevice.cleanup_expired_devices()
    if expired_count > 0:
        print(f"Cleaned up {expired_count} expired trusted devices")

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

    print(f"Starting Flask server on {gethostname()} at http://127.0.0.1:{FlaskServerPort}")
    # serve(app, host="127.0.0.1", port=FlaskServerPort)
    app.run(host="127.0.0.1", port=FlaskServerPort, debug=False)

    