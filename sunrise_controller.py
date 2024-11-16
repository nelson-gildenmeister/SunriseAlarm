from threading import Timer
import time
import signal
import sys

brightness_level:int = 0


def button1_press(channel):
    pass

def button2_press(channel):
    pass

def button3_press(channel):
    pass

def button4_press(channel):
    pass



class SunriseController:
    def __init__(self, view, data, dimmer):
        self.view = view
        self.data = data
        self.dimmer = dimmer
        signal.signal(signal.SIGINT, self.signal_handler)


    def start_schedule(self):
        pass

    def set_schedule(self):
        pass

    def cancel_schedule(self):
        pass

    def set_clock(self):
        pass

    def signal_handler(self, sig, frame):
        # shutdown()
        sys.exit(0)


