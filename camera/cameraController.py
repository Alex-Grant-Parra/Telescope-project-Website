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
    def capturePhoto(save_folder):
        """
        Captures a photo using gphoto2, downloads it to the specified folder,
        then deletes the photo from the camera if it still exists.
        Returns the filename of the saved photo.
        """
        # Ensure folder exists
        makedirs(save_folder, exist_ok=True)

        # Generate a unique filename based on timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"photo_{timestamp}.jpg"
        filepath = path.join(save_folder, filename)

        # Capture image (only capture on camera)
        capture = run(["gphoto2", "--capture-image"], capture_output=True, text=True)
        if capture.returncode != 0:
            raise Exception(f"Capture failed: {capture.stderr.strip()}")

        # List files on camera to find latest file number
        files_list = run(["gphoto2", "--list-files"], capture_output=True, text=True)
        if files_list.returncode != 0:
            raise Exception(f"Failed to list files: {files_list.stderr.strip()}")

        # Parse the latest file number from the list (search from bottom up)
        lines = files_list.stdout.splitlines()
        latest_file_number = None
        for line in reversed(lines):
            if line.strip().startswith("#"):
                parts = line.split()
                if len(parts) > 1 and parts[0].startswith("#"):
                    latest_file_number = parts[0][1:]  # Remove leading #
                    break

        if latest_file_number is None:
            raise Exception("No files found on camera after capture")

        # Download the latest file to the desired path
        get_file = run(
            ["gphoto2", "--get-file", latest_file_number, "--filename", filepath],
            capture_output=True,
            text=True
        )
        if get_file.returncode != 0:
            raise Exception(f"Download failed: {get_file.stderr.strip()}")

        # Wait a moment before deleting to allow camera to finalize file
        sleep(2)

        # Re-list files to confirm the file still exists before deleting
        files_list_after = run(["gphoto2", "--list-files"], capture_output=True, text=True)
        if files_list_after.returncode == 0:
            file_exists = False
            for line in files_list_after.stdout.splitlines():
                if line.strip().startswith(f"#{latest_file_number} "):
                    file_exists = True
                    break

            if file_exists:
                delete_file = run(
                    ["gphoto2", "--delete-file", latest_file_number],
                    capture_output=True,
                    text=True
                )
                if delete_file.returncode != 0:
                    # Suppress known 'no files' error, warn on others
                    if "*** Error (-2: 'Bad parameters')" in delete_file.stderr:
                        print(f"Warning: File #{latest_file_number} not found on camera, skipping delete.")
                    else:
                        print(f"Warning: Could not delete file {latest_file_number} from camera: {delete_file.stderr.strip()}")
            else:
                print(f"Warning: File #{latest_file_number} not found on camera when attempting delete, skipping.")
        else:
            print(f"Warning: Could not list files before deletion: {files_list_after.stderr.strip()}")

        # Reset camera to release lock
        run(["gphoto2", "--reset"], capture_output=True, text=True)

        # Optional: wait a moment for camera to be ready again
        sleep(2)

        return filename



Camera.ensureConnection()

# Camera settings to list
settings = {
    "Shutter Speed": "/main/capturesettings/shutterspeed",
    "ISO": "/main/imgsettings/iso",
}