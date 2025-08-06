# This code is for use on (Linux) computers that are using CPython with
# Adafruit Blinka to support CircuitPython libraries. CircuitPython does
# not support PIL/pillow (python imaging library)!

# YOU MUST BE IN THE PYTHON VENV THAT HAS Blinka INSTALLED TO RUN!!!
# source ./blinka/bin/activate

# Do not use the RPi.GPIO python module - it is NOT supported by Raspberry Pi Ltd.
# Instead, use rpi-lgpio which is supported and emulates all the RPi.GPIO calls

import subprocess
import time

import adafruit_ssd1306
import busio
from PIL import Image, ImageDraw, ImageFont
from board import SCL, SDA


class OledDisplay:
    __max_line_len__ = 21

    def __init__(self, display_auto_power_off_minutes: int, debug: bool):
        self.debug = debug
        self.display_on: bool = True
        self.display_auto_power_off_minutes: float = display_auto_power_off_minutes
        self.start_display_time: float = time.time()
        self.x_pos: int = 0
        self.line1: str = ''
        self.line2: str = ''
        self.line3: str = ''
        self.line4 : str= ''
        self.scroll_idx = 0
        self.scroll: bool = True
        self.debug = False
        self.is_status_display = True
        self.status_display_line = ''

        # Create the I2C interface.
        self.i2c = busio.I2C(SCL, SDA)

        # Create the SSD1306 OLED class.
        # The first two parameters are the pixel width and pixel height.  Change these
        # to the right size for your display!
        self.disp = adafruit_ssd1306.SSD1306_I2C(128, 32, self.i2c)

        # Create blank image for drawing.
        # Make sure to create image with mode '1' for 1-bit color.
        self.width = self.disp.width
        self.height = self.disp.height
        self.padding = -2
        self.image = Image.new("1", (self.width, self.height))

        # Get drawing object to draw on image.
        self.draw: ImageDraw = ImageDraw.Draw(self.image)

        # Load default font.
        self.font = ImageFont.load_default()

        # Alternatively load a TTF font.  Make sure the .ttf font file is in the
        # same directory as the python script!
        # Some other nice fonts to try: http://www.dafont.com/bitmap.php
        #self.font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 9)
        #self.font = ImageFont.truetype('./Prototype.ttf', 9)

        self.clear_display()

    def clear_display(self):
        self.disp.fill(0)
        self.disp.show()

    def set_display_lines(self, line1: str, line2: str, line3: str, line4: str):
        self.line1 = line1
        self.line2 = line2
        self.line3 = line3
        self.line4 = line4

    def set_line1(self, line1):
        self.line1 = line1

    def set_line2(self, line2):
        self.line2 = line2

    def set_line3(self, line3):
        self.line3 = line3

    def set_line4(self, line4):
        self.line4 = line4

    def set_status_display_line(self, status):
        self.status_display_line = status

    def enable_status_display(self):
        self.is_status_display = True

    def disable_status_display(self):
        self.is_status_display = False

    def update_display(self):
        # See if auto-power off
        if not self.is_display_on():
            return

        third_line: str
        top = self.padding
        # Draw a black filled box to clear the image.
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

        # Set display lines using defaults for empty lines
        self.scroll_idx = 0
        if not self.line1:
            first_line = 'Sunrise Alarm'
        else:
            first_line = self.line1
        if not self.line2:
            cmd = "date \"+%a, %b %d %I:%M %P\""
            date = subprocess.check_output(cmd, shell=True).decode("utf-8")
            second_line = date
        else:
            second_line = self.line2

        if self.is_status_display:
            third_line = self.status_display_line
        else:
            third_line = self.line3
        fourth_line = self.line4

        # Write four lines of text.
        self.draw.text((0, top + 0), first_line, font=self.font, fill=255)
        self.draw.text((0, top + 8), second_line, font=self.font, fill=255)
        self.draw.text((0, top + 16), third_line[self.x_pos:], font=self.font, fill=255)
        self.draw.text((0, top + 25), fourth_line, font=self.font, fill=255)

        # Display image.
        self.disp.image(self.image)
        self.disp.show()

        # if line3_scroll and len(third_line) > self.__max_line_len__:
        #     for self.x_pos in range(1, len(third_line) + 1 - self.__max_line_len__):
        #         time.sleep(0.1)
        #         # Wrap back around to zero index
        #         idx = self.x_pos % len(third_line)
        #         self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
        #         self.draw.text((0, top + 0), first_line, font=self.font, fill=255)
        #         self.draw.text((0, top + 8), second_line, font=self.font, fill=255)
        #         self.draw.text((0, top + 16), third_line[idx:], font=self.font, fill=255)
        #         self.draw.text((0, top + 25), fourth_line, font=self.font, fill=255)
        #
        #         # Display image.
        #         self.disp.image(self.image)
        #         self.disp.show()

    def scroll_line3(self) -> bool:
        at_end = False
        third_line: str

        # See if auto-power off
        if not self.is_display_on():
            return at_end

        if not self.scroll or len(self.line3) < self.__max_line_len__:
            return at_end

        top = self.padding
        # No way to clear just one line - everything is additive and spaces don't overwrite anything
        # Draw a black filled box to clear the image.
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

        # Set display lines using defaults for empty lines
        if not self.line1:
            first_line = 'Sunrise Alarm'
        else:
            first_line = self.line1
        if not self.line2:
            cmd = "date \"+%a, %b %d %I:%M %P\""
            date = subprocess.check_output(cmd, shell=True).decode("utf-8")
            second_line = date
        else:
            second_line = self.line2
        if self.is_status_display:
            third_line = self.status_display_line
        else:
            third_line = self.line3
        fourth_line = self.line4


        self.scroll_idx = self.scroll_idx + 1
        if self.scroll_idx > len(self.line3):
            self.scroll_idx = 0
            at_end = True

        # Wrap back around to zero index
        idx = self.scroll_idx % len(self.line3)
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
        self.draw.text((0, top + 0), first_line, font=self.font, fill=255)
        self.draw.text((0, top + 8), second_line, font=self.font, fill=255)
        self.draw.text((0, top + 16), third_line[idx:], font=self.font, fill=255)
        self.draw.text((0, top + 25), fourth_line, font=self.font, fill=255)

        # Display image.
        self.disp.image(self.image)
        self.disp.show()

        return at_end

    # Determine whether display has been on past the maximum on time.
    def is_display_on(self):
        if not self.display_on:
            return False
        # Display is currently on, check if it should be off
        end_display_time = time.time()
        display_time_minutes = int((end_display_time - self.start_display_time) / 60)

        if display_time_minutes < self.display_auto_power_off_minutes:
            return True

        # Display needs to be turned off
        print('Auto off display')
        self.display_on = False
        self.clear_display()

        return False


    # Public method to turn display on
    def turn_display_on(self):
        self.start_display_time = time.time()
        self.display_on = True
        self.update_display()

    def shutdown(self):
        # Blank display on stop
        self.disp.fill(0)
        self.disp.show()
