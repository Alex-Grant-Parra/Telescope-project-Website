# ASTRA

ASTRA is a Flask-based telescope control and astronomy web platform.

It combines:
- a web app
- a live star map
- real-time WebSocket channels for telescope commands and live view streaming
- security features

## What This Repo Contains

- Main server: Server.py
- Flask support code: app/ and config/
- Controllers (Flask blueprints): controllers/
- Realtime services: app/WebsocketServer.py
- Data models and database layer: models/
- Astronomy and planetary models: Astrophysics/
- Security modules: security/
- Frontend templates and assets: templates/ and static/
- Project docs and reference material: docs/
- Operations scripts: scripts/
- Deployment and runtime files: infrastructure/ and instance/
- Utilities and helper tools: utility/ and tools/
- Downloads, uploads, and captured images: downloads/ and camera_photos/

## Quick Start

1. Create and activate a virtual environment.

Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Install dependencies:

```bash
pip install -r utility/requirements.txt
```

3. Create instance/.env (recommended) with at least:

```env
FLASK_SECRET_KEY=change-me
ENCRYPTION_KEY=change-me
MAIL_USERNAME=you@example.com
MAIL_PASSWORD=change-me
```

4. Start the server:

```bash
python Server.py
```

Default HTTP port is 5000.

## Core Runtime Behavior

- Flask app boots from Server.py.
- Blueprints are auto-loaded from controllers/.
- SQLite database is stored at instance/Data.db.
- WebSocket services start with the app:
	- Command server: port 4000
	- LiveView server: port 8000
- Route list is auto-generated to templates/routes.txt at startup.

## Important Environment Variables

- FLASK_SECRET_KEY: Flask session secret
- ENCRYPTION_KEY: application encryption key
- FLASK_USE_SSL: enable Flask TLS mode (True/False)
- SSL_CERT_PATH, SSL_KEY_PATH: cert and key when FLASK_USE_SSL is enabled
- FLASK_SERVER_HOST, FLASK_SERVER_PORT: host/port display and overrides
- MAX_UPLOAD_BYTES: max upload size (default 128 MiB)
- WS_IP: WebSocket bind IP (default 0.0.0.0)
- WS_PING_INTERVAL, WS_PING_TIMEOUT: WebSocket keepalive settings
- TURNSTILE_SITE_KEY, TURNSTILE_SECRET_KEY: CAPTCHA support

## Planetary Models

ASTRA includes a few different planetary models under the Astrophysics folder, each with varying precision.
- V1_Keplarian is a traditional keplarian algorithm
- V2_VSOP87A is an iterative solution, taking the sum of a large number of orbital parameters
- V3_Helios is a custom N-body engine, with a local integrator and engine, with initial parameters provided by JPL SPICE data

## Notes

- instance/.env contains secrets and should not be committed.
- infrastructure/ contains deployment-related files and logs.
