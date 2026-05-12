from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Iterable, Optional

try:
	from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageSequence  # type: ignore[reportMissingImports]
except ImportError as exc:  # pragma: no cover - dependency check
	raise ImportError(
		"graphics.engine requires Pillow. Install it with: pip install Pillow"
	) from exc

from esp32.interfaceESP32 import ESP32Display


def _normalize_hex_color(color: str) -> str:
	return ESP32Display._normalize_color(color)


def _tuple_to_hex(rgb: tuple[int, int, int]) -> str:
	return f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _clamp(value: float, minimum: float, maximum: float) -> float:
	return max(minimum, min(maximum, value))


def _rgb_to_rgb565_bytes(image: Image.Image) -> bytes:
	rgba = image.convert("RGBA")
	out = bytearray(rgba.width * rgba.height * 2)
	idx = 0
	for r, g, b, a in rgba.getdata():
		if a < 8:
			r = g = b = 0
		value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
		out[idx] = (value >> 8) & 0xFF
		out[idx + 1] = value & 0xFF
		idx += 2
	return bytes(out)


@dataclass
class TextStyle:
	color: str = "FFFFFF"
	font_size: int = 14
	font_path: Optional[str] = None
	anchor: str = "lt"


class DisplayCanvas:
	"""In-memory RGBA canvas for composing complex scenes before rendering."""

	def __init__(self, width: int, height: int, background: str = "#000000") -> None:
		self.width = int(width)
		self.height = int(height)
		bg = _normalize_hex_color(background)
		self.image = Image.new("RGBA", (self.width, self.height), f"#{bg}FF")
		self.draw = ImageDraw.Draw(self.image)

	def clear(self, color: str = "#000000") -> "DisplayCanvas":
		hex_color = _normalize_hex_color(color)
		self.draw.rectangle((0, 0, self.width, self.height), fill=f"#{hex_color}FF")
		return self

	def rectangle(
		self,
		x: int,
		y: int,
		width: int,
		height: int,
		fill: Optional[str] = None,
		outline: Optional[str] = None,
		outline_width: int = 1,
	) -> "DisplayCanvas":
		fill_color = f"#{_normalize_hex_color(fill)}FF" if fill else None
		outline_color = f"#{_normalize_hex_color(outline)}FF" if outline else None
		self.draw.rectangle(
			(x, y, x + width - 1, y + height - 1),
			fill=fill_color,
			outline=outline_color,
			width=max(1, int(outline_width)),
		)
		return self

	def circle(
		self,
		x: int,
		y: int,
		radius: int,
		fill: Optional[str] = None,
		outline: Optional[str] = None,
		outline_width: int = 1,
	) -> "DisplayCanvas":
		fill_color = f"#{_normalize_hex_color(fill)}FF" if fill else None
		outline_color = f"#{_normalize_hex_color(outline)}FF" if outline else None
		self.draw.ellipse(
			(x - radius, y - radius, x + radius, y + radius),
			fill=fill_color,
			outline=outline_color,
			width=max(1, int(outline_width)),
		)
		return self

	def line(
		self,
		x0: int,
		y0: int,
		x1: int,
		y1: int,
		color: str = "#FFFFFF",
		width: int = 1,
	) -> "DisplayCanvas":
		hex_color = _normalize_hex_color(color)
		self.draw.line((x0, y0, x1, y1), fill=f"#{hex_color}FF", width=max(1, int(width)))
		return self

	def text(
		self,
		text: str,
		x: int,
		y: int,
		style: Optional[TextStyle] = None,
	) -> "DisplayCanvas":
		style = style or TextStyle()
		font = GraphicsEngine.load_font(style.font_size, style.font_path)
		hex_color = _normalize_hex_color(style.color)
		self.draw.text((x, y), text, fill=f"#{hex_color}FF", font=font, anchor=style.anchor)
		return self

	def paste(self, image: Image.Image, x: int, y: int) -> "DisplayCanvas":
		src = image.convert("RGBA")
		self.image.alpha_composite(src, (int(x), int(y)))
		return self


