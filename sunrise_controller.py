import signal
import sys
from threading import Timer
import datetime as dt
import sched
import time

from dimmer import Dimmer
from enum import Enum
from sunrise_data import SunriseData, SunriseSettings, DisplayMode
from sunrise_view import OledDisplay

class DayOfWeek(Enum):
    Monday = 0
    Tuesday = 1
    Wednesday = 2
    Thursday = 3
    Friday = 4
    Saturday = 5
    Sunday = 6

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

        if self.settings.start_time[weekday]:
            start_time = dt.datetime.strptime(self.settings.start_time[weekday], "%H:%M:%S")
            if (start_time > now) and (start_time < (now + dt.timedelta(minutes=self.settings.minutes[weekday]))):
                # TODO - In the middle of sunrise, set to proper level
                pass
            elif start_time < now:
                # Sunrise start is today but in the future, set up an event to start
                self.schedule_sunrise_start(self.settings.start_time[weekday])
        else:
            # No scheduled time for today, look for the next scheduled time and set up an event for it
            # Start tomorrow. Be sure to wrap around if end of week (Sunday)
            day_index = (weekday + 1) % DayOfWeek.Sunday.value
            for day in range(7):
                if self.settings.start_time[day_index]:
                    self.schedule_sunrise_start(self.settings.start_time[weekday])
                    break
                day_index = (day_index + 1) % DayOfWeek.Sunday.value


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


    def schedule_sunrise_start(self, start_time):
        # Create a new scheduler
        scheduler = sched.scheduler(time.time, time.sleep)

        # Schedule the backup to run at 1:00 AM every day
        #backup_time = time.strptime('01:00:00', '%H:%M:%S')
        backup_time = time.strptime('01:00:00', '%H:%M:%S')
        backup_event = scheduler.enterabs(time.mktime(backup_time), 1, self.start_schedule, ())

        # Start the scheduler
        scheduler.run()


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
