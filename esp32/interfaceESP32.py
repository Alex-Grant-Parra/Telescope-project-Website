from __future__ import annotations

import glob
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import serial  # pyserial


@dataclass
class ESP32SerialConfig:
	port: str = "/dev/ttyUSB0"
	baudrate: int = 115200
	timeout: float = 0.5


class ESP32Connection:
	def __init__(self, cfg: ESP32SerialConfig | None = None, *, scan_all_ports: bool = True) -> None:
		self.cfg = cfg or ESP32SerialConfig()
		self.ser = None
		
		candidate_ports = self._candidate_ports(self.cfg.port if scan_all_ports else None)
		last_error: Exception | None = None
		for port in candidate_ports:
			try:
				self.ser = serial.Serial(port, self.cfg.baudrate, timeout=self.cfg.timeout)
				self.cfg.port = port
				if not self._probe_identity():
					self.close()
					continue
				print(f"[ESP32] Connected to {port}")
				break
			except (serial.SerialException, OSError, RuntimeError) as e:
				last_error = e
				self.close()
				continue

		if self.ser is None:
			ports_text = ", ".join(candidate_ports) if candidate_ports else self.cfg.port
			raise RuntimeError(
				f"Unable to connect to ESP32 on available USB serial ports: {ports_text}"
			) from last_error
		
		self._lock = threading.Lock()
		time.sleep(0.2)
		self._drain()
		try:
			ESP32LED.attach(self)
		except NameError:
			pass

	@staticmethod
	def _candidate_ports(preferred_port: Optional[str] = None) -> list[str]:
		ports: list[str] = []
		seen: set[str] = set()

		def add_port(port: str) -> None:
			if port and port not in seen:
				seen.add(port)
				ports.append(port)

		add_port(preferred_port or "")
		for pattern in ("/dev/serial/by-id/*", "/dev/ttyUSB*", "/dev/ttyACM*"):
			for port in sorted(glob.glob(pattern)):
				add_port(port)
		return ports

	def _probe_identity(self) -> bool:
		try:
			self._drain()
			line = json.dumps({"cmd": "list_motors"}, separators=(",", ":")) + "\n"
			self.ser.write(line.encode("utf-8"))
			self.ser.flush()
			resp = self.ser.readline().decode("utf-8", errors="ignore").strip()
			if not resp:
				return False
			data = json.loads(resp)
			return data.get("status") == "ok"
		except Exception:
			return False

	def close(self) -> None:
		try:
			if self.ser is not None:
				self.ser.close()
		except Exception:
			pass
		finally:
			self.ser = None

	def _drain(self) -> None:
		try:
			self.ser.reset_input_buffer()
		except Exception:
			pass

	def send(self, payload: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
		line = json.dumps(payload, separators=(",", ":")) + "\n"
		with self._lock:
			if timeout is not None:
				prev_timeout = self.ser.timeout
				self.ser.timeout = timeout
			try:
				self.ser.write(line.encode("utf-8"))
				self.ser.flush()
				resp = self.ser.readline().decode("utf-8", errors="ignore").strip()
			finally:
				if timeout is not None:
					self.ser.timeout = prev_timeout
		if not resp:
			raise TimeoutError("No response from ESP32")
		try:
			data = json.loads(resp)
		except json.JSONDecodeError as exc:
			raise RuntimeError(f"Invalid JSON from ESP32: {resp}") from exc
		if data.get("status") != "ok":
			error_msg = data.get("message", "ESP32 error")
			raise RuntimeError(f"ESP32 error: {error_msg} | Full response: {data}")
		return data.get("data", {})

	def list_motors(self) -> Dict[str, Any]:
		return self.send({"cmd": "list_motors"})

	def delete_motor(self, motor_id: str) -> Dict[str, Any]:
		return self.send({"cmd": "delete_motor", "motor": motor_id})

	def led_on(self) -> Dict[str, Any]:
		return self.send({"cmd": "led", "led": "board", "mode": "on"})

	def led_off(self) -> Dict[str, Any]:
		return self.send({"cmd": "led", "led": "board", "mode": "off"})

	def led_blink(self, interval_ms: int = 500, auto_off_ms: Optional[int] = None) -> Dict[str, Any]:
		payload: Dict[str, Any] = {
			"cmd": "led",
			"led": "board",
			"mode": "blink",
			"interval_ms": int(interval_ms),
		}
		if auto_off_ms is not None:
			payload["auto_off_ms"] = int(auto_off_ms)
		return self.send(payload)


class ESP32LED:
	class Channel:
		def __init__(self, conn: ESP32Connection, name: str, pin: int) -> None:
			self.conn = conn
			self.name = name
			self.pin = pin

		def action(
			self,
			mode: Optional[str] = None,
			on: Optional[bool] = None,
			interval_ms: int = 500,
			auto_off_ms: Optional[int] = None,
		) -> Dict[str, Any]:
			payload: Dict[str, Any] = {"cmd": "led", "led": self.name}
			if mode is not None:
				payload["mode"] = mode
			elif on is not None:
				payload["on"] = bool(on)
			else:
				payload["mode"] = "on"
			if payload.get("mode") == "blink":
				payload["interval_ms"] = int(interval_ms)
				if auto_off_ms is not None:
					payload["auto_off_ms"] = int(auto_off_ms)
			return self.conn.send(payload)

		def on(self) -> Dict[str, Any]:
			return self.action(mode="on")

		def off(self) -> Dict[str, Any]:
			return self.action(mode="off")

		def blink(self, interval_ms: int = 500, auto_off_ms: Optional[int] = None) -> Dict[str, Any]:
			return self.action(mode="blink", interval_ms=interval_ms, auto_off_ms=auto_off_ms)

	def __init__(self, conn: ESP32Connection) -> None:
		self.conn = conn
		self.board = self.Channel(conn, "board", 2)
		self.boardLED = self.board
		self.yellow = self.Channel(conn, "yellow", 18)
		self.blue = self.Channel(conn, "blue", 5)
		self.white = self.Channel(conn, "white", 17)
		self.green = self.Channel(conn, "green", 16)
		self.red = self.Channel(conn, "red", 4)

	@classmethod
	def attach(cls, conn: ESP32Connection) -> "ESP32LED":
		instance = cls(conn)
		cls.board = instance.board
		cls.boardLED = instance.board
		cls.yellow = instance.yellow
		cls.blue = instance.blue
		cls.white = instance.white
		cls.green = instance.green
		cls.red = instance.red
		return instance


class ESP32Motor:
	def __init__(self, conn: ESP32Connection, motor_id: str) -> None:
		self.conn = conn
		self.motor_id = motor_id
		self._steps_per_rev = 1600
		self._current_speed_us = 1250

	@classmethod
	def create(
		cls,
		conn: ESP32Connection,
		motor_id: str,
		step_pin: int,
		dir_pin: int,
		en_pin: int,
		steps_per_rev: int = 1600,
		speed_us: Optional[int] = None,
		engage: bool = False,
		replace: bool = False,
	) -> "ESP32Motor":
		"""Create a new motor instance on the ESP32.
		
		Args:
			replace: If True, delete existing motor with same ID before creating
		"""
		if replace:
			try:
				conn.delete_motor(motor_id)
			except RuntimeError:
				pass  # Motor didn't exist, that's fine
		
		payload: Dict[str, Any] = {
			"cmd": "create_motor",
			"motor": motor_id,
			"step": int(step_pin),
			"dir": int(dir_pin),
			"en": int(en_pin),
			"steps_per_rev": int(steps_per_rev),
			"engage": bool(engage),
		}
		if speed_us is not None:
			payload["speed_us"] = int(speed_us)
		conn.send(payload)
		instance = cls(conn, motor_id)
		instance._steps_per_rev = steps_per_rev
		instance._current_speed_us = speed_us if speed_us is not None else 1250
		return instance

	def engage(self) -> Dict[str, Any]:
		return self.conn.send({"cmd": "engage", "motor": self.motor_id})

	def disengage(self) -> Dict[str, Any]:
		return self.conn.send({"cmd": "disengage", "motor": self.motor_id})

	def enable(self, on: bool) -> Dict[str, Any]:
		return self.conn.send({"cmd": "enable", "motor": self.motor_id, "value": bool(on)})

	def set_speed_us(self, delay_us: int) -> Dict[str, Any]:
		self._current_speed_us = delay_us
		return self.conn.send({"cmd": "set_speed", "motor": self.motor_id, "speed_us": int(delay_us)})

	def set_speed_sps(self, steps_per_sec: float) -> Dict[str, Any]:
		self._current_speed_us = int(1_000_000 / steps_per_sec)
		return self.conn.send({"cmd": "set_speed", "motor": self.motor_id, "sps": float(steps_per_sec)})

	def turn_degrees(self, degrees: float, forward: bool = True, timeout: Optional[float] = None, waitUntilFinished: bool = False) -> Dict[str, Any]:
		# Handle negative degrees (flip direction)
		if degrees < 0:
			degrees = abs(degrees)
			forward = not forward
		
		# Calculate expected duration
		steps = int((degrees / 360.0) * self._steps_per_rev)
		duration_s = (steps * self._current_speed_us) / 1_000_000
		
		if timeout is None:
			timeout = duration_s + 2.0
		
		# Get initial position if we need to wait and verify
		if waitUntilFinished:
			initial_position = self.get_position_degrees()
			target_position = initial_position + degrees if forward else initial_position - degrees
		
		# Send the turn command
		result = self.conn.send(
			{
				"cmd": "turn_degrees",
				"motor": self.motor_id,
				"degrees": float(degrees),
				"forward": bool(forward),
			},
			timeout=timeout,
		)
		
		# Poll until motor reaches target position
		if waitUntilFinished:
			tolerance = 0.5  # degrees
			poll_interval = 0.1  # seconds
			
			while True:
				current_position = self.get_position_degrees()
				if abs(current_position - target_position) <= tolerance:
					break
				
				time.sleep(poll_interval)
			
			result["final_position"] = current_position
			result["target_position"] = target_position
			result["position_error"] = abs(current_position - target_position)
		
		return result

	def start_continuous(self, forward: bool = True) -> Dict[str, Any]:
		#Start the motor spinning continuously until stopped.
		
		return self.conn.send(
			{
				"cmd": "start_continuous",
				"motor": self.motor_id,
				"forward": bool(forward),
			}
		)

	def stop(self) -> Dict[str, Any]:
		return self.conn.send({"cmd": "stop", "motor": self.motor_id})

	def status(self) -> Dict[str, Any]:
		return self.conn.send({"cmd": "status", "motor": self.motor_id})

	def get_position(self) -> int:
		"""Get the current position of the motor in steps (signed integer)."""
		result = self.conn.send({"cmd": "get_position", "motor": self.motor_id})
		return result.get("position", 0)

	def get_position_degrees(self, gear_ratio: float = 360.0) -> float:
		"""Get the current position in degrees (polar alignment deviation).
		
		Args:
			gear_ratio: Sky degrees per motor revolution (default: 360 for RA, 144 for DEC)
		
		Returns:
			Angular deviation in degrees
		"""
		steps = self.get_position()
		return (steps * gear_ratio) / self._steps_per_rev

	def get_position_arcmin(self, gear_ratio: float = 360.0) -> float:
		"""Get the current position in arcminutes (fine alignment precision)."""
		degrees = self.get_position_degrees(gear_ratio)
		return degrees * 60

	def get_position_arcsec(self, gear_ratio: float = 360.0) -> float:
		"""Get the current position in arcseconds (highest precision)."""
		arcmin = self.get_position_arcmin(gear_ratio)
		return arcmin * 60

	def reset_position(self) -> Dict[str, Any]:
		"""Reset the motor position counter to zero."""
		return self.conn.send({"cmd": "reset_position", "motor": self.motor_id})

