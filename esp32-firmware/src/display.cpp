#include "display.h"
#include <SPI.h>

// Global display state
DisplayState g_display_state = {
  .initialized = false,
  .powered = true,
  .brightness = 255,
  .background_color = COLOR_BLACK,
  .text_color = COLOR_WHITE,
  .text_size = 1,
  .cursor_x = 0,
  .cursor_y = 0
};

// Forward declarations for low-level SPI operations
static void displayWrite8(uint8_t byte);
static void displayWrite16(uint16_t word);
static void displayWriteBytes(const uint8_t* data, size_t len);
static void displayCommandMode();
static void displayDataMode();
static void displayReset();
static void displaySetWindow(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1);
static void displayFillCircleHelper(uint16_t x, uint16_t y, uint16_t r, uint8_t corners, uint16_t delta, uint16_t color);

// SPI communication helpers
static void displayWrite8(uint8_t byte) {
  SPI.write(byte);
}

static void displayWrite16(uint16_t word) {
  displayWrite8(word >> 8);
  displayWrite8(word & 0xFF);
}

static void displayWriteBytes(const uint8_t* data, size_t len) {
  for (size_t i = 0; i < len; i++) {
    SPI.write(data[i]);
    if ((i & 0x3FF) == 0) {
      yield();
    }
  }
}

static void displayCommandMode() {
  digitalWrite(DISPLAY_DC, LOW);
}

static void displayDataMode() {
  digitalWrite(DISPLAY_DC, HIGH);
}

static void displayReset() {
  digitalWrite(DISPLAY_RES, LOW);
  delay(10);
  digitalWrite(DISPLAY_RES, HIGH);
  delay(10);
}

static void displaySetWindow(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1) {
  // Column address set (CASET)
  displayCommandMode();
  displayWrite8(0x2A);
  displayDataMode();
  displayWrite16(x0);
  displayWrite16(x1);
  
  // Row address set (RASET)
  displayCommandMode();
  displayWrite8(0x2B);
  displayDataMode();
  displayWrite16(y0);
  displayWrite16(y1);
}

// Initialize display
void initializeDisplay() {
  if (g_display_state.initialized) {
    return;
  }

  // Initialize pins
  pinMode(DISPLAY_DC, OUTPUT);
  pinMode(DISPLAY_RES, OUTPUT);
  pinMode(DISPLAY_BL, OUTPUT);

  // Initialize SPI with explicit parameters
  // SPI.begin(SCK, MISO, MOSI, CS)
  // We don't use MISO (read-only) or CS (tied to ground)
  SPI.begin(DISPLAY_SCK, -1, DISPLAY_SDA, -1);
  SPI.setFrequency(40000000);  // 40 MHz for display throughput
  SPI.setDataMode(SPI_MODE0);

  // Reset display
  displayReset();

  // Initialize ST7735S - using smaller delays to avoid blocking serial
  // Sleep out
  displayCommandMode();
  displayWrite8(0x11);  // SLPOUT
  delay(10);
  
  // Yield to allow serial handler to run
  yield();

  // Interface Pixel Format - 16-bit/pixel (RGB565)
  displayCommandMode();
  displayWrite8(0x3A);  // COLMOD
  displayDataMode();
  displayWrite8(0x05);  // 16-bit/pixel
  
  delay(5);
  yield();

  // Memory Data Access Control - BGR mode
  displayCommandMode();
  displayWrite8(0x36);  // MADCTL
  displayDataMode();
  displayWrite8(0x08);  // BGR
  
  delay(5);
  yield();
  // Display on
  displayCommandMode();
  displayWrite8(0x29);  // DISPON
  
  delay(10);
  yield();

  // Set column address range (CASET)
  displayCommandMode();
  displayWrite8(0x2A);
  displayDataMode();
  displayWrite8(0x00);
  displayWrite8(0x00);
  displayWrite8(0x00);
  displayWrite8(0x7F);  // 128-1
  
  delay(2);
  yield();
  
  // Set row address range (RASET)
  displayCommandMode();
  displayWrite8(0x2B);
  displayDataMode();
  displayWrite8(0x00);
  displayWrite8(0x00);
  displayWrite8(0x00);
  displayWrite8(0x9F);  // 160-1
  
  delay(2);
  yield();

  // Set backlight to full brightness initially
  analogWrite(DISPLAY_BL, 255);

  g_display_state.initialized = true;
}

void cleanupDisplay() {
  if (!g_display_state.initialized) {
    return;
  }
  displayPower(false);
  SPI.end();
  g_display_state.initialized = false;
}

void displayPower(bool on) {
  if (!g_display_state.initialized) {
    return;
  }
  
  displayCommandMode();
  if (on) {
    displayWrite8(0x29);  // DISPON
    g_display_state.powered = true;
  } else {
    displayWrite8(0x28);  // DISPOFF
    g_display_state.powered = false;
  }
}

void displayBacklight(uint8_t brightness) {
  if (!g_display_state.initialized) {
    return;
  }
  g_display_state.brightness = brightness;
  analogWrite(DISPLAY_BL, brightness);
}

