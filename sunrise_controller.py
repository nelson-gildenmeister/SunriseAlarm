import signal
import sys
from threading import Timer
import datetime as dt

from dimmer import Dimmer
from sunrise_data import SunriseData, SunriseSettings, DisplayMode
from sunrise_view import OledDisplay


class SunriseController:
    def __init__(self, view: OledDisplay, data, dimmer):
        self.view = view
        self.data: SunriseData = data
        self.settings: SunriseSettings = data.settings
        self.dimmer: Dimmer = dimmer
        signal.signal(signal.SIGINT, self.signal_handler)
        self.start: dt.datetime = dt.datetime.now()
        self.cancel: bool = False
        self.sec_per_step: int = 0

    def startup(self):
        # TODO - Hook up button gpio pins to their event handlers

        display_mode = DisplayMode.idle

        # Either sunrise start is in the future or are in the middle of a sunrise.
        # First, get the day and time of the next scheduled sunrise.
        now = dt.datetime.now()
        weekday = now.weekday()

        if self.settings.minutes[weekday] > 0:
            start_time = dt.datetime.strptime(self.settings.start_time[weekday], "%H:%M:%S")
            if (start_time > now) and (start_time < (now + dt.timedelta(minutes=self.settings.minutes[weekday]))):
                pass

        self.data.set_display_mode(display_mode)


    def start_schedule(self):
        # Calculate the end time based upon current time and length
        self.start = dt.datetime.now()
        self.sec_per_step: int = int(self.data.sunrise_duration_minutes.seconds / self.dimmer.get_num_steps())
        self.dimmer.set_level(self.dimmer.get_min_level())
        self.check_schedule()

    def check_schedule(self):
        if (self.dimmer.get_level() < self.dimmer.get_max_level()) and not self.cancel:
            self.dimmer.increment_level()
            t = Timer(self.sec_per_step, self.check_schedule)
            t.start()

    def set_schedule(self):
        pass

    def cancel_schedule(self):
        self.cancel = True
        self.dimmer.set_level(self.dimmer.get_min_level())


    def set_display_on(self, mode):
        self.data.set_display_mode(mode)
        self.view

    def set_clock(self):
        pass

    def button1_press(self, channel):
        if not self.data.is_display_on():
            self.data.

    def button2_press(self, channel):
        pass

    def button3_press(self, channel):
        pass

    def button4_press(self, channel):
        pass

    def signal_handler(self, sig, frame):
        self.dimmer.shutdown()
        sys.exit(0)
