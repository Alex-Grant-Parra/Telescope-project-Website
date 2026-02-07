FlaskServerPort = 5000
ifOnline = True

from utility.setupLibs import ensure_requirements
ensure_requirements()

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
from app.db import db
import subprocess
import atexit
from waitress import serve  
from datetime import datetime
import ipaddress
# Import security components
from security import SecurityMiddleware, register_security_error_handlers

# Get the base dir
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
# Use os.path.join (BASE_DIR is a string) to build env path
env_path = os.path.join(BASE_DIR, 'instance', '.env')

if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    # fallback: try system env or log that .env is missing
    print(f".env not found at {env_path}")
    

# # Startup Cloudflare Tunnel
# try:
#     # Redirect cloudflared stdout/stderr to log files to avoid console output
#     cf_out = open(os.path.join(BASE_DIR, "infrastructure", "logs", "cloudflared_stdout.log"), "a", encoding="utf-8")
#     cf_err = open(os.path.join(BASE_DIR, "infrastructure", "logs", "cloudflared_stderr.log"), "a", encoding="utf-8")
#     cloudflaredProc = subprocess.Popen([
#         "cloudflared",
#         "tunnel",
#         "--config",
#         "/home/alex/Server/infrastructure/config.yml",
#         "run",
#         "server",
#     ], stdout=cf_out, stderr=cf_err, cwd=os.path.join(BASE_DIR, "infrastructure"))
#     print("Cloudflare Tunnel started in background (logs: infrastructure/logs)")
# except Exception as e:
#     print(f"Failed to start cloudflared: {e}")

# # Cleanup function for shutting down processes
# def cleanup_processes():
#     """Clean up Cloudflare Tunnel process on exit"""
#     try:
#         if 'cloudflaredProc' in globals() and cloudflaredProc.poll() is None:
#             print("Terminating Cloudflare Tunnel process...")
#             cloudflaredProc.terminate()
#     except Exception as e:
#         print(f"Error terminating Cloudflare Tunnel: {e}")

# # Register cleanup function
# atexit.register(cleanup_processes)

# Flask App Initialization


# Flask Configuration
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")

DATABASE_PATH = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'Data.db')}"
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_PATH 
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS") == "True"
app.config["ENCRYPTION_KEY"] = os.getenv("ENCRYPTION_KEY")

db.init_app(app)

# Email Configuration
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.zoho.eu")
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = not(app.config["MAIL_USE_TLS"])
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = app.config["MAIL_USERNAME"]

# Optional role-based sender identities (From header). These can be plain emails
# or configured aliases. If not provided, fallback to the default sender.
app.config["MAIL_SUPPORT_SENDER"] = os.getenv("MAIL_SUPPORT_SENDER", app.config["MAIL_DEFAULT_SENDER"])
app.config["MAIL_SUPPORT_NAME"] = os.getenv("MAIL_SUPPORT_NAME", "Support")
app.config["MAIL_AUTH_SENDER"] = os.getenv("MAIL_AUTH_SENDER", app.config["MAIL_DEFAULT_SENDER"])
app.config["MAIL_AUTH_NAME"] = os.getenv("MAIL_AUTH_NAME", "Auth")

# Optional: separate SMTP configs per role (Support/Auth). If provided, the
# app will use these credentials and server to send emails for that role.
# Otherwise, it will fallback to the default Flask-Mail sender above.
app.config["MAIL_SUPPORT_SMTP_SERVER"] = os.getenv("MAIL_SUPPORT_SMTP_SERVER")
app.config["MAIL_SUPPORT_SMTP_PORT"] = int(os.getenv("MAIL_SUPPORT_SMTP_PORT", "0") or 0)
app.config["MAIL_SUPPORT_SMTP_USE_TLS"] = os.getenv("MAIL_SUPPORT_SMTP_USE_TLS", "True").lower() in ("1","true","yes")
app.config["MAIL_SUPPORT_SMTP_USERNAME"] = os.getenv("MAIL_SUPPORT_SMTP_USERNAME")
app.config["MAIL_SUPPORT_SMTP_PASSWORD"] = os.getenv("MAIL_SUPPORT_SMTP_PASSWORD")

