from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from esp32.interfaceESP32 import ESP32Connection, ESP32LED
from utils.esp32_state import esp32_state


@dataclass
class _LedState:
	error_active: bool = False
	error_critical: bool = False
	movement_mode: Optional[str] = None
	tracking_active: bool = False
	tracking_pulse: bool = False
	command_busy: bool = False
	blue_on_when_idle: bool = True


class LEDManager:
	def __init__(self) -> None:
		self._state = _LedState()
		self._lock = threading.RLock()
		self._flash_lock = threading.Lock()
		self._last_led_command_at = 0.0
		self._command_gap_s = 0.5
		self._applied_signatures: dict[str, tuple[str, int]] = {}
		self._conn: Optional[ESP32Connection] = None
		self._leds: Optional[ESP32LED] = None

	def _ensure_connection(self) -> bool:
		conn = esp32_state.ensure_connection()
		if conn is None:
			self._conn = None
			self._leds = None
			return False
		if self._conn is conn and self._leds is not None:
			return True
		self._conn = conn
		self._leds = ESP32LED(conn)
		self._applied_signatures.clear()
		print("[LEDManager] ESP32 LED connection established")
		return True

	def _set_channel(self, channel_name: str, mode: str, interval_ms: int = 500) -> None:
		if not self._ensure_connection() or self._leds is None:
			return
		signature = (mode, int(interval_ms) if mode == "blink" else 0)
		if self._applied_signatures.get(channel_name) == signature:
			return
		now = time.monotonic()
		elapsed = now - self._last_led_command_at
		if elapsed < self._command_gap_s:
			time.sleep(self._command_gap_s - elapsed)
		channel = getattr(self._leds, channel_name, None)
		if channel is None:
			return
		if mode == "on":
			channel.on()
		elif mode == "off":
			channel.off()
		elif mode == "blink":
			channel.blink(interval_ms=interval_ms)
		else:
			raise ValueError(f"Unsupported LED mode: {mode}")
		self._applied_signatures[channel_name] = signature
		self._last_led_command_at = time.monotonic()

	def _apply_locked(self) -> None:
		if not self._ensure_connection() or self._leds is None:
			return

		if self._state.error_active:
			self._set_channel("red", "blink" if self._state.error_critical else "on", 160)
			self._set_channel("yellow", "off")
			self._set_channel("green", "off")
			self._set_channel("blue", "off")
			return

		self._set_channel("red", "off")

		if self._state.movement_mode == "homing":
			self._set_channel("yellow", "on")
			self._set_channel("green", "off")
		elif self._state.movement_mode == "slewing":
			self._set_channel("yellow", "blink", 700)
			self._set_channel("green", "off")
		elif self._state.tracking_active:
			self._set_channel("yellow", "off")
			self._set_channel("green", "blink" if self._state.tracking_pulse else "on", 1800)
		else:
			self._set_channel("yellow", "off")
			self._set_channel("green", "off")

		if self._state.command_busy:
			self._set_channel("blue", "blink", 1400)
		elif self._state.blue_on_when_idle:
			self._set_channel("blue", "on")
		else:
			self._set_channel("blue", "off")

	def _flash_white(self, flashes: int = 1, on_time: float = 0.12, off_time: float = 0.08) -> None:
		if not self._ensure_connection() or self._leds is None:
			return
		if flashes <= 0:
			return
		with self._flash_lock:
			for index in range(flashes):
				self._set_channel("white", "on")
				time.sleep(on_time)
				self._set_channel("white", "off")
				if index < flashes - 1:
					time.sleep(off_time)
			with self._lock:
				self._apply_locked()

	def apply(self) -> None:
		with self._lock:
			self._apply_locked()

	def set_error(self, active: bool, critical: bool = False) -> None:
		with self._lock:
			self._state.error_active = bool(active)
			self._state.error_critical = bool(critical)
			if active:
				self._state.movement_mode = None
				self._state.tracking_active = False
				self._state.command_busy = False
				self._state.blue_on_when_idle = False
			else:
				self._state.blue_on_when_idle = True
			self._apply_locked()

	def clear_error(self) -> None:
		self.set_error(False)

	def set_ui_connected(self, connected: bool) -> None:
		with self._lock:
			self._state.blue_on_when_idle = bool(connected)
			# Only touch the blue indicator here; the rest of the state is driven
			# by the normal refresh path.
			self._set_channel("blue", "on" if connected else "off")

	def shutdown(self) -> None:
		with self._lock:
			self._state.blue_on_when_idle = False
			channel = getattr(self._leds, "blue", None) if self._leds is not None else None
			if channel is None:
				return
			try:
				channel.off()
			except Exception:
				pass

	def set_movement(self, mode: Optional[str]) -> None:
		mode = mode.lower() if isinstance(mode, str) else None
		if mode not in {None, "slewing", "homing"}:
			raise ValueError("movement mode must be 'slewing', 'homing', or None")
		with self._lock:
			self._state.movement_mode = mode
			if mode is not None:
				self._state.tracking_active = False
			self._apply_locked()

	def set_tracking(self, active: bool, pulse: bool = False) -> None:
		with self._lock:
			self._state.tracking_active = bool(active)
			self._state.tracking_pulse = bool(pulse)
			if active:
				self._state.movement_mode = None
				self._state.blue_on_when_idle = True
			self._apply_locked()

	def set_idle(self) -> None:
		with self._lock:
			self._state.error_active = False
			self._state.error_critical = False
			self._state.movement_mode = None
			self._state.tracking_active = False
			self._state.tracking_pulse = False
			self._state.command_busy = False
			self._state.blue_on_when_idle = True
			self._apply_locked()

	def set_command_busy(self, active: bool) -> None:
		with self._lock:
			self._state.command_busy = bool(active)
			self._apply_locked()

	def flash_target_acquired(self, major: bool = True) -> None:
		threading.Thread(
			target=self._flash_white,
			kwargs={"flashes": 2 if major else 1, "on_time": 0.14 if major else 0.1},
			daemon=True,
		).start()

	def flash_capture_started(self) -> None:
		threading.Thread(
			target=self._flash_white,
			kwargs={"flashes": 2, "on_time": 0.16, "off_time": 0.08},
			daemon=True,
		).start()

	def flash_parking_complete(self) -> None:
		threading.Thread(
			target=self._flash_white,
			kwargs={"flashes": 1, "on_time": 0.18, "off_time": 0.05},
			daemon=True,
		).start()

	def flash_homing_complete(self) -> None:
		threading.Thread(
			target=self._flash_white,
			kwargs={"flashes": 1, "on_time": 0.16, "off_time": 0.05},
			daemon=True,
		).start()

	def flash_tracking_locked(self) -> None:
		threading.Thread(
			target=self._flash_white,
			kwargs={"flashes": 1, "on_time": 0.12, "off_time": 0.05},
			daemon=True,
		).start()

	def flash_command_complete(self, success: bool = True) -> None:
		if success:
			self.flash_tracking_locked()
		else:
			threading.Thread(
				target=self._flash_white,
				kwargs={"flashes": 2, "on_time": 0.08, "off_time": 0.05},
				daemon=True,
			).start()

	@contextmanager
	def command_scope(self):
		self.set_command_busy(True)
		try:
			yield
		finally:
			self.set_command_busy(False)


_LED_MANAGER: Optional[LEDManager] = None


def get_led_manager() -> LEDManager:
	global _LED_MANAGER
	if _LED_MANAGER is None:
		_LED_MANAGER = LEDManager()
	return _LED_MANAGER
