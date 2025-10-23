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
	def __init__(self, cfg: ESP32Config | None = None) -> None:
		self.cfg = cfg or ESP32Config()
		self.ser = serial.Serial(self.cfg.port, self.cfg.baudrate, timeout=self.cfg.timeout)
		self._lock = threading.Lock()
		# Give ESP32 a moment after opening
		time.sleep(0.2)
		self._drain()

	def close(self) -> None:
		try:
			self.ser.close()
		except Exception:
			pass

	# Core send/receive
	def _send(self, obj: Dict[str, Any]) -> Dict[str, Any]:
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
		# Clear any boot messages
		try:
			self.ser.reset_input_buffer()
		except Exception:
			pass

	# High-level API
	def enable(self, on: bool) -> Dict[str, Any]:
		return self._send({"cmd": "enable", "value": bool(on)})

	def set_direction(self, forward: bool) -> Dict[str, Any]:
		return self._send({"cmd": "set_dir", "forward": bool(forward)})

	def set_speed(self, steps_per_sec: float) -> Dict[str, Any]:
		return self._send({"cmd": "set_speed", "sps": float(steps_per_sec)})

	def move_steps(self, steps: int, sps: Optional[float] = None, forward: Optional[bool] = None) -> Dict[str, Any]:
		payload: Dict[str, Any] = {"cmd": "move_steps", "steps": int(steps)}
		if sps is not None:
			payload["sps"] = float(sps)
		if forward is not None:
			payload["forward"] = bool(forward)
		return self._send(payload)

	def stop(self) -> Dict[str, Any]:
		return self._send({"cmd": "stop"})

	def set_microsteps(self, microsteps: int) -> Dict[str, Any]:
		return self._send({"cmd": "set_microsteps", "value": int(microsteps)})

	def set_current(self, mA: int) -> Dict[str, Any]:
		return self._send({"cmd": "set_current", "mA": int(mA)})

	def set_mode(self, mode: str) -> Dict[str, Any]:
		# mode: "stealth" (stealthChop2) or "spread" (SpreadCycle)
		m = mode.lower()
		if m.startswith("stealth"):
			val = "stealth"
		elif m.startswith("spread"):
			val = "spread"
		else:
			raise ValueError("mode must be 'stealth' or 'spread'")
		return self._send({"cmd": "set_mode", "mode": val})

	def set_accel(self, steps_per_sec2: float) -> Dict[str, Any]:
		return self._send({"cmd": "set_accel", "sps2": float(steps_per_sec2)})

	def status(self) -> Dict[str, Any]:
		return self._send({"cmd": "status"})


if __name__ == "__main__":
	# Simple manual test runner
	cfg = ESP32Config(port="/dev/ttyUSB0", baudrate=115200)
	m = ESP32Motor(cfg)
	try:
		print("ESP32 status:", m.status())
		print("Enable:", m.enable(True))
		print("Mode stealth:", m.set_mode("stealth"))
		print("Current 500mA:", m.set_current(500))
		print("Microsteps 16:", m.set_microsteps(16))
		print("Accel:", m.set_accel(1500))
		print("Set dir forward:", m.set_direction(True))
		print("Speed 800 sps:", m.set_speed(800))
		time.sleep(2)
		print("Stop:", m.stop())
	finally:
		m.close()

# MICROSTEPS=16 python turn_degrees.py 360 --duration 5