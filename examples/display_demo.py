#!/usr/bin/env python3
"""
Example usage of the ST7735S TFT display control from Raspberry Pi.
This demonstrates the ESP32Display class capabilities.
"""

import sys
import os
import time

# Add parent directory to path so we can import esp32 module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from esp32.interfaceESP32 import ESP32Connection, ESP32Display


def main():
	"""Run display examples."""
	
	print("Connecting to ESP32...")
	try:
		conn = ESP32Connection()
	except RuntimeError as e:
		print(f"Failed to connect: {e}")
		return
	
	print("Creating display interface...")
	display = ESP32Display(conn)
	
	try:
		# Initialize display
		print("Initializing display...")
		display.initialize()
		display.set_backlight(200)
		
		# Example 1: Color fill
		print("\nExample 1: Color fills")
		colors_to_test = ["red", "green", "blue", "yellow", "cyan", "magenta"]
		for color in colors_to_test:
			print(f"  Filling screen with {color}...")
			display.clear(color)
			time.sleep(1)
		
		# Example 2: Geometric shapes
		print("\nExample 2: Geometric shapes")
		display.clear("black")
		
		# Draw rectangles
		display.fill_rectangle(5, 5, 30, 30, "red")
		display.fill_rectangle(40, 5, 30, 30, "green")
		display.fill_rectangle(75, 5, 30, 30, "blue")
		
		# Draw circles
		display.fill_circle(20, 70, 15, "yellow")
		display.fill_circle(65, 70, 15, "cyan")
		display.fill_circle(110, 70, 15, "magenta")
		
		# Draw lines
		display.draw_line(0, 100, 128, 100, "white")
		display.draw_line(64, 50, 64, 150, "white")
		
		time.sleep(3)
		
		# Example 3: Test pattern
		print("\nExample 3: Test pattern")
		display.draw_test_pattern()
		time.sleep(3)
		
		# Example 4: Gradient effect (simulated)
		print("\nExample 4: Brightness control")
		for brightness in range(0, 256, 15):
			display.set_backlight(brightness)
			time.sleep(0.2)
		
		for brightness in range(255, -1, -15):
			display.set_backlight(brightness)
			time.sleep(0.2)
		
		display.set_backlight(200)
		
		# Example 5: Drawing grid
		print("\nExample 5: Grid pattern")
		display.clear("black")
		
		# Draw grid
		for x in range(0, 128, 16):
			display.draw_line(x, 0, x, 160, "blue")
		
		for y in range(0, 160, 16):
			display.draw_line(0, y, 128, y, "blue")
		
		# Add some markers
		for i in range(0, 128, 32):
			display.fill_circle(i, 0, 2, "red")
		
		time.sleep(2)
		
		# Example 6: Animation
		print("\nExample 6: Animation - expanding circles")
		display.clear("black")
		
		for radius in range(1, 40, 2):
			display.draw_circle(64, 80, radius, "green")
			time.sleep(0.1)
		
		time.sleep(1)
		
		# Example 7: Get display status
		print("\nExample 7: Display status")
		status = display.get_status()
		print(f"  Initialized: {status['initialized']}")
		print(f"  Powered: {status['powered']}")
		print(f"  Brightness: {status['brightness']}")
		print(f"  Resolution: {status['width']}×{status['height']}")
		print(f"  Text color: {status['text_color']}")
		print(f"  Background: {status['background_color']}")
		
		# Final screen
		print("\nDemo complete!")
		display.clear("black")
		display.set_text_color("white")
		display.set_background_color("black")
		
		# Draw final message area
		display.fill_rectangle(10, 60, 108, 40, "blue")
		display.draw_rectangle(10, 60, 108, 40, "white")
		
		print("Display controller working correctly!")
		
	except Exception as e:
		print(f"Error: {e}")
		import traceback
		traceback.print_exc()
	
	finally:
		# Clean up
		print("\nCleaning up...")
		display.set_backlight(0)
		display.clear("black")


if __name__ == "__main__":
	main()