// Fill screen with color
void displayFillScreen(uint16_t color) {
  if (!g_display_state.initialized) {
    return;
  }
  
  displaySetWindow(0, 0, DISPLAY_WIDTH - 1, DISPLAY_HEIGHT - 1);
  
  displayCommandMode();
  displayWrite8(0x2C);  // RAMWR - Write to RAM
  
  displayDataMode();
  for (uint16_t i = 0; i < DISPLAY_WIDTH * DISPLAY_HEIGHT; i++) {
    displayWrite16(color);
    // Yield every 256 pixels to prevent blocking serial handler
    if ((i & 0xFF) == 0) {
      yield();
    }
  }
  
  g_display_state.background_color = color;
  g_display_state.cursor_x = 0;
  g_display_state.cursor_y = 0;
}

// Draw single pixel
void displayDrawPixel(uint16_t x, uint16_t y, uint16_t color) {
  if (!g_display_state.initialized || x >= DISPLAY_WIDTH || y >= DISPLAY_HEIGHT) {
    return;
  }
  
  displaySetWindow(x, y, x, y);
  
  displayCommandMode();
  displayWrite8(0x2C);  // RAMWR
  
  displayDataMode();
  displayWrite16(color);
}

// Draw rectangle (outline)
void displayDrawRectangle(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color) {
  if (!g_display_state.initialized) {
    return;
  }
  
  // Top
  displayDrawLine(x, y, x + w - 1, y, color);
  // Bottom
  displayDrawLine(x, y + h - 1, x + w - 1, y + h - 1, color);
  // Left
  displayDrawLine(x, y, x, y + h - 1, color);
  // Right
  displayDrawLine(x + w - 1, y, x + w - 1, y + h - 1, color);
}

// Fill rectangle
void displayFillRectangle(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color) {
  if (!g_display_state.initialized) {
    return;
  }
  
  displaySetWindow(x, y, x + w - 1, y + h - 1);
  
  displayCommandMode();
  displayWrite8(0x2C);  // RAMWR
  
  displayDataMode();
  uint32_t pixel_count = (uint32_t)w * h;
  for (uint32_t i = 0; i < pixel_count; i++) {
    displayWrite16(color);
    // Yield every 256 pixels to prevent blocking serial handler
    if ((i & 0xFF) == 0) {
      yield();
    }
  }
}

// Draw circle (outline)
void displayDrawCircle(uint16_t x, uint16_t y, uint16_t r, uint16_t color) {
  if (!g_display_state.initialized) {
    return;
  }
  
  int f = 1 - r;
  int ddF_x = 1;
  int ddF_y = -2 * r;
  int px = 0;
  int py = r;

  displayDrawPixel(x, y + r, color);
  displayDrawPixel(x, y - r, color);
  displayDrawPixel(x + r, y, color);
  displayDrawPixel(x - r, y, color);

  while (px < py) {
    if (f >= 0) {
      py--;
      ddF_y += 2;
      f += ddF_y;
    }
    px++;
    ddF_x += 2;
    f += ddF_x;

    displayDrawPixel(x + px, y + py, color);
    displayDrawPixel(x - px, y + py, color);
    displayDrawPixel(x + px, y - py, color);
    displayDrawPixel(x - px, y - py, color);
    displayDrawPixel(x + py, y + px, color);
    displayDrawPixel(x - py, y + px, color);
    displayDrawPixel(x + py, y - px, color);
    displayDrawPixel(x - py, y - px, color);
  }
}

// Fill circle
void displayFillCircle(uint16_t x, uint16_t y, uint16_t r, uint16_t color) {
  if (!g_display_state.initialized) {
    return;
  }
  
  displayDrawLine(x, y - r, x, y + r, color);
  displayFillCircleHelper(x, y, r, 3, 0, color);
}

// Helper for filled circle
static void displayFillCircleHelper(uint16_t x, uint16_t y, uint16_t r, uint8_t corners, uint16_t delta, uint16_t color) {
  int f = 1 - r;
  int ddF_x = 1;
  int ddF_y = -2 * r;
  int px = 0;
  int py = r;

  while (px < py) {
    if (f >= 0) {
      py--;
      ddF_y += 2;
      f += ddF_y;
    }
    px++;
    ddF_x += 2;
    f += ddF_x;

    if (corners & 1) {
      displayDrawLine(x + px, y - py, x + px, y + py, color);
      displayDrawLine(x + py, y - px, x + py, y + px, color);
    }
    if (corners & 2) {
      displayDrawLine(x - px, y - py, x - px, y + py, color);
      displayDrawLine(x - py, y - px, x - py, y + px, color);
    }
  }
}