app.config["MAIL_AUTH_SMTP_SERVER"] = os.getenv("MAIL_AUTH_SMTP_SERVER")
app.config["MAIL_AUTH_SMTP_PORT"] = int(os.getenv("MAIL_AUTH_SMTP_PORT", "0") or 0)
app.config["MAIL_AUTH_SMTP_USE_TLS"] = os.getenv("MAIL_AUTH_SMTP_USE_TLS", "True").lower() in ("1","true","yes")
app.config["MAIL_AUTH_SMTP_USERNAME"] = os.getenv("MAIL_AUTH_SMTP_USERNAME")
app.config["MAIL_AUTH_SMTP_PASSWORD"] = os.getenv("MAIL_AUTH_SMTP_PASSWORD")

# Flask-Login & Email Configurations
login_manager = LoginManager()
login_manager.init_app(app)

mail = Mail(app)

# Site domain
app.config["APP_DOMAIN"] = os.getenv("APP_DOMAIN", "telescopes.dev")

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

# Initialize Security Middleware
security_middleware = SecurityMiddleware()
security_middleware.init_app(app)

# Register security error handlers
register_security_error_handlers(app)

print("Security middleware initialized - IP blacklist active")

# Log CSRF failures with useful diagnostics for headless clients
try:
    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        try:
            details = {
                "path": request.path,
                "method": request.method,
                "origin": request.headers.get('Origin'),
                "referer": request.headers.get('Referer'),
                "content_type": request.headers.get('Content-Type'),
                "has_csrf_header": bool(request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token')),
                "cookies": list(request.cookies.keys()),
            }
            print(f"[CSRF ERROR] {e.description} :: {details}")
        except Exception as log_e:
            print(f"[CSRF ERROR] {e.description} (failed to log details: {log_e})")

        # Prefer JSON response for API-like requests
        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.path.startswith('/upload')
        if wants_json:
            return jsonify({
                "status": "error",
                "message": "CSRF validation failed",
                "detail": e.description
            }), 400
        # Fallback: simple text
        return ("CSRF validation failed", 400, {"Content-Type": "text/plain"})
except Exception as e:
    print(f"Failed to register CSRF error handler: {e}")

# HTTPS Enforcement Middleware
@app.before_request
def force_https():
    """Redirect HTTP->HTTPS appropriately.

    Rules:
    - If already secure or a reverse proxy says original was HTTPS, do nothing.
    - Always allow localhost/127.0.0.1 without redirect (handy for local dev/tools).
    - If request targets a private LAN IP on the Flask HTTP port (e.g., 8080),
      redirect to the same host over HTTPS on the default port (handled by Caddy).
    - For domains (non-IP hosts), redirect http:// -> https://.
    """
    if request.is_secure or (request.headers.get('X-Forwarded-Proto') or '').lower() == 'https':
        return None

    raw_host = request.host or ''
    host_only, port = raw_host, ''
    if ':' in raw_host:
        host_only, port = raw_host.rsplit(':', 1)

    # Allow localhost/private prefixes explicitly via env config
    local_hosts = os.getenv('LOCAL_IP_ADDRESSES', '127.0.0.1,localhost,192.168.0').split(',')
    local_hosts = [h.strip() for h in local_hosts if h.strip()]
    if any(host_only.startswith(h) for h in local_hosts):
        return None

    # If the host is an IP address, decide based on private/public and port
    try:
        ip_obj = ipaddress.ip_address(host_only)
        if ip_obj.is_private:
            # If hitting the Flask server directly on its HTTP port, upgrade to HTTPS on the same host
            try:
                flask_port_str = str(FlaskServerPort)
            except Exception:
                flask_port_str = '8080'

            if port == flask_port_str:
                # Build HTTPS URL without the explicit HTTP port
                target = f"https://{host_only}{request.full_path if request.query_string else request.path}"
                return redirect(target, code=301)
            # Otherwise (private IP but different port), do not force to avoid surprises
            return None
        else:
            # Public IPs: upgrade to HTTPS
            return redirect(request.url.replace('http://', 'https://'), code=301)
    except ValueError:
        # Not an IP literal (likely a domain): upgrade to HTTPS
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

# CSRF configuration for API/headless clients
app.config['WTF_CSRF_TIME_LIMIT'] = int(os.getenv('WTF_CSRF_TIME_LIMIT', '3600'))  # 1 hour default
app.config['WTF_CSRF_HEADERS'] = ['X-CSRFToken', 'X-CSRF-Token']

try:
    from flask_wtf.csrf import generate_csrf

    @app.route('/security/csrf-token', methods=['GET'])
    def get_csrf_token():
        """Issue a CSRF token for headless/API clients.

        Client flow:
        1) GET /security/csrf-token -> receive JSON {csrfToken} and session cookie
        2) POST to protected endpoint with:
           - Cookies from step 1
           - Header 'X-CSRFToken': csrfToken
        """
        token = generate_csrf()
        resp = jsonify({"csrfToken": token})
        # Double-submit cookie pattern: mirror token in a readable cookie for diagnostics/tools
        resp.set_cookie(
            'csrf_token', token,
            secure=request.is_secure,
            httponly=False,
            samesite='Lax',
            path='/'
        )
        return resp
except Exception as e:
    print(f"CSRF token endpoint not available: {e}")

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
                # Replace dynamic parts with example values fo`r display
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
from app.WebsocketServer import (
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

    # Determine whether SSL/TLS should be enabled when starting the Flask
    # server. If the environment requests SSL and provides a cert/key pair,
    # we'll start Flask with an ssl_context so the server can accept TLS
    # handshakes. Otherwise, run plain HTTP. This makes explicit the behavior
    # and prevents ERR_SSL_PROTOCOL_ERROR when clients attempt HTTPS against a
    # plain HTTP server.
    flask_host = os.getenv("FLASK_SERVER_HOST", "127.0.0.1")
    flask_port = os.getenv("FLASK_SERVER_PORT", FlaskServerPort)
    print(f"Starting Flask server on {gethostname()} at http://{flask_host}:{flask_port}")

    # Environment-driven SSL toggle
    use_ssl = os.getenv('FLASK_USE_SSL', 'False').lower() in ('1', 'true', 'yes')
    ssl_cert = os.getenv('SSL_CERT_PATH')
    ssl_key = os.getenv('SSL_KEY_PATH')

    if use_ssl:
        # Require both cert and key to be present on disk
        if ssl_cert and ssl_key and os.path.exists(ssl_cert) and os.path.exists(ssl_key):
            print(f"Starting Flask with SSL on 0.0.0.0:{FlaskServerPort} using cert: {ssl_cert}")
            try:
                app.run(host="0.0.0.0", port=FlaskServerPort, debug=False, ssl_context=(ssl_cert, ssl_key))
            except Exception as e:
                print(f"Failed to start Flask with SSL: {e}")
                print("Falling back to plain HTTP on the same port")
                app.run(host="0.0.0.0", port=FlaskServerPort, debug=False)
        else:
            print("FLASK_USE_SSL is set but SSL_CERT_PATH/SSL_KEY_PATH are missing or files do not exist.")
            print("Starting without SSL. If you want HTTPS, set FLASK_USE_SSL=True and provide valid SSL_CERT_PATH and SSL_KEY_PATH.")
            app.run(host="0.0.0.0", port=FlaskServerPort, debug=False)
    else:
        # Plain HTTP
        app.run(host="0.0.0.0", port=FlaskServerPort, debug=False)

    