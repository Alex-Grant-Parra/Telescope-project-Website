from subprocess import run
from time import sleep
from os import makedirs, path
from datetime import datetime

class Camera:

    def ensureConnection(retryCount=3, delaySeconds=2):
        # Checks for a connected camera using gphoto2.
        # Retries if not found, and returns True if connected, False otherwise.
        for attempt in range(1, retryCount + 1):
            try:
                result = run(
                    ["gphoto2", "--auto-detect"],
                    capture_output=True,
                    text=True
                )
                output = result.stdout.strip()
                if "usb:" in output.lower():
                    print("Camera connected.")
                    return True
                else:
                    print(f"No camera detected. Attempt {attempt} of {retryCount}.")
                    if attempt < retryCount:
                        sleep(delaySeconds)
            except Exception as error:
                print(f"Error checking camera: {error}")
                return False

        print("Camera connection failed after retries.")
        return False

    def getSettingChoices(label, path):
        try:
            # Check connection first
            if not Camera.ensureConnection():
                print(f"Camera not connected when querying {label}")
                return []
            result = run(
                ["gphoto2", "--get-config", path],
                capture_output=True,
                text=True,
                timeout=5  # seconds, adjust as needed
            )
            output = result.stdout
            choices = []

            for line in output.splitlines():
                if line.strip().startswith("Choice:"):
                    parts = line.split(" ", 2)
                    if len(parts) == 3:
                        choices.append(parts[2])
            
            return choices

        except Exception as error:
            print(f"Error reading {label}: {error}")
            return []

    @staticmethod
    def setSetting(path, value):
        """
        Sets a camera setting using gphoto2.
        """
        from subprocess import run
        result = run(
            ["gphoto2", "--set-config", f"{path}={value}"],
            capture_output=True,
            text=True
        )
        print(result)
        if result.returncode != 0:
            raise Exception(result.stderr.strip())
        return True

    @staticmethod
    def get_latest_file_number():
        result = run(["gphoto2", "--list-files"], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to list files: {result.stderr.strip()}")
        lines = result.stdout.splitlines()
        max_num = 0
        for line in lines:
            if line.strip().startswith("#"):
                parts = line.split()
                if len(parts) > 1 and parts[0].startswith("#"):
                    try:
                        num = int(parts[0][1:])
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        continue
        return max_num

    @staticmethod
    def capturePhoto(save_folder):
        makedirs(save_folder, exist_ok=True)

        # Use gphoto2's built-in capture and download
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Download all files to the save_folder, keeping original names
        capture = run(
            [
                "gphoto2",
                "--capture-image-and-download",
                "--filename", f"{save_folder}/photo_{timestamp}_%C.%C"
            ],
            capture_output=True,
            text=True
        )
        print(f"[DEBUG] Capture and download output: {capture.stdout} {capture.stderr}")
        if capture.returncode != 0:
            raise Exception(f"Capture and download failed: {capture.stderr.strip()}")

        # Collect downloaded filenames from output
        downloaded_files = []
        for line in capture.stdout.splitlines():
            if "Saving file as" in line:
                # Extract the filename from the output
                saved_file = line.split("Saving file as")[-1].strip()
                downloaded_files.append(path.basename(saved_file))

        # Reset camera and wait for device to be free
        run(["gphoto2", "--reset"], capture_output=True, text=True)
        sleep(5)

        return downloaded_files



Camera.ensureConnection()

# Camera settings to list
settings = {
    "Shutter Speed": "/main/capturesettings/shutterspeed",
    "ISO": "/main/imgsettings/iso",
}