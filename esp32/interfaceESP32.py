from __future__ import annotations

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
	def __init__(self, cfg: ESP32SerialConfig | None = None) -> None:
		self.cfg = cfg or ESP32SerialConfig()
		try:
			self.ser = serial.Serial(self.cfg.port, self.cfg.baudrate, timeout=self.cfg.timeout)
		except serial.SerialException as e:
			import glob
			available = glob.glob('/dev/tty*') + glob.glob('/dev/cu*')
			usb_ports = [p for p in available if 'USB' in p or 'ACM' in p]
			raise RuntimeError(
				f"Cannot open {self.cfg.port}: {e}\n"
				f"Available USB ports: {usb_ports if usb_ports else 'None found'}\n"
				f"Try: ls /dev/tty* | grep -E '(USB|ACM)'"
			) from e
		self._lock = threading.Lock()
		time.sleep(0.2)
		self._drain()

	def close(self) -> None:
		try:
			self.ser.close()
		except Exception:
			pass

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
			raise RuntimeError(data.get("message", "ESP32 error"))
		return data.get("data", {})

	def list_motors(self) -> Dict[str, Any]:
		return self.send({"cmd": "list_motors"})

	def delete_motor(self, motor_id: str) -> Dict[str, Any]:
		return self.send({"cmd": "delete_motor", "motor": motor_id})

	def led_on(self) -> Dict[str, Any]:
		return self.send({"cmd": "led", "mode": "on"})

	def led_off(self) -> Dict[str, Any]:
		return self.send({"cmd": "led", "mode": "off"})

	def led_blink(self, interval_ms: int = 500, auto_off_ms: Optional[int] = None) -> Dict[str, Any]:
		payload: Dict[str, Any] = {
			"cmd": "led",
			"mode": "blink",
			"interval_ms": int(interval_ms),
		}
		if auto_off_ms is not None:
			payload["auto_off_ms"] = int(auto_off_ms)
		return self.send(payload)


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

	def turn_degrees(self, degrees: float, forward: bool = True, timeout: Optional[float] = None) -> Dict[str, Any]:
		if timeout is None:
			steps = int((degrees / 360.0) * self._steps_per_rev)
			duration_s = (steps * self._current_speed_us) / 1_000_000
			timeout = duration_s + 2.0
		return self.conn.send(
			{
				"cmd": "turn_degrees",
				"motor": self.motor_id,
				"degrees": float(degrees),
				"forward": bool(forward),
			},
			timeout=timeout,
		)

	def stop(self) -> Dict[str, Any]:
		return self.conn.send({"cmd": "stop", "motor": self.motor_id})

	def status(self) -> Dict[str, Any]:
		return self.conn.send({"cmd": "status", "motor": self.motor_id})

