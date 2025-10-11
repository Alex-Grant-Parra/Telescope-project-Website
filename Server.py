FlaskServerPort = 8080
ifOnline = True

from flask import Flask, request, jsonify, redirect, url_for, Response, session, flash
import json
from flask_login import LoginManager, logout_user, current_user
import logging
from flask_mail import Mail 
from dotenv import load_dotenv
from flask_wtf import CSRFProtect
import os
import importlib
from socket import gethostname
from db import db
import subprocess
import atexit
from waitress import serve
from datetime import datetime
# Import security components
from security import SecurityMiddleware, register_security_error_handlers

# Get the base dir
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
load_dotenv()

# Check for correct account
if os.getlogin() == os.getenv("EXECUTER"):
    ifOnline = False

if ifOnline:
    print("Running server for online developement")
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
else:
    print("Running server for local development")

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

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

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

# Generate routes.txt file with accessible pages
def generate_routes_file():
    """Generate a routes.txt file with all accessible GET routes"""
    routes_file_path = os.path.join(BASE_DIR, "templates", "routes.txt")
    
    accessible_routes = []
    for rule in app.url_map.iter_rules():
        # Only include GET routes that are likely to be pages (not API endpoints)
        if 'GET' in rule.methods:
            route_str = str(rule.rule)
            # Exclude certain patterns that are typically backend-only
            if not any(pattern in route_str.lower() for pattern in [
                '/api/', '/ajax/', '/sendcommand', '/liveview', '/client/register',
                '/admin/user/', '/admin/blacklist/', '/security/tokens/show',
                '/security/tokens/generate', '/security/tokens/revoke'
            ]):
                # Replace dynamic parts with example values for display
                display_route = route_str
                if '<int:' in display_route:
                    display_route = display_route.replace('<int:user_id>', '1')
                    display_route = display_route.replace('<int:id>', '1')
                if '<' in display_route and '>' in display_route:
                    # Replace other dynamic parts with examples
                    display_route = display_route.replace('<client_id>', 'example-client')
                    display_route = display_route.replace('<filename>', 'example.log')
                    display_route = display_route.replace('<path:filename>', 'example.log')
                
                accessible_routes.append(f"{display_route} -> {rule.endpoint}")
    
    # Sort routes alphabetically
    accessible_routes.sort()
    
    # Write to routes.txt
    try:
        with open(routes_file_path, 'w', encoding='utf-8') as f:
            f.write("# Accessible Routes - Generated automatically\n")
            f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for route in accessible_routes:
                f.write(f"{route}\n")
        print(f"Generated routes.txt with {len(accessible_routes)} accessible routes")
    except Exception as e:
        print(f"Error generating routes.txt: {e}")

# Generate the routes file
generate_routes_file()

# User Loader for Flask-Login
from models.user import User
from models.trusted_device import TrustedDevice  # Import to register the model

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Enforce that disabled accounts are logged out immediately
@app.before_request
def enforce_enabled_account():
    try:
        # Skip for static files and auth endpoints to avoid redirect loop
        endpoint = (request.endpoint or '')
        allowed_prefixes = (
            'static', 'auth.login', 'auth.logout', 'auth.register', 'auth.forgot_password', 'auth.reset_password', 'auth.login_2fa'
        )
        for p in allowed_prefixes:
            if endpoint.startswith(p):
                return None

        if current_user and getattr(current_user, 'is_authenticated', False):
            try:
                if not getattr(current_user, 'is_active', True):
                    sec_logger = logging.getLogger('security')
                    try:
                        sec_logger.info(json.dumps({'event': 'force_logout_disabled_account', 'user_id': current_user.get_id()}))
                    except Exception:
                        sec_logger.info('force_logout_disabled_account')

                    # Log the user out and clear session
                    try:
                        logout_user()
                    except Exception:
                        pass
                    try:
                        session.clear()
                    except Exception:
                        pass
                    flash('Your account has been disabled. You have been logged out.', 'warning')
                    return redirect(url_for('auth.login'))
            except Exception:
                # If check fails, be permissive
                return None
    except Exception:
        return None

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

# Exempt API endpoint from CSRF checks (it's an internal JSON API used by clients)
try:
    csrf.exempt(send_command)
except Exception:
    # If CSRFProtect isn't available for some reason, ignore so server still runs
    pass

@app.route('/liveview/<client_id>')
def liveview(client_id):
    return liveview_handler(client_id)

@app.route('/client/register', methods=['POST'])
def register_client():
    return register_client_handler()

# Exempt client registration endpoint from CSRF checks (used by non-browser clients)
try:
    csrf.exempt(register_client)
except Exception:
    pass

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

    