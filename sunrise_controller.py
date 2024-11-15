from threading import Timer
import time

brightness_level:int = 0


def button1_press(channel):
    pass

def button2_press(channel):
    pass

def button3_press(channel):
    pass

def button4_press(channel):
    pass

def turn_off_gate():
    #  GPIO.output(triac_gate_gpio, GPIO.HIGH)
    pass


def zero_cross(channel):
    global brightness_level
    # Turn off triac gate since we are at zero crossing
    if brightness_level > 0:
        # Calculate delay and start timer
        ms_delay = 2_000 + (8_000 - (80 * brightness_level))
        interval_sec = int(ms_delay / 1000)
        #  GPIO.output(triac_gate_gpio, GPIO.HIGH)
        t = Timer(interval_sec, turn_off_gate)
        t.start()


class SunriseController:
    def __init__(self, view, settings):
        self.view = view
        self.settings = settings
