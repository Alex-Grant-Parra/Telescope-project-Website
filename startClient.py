import subprocess

projectDir = "/home/alex/Telescope-Project-Client-canary"

VENV_PATH = f"{projectDir}/venv/bin/python"

FLASK_APP_PATH = f"{projectDir}/Client.py"
try:
    subprocess.run([VENV_PATH, FLASK_APP_PATH], check=True)

except KeyboardInterrupt:
    print("Closed client connection successfully")
    quit()
    