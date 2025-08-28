## Introduction
This project implements a sunrise alarm clock that allows a user to wake up gradually via slow dimming up of a plugged in lamp.
The code is used in conjunction with the following hardware: raspberrypi, dimmer module, oled display, 4-button module, 120V socket.  A descriptive parts list appears at the bottom of this README.

## Host Ubuntu VM install on VmWare:
Don't install VMware Tools (to get copy/paste, etc.). Use open-vm-tools-desktop if using a GUI or for command line use open-vm-tools and then restart:
sudo apt update && sudo apt -y install open-vm-tools-desktop
Command line (no GUI): sudo apt update && sudo apt -y install open-vm-tools

## RaspberryPi First Time Setup
Headless Wireless Settings:
sudo raspi-config

Install git:
```sudo apt install git```

Setup git access to allow clone:
```
cd ~/.ssh
ssh-keygen -t rsa -b 4096 -C "my_email@email_server"
cat id_rsa.pub
```
On the github website, under your account, in the "SSH and GPG keys" section, click on "new SSH key" and copy/paste the key.
```
git config --global user.name "user-name"
git config --global user.email my_email@email_server
```
Clone your repo.

How to mount shared directory with open-vm-tools:
https://gist.github.com/darrenpmeyer/b69242a45197901f17bfe06e78f4dee3

Install Python3.11 since there are issues trying to use higher version with RaspberryPi libraries:
```
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.11
```

Point python3 link to python3.11:
Note: DON'T DO THIS - CAN'T LAUNCH A TERMINAL AFTER, look for a better way
```
cd /usr/bin
sudo unlink python3
sudo ln python3.11 python3
```
**Create a Python virtual environment (E.g., ~/SunriseAlarm/sunrise_venv) and activate it before doing the pip installs below.**

Do not use the RPi.GPIO python module - it is NOT supported by Raspberry Pi Ltd.
Instead use rpi-lgpio which is supported and emulates all the RPi.GPIO calls:
```
pip install rpi-lgpio
```
If venv does not have pigpio:
```
pip install pigpio
```

### Stuff needed for Adafruit PiOLED:

1. Install Circuit Python and Blinka:
```
> sudo apt-get update
> sudo apt-get -y upgrade
> sudo apt-get install python3-pip

> sudo apt install --upgrade python3-setuptools
```
2. Setup virtual env and activate:
```
> sudo apt install python3-venv
> python3 -m venv .venv --system-site-packages
> source .venv/bin/activate
```
3. Enable Interfaces:
```
> sudo raspi-config nonint do_i2c 0
> sudo raspi-config nonint do_spi 0
> sudo raspi-config nonint do_serial_hw 0
> sudo raspi-config nonint do_ssh 0
> sudo raspi-config nonint do_camera 0
> sudo raspi-config nonint disable_raspi_config_at_boot 0
```
4. Install Blinka and dependencies:
```
> sudo apt-get install -y i2c-tools libgpiod-dev python3-libgpiod
> pip3 install --upgrade RPi.GPIO
> pip3 install --upgrade adafruit-blinka
```
5. Check Interfaces:
```
> ls /dev/i2c* /dev/spi*
/dev/i2c-1 /dev/spidev0.0 /dev/spidev0.1
```
6. Install Library for PiOLED:
```
> pip install adafruit-circuitpython-ssd1306
```
7. Install pillow for fonts:
```
> sudo apt-get install python3-pil
```
8. Shutdown, plugin OLED, test
```
> sudo shutdown -h now
```

### PiOLED Pinout:
Top row pins Left to Right:
2 (5V), 4 (5V), 6 (Ground)
Second row pins Left to Right:
1 (3V3), 3 (SDA I2C), 5 (SCL I2C)
```
-----------
|   2 4 6 |
|   o o o |
|   o o o |
|   1 3 5 |
|-----------------------------|
|                             |
|                             |
|                             |
-------------------------------
```

### Start pigpio daemon:
```
> sudo pigpiod
```
To start pigpio automatically upon boot, edit rc.local:
```
> sudo vi /etc/rc.local
```
Add this line before the exit line:
```
/usr/bin/pigpiod
```

### Miscellaneous Info for pigpio:
Startup instructions are no longer correct, use instructions in this README

https://raspberrypi.stackexchange.com/questions/89577/led-pwm-fading-is-flickering

https://abyz.me.uk/rpi/pigpio/download.html

Stop the pigpio daemon:
```
sudo kill pigpiod
```

### Development workflow:
1. If not already in Python virtual environment, switch to it:
```
source ~/SunriseAlarm/sunrise_venv/bin/activate
```
2. Update the code from the repository after first discarding any local changes:
```
git checkout .
git fetch -p origin
git merge origin/master
```
3. Start the program:
```
python sunrise_main.py
```

## Hardware List
Note that the dimmer module used is NOT a zero-crossing detect type.  Instead, it is controlled by connecting its Pulse Width Modulated (PWM) input to a GPIO pin on the RaspberryPi and varying the duty cycle to control the brightness level.
1. Raspberry Pi Zero 2 or Zero 2 W
2. Adafruit PiOLED - 128X32 Monochrome OLED: [Adafruit PiOled](https://www.adafruit.com/product/3527)
3. PWM AC Voltage Dimmer - available from Amazon: [PWM dimmer](https://www.amazon.com/Light-Dimmer-Module-Arduino-Raspberry/dp/B06Y1DT1WP?pd_rd_w=vvctp&content-id=amzn1.sym.4af096b2-fb5d-43d2-a23c-ac48118349a2&pf_rd_p=4af096b2-fb5d-43d2-a23c-ac48118349a2&pf_rd_r=SND5D1CAYWRCNDGEEBTS&pd_rd_wg=tn9Gn&pd_rd_r=c463b44b-bfe3-47ac-ab67-65d962170773&pd_rd_i=B06Y1DT1WP&psc=1&ref_=pd_basp_d_rpt_ba_s_1_t) or direct from www.IOTMUG.com
4. 4-key Keyboard module push button switch: [pushbutton module](https://www.amazon.com/gp/product/B09WB1VD97/ref=ox_sc_act_title_1?smid=A1U1S78HE02JLU&psc=1)
5. AC 120V USA standard 2 prong power socket