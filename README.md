Headless Wireless Settings:
sudo raspi-config


HOST (windows machine):

Ubuntu VM install on VmWare:
Don't install VMware Tools (to get copy/paste, etc.). Use open-vm-tools-desktop if using a GUI or for command line use open-vm-tools and then restart:
sudo apt update && sudo apt -y install open-vm-tools-desktop
# Command line (no GUI): sudo apt update && sudo apt -y install open-vm-tools


Install git:
sudo apt install git

Setup git access to allow clone:
cd ~/.ssh
ssh-keygen -t rsa -b 4096 -C "nelson.gildenmeister@gmail.com"
cat id_rsa.pub
One the github website, under your account, in the "SSH and GPG keys" section, click on "new SSH key" and copy/paste the key.
git config --global user.name "nelson-gildenmeister"
git config --global user.email nelson.gildemeister@gmail.com
Clone your repo.

How to mount shared directory with open-vm-tools:
https://gist.github.com/darrenpmeyer/b69242a45197901f17bfe06e78f4dee3

Install Python3.11 since issues trying to use higher version with RaspberryPi libraries:
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.11

Point python3 link to python3.11:
# DON'T DO THIS - CAN'T LAUNCH A TERMINAL AFTER, look for a better way
cd /usr/bin
sudo unlink python3
sudo ln python3.11 python3

Do not use the RPi.GPIO python module - it is NOT supported by Raspberry Pi Ltd.
Instead use rpi-lgpio which is supported and emulates all the RPi.GPIO calls:
pip install rpi-lgpio


Stuff needed for Adafruit PiOLED:
--------------------------------
1) First install Circuit Python and Blinka:
> sudo apt-get update
> sudo apt-get -y upgrade
> sudo apt-get install python3-pip

> sudo apt install --upgrade python3-setuptools

1.a) Setup virtual env and activate:
> sudo apt install python3-venv
> python3 -m venv .venv --system-site-packages
> source .venv/bin/activate

1.b) Enable Interfaces:
> sudo raspi-config nonint do_i2c 0
> sudo raspi-config nonint do_spi 0
> sudo raspi-config nonint do_serial_hw 0
> sudo raspi-config nonint do_ssh 0
> sudo raspi-config nonint do_camera 0
> sudo raspi-config nonint disable_raspi_config_at_boot 0

1.c) Install Blinka and dependencies:
> sudo apt-get install -y i2c-tools libgpiod-dev python3-libgpiod
> pip3 install --upgrade RPi.GPIO
> pip3 install --upgrade adafruit-blinka

1.d) Check Interfaces:
> ls /dev/i2c* /dev/spi*
/dev/i2c-1 /dev/spidev0.0 /dev/spidev0.1

2) Install Library for PiOLED:
> pip install adafruit-circuitpython-ssd1306

3) Install pillow for fonts:
> sudo apt-get install python3-pil

4) Shutdown, plugin OLED, test
> sudo shutdown -h now
Pinout:
Top row pins Left to Right:
2 (5V), 4 (5V), 6 (Ground)
Second row pins Left to Right:
1 (3V3), 3 (SDA I2C), 5 (SCL I2C)

-----------
|   2 4 6 |
| O o o o |
|   o o o |
|   1 3 5 |
|-----------------------------|
|                             |
|                             |
|                             |
-------------------------------

5) Start pigpio daemon:
> sudo pigpiod
To start automatically upon boot:
> sudo vi /etc/rc.local
Add this line before the exit line:
/usr/bin/pigpiod


Info for pigpio:
https://raspberrypi.stackexchange.com/questions/89577/led-pwm-fading-is-flickering  (Startup instructions are no longer correct, use from below)
https://abyz.me.uk/rpi/pigpio/download.html
Start pigpio daemon:
sudo pigpiod
Stop the pigpio daemon:
sudo kill pigpiod
If venv does not have pigpio:
pip install pigpio



Development workflow:
git fetch -p origin
git merge origin/master

python sunrise_main.py
