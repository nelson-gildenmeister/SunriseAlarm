# SPDX-FileCopyrightText: 2017 Tony DiCola for Adafruit Industries
# SPDX-FileCopyrightText: 2017 James DeVito for Adafruit Industries
# SPDX-License-Identifier: MIT

# This example is for use on (Linux) computers that are using CPython with
# Adafruit Blinka to support CircuitPython libraries. CircuitPython does
# not support PIL/pillow (python imaging library)!

# YOU MUST BE IN THE PYTHON VENV THAT HAS Blinka INSTALLED TO RUN!!!
# source ./blinka/bin/activate

# Do not use the RPi.GPIO python module - it is NOT supported by Raspberry Pi Ltd.
# Instead use rpi-lgpio which is supported and emulates all the RPi.GPIO calls

import time
import subprocess
import RPi.GPIO as GPIO
import mypy

from board import SCL, SDA
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
from sunrise_view import OledDisplay

btn1_gpio = 20
status = 0
status_str = "Program running...Sunrise has not started yet"
x_pos = 0
sunrise_max_minutes = 90
display_auto_power_off_minutes = 1
brightness_level = 0



# Setup GPIO pins - use BCM numbering instead of pin (GPIO.BOARD) numbering
GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setup(btn1_gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(btn1_gpio, GPIO.FALLING, callback=button1_press, bouncetime=300)

# Create the I2C interface.
i2c = busio.I2C(SCL, SDA)

# Create the SSD1306 OLED class.
# The first two parameters are the pixel width and pixel height.  Change these
# to the right size for your display!
disp = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)

# Clear display.
disp.fill(0)
disp.show()

# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
width = disp.width
height = disp.height
image = Image.new("1", (width, height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0, 0, width, height), outline=0, fill=0)

# Draw some shapes.
# First define some constants to allow easy resizing of shapes.
padding = -2
top = padding
bottom = height - padding
# Move left to right keeping track of the current x position for drawing shapes.
x = 0

# Load default font.
font = ImageFont.load_default()

start = time.time()
# Make sure display auto-turns off
start_display_time = time.time()

# Alternatively load a TTF font.  Make sure the .ttf font file is in the
# same directory as the python script!
# Some other nice fonts to try: http://www.dafont.com/bitmap.php
# font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 9)

try:
    while True:
        # Draw a black filled box to clear the image.
        draw.rectangle((0, 0, width, height), outline=0, fill=0)

        cmd = "date \"+%a, %b %d  %I:%M\""
        date = subprocess.check_output(cmd, shell=True).decode("utf-8")

        # See if auto-power off
        end_display_time = time.time()
        display_time_minutes = int((end_display_time - start_display_time) / 60)

        if display_time_minutes < display_auto_power_off_minutes:
            # Write four lines of text.
            draw.text((x, top + 0), "SUNRISE ALARM", font=font, fill=255)
            draw.text((x, top + 8), date, font=font, fill=255)
            draw.text((x, top + 16), "Status: " + status_str[x_pos:], font=font, fill=255)
            draw.text((x, top + 25), "Select   <   >   Back", font=font, fill=255)

        # Display image.
        disp.image(image)
        disp.show()
        # Keep status up longer if at start of status message.
        if x_pos == 0:
            time.sleep(1.0)
        else:
            time.sleep(0.1)

        end = time.time()
        elapsed_minutes = int((end - start) / 60)
        remain_minutes = int(sunrise_max_minutes - elapsed_minutes)
        if elapsed_minutes == 0:
            status_str = f"Sunrise just started...less than {sunrise_max_minutes} minutes remaining"
        elif remain_minutes <= 0:
            status_str = "Sunrise finished"
        else:
            status_str = f"Sunrise started {elapsed_minutes} minutes ago...{remain_minutes} minutes remaining"
        x_pos = x_pos + 1
        if x_pos >= len(status_str):
            x_pos = 0

        # if  not GPIO.input(btn1_gpio):
        #    status_str = "Stopped!"
        # else:
        #    status_str = "Running..."

finally:
    GPIO.cleanup()
    # Blank display on stop
    disp.fill(0)
    disp.show()


if __name__ == '__main__':
    oled = OledDisplay(3)
