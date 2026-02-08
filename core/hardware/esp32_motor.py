"""
RPi <-> ESP32 serial controller for TMC2209 telescope motor.

Protocol: newline-delimited JSON commands, responses include {status: ok|error, ...}
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import serial  # pyserial


@dataclass
class ESP32Config:
	port: str = "/dev/ttyUSB0"
	baudrate: int = 115200
	timeout: float = 0.2  # read timeout seconds


class ESP32Motor:
	def __init__(self, cfg: ESP32Config | None = None, motor_id: str = "motor1") -> None:
		"""Open the serial port and prepare the controller.

		- cfg: serial connection settings (port, baudrate, timeout)
		- motor_id: identifier for the specific motor to control (e.g., "motor1", "motor2")
		"""
		self.cfg = cfg or ESP32Config()
		self.motor_id = motor_id
		self.ser = serial.Serial(self.cfg.port, self.cfg.baudrate, timeout=self.cfg.timeout)
		self._lock = threading.Lock()
		# Give ESP32 a moment after opening
		time.sleep(0.2)
		self._drain()

	def close(self) -> None:
		"""Close the underlying serial port (safe to call multiple times)."""
		try:
			self.ser.close()
		except Exception:
			pass

	# Core send/receive
	def _send(self, obj: Dict[str, Any]) -> Dict[str, Any]:
		"""Send a JSON command and return the 'data' object from the response.

		Raises TimeoutError on no reply, RuntimeError on error status or bad JSON.
		"""
		line = json.dumps(obj, separators=(",", ":")) + "\n"
		with self._lock:
			self.ser.write(line.encode("utf-8"))
			self.ser.flush()
			resp = self.ser.readline().decode("utf-8", errors="ignore").strip()
		if not resp:
			raise TimeoutError("No response from ESP32")
		try:
			data = json.loads(resp)
		except json.JSONDecodeError as e:
			raise RuntimeError(f"Invalid JSON from ESP32: {resp}") from e
		if data.get("status") != "ok":
			raise RuntimeError(data.get("message", "ESP32 error"))
		return data.get("data", {})

	def _drain(self) -> None:
		"""Clear any boot messages remaining in the input buffer."""
		try:
			self.ser.reset_input_buffer()
		except Exception:
			pass

	# High-level API
	def enable(self, on: bool) -> Dict[str, Any]:
		"""Enable or disable the stepper driver (power stage)."""
		return self._send({"cmd": "enable", "motor": self.motor_id, "value": bool(on)})

	def set_direction(self, forward: bool) -> Dict[str, Any]:
		"""Set motor direction: True=forward, False=reverse (DIR pin)."""
		return self._send({"cmd": "set_dir", "motor": self.motor_id, "forward": bool(forward)})

	def set_speed(self, steps_per_sec: float) -> Dict[str, Any]:
		"""Set target speed in steps/second and enter continuous mode (does not auto-enable)."""
		return self._send({"cmd": "set_speed", "motor": self.motor_id, "sps": float(steps_per_sec)})

	def start(self, steps_per_sec: float, forward: Optional[bool] = None) -> Dict[str, Any]:
		"""Start continuous rotation at the given speed; optionally set direction.

		This enables the driver automatically and begins stepping until `stop()` is called.
		"""
		payload: Dict[str, Any] = {"cmd": "start", "motor": self.motor_id, "sps": float(steps_per_sec)}
		if forward is not None:
			payload["forward"] = bool(forward)
		return self._send(payload)

	def move_steps(self, steps: int, sps: Optional[float] = None, forward: Optional[bool] = None) -> Dict[str, Any]:
		"""Queue a finite move by number of steps; optional speed and direction override."""
		payload: Dict[str, Any] = {"cmd": "move_steps", "motor": self.motor_id, "steps": int(steps)}
		if sps is not None:
			payload["sps"] = float(sps)
		if forward is not None:
			payload["forward"] = bool(forward)
		return self._send(payload)

	def stop(self) -> Dict[str, Any]:
		"""Stop motion, clear pending steps, and disable the driver."""
		return self._send({"cmd": "stop", "motor": self.motor_id})

	def set_microsteps(self, microsteps: int) -> Dict[str, Any]:
		"""Set TMC2209 microstepping factor (e.g., 16, 32, 64)."""
		return self._send({"cmd": "set_microsteps", "motor": self.motor_id, "value": int(microsteps)})

	def set_current(self, mA: int) -> Dict[str, Any]:
		"""Set RMS motor current in milliamps (driver.rms_current)."""
		return self._send({"cmd": "set_current", "motor": self.motor_id, "mA": int(mA)})

	def set_mode(self, mode: str) -> Dict[str, Any]:
		# mode: "stealth" (stealthChop2) or "spread" (SpreadCycle)
		"""Switch chopper mode: 'stealth' for stealthChop2 or 'spread' for SpreadCycle."""
		m = mode.lower()
		if m.startswith("stealth"):
			val = "stealth"
		elif m.startswith("spread"):
			val = "spread"
		else:
			raise ValueError("mode must be 'stealth' or 'spread'")
		return self._send({"cmd": "set_mode", "motor": self.motor_id, "mode": val})

	def set_accel(self, steps_per_sec2: float) -> Dict[str, Any]:
		"""Set max acceleration in steps/second^2 used by the speed ramp."""
		return self._send({"cmd": "set_accel", "motor": self.motor_id, "sps2": float(steps_per_sec2)})

	def status(self) -> Dict[str, Any]:
		"""Query current firmware status and configuration snapshot."""
		return self._send({"cmd": "status", "motor": self.motor_id})
	
	def status_all(self) -> Dict[str, Any]:
		"""Query status of all motors on the ESP32."""
		return self._send({"cmd": "status"})


# Factory function for clearer motor instantiation
def create_motor(motor_id: str = "motor1", port: str = "/dev/ttyUSB0", baudrate: int = 115200, timeout: float = 0.2) -> ESP32Motor:
	"""Create a motor controller with clear parameter specification.
	
	Args:
		motor_id: Motor identifier (e.g., "motor1", "motor2")
		port: Serial port path
		baudrate: Serial communication speed
		timeout: Read timeout in seconds
	
	Returns:
		ESP32Motor: Configured motor controller instance
		
	Example:
		motor1 = create_motor(motor_id="motor1", port="/dev/ttyUSB0")
		motor2 = create_motor(motor_id="motor2", port="/dev/ttyUSB1")
	"""
	cfg = ESP32Config(port=port, baudrate=baudrate, timeout=timeout)
	return ESP32Motor(cfg, motor_id=motor_id)


class ESP32MotorArray:
	"""Manage multiple motors easily with list-like access."""
	
	def __init__(self, motor_configs: list[dict]):
		"""Initialize multiple motors from configuration list.
		
		Args:
			motor_configs: List of motor configuration dictionaries
			Example: [
				{"motor_id": "motor1", "port": "/dev/ttyUSB0"},
				{"motor_id": "motor2", "port": "/dev/ttyUSB1"}
			]
		"""
		self.motors = []
		for config in motor_configs:
			motor = create_motor(**config)
			self.motors.append(motor)
	
	def __getitem__(self, index: int) -> ESP32Motor:
		"""Access motor by index."""
		return self.motors[index]
	
	def __len__(self) -> int:
		"""Get number of motors."""
		return len(self.motors)
	
	def get_by_id(self, motor_id: str) -> ESP32Motor:
		"""Get motor by ID."""
		for motor in self.motors:
			if motor.motor_id == motor_id:
				return motor
		raise ValueError(f"Motor with ID '{motor_id}' not found")
	
	def close_all(self):
		"""Close all motor connections."""
		for motor in self.motors:
			motor.close()
	
	def status_all(self) -> Dict[str, Any]:
		"""Get status of all motors (uses first motor's connection)."""
		if self.motors:
			return self.motors[0].status_all()
		return {}


if __name__ == "__main__":
	# Demonstrate different ways to create and manage motors
	
	print("=== Method 1: Direct instantiation ===")
	cfg = ESP32Config(port="/dev/ttyUSB0", baudrate=115200)
	motor1 = ESP32Motor(cfg, motor_id="motor1")
	
	print("=== Method 2: Factory function ===")
	motor1_alt = create_motor(motor_id="motor1", port="/dev/ttyUSB0")
	
	print("=== Method 3: Motor array for multiple motors ===")
	motor_configs = [
		{"motor_id": "motor1", "port": "/dev/ttyUSB0"},
		# {"motor_id": "motor2", "port": "/dev/ttyUSB1"}  # Add when you have second motor
	]
	motors = ESP32MotorArray(motor_configs)
	
	try:
		# Use the motor array approach
		print("All motors status:", motors.status_all())
		
		# Access motor by index
		motor1_from_array = motors[0]
		print("Motor1 specific status:", motor1_from_array.status())
		
		# Access motor by ID
		motor1_by_id = motors.get_by_id("motor1")
		print("Enable motor1:", motor1_by_id.enable(True))
		print("Mode stealth:", motor1_by_id.set_mode("stealth"))
		print("Current 500mA:", motor1_by_id.set_current(500))
		print("Microsteps 16:", motor1_by_id.set_microsteps(16))
		print("Accel:", motor1_by_id.set_accel(1500))
		print("Set dir forward:", motor1_by_id.set_direction(True))
		print("Speed 800 sps:", motor1_by_id.set_speed(800))
		time.sleep(2)
		print("Stop:", motor1_by_id.stop())
		
	finally:
		motor1.close()
		motor1_alt.close()
		motors.close_all()

# MICROSTEPS=16 python turn_degrees.py 360 --duration 5
