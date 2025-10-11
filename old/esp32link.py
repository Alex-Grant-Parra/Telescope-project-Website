import serial
import time
import threading
from typing import Optional, Dict, Any
import logging

class ESP32StepperController:
    """
    Controller class for ESP32-based stepper motor control via TMC2209 driver.
    Communicates with ESP32 over USB serial connection.
    """
    
    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200, timeout: float = 2.0):
        """
        Initialize ESP32 stepper controller.
        
        Args:
            port: Serial port path (default: /dev/ttyUSB0)
            baudrate: Serial communication speed (default: 115200)
            timeout: Serial timeout in seconds (default: 2.0)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_connection: Optional[serial.Serial] = None
        self.is_connected = False
        self.lock = threading.Lock()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def connect(self) -> bool:
        """
        Establish serial connection to ESP32.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            
            # Wait for ESP32 to initialize
            time.sleep(2)
            
            # Clear any initial messages
            self.serial_connection.flushInput()
            self.serial_connection.flushOutput()
            
            # Test connection with status command
            response = self._send_command("STATUS")
            if response and response.startswith("STATUS:"):
                self.is_connected = True
                self.logger.info(f"Connected to ESP32 on {self.port}")
                return True
            else:
                self.logger.error("Failed to get valid response from ESP32")
                self.disconnect()
                return False
                
        except serial.SerialException as e:
            self.logger.error(f"Failed to connect to ESP32: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during connection: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from ESP32."""
        if self.serial_connection and self.serial_connection.is_open:
            # Send emergency stop before disconnecting
            try:
                self._send_command("STOP")
                self._send_command("DISABLE")
            except:
                pass  # Ignore errors during shutdown
            
            self.serial_connection.close()
            
        self.is_connected = False
        self.serial_connection = None
        self.logger.info("Disconnected from ESP32")
    
    def _send_command(self, command: str) -> Optional[str]:
        """
        Send command to ESP32 and return response.
        
        Args:
            command: Command string to send
            
        Returns:
            str: Response from ESP32, None if error
        """
        if not self.serial_connection:
            self.logger.error("No serial connection to ESP32")
            return None
        
        try:
            with self.lock:
                # Send command
                command_bytes = (command + '\n').encode('utf-8')
                self.serial_connection.write(command_bytes)
                self.serial_connection.flush()
                
                # Read response, but handle asynchronous messages
                max_attempts = 3
                for attempt in range(max_attempts):
                    response = self.serial_connection.readline().decode('utf-8').strip()
                    
                    if response:
                        # Check if this is an asynchronous message (movement completion)
                        if response.startswith("OK:Movement complete"):
                            self.logger.debug(f"Received async message: {response}")
                            # Continue reading for the actual command response
                            continue
                        
                        self.logger.debug(f"Command: {command} -> Response: {response}")
                        return response
                    else:
                        self.logger.warning(f"No response to command: {command} (attempt {attempt + 1})")
                        
                return None
                    
        except serial.SerialTimeoutException:
            self.logger.error(f"Timeout sending command: {command}")
            return None
        except Exception as e:
            self.logger.error(f"Error sending command '{command}': {e}")
            return None
    
    def enable_motor(self) -> bool:
        """
        Enable the stepper motor.
        
        Returns:
            bool: True if successful
        """
        response = self._send_command("ENABLE")
        return response and response.startswith("OK:")
    
    def disable_motor(self) -> bool:
        """
        Disable the stepper motor.
        
        Returns:
            bool: True if successful
        """
        response = self._send_command("DISABLE")
        return response and response.startswith("OK:")
    
    def move_steps(self, steps: int) -> bool:
        """
        Move motor by specified number of steps (relative movement).
        
        Args:
            steps: Number of steps to move (positive = clockwise, negative = counterclockwise)
            
        Returns:
            bool: True if movement started successfully
        """
        response = self._send_command(f"MOVE:{steps}")
        return response and response.startswith("OK:")
    
    def goto_position(self, position: int) -> bool:
        """
        Move motor to absolute position.
        
        Args:
            position: Target position in steps
            
        Returns:
            bool: True if movement started successfully
        """
        response = self._send_command(f"GOTO:{position}")
        return response and response.startswith("OK:")
    
    def set_speed(self, microseconds: int) -> bool:
        """
        Set motor speed by adjusting step delay.
        
        Args:
            microseconds: Delay between steps in microseconds (100-10000)
                         Lower values = faster speed
            
        Returns:
            bool: True if speed set successfully
        """
        if not 100 <= microseconds <= 10000:
            self.logger.error("Speed must be between 100-10000 microseconds")
            return False
            
        response = self._send_command(f"SPEED:{microseconds}")
        return response and response.startswith("OK:")
    
    def home_position(self) -> bool:
        """
        Set current position as home (0).
        
        Returns:
            bool: True if successful
        """
        response = self._send_command("HOME")
        return response and response.startswith("OK:")
    
    def set_microsteps(self, microsteps: int) -> bool:
        """
        Set microstep resolution.
        
        Args:
            microsteps: Microstep setting (1,2,4,8,16,32,64,256)
            
        Returns:
            bool: True if successful
        """
        valid_microsteps = [1, 2, 4, 8, 16, 32, 64, 256]
        if microsteps not in valid_microsteps:
            self.logger.error(f"Invalid microstep value. Must be one of: {valid_microsteps}")
            return False
            
        response = self._send_command(f"MICROSTEP:{microsteps}")
        return response and response.startswith("OK:")
    
    def set_movement_type(self, movement_type: str) -> bool:
        """
        Set movement type/mode.
        
        Args:
            movement_type: Movement type ("STEALTH", "INTERPOLATED", "CONTINUOUS")
            
        Returns:
            bool: True if successful
        """
        valid_types = ["STEALTH", "INTERPOLATED", "CONTINUOUS"]
        movement_type = movement_type.upper()
        
        if movement_type not in valid_types:
            self.logger.error(f"Invalid movement type. Must be one of: {valid_types}")
            return False
            
        response = self._send_command(f"MOVEMENT:{movement_type}")
        return response and response.startswith("OK:")
    
    def emergency_stop(self) -> bool:
        """
        Emergency stop - immediately halt motor movement.
        
        Returns:
            bool: True if successful
        """
        response = self._send_command("STOP")
        return response and response.startswith("OK:")
    
    def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Get current motor status.
        
        Returns:
            dict: Status information or None if error
        """
        response = self._send_command("STATUS")
        if not response or not response.startswith("STATUS:"):
            return None
        
        try:
            # Parse status response
            # Format: STATUS:Enabled=true,Position=123,Target=456,Speed=1000,Moving=false
            status_data = response[7:]  # Remove "STATUS:" prefix
            status_dict = {}
            
            for pair in status_data.split(','):
                key, value = pair.split('=')
                
                # Convert values to appropriate types
                if value.lower() in ['true', 'false']:
                    status_dict[key] = value.lower() == 'true'
                elif value in ['0', '1'] and key in ['Enabled', 'Moving']:
                    status_dict[key] = value == '1'
                elif key in ['Position', 'Target', 'Speed', 'Microsteps']:
                    status_dict[key] = int(value)
                else:
                    status_dict[key] = value
            
            return status_dict
            
        except Exception as e:
            self.logger.error(f"Error parsing status response: {e}")
            return None
    
    def wait_for_movement_complete(self, check_interval: float = 0.1, timeout: float = 30.0) -> bool:
        """
        Wait for current movement to complete.
        
        Args:
            check_interval: How often to check status (seconds)
            timeout: Maximum time to wait (seconds)
            
        Returns:
            bool: True if movement completed, False if timeout or error
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_status()
            if not status:
                self.logger.error("Could not get status while waiting for movement")
                return False
            
            if not status.get('Moving', False):
                self.logger.info(f"Movement completed at position {status.get('Position', 'unknown')}")
                return True
            
            time.sleep(check_interval)
        
        self.logger.warning("Movement timeout - stopping motor")
        self.emergency_stop()
        return False
    
    def move_degrees(self, degrees: float, steps_per_revolution: int = 200) -> bool:
        """
        Move motor by specified degrees.
        
        Args:
            degrees: Degrees to move (positive = clockwise)
            steps_per_revolution: Steps per full revolution (default: 200 for NEMA17)
            
        Returns:
            bool: True if movement started successfully
        """
        steps = int((degrees / 360.0) * steps_per_revolution)
        return self.move_steps(steps)
    
    def move_revolutions(self, revolutions: float, steps_per_revolution: int = 200) -> bool:
        """
        Move motor by specified number of revolutions.
        
        Args:
            revolutions: Number of revolutions (positive = clockwise)
            steps_per_revolution: Steps per full revolution (default: 200 for NEMA17)
            
        Returns:
            bool: True if movement started successfully
        """
        steps = int(revolutions * steps_per_revolution)
        return self.move_steps(steps)
    
    def __enter__(self):
        """Context manager entry."""
        if not self.connect():
            raise ConnectionError("Could not connect to ESP32")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


def main():
    """Example usage of the ESP32StepperController."""
    
    # Initialize controller
    controller = ESP32StepperController(port='/dev/ttyUSB0')
    
    try:
        # Connect to ESP32
        if not controller.connect():
            print("Failed to connect to ESP32")
            return
        
        # Enable motor
        if controller.enable_motor():
            print("Motor enabled successfully")
        else:
            print("Failed to enable motor")
            return
        
        # Set speed (1000 microseconds between steps)
        controller.set_speed(1000)
        print("Speed set to 1000 microseconds")
        
        # Get initial status
        status = controller.get_status()
        if status:
            print(f"Initial status: {status}")
        
        # Move 1 revolution clockwise
        print("Moving 1 revolution clockwise...")
        controller.move_revolutions(1.0)
        controller.wait_for_movement_complete()
        
        # Wait a bit
        time.sleep(1)
        
        # Move 90 degrees counterclockwise
        print("Moving 90 degrees counterclockwise...")
        controller.move_degrees(-90)
        controller.wait_for_movement_complete()
        
        # Get final status
        status = controller.get_status()
        if status:
            print(f"Final status: {status}")
        
        # Home the motor
        controller.home_position()
        print("Motor homed to position 0")
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        controller.emergency_stop()
        
    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        # Disable motor and disconnect
        controller.disable_motor()
        controller.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    main()