class GraphicsEngine:
	"""
	High-level graphics engine for ESP32Display.

	This engine composes scenes with Pillow, then pushes them to the ESP32 TFT
	using the display primitive commands already available in the firmware.
	"""

	def __init__(
		self,
		display: ESP32Display,
		assets_dir: Optional[str | Path] = None,
		*,
		auto_initialize: bool = False,
		default_background: str = "000000",
		default_foreground: str = "FFFFFF",
		default_pixel_size: int = 1,
	) -> None:
		self.display = display
		self.width = ESP32Display.WIDTH
		self.height = ESP32Display.HEIGHT
		self.assets_dir = Path(assets_dir) if assets_dir else Path(__file__).parent / "assets"
		self.default_background = _normalize_hex_color(default_background)
		self.default_foreground = _normalize_hex_color(default_foreground)
		self.default_pixel_size = max(1, int(default_pixel_size))

		if auto_initialize:
			self.initialize()

	def initialize(self, backlight: int = 220) -> None:
		self.display.initialize()
		self.display.set_backlight(backlight)
		self.display.set_text_color(self.default_foreground)
		self.display.set_background_color(self.default_background)
		self.display.clear(self.default_background)

	def set_theme(self, foreground: str = "FFFFFF", background: str = "000000") -> None:
		self.default_foreground = _normalize_hex_color(foreground)
		self.default_background = _normalize_hex_color(background)
		self.display.set_text_color(self.default_foreground)
		self.display.set_background_color(self.default_background)

	def clear(self, color: Optional[str] = None) -> None:
		self.display.clear(_normalize_hex_color(color or self.default_background))

	def set_backlight(self, value: int) -> None:
		self.display.set_backlight(max(0, min(255, int(value))))

	@staticmethod
	def load_font(size: int, font_path: Optional[str] = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
		size = max(8, int(size))
		if font_path:
			return ImageFont.truetype(font_path, size=size)
		for candidate in ("DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
			try:
				return ImageFont.truetype(candidate, size=size)
			except OSError:
				continue
		return ImageFont.load_default()

	def new_canvas(self, width: Optional[int] = None, height: Optional[int] = None, background: str = "000000") -> DisplayCanvas:
		return DisplayCanvas(width or self.width, height or self.height, background)

	def resolve_asset(self, asset_name_or_path: str | Path) -> Path:
		path = Path(asset_name_or_path)
		if path.is_absolute() and path.exists():
			return path

		local_candidate = self.assets_dir / path
		if local_candidate.exists():
			return local_candidate

		if path.exists():
			return path

		raise FileNotFoundError(
			f"Asset not found: {asset_name_or_path}. Checked {local_candidate} and current working path."
		)

	def draw_text(
		self,
		text: str,
		x: int,
		y: int,
		*,
		color: str = "FFFFFF",
		font_size: int = 14,
		font_path: Optional[str] = None,
		anchor: str = "lt",
		antialias: bool = True,
		pixel_size: Optional[int] = None,
	) -> None:
		font = self.load_font(font_size, font_path)
		mask = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
		draw = ImageDraw.Draw(mask)
		hex_color = _normalize_hex_color(color)
		if antialias:
			draw.text((x, y), text, font=font, fill=f"#{hex_color}FF", anchor=anchor)
		else:
			draw.fontmode = "1"
			draw.text((x, y), text, font=font, fill=f"#{hex_color}FF", anchor=anchor)
		self.render_image(mask, pixel_size=pixel_size)

	def draw_text_box(
		self,
		text: str,
		x: int,
		y: int,
		width: int,
		height: int,
		*,
		text_color: str = "FFFFFF",
		background: Optional[str] = None,
		border_color: Optional[str] = None,
		padding: int = 4,
		font_size: int = 14,
		font_path: Optional[str] = None,
	) -> None:
		canvas = self.new_canvas(background="000000")
		if background is not None:
			canvas.rectangle(x, y, width, height, fill=background)
		if border_color is not None:
			canvas.rectangle(x, y, width, height, outline=border_color)

		font = self.load_font(font_size, font_path)
		draw = canvas.draw
		color = f"#{_normalize_hex_color(text_color)}FF"
		max_x = x + width - padding
		cursor_x = x + padding
		cursor_y = y + padding
		line_height = max(10, font_size + 2)

		for word in text.split():
			word_bbox = draw.textbbox((0, 0), word, font=font)
			word_w = word_bbox[2] - word_bbox[0]
			space_bbox = draw.textbbox((0, 0), " ", font=font)
			space_w = space_bbox[2] - space_bbox[0]
			if cursor_x + word_w > max_x:
				cursor_x = x + padding
				cursor_y += line_height
			if cursor_y + line_height > y + height - padding:
				break
			draw.text((cursor_x, cursor_y), word, fill=color, font=font)
			cursor_x += word_w + space_w

		self.render_image(canvas.image)

	def draw_image(
		self,
		asset_name_or_path: str | Path,
		x: int = 0,
		y: int = 0,
		*,
		width: Optional[int] = None,
		height: Optional[int] = None,
		scale: float = 1.0,
		keep_aspect: bool = True,
		rotation: float = 0.0,
		flip_horizontal: bool = False,
		flip_vertical: bool = False,
		color_tint: Optional[str] = None,
		brightness: float = 1.0,
		pixel_size: Optional[int] = None,
	) -> None:
		img_path = self.resolve_asset(asset_name_or_path)
		with Image.open(img_path) as image:
			prepared = self._prepare_image(
				image=image,
				width=width,
				height=height,
				scale=scale,
				keep_aspect=keep_aspect,
				rotation=rotation,
				flip_horizontal=flip_horizontal,
				flip_vertical=flip_vertical,
				color_tint=color_tint,
				brightness=brightness,
			)
			self.render_image(prepared, x=x, y=y, pixel_size=pixel_size)

	def play_gif(
		self,
		asset_name_or_path: str | Path,
		*,
		x: int = 0,
		y: int = 0,
		width: Optional[int] = None,
		height: Optional[int] = None,
		scale: float = 1.0,
		loops: int = 0,
		override_frame_delay_ms: Optional[int] = None,
		clear_between_frames: bool = False,
		pixel_size: Optional[int] = None,
	) -> None:
		img_path = self.resolve_asset(asset_name_or_path)
		with Image.open(img_path) as gif:
			if not getattr(gif, "is_animated", False):
				raise ValueError(f"Asset is not an animated GIF: {img_path}")

			loop_target = loops if loops > 0 else 1
			for _ in range(loop_target):
				for frame in ImageSequence.Iterator(gif):
					frame_rgba = frame.copy().convert("RGBA")
					prepared = self._prepare_image(
						image=frame_rgba,
						width=width,
						height=height,
						scale=scale,
						keep_aspect=True,
					)
					if clear_between_frames:
						# Compose full-screen frame in-memory to avoid sending a separate clear command
						full = Image.new("RGBA", (self.width, self.height), f"#{self.default_background}FF")
						full.alpha_composite(prepared, (int(x), int(y)))
						self.render_image(full, x=0, y=0, pixel_size=pixel_size)
					else:
						self.render_image(prepared, x=x, y=y, pixel_size=pixel_size)

					delay_ms = override_frame_delay_ms
					if delay_ms is None:
						delay_ms = int(frame.info.get("duration", gif.info.get("duration", 100)))
					sleep(max(0.01, delay_ms / 1000.0))

	def render_canvas(self, canvas: DisplayCanvas, x: int = 0, y: int = 0, pixel_size: Optional[int] = None) -> None:
		self.render_image(canvas.image, x=x, y=y, pixel_size=pixel_size)

	def render_image(self, image: Image.Image, x: int = 0, y: int = 0, pixel_size: Optional[int] = None) -> None:
		pixel_size = max(1, int(pixel_size or self.default_pixel_size))
		prepared = self._prepare_image(
			image=image,
			width=min(self.width, image.width * pixel_size),
			height=min(self.height, image.height * pixel_size),
			scale=float(pixel_size),
			keep_aspect=False,
		)

		# If the display supports bulk blit, send the smallest rectangle that fully
		# represents the composed result to reduce transfer size and avoid extra
		# separate clear commands which cause visible sweeping effects on the TFT.
		if hasattr(self.display, "blit_rgb565"):
			# If the prepared image already covers the full display and is positioned
			# at 0,0, compose it onto a background and send the full frame.
			if prepared.width == self.width and prepared.height == self.height and int(x) == 0 and int(y) == 0:
				frame = Image.new("RGBA", (self.width, self.height), f"#{self.default_background}FF")
				frame.alpha_composite(prepared, (0, 0))
				self.display.blit_rgb565(0, 0, self.width, self.height, _rgb_to_rgb565_bytes(frame))
				return

			# Otherwise send only the prepared region; composite it onto the
			# background so transparent pixels overwrite correctly without a
			# separate clear command on the device.
			bg = Image.new("RGBA", (prepared.width, prepared.height), f"#{self.default_background}FF")
			bg.alpha_composite(prepared, (0, 0))
			self.display.blit_rgb565(int(x), int(y), bg.width, bg.height, _rgb_to_rgb565_bytes(bg))
			return

		# Fallback path if the connected display object does not support bulk blitting.
		rgba = frame.convert("RGBA")
		for row in range(rgba.height):
			row_y = row
			pixels = [rgba.getpixel((col, row)) for col in range(rgba.width)]
			for start, end, rgb in self._row_spans(pixels):
				span_w = end - start
				if span_w <= 0:
					continue
				self.display.fill_rectangle(start, row_y, span_w, 1, _tuple_to_hex(rgb))

	def _prepare_image(
		self,
		image: Image.Image,
		*,
		width: Optional[int] = None,
		height: Optional[int] = None,
		scale: float = 1.0,
		keep_aspect: bool = True,
		rotation: float = 0.0,
		flip_horizontal: bool = False,
		flip_vertical: bool = False,
		color_tint: Optional[str] = None,
		brightness: float = 1.0,
	) -> Image.Image:
		img = image.convert("RGBA")

		if flip_horizontal:
			img = ImageOps.mirror(img)
		if flip_vertical:
			img = ImageOps.flip(img)

		target_w = int(width) if width is not None else max(1, int(img.width * scale))
		# If neither width nor height is specified, default to fitting the
		# display area so images/gifs are auto-scaled to the screen.
		if width is None and height is None:
			# Fit to engine display size while preserving aspect when requested
			target_w = self.width
			target_h = self.height
		else:
			target_h = int(height) if height is not None else max(1, int(img.height * scale))

		target_w = max(1, target_w)
		target_h = max(1, target_h)

		if keep_aspect:
			img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
		else:
			img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

		if rotation:
			img = img.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)

		if color_tint:
			tint_rgb = tuple(int(_normalize_hex_color(color_tint)[i : i + 2], 16) for i in (0, 2, 4))
			tint_layer = Image.new("RGBA", img.size, (*tint_rgb, 255))
			img = Image.blend(img, tint_layer, alpha=0.35)

		if abs(brightness - 1.0) > 0.001:
			enhancer = ImageEnhance.Brightness(img)
			img = enhancer.enhance(_clamp(brightness, 0.05, 4.0))

		return img

	@staticmethod
	def _row_spans(
		pixels: Iterable[tuple[int, int, int, int]],
	) -> Iterable[tuple[int, int, tuple[int, int, int]]]:
		start = None
		current_color: Optional[tuple[int, int, int]] = None
		idx = 0
		for idx, rgba in enumerate(pixels):
			r, g, b, a = rgba
			if a < 8:
				if start is not None and current_color is not None:
					yield (start, idx, current_color)
					start = None
					current_color = None
				continue

			rgb = (r, g, b)
			if start is None:
				start = idx
				current_color = rgb
				continue

			if rgb != current_color:
				yield (start, idx, current_color)
				start = idx
				current_color = rgb

		if start is not None and current_color is not None:
			yield (start, idx + 1, current_color)

	def banner(
		self,
		text: str,
		*,
		background: str = "0000AA",
		foreground: str = "FFFFFF",
		height: int = 26,
		font_size: int = 16,
	) -> None:
		canvas = self.new_canvas(background=self.default_background)
		canvas.rectangle(0, 0, self.width, height, fill=background)
		canvas.text(
			text,
			self.width // 2,
			height // 2,
			TextStyle(color=foreground, font_size=font_size, anchor="mm"),
		)
		self.render_canvas(canvas)

	def progress_bar(
		self,
		progress: float,
		*,
		x: int = 8,
		y: int = 70,
		width: int = 112,
		height: int = 14,
		border: str = "FFFFFF",
		fill: str = "00AAFF",
		background: str = "111111",
	) -> None:
		canvas = self.new_canvas(background=self.default_background)
		canvas.rectangle(x, y, width, height, fill=background, outline=border)
		inner_padding = 2
		inner_w = width - inner_padding * 2
		filled = int(inner_w * _clamp(progress, 0.0, 1.0))
		if filled > 0:
			canvas.rectangle(
				x + inner_padding,
				y + inner_padding,
				filled,
				height - inner_padding * 2,
				fill=fill,
			)
		self.render_canvas(canvas)

