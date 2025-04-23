import subprocess

VENV_PATH = "/home/alex/Telescope_project/Main_Project/venv/bin/python"

FLASK_APP_PATH = "/home/alex/Telescope_project/Main_Project/Server.py"

subprocess.run([VENV_PATH, FLASK_APP_PATH], check=True)