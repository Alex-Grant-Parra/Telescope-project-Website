# ASTRA \- Automated Sidereal Tracking and Remote Astronomy

## A modern telescope automation system for remote observation, object tracking and astrophotography with a web-based observatory management platform.

---

## Features

* Web-based telescope control  
* Distributed telescope network management  
* Automated target acquisition and tracking  
* Astrophotography image capture  
* Observation scheduling and automation  
* Interactive planetarium interface  
* Astronomical object database  
* Solar system object tracking  
* Remote camera and mount control  
* REST API for astronomical data access  
* Raspberry Pi and ESP32 powered telescope nodes  
* Beginner-friendly operation with advanced manual controls  
* Source-available and self-hostable

## System Architecture

ASTRA uses a web-based control server connected to distributed Raspberry Pi \+ ESP32 telescope nodes. Commands, live view camera frames, and tracking data flow through WebSocket channels, while each node handles its own motor control, sensors, and imaging pipeline.

![System Architecture](https://raw.githubusercontent.com/Alex-Grant-Parra/ASTRA/Server/canary/docs/System%20Architecture.drawio.png)

## Client Setup (For running ASTRA on your telescope system)

* In the email you were sent when you purchased the telescope system, select register. This will give you a client ID, API token and server URL.  
* Create an account, and link your client ID and API key to it, following the on screen directions.  
* Power on the system, and wait for the blue LED to stay constantly lit.  
* Use the keypad to enter in the client ID, API token and server URL. There will be an on screen confirmation when connected.  
* (Recommended) Check for updates in the settings window. This may take several minutes if updates are found. Do not power off your device.   
* Log in and access the main interface page. It is recommended that you follow the first time tutorial on how to use the site.

## ADVANCED - Server Setup (For running your own control server)

 * Follow this guide to learn how to do this:
 https://github.com/Alex-Grant-Parra/ASTRA/wiki/Server-Setup-(For-running-your-own-control-server)

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
- When downloading the server, the database will not be included. This may change in future versions, but you will have to supply your own data for now.
