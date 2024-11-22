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
    def __init__(self, display_auto_power_off_minutes):
        self.display_on:bool = True
        self.display_auto_power_off_minutes:float  = display_auto_power_off_minutes
        self.start_display_time:float = time.time()
        self.x_pos:int = 0

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
        self.image = Image.new("1", (self.width, self.height))

        # Get drawing object to draw on image.
        self.draw:ImageDraw = ImageDraw.Draw(self.image)

        # Load default font.
        self.font = ImageFont.load_default()

        # Alternatively load a TTF font.  Make sure the .ttf font file is in the
        # same directory as the python script!
        # Some other nice fonts to try: http://www.dafont.com/bitmap.php
        # font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 9)

        self.clear_display()


    def clear_display(self):
        self.disp.fill(0)
        self.disp.show()


    def update_status_display(self, start_time, end_time):
        # Draw a black filled box to clear the image.
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

        cmd = "date \"+%a, %b %d  %I:%M\""
        date = subprocess.check_output(cmd, shell=True).decode("utf-8")

        # See if auto-power off
        if not self.is_display_on():
            return

        current = time.time()
        elapsed_minutes = int((current - start_time) / 60)
        remain_minutes = int(end_time - elapsed_minutes)
        if elapsed_minutes == 0:
            status_str = f"Sunrise just started...less than {end_time} minutes remaining"
        elif remain_minutes <= 0:
            status_str = "Waiting for next sunrise"
        else:
            status_str = f"Sunrise started {elapsed_minutes} minutes ago...{remain_minutes} minutes remaining"

        # Write four lines of text.
        self.draw.text((x, top + 0), "SUNRISE ALARM", font=self.font, fill=255)
        self.draw.text((x, top + 8), date, font=font, fill=255)
        self.draw.text((x, top + 16), "Status: " + status_str[x_pos:], font=self.font, fill=255)
        self.draw.text((x, top + 25), "Select   <   >   Back", font=self.font, fill=255)

        self.x_pos = self.x_pos + 1
        if self.x_pos >= len(status_str):
            x_pos = 0

        # Display image.
        self.disp.image(self.image)
        self.disp.show()
        # Keep status up longer if at start of status message.
        if self.x_pos == 0:
            time.sleep(1.0)
        else:
            time.sleep(0.1)




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
        self.display_on = False
        self.clear_display()

        return False


    # Public method to turn display on
    def turn_display_on(self):
        self.start_display_time = time.time()
        self.display_on = True
        self.update_status_display()

    def shutdown(self):
        # Blank display on stop
        self.disp.fill(0)
        self.disp.show()