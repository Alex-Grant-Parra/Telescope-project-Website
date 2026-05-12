from __future__ import annotations

import glob
import json
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import serial  # pyserial


@dataclass
class ESP32SerialConfig:
	port: str = "/dev/ttyUSB0"
	baudrate: int = 2000000
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

	@staticmethod
	def _repair_json_response(resp: str) -> str:
		# Recover from a small set of known serial glitches so the display can still initialize.
		resp = resp.strip()
		resp = resp.replace('"bright255', '"brightness":255')
		resp = re.sub(r'"bright(?:ness)?(\d+)', r'"brightness":\1', resp)
		resp = re.sub(r'("brightness")([0-9]+)', r'\1:\2', resp)
		return resp

	def _parse_response(self, resp: str) -> Dict[str, Any]:
		try:
			data = json.loads(resp)
		except json.JSONDecodeError:
			repaired = self._repair_json_response(resp)
			if repaired != resp:
				data = json.loads(repaired)
			else:
				raise
		if data.get("status") != "ok":
			error_msg = data.get("message", "ESP32 error")
			raise RuntimeError(f"ESP32 error: {error_msg} | Full response: {data}")
		return data.get("data", {})

	def send(self, payload: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
		line = json.dumps(payload, separators=(",", ":")) + "\n"
		last_resp = ""
		with self._lock:
			for attempt in range(2):
				if timeout is not None:
					prev_timeout = self.ser.timeout
					self.ser.timeout = timeout
				try:
					self.ser.write(line.encode("utf-8"))
					self.ser.flush()
					last_resp = self.ser.readline().decode("utf-8", errors="ignore").strip()
				finally:
					if timeout is not None:
						self.ser.timeout = prev_timeout
				if last_resp:
					try:
						return self._parse_response(last_resp)
					except (json.JSONDecodeError, RuntimeError):
						if attempt == 0:
							self._drain()
							continue
						raise
			self._drain()
		raise TimeoutError(f"No valid response from ESP32: {last_resp!r}")

	def send_binary(
		self,
		payload: Dict[str, Any],
		binary_data: bytes | bytearray | memoryview,
		timeout: Optional[float] = None,
	) -> Dict[str, Any]:
		data_bytes = memoryview(binary_data).tobytes()
		line = json.dumps(payload, separators=(",", ":")) + "\n"
		baudrate = max(1, int(self.ser.baudrate))
		estimated_transfer_s = (len(data_bytes) * 10.0 / baudrate) + 5.0
		transfer_timeout = max(self.ser.timeout, estimated_transfer_s)
		if timeout is not None:
			transfer_timeout = max(float(timeout), transfer_timeout)

		with self._lock:
			resp = ""
			prev_timeout = self.ser.timeout
			try:
				for attempt in range(2):
					self.ser.timeout = transfer_timeout * (1.0 + 0.25 * attempt)
					self.ser.write(line.encode("utf-8"))
					self.ser.flush()
					self.ser.write(data_bytes)
					self.ser.flush()
					resp = self.ser.readline().decode("utf-8", errors="ignore").strip()
					if resp:
						break
					self._drain()
			finally:
				self.ser.timeout = prev_timeout
		if not resp:
			raise TimeoutError("No response from ESP32")
		return self._parse_response(resp)

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
		# Create a new motor instance on the ESP32.
		# 
		# Args:
		#	replace: If True, delete existing motor with same ID before creating
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
		# Get the current position of the motor in steps (signed integer).
		result = self.conn.send({"cmd": "get_position", "motor": self.motor_id})
		return result.get("position", 0)

	def get_position_degrees(self, gear_ratio: float = 360.0) -> float:
		# Get the current position in degrees (polar alignment deviation).
		# 
		# Args:
		#	gear_ratio: Sky degrees per motor revolution (default: 360 for RA, 144 for DEC)
		# 
		# Returns:
		#	Angular deviation in degrees
		steps = self.get_position()
		return (steps * gear_ratio) / self._steps_per_rev

	def get_position_arcmin(self, gear_ratio: float = 360.0) -> float:
		# Get the current position in arcminutes (fine alignment precision).
		degrees = self.get_position_degrees(gear_ratio)
		return degrees * 60

	def get_position_arcsec(self, gear_ratio: float = 360.0) -> float:
		# Get the current position in arcseconds (highest precision).
		arcmin = self.get_position_arcmin(gear_ratio)
		return arcmin * 60

	def reset_position(self) -> Dict[str, Any]:
		# Reset the motor position counter to zero.
		return self.conn.send({"cmd": "reset_position", "motor": self.motor_id})


class ESP32Display:
	# Control the ST7735S TFT LCD display connected to ESP32.

	# Display constants
	WIDTH = 128
	HEIGHT = 160

	# Standard colors (RGB565)
	COLORS = {
		"black": "000000",
		"red": "FF0000",
		"green": "00FF00",
		"blue": "0000FF",
		"white": "FFFFFF",
		"yellow": "FFFF00",
		"cyan": "00FFFF",
		"magenta": "FF00FF",
	}

	def __init__(self, conn: ESP32Connection) -> None:
		self.conn = conn
		self._initialized = False
		self._brightness = 255
		self._text_color = "FFFFFF"
		self._bg_color = "000000"
		self._cursor_x = 0
		self._cursor_y = 0

	def initialize(self) -> Dict[str, Any]:
		# Initialize the display hardware.
		result = self.conn.send({"cmd": "display", "action": "init"}, timeout=5.0)
		self._initialized = True
		return result

	def cleanup(self) -> None:
		# Clean up display resources.
		if self._initialized:
			self.power(False)
			self._initialized = False

	def power(self, on: bool) -> Dict[str, Any]:
		# Turn display power on/off.
		return self.conn.send({"cmd": "display", "action": "power", "on": bool(on)})

	def set_backlight(self, brightness: int) -> Dict[str, Any]:
		# Set backlight brightness (0-255).
		# 
		# Args:
		#	brightness: PWM value 0-255 where 0 is off and 255 is full brightness
		brightness = max(0, min(255, int(brightness)))
		self._brightness = brightness
		return self.conn.send({"cmd": "display", "action": "backlight", "brightness": brightness})

	def get_status(self) -> Dict[str, Any]:
		# Get current display status.
		return self.conn.send({"cmd": "display", "action": "status"})

	def blit_rgb565(self, x: int, y: int, width: int, height: int, data: bytes | bytearray | memoryview) -> Dict[str, Any]:
		# Upload a full RGB565 frame or sub-frame in one binary transfer.
		payload = {
			"cmd": "display",
			"action": "blit",
			"x": int(x),
			"y": int(y),
			"w": int(width),
			"h": int(height),
			"format": "RGB565",
			"length": int(len(memoryview(data))),
		}
		return self.conn.send_binary(payload, data)

	def clear(self, color: Optional[str] = None) -> Dict[str, Any]:
		# Clear the display with a background color.
		# 
		# Args:
		#	color: Hex color string (e.g., "000000" for black) or color name
		if color is None:
			color = self._bg_color
		else:
			color = self._normalize_color(color)
			self._bg_color = color

		return self.conn.send({"cmd": "display", "action": "clear", "color": color}, timeout=3.0)

	def fill_screen(self, color: Optional[str] = None) -> Dict[str, Any]:
		# Fill entire screen with color (alias for clear).
		return self.clear(color)

	# Drawing functions
	def draw_pixel(self, x: int, y: int, color: Optional[str] = None) -> Dict[str, Any]:
		# Draw a single pixel.
		if color is None:
			color = self._text_color
		else:
			color = self._normalize_color(color)

		if not self._validate_coords(x, y):
			raise ValueError(f"Coordinates ({x}, {y}) out of display bounds")

		return self.conn.send(
			{"cmd": "display", "action": "draw_pixel", "x": x, "y": y, "color": color}
		)

	def draw_rectangle(
		self,
		x: int,
		y: int,
		width: int,
		height: int,
		color: Optional[str] = None,
		fill: bool = False,
	) -> Dict[str, Any]:
		# Draw a rectangle.
		# 
		# Args:
		#	x, y: Top-left corner coordinates
		#	width, height: Rectangle dimensions
		#	color: Border/fill color
		#	fill: If True, fill the rectangle; if False, draw outline only
		if color is None:
			color = self._text_color
		else:
			color = self._normalize_color(color)

		action = "fill_rect" if fill else "draw_rect"
		# Use longer timeout for filled rectangles (more SPI data)
		timeout = 3.0 if fill else 1.0
		return self.conn.send(
			{
				"cmd": "display",
				"action": action,
				"x": int(x),
				"y": int(y),
				"w": int(width),
				"h": int(height),
				"color": color,
			},
			timeout=timeout,
		)

	def fill_rectangle(
		self, x: int, y: int, width: int, height: int, color: Optional[str] = None
	) -> Dict[str, Any]:
		# Fill a rectangle with color.
		return self.draw_rectangle(x, y, width, height, color, fill=True)

	def draw_line(
		self, x0: int, y0: int, x1: int, y1: int, color: Optional[str] = None
	) -> Dict[str, Any]:
		# Draw a line from (x0, y0) to (x1, y1).
		if color is None:
			color = self._text_color
		else:
			color = self._normalize_color(color)

		return self.conn.send(
			{
				"cmd": "display",
				"action": "draw_line",
				"x0": int(x0),
				"y0": int(y0),
				"x1": int(x1),
				"y1": int(y1),
				"color": color,
			}
		)

	def draw_circle(
		self,
		x: int,
		y: int,
		radius: int,
		color: Optional[str] = None,
		fill: bool = False,
	) -> Dict[str, Any]:
		# Draw a circle.
		# 
		# Args:
		#	x, y: Center coordinates
		#	radius: Circle radius in pixels
		#	color: Circle color
		#	fill: If True, fill the circle; if False, draw outline only
		if color is None:
			color = self._text_color
		else:
			color = self._normalize_color(color)

		action = "fill_circle" if fill else "draw_circle"
		# Use longer timeout for filled circles (more SPI data)
		timeout = 3.0 if fill else 1.0
		return self.conn.send(
			{
				"cmd": "display",
				"action": action,
				"x": int(x),
				"y": int(y),
				"r": int(radius),
				"color": color,
			},
			timeout=timeout,
		)

	def fill_circle(
		self, x: int, y: int, radius: int, color: Optional[str] = None
	) -> Dict[str, Any]:
		# Fill a circle with color.
		return self.draw_circle(x, y, radius, color, fill=True)

	# Text functions
	def set_cursor(self, x: int, y: int) -> Dict[str, Any]:
		# Set cursor position for text rendering.
		self._cursor_x = int(x)
		self._cursor_y = int(y)
		return self.conn.send(
			{"cmd": "display", "action": "set_cursor", "x": self._cursor_x, "y": self._cursor_y}
		)

	def set_text_color(self, color: str) -> Dict[str, Any]:
		# Set text color.
		color = self._normalize_color(color)
		self._text_color = color
		return self.conn.send({"cmd": "display", "action": "set_text_color", "color": color})

	def set_background_color(self, color: str) -> Dict[str, Any]:
		# Set background color.
		color = self._normalize_color(color)
		self._bg_color = color
		return self.conn.send({"cmd": "display", "action": "set_bg_color", "color": color})

	# Utility methods
	@staticmethod
	def _normalize_color(color: str) -> str:
		# Normalize color to hex format.
		# 
		# Args:
		#	color: Can be a color name from COLORS dict or hex string
		# 
		# Returns:
		#	Hex color string (6 characters)
		if color.lower() in ESP32Display.COLORS:
			return ESP32Display.COLORS[color.lower()]
		
		# Clean up hex format
		color = color.lstrip("#").upper()
		if len(color) == 6 and all(c in "0123456789ABCDEF" for c in color):
			return color
		
		raise ValueError(f"Invalid color format: {color}")

	@staticmethod
	def _validate_coords(x: int, y: int) -> bool:
		# Check if coordinates are within display bounds.
		return 0 <= x < ESP32Display.WIDTH and 0 <= y < ESP32Display.HEIGHT

	def draw_test_pattern(self) -> Dict[str, Any]:
		# Draw a test pattern (colors, rectangles, text areas) for debugging.
		# Clear with black
		self.clear("black")
		
		# Draw colored rectangles
		self.fill_rectangle(0, 0, 32, 40, "red")
		self.fill_rectangle(32, 0, 32, 40, "green")
		self.fill_rectangle(64, 0, 32, 40, "blue")
		self.fill_rectangle(96, 0, 32, 40, "yellow")
		
		# Draw circles
		self.fill_circle(32, 80, 15, "cyan")
		self.fill_circle(96, 80, 15, "magenta")
		
		# Draw lines
		self.draw_line(0, 100, 128, 100, "white")
		self.draw_line(64, 60, 64, 160, "white")
		
		return self.get_status()


