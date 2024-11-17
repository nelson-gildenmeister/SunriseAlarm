import datetime as dt
import signal
import sys
from threading import Timer

from dimmer import Dimmer
from sunrise_data import SunriseData


class SunriseController:
    def __init__(self, view, data, dimmer):
        self.view = view
        self.data: SunriseData = data
        self.dimmer: Dimmer = dimmer
        signal.signal(signal.SIGINT, self.signal_handler)
        self.start: dt.datetime = dt.datetime.now()
        self.cancel: bool = False
        self.sec_per_step: int = 0


    def start_schedule(self):
        # Calculate the end time based upon current time and length
        self.start = dt.datetime.now()
        self.sec_per_step: int = int(self.data.sunrise_duration_minutes.seconds / self.dimmer.get_num_steps())
        self.dimmer.set_level(self.dimmer.get_min_level())

        # Loop until schedule time ends, sleeping until need to change brightness.  Check for
        # events that can end the loop early like cancel or shutdown.
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

    def set_clock(self):
        pass

    def button1_press(self, channel):
        pass

    def button2_press(self, channel):
        pass

    def button3_press(self, channel):
        pass

    def button4_press(self, channel):
        pass

    def signal_handler(self, sig, frame):
        self.dimmer.shutdown()
        sys.exit(0)


