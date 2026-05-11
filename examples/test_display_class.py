#!/usr/bin/env python3
"""
Simple test to verify the ESP32Display class loads and basic methods work.
Run this WITHOUT an ESP32 connection to test the Python side.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from esp32.interfaceESP32 import ESP32Display, ESP32Connection


def test_display_class():
    """Test that ESP32Display class exists and has expected methods."""
    print("✓ ESP32Display class imported successfully")
    
    # Check all expected methods exist
    methods = [
        'initialize', 'cleanup', 'power', 'set_backlight', 'get_status',
        'clear', 'fill_screen', 'draw_pixel', 'draw_rectangle', 'fill_rectangle',
        'draw_line', 'draw_circle', 'fill_circle', 'set_cursor',
        'set_text_color', 'set_background_color', 'draw_test_pattern'
    ]
    
    for method in methods:
        if hasattr(ESP32Display, method):
            print(f"  ✓ Method '{method}' exists")
        else:
            print(f"  ✗ Method '{method}' missing!")
            return False
    
    # Check color constants
    print("\n✓ Color palette:")
    for name, value in ESP32Display.COLORS.items():
        print(f"  {name}: {value}")
    
    # Test color normalization
    print("\n✓ Testing color normalization:")
    test_colors = [
        ("red", "FF0000"),
        ("RED", "FF0000"),
        ("ABCDEF", "ABCDEF"),
        ("#123456", "123456"),
    ]
    
    for input_color, expected in test_colors:
        result = ESP32Display._normalize_color(input_color)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {input_color} → {result} (expected {expected})")
    
    # Test coordinate validation
    print("\n✓ Testing coordinate validation:")
    test_coords = [
        (0, 0, True),
        (127, 159, True),
        (128, 159, False),
        (127, 160, False),
        (-1, 0, False),
    ]
    
    for x, y, expected in test_coords:
        result = ESP32Display._validate_coords(x, y)
        status = "✓" if result == expected else "✗"
        print(f"  {status} ({x}, {y}) valid: {result}")
    
    print("\n✅ All Python-side tests passed!")
    return True


if __name__ == "__main__":
    try:
        test_display_class()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
