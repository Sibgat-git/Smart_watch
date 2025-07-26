# ssd1306.py

# Based on MicroPython SSD1306 OLED driver, written by Peter Hinch, et al.
# Optimized for basic use cases with I2C.

import framebuf

# Register definitions
SET_CONTRAST        = 0x81
SET_ENTIRE_ON       = 0xA4
SET_NORM_INV        = 0xA6
SET_DISP            = 0xAE
SET_MEM_ADDR        = 0x20
SET_COL_ADDR        = 0x21
SET_PAGE_ADDR       = 0x22
SET_DISP_START_LINE = 0x40
SET_SEG_REMAP       = 0xA0
SET_MUX_RATIO       = 0xA8
SET_COM_OUT_DIR     = 0xC0
SET_COM_PIN_CFG     = 0xDA
SET_DISP_OFFSET     = 0xD3
SET_CLK_DIV         = 0xD5
SET_PRECHARGE       = 0xD9
SET_VCOMD           = 0xDB
SET_NOP             = 0xE3
CHARGE_PUMP         = 0x8D

class SSD1306:
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        self.framebuf = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def init_display(self):
        for cmd in (
            SET_DISP | 0x00,  # off
            # address setting
            SET_MEM_ADDR, 0x00,  # 0x00 horizontal addressing mode
            # resolution and layout
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01,  # column addr 127 mapped to seg0
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR | 0x08,  # scan from com[N-1] to com0
            SET_COM_PIN_CFG, 0x02 if self.width > self.height else 0x12, # Adjusted based on common configurations for 128x64
            SET_DISP_OFFSET, 0x00,
            SET_CLK_DIV, 0x80,
            SET_PRECHARGE, 0x22 if self.external_vcc else 0xF1,
            SET_VCOMD, 0x20,  # 0.77*Vcc
            CHARGE_PUMP, 0x10 if self.external_vcc else 0x14,
            SET_CONTRAST, 0xFF,  # full contrast
            SET_ENTIRE_ON,       # output follows RAM contents
            SET_NORM_INV,        # not inverted
            SET_DISP | 0x01):    # on
            self.write_cmd(cmd)
        self.show()

    def poweroff(self):
        self.write_cmd(SET_DISP | 0x00)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST, contrast)

    def invert(self, invert):
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def rotate(self, rotate):
        self.write_cmd(SET_COM_OUT_DIR | ((rotate & 1) << 3))
        self.write_cmd(SET_SEG_REMAP | (rotate & 1))

    def show(self):
        self.write_cmd(SET_COL_ADDR, 0x00, self.width - 1)
        self.write_cmd(SET_PAGE_ADDR, 0x00, self.pages - 1)
        self.write_data(self.buffer)

    def fill(self, col):
        self.framebuf.fill(col)

    def pixel(self, x, y, col):
        self.framebuf.pixel(x, y, col)

    def scroll(self, dx, dy):
        self.framebuf.scroll(dx, dy)

    def text(self, string, x, y, col=1):
        self.framebuf.text(string, x, y, col)

    def blit(self, fbuf, x, y, width, height):
        # Optimized blit for entire image
        # This assumes the fbuf is a bytearray of the correct size (width * height / 8)
        # and directly copies it to the internal buffer.
        # It bypasses the more complex framebuf.blit if the sizes match.
        if x == 0 and y == 0 and width == self.width and height == self.height:
            self.buffer[:] = fbuf[:] # Direct bytearray copy
        else:
            # Fallback for partial blit, if framebuf.blit supports bytearrays directly
            # or if fbuf itself is a FrameBuffer object.
            # The micropython-lib version of ssd1306.py usually handles this.
            # If still getting TypeErrors here, a manual pixel copy loop might be needed.
            self.framebuf.blit(framebuf.FrameBuffer(fbuf, width, height, framebuf.MONO_VLSB), x, y)


class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3c, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd1, cmd2=None, cmd3=None):
        if cmd2 is None:
            self.temp[0] = 0x80  # Co=1, D/C#=0
            self.temp[1] = cmd1
            self.i2c.writeto(self.addr, self.temp)
        elif cmd3 is None:
            self.temp[0] = 0x80  # Co=1, D/C#=0
            self.temp[1] = cmd1
            self.i2c.writeto(self.addr, self.temp)
            self.temp[0] = 0x80  # Co=1, D/C#=0
            self.temp[1] = cmd2
            self.i2c.writeto(self.addr, self.temp)
        else:
            # For commands that take two parameters (e.g., SET_COL_ADDR)
            self.temp[0] = 0x80  # Co=1, D/C#=0
            self.temp[1] = cmd1
            self.i2c.writeto(self.addr, self.temp)
            self.temp[0] = 0x80  # Co=1, D/C#=0
            self.temp[1] = cmd2
            self.i2c.writeto(self.addr, self.temp)
            self.temp[0] = 0x80  # Co=1, D/C#=0
            self.temp[1] = cmd3
            self.i2c.writeto(self.addr, self.temp)


    def write_data(self, buf):
        self.i2c.writeto(self.addr, b'\x40' + buf) # Co=0, D/C#=1