// Draw line (Bresenham's algorithm)
void displayDrawLine(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1, uint16_t color) {
  if (!g_display_state.initialized) {
    return;
  }
  
  int dx = (x1 > x0) ? (x1 - x0) : (x0 - x1);
  int dy = (y1 > y0) ? (y1 - y0) : (y0 - y1);
  int sx = (x0 < x1) ? 1 : -1;
  int sy = (y0 < y1) ? 1 : -1;
  int err = dx - dy;

  while (1) {
    displayDrawPixel(x0, y0, color);
    if (x0 == x1 && y0 == y1) break;
    
    int e2 = 2 * err;
    if (e2 > -dy) {
      err -= dy;
      x0 += sx;
    }
    if (e2 < dx) {
      err += dx;
      y0 += sy;
    }
  }
}

void displayBeginBlit(uint16_t x, uint16_t y, uint16_t w, uint16_t h) {
  if (!g_display_state.initialized) {
    return;
  }

  if (w == 0 || h == 0) {
    return;
  }

  displaySetWindow(x, y, x + w - 1, y + h - 1);
  displayCommandMode();
  displayWrite8(0x2C);  // RAMWR
  displayDataMode();
}

void displayWriteBlitData(const uint8_t* data, size_t len) {
  if (!g_display_state.initialized || data == nullptr || len == 0) {
    return;
  }

  displayWriteBytes(data, len);
}

void displayEndBlit() {
  // No-op; kept for symmetry and future hooks.
}

// Text color functions
void displaySetTextColor(uint16_t color) {
  g_display_state.text_color = color;
}

void displaySetBackgroundColor(uint16_t color) {
  g_display_state.background_color = color;
}

void displaySetTextSize(uint8_t size) {
  if (size > 0 && size <= 8) {
    g_display_state.text_size = size;
  }
}

void displaySetCursor(uint16_t x, uint16_t y) {
  if (x < DISPLAY_WIDTH && y < DISPLAY_HEIGHT) {
    g_display_state.cursor_x = x;
    g_display_state.cursor_y = y;
  }
}

// Print text at current cursor position
void displayPrintText(const String& text) {
  if (!g_display_state.initialized) {
    return;
  }
  
  const uint8_t char_width = 6 * g_display_state.text_size;
  const uint8_t char_height = 8 * g_display_state.text_size;
  
  for (size_t i = 0; i < text.length(); i++) {
    uint16_t next_x = g_display_state.cursor_x + char_width;
    if (next_x > DISPLAY_WIDTH) {
      g_display_state.cursor_x = 0;
      g_display_state.cursor_y += char_height;
    }
    if (g_display_state.cursor_y + char_height > DISPLAY_HEIGHT) {
      g_display_state.cursor_y = 0;
    }
    
    // Simple character drawing placeholder
    // In a real implementation, you'd draw individual pixels for each character
    displaySetWindow(g_display_state.cursor_x, g_display_state.cursor_y,
                     g_display_state.cursor_x + char_width - 1,
                     g_display_state.cursor_y + char_height - 1);
    displayCommandMode();
    displayWrite8(0x2C);  // RAMWR
    displayDataMode();
    for (uint16_t j = 0; j < char_width * char_height; j++) {
      displayWrite16(g_display_state.text_color);
    }
    
    g_display_state.cursor_x = next_x;
    yield();  // Yield after each character
  }
}

void displayPrintLine(const String& text) {
  displayPrintText(text);
  g_display_state.cursor_x = 0;
  g_display_state.cursor_y += 8 * g_display_state.text_size;
}

void displayClearLine(uint16_t line_num) {
  if (!g_display_state.initialized) {
    return;
  }
  
  uint16_t y = line_num * (8 * g_display_state.text_size);
  uint16_t height = 8 * g_display_state.text_size;
  
  if (y < DISPLAY_HEIGHT) {
    displayFillRectangle(0, y, DISPLAY_WIDTH, height, g_display_state.background_color);
  }
}

// Utility: Convert hex string to RGB565 color
uint16_t hexToColor(const String& hex_str) {
  unsigned long hex = strtoul(hex_str.c_str(), nullptr, 16);
  
  uint8_t r = (hex >> 16) & 0xFF;
  uint8_t g = (hex >> 8) & 0xFF;
  uint8_t b = hex & 0xFF;
  
  // Convert to RGB565
  uint16_t r5 = (r >> 3) & 0x1F;
  uint16_t g6 = (g >> 2) & 0x3F;
  uint16_t b5 = (b >> 3) & 0x1F;
  
  return (r5 << 11) | (g6 << 5) | b5;
}

String colorToHex(uint16_t color) {
  uint8_t r5 = (color >> 11) & 0x1F;
  uint8_t g6 = (color >> 5) & 0x3F;
  uint8_t b5 = color & 0x1F;
  
  uint8_t r = (r5 << 3) | (r5 >> 2);
  uint8_t g = (g6 << 2) | (g6 >> 4);
  uint8_t b = (b5 << 3) | (b5 >> 2);
  
  char hex[7];
  snprintf(hex, sizeof(hex), "%02X%02X%02X", r, g, b);
  return String(hex);
}

void displayGetState() {
  // This is called by displayGetStatus in commands.cpp
}
