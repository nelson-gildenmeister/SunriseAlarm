import datetime as dt
import signal
import sys
import time
from dataclasses import dataclass
from enum import Enum
from sched import scheduler
from threading import Timer

from dimmer import Dimmer
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

class State(Enum):
    IdleNoProg = 0
    IdleProgSet = 1
    InProgress = 2
    MainMenu = 3



@dataclass
class DisplayState:
    button_states = {State.IdleNoProg: ['Menu', 'On', 'Off', 'Dim'],
                     'idle_prog_set': ['Menu', 'On', 'Off', 'Dim'],
                     'in_progress': ['Menu', 'On', 'Off', 'Dim'],
                     'main_menu': ['Sel', '<', '>', 'Bck' ]}
    status_menus = {'main_menu'}
    status = {'idle_no_prog': ['No sunrise program set'],
              'idle_prog_set': ['Next sunrise starts in: %1'],
              'in_progress': ['Sunrise started %1 minutes ago...%2 minutes remaining'],
              'main_menu': ['Set Schedule', 'Set Clock']}


class SunriseController:
    def __init__(self, view: OledDisplay, data, dimmer):
        self.sunrise_event_id = None
        self.view = view
        self.data: SunriseData = data
        self.settings: SunriseSettings = data.settings
        self.dimmer: Dimmer = dimmer
        signal.signal(signal.SIGINT, self.signal_handler)
        self.start: dt.datetime = dt.datetime.now()
        self.cancel: bool = False
        self.sec_per_step: int = 0
        self.is_running: bool = False

    def startup(self):
        # TODO - Hook up button gpio pins to their event handlers

        display_mode = DisplayMode.idle

        # Either sunrise start is in the future or are in the middle of a sunrise.
        # First, get the day and time of the next scheduled sunrise.
        now = dt.datetime.now()
        weekday = now.weekday()

        if self.settings.start_time[weekday]:
            start_time = dt.datetime.strptime(self.settings.start_time[weekday], '%H:%M:%S')
            if (start_time > now) and (start_time < (now + dt.timedelta(minutes=self.settings.minutes[weekday]))):
                # TODO - In the middle of sunrise, set to proper level
                minutes_remaining = (now - dt.timedelta(minutes=self.settings.minutes[weekday])).minute
                percent_brightness = int(minutes_remaining / self.settings.minutes[weekday])
                self.start_schedule(percent_brightness)
                pass
            elif start_time < now:
                # Sunrise start is today but in the future, set up an event to start
                self.schedule_sunrise_start(self.settings.start_time[weekday])
        else:
            # No scheduled time for today, look for the next scheduled time and set up an event for it
            # Start tomorrow. Be sure to wrap around if end of week (Sunday)
            day_index = (weekday + 1) % DayOfWeek.Sunday.value
            for day in range(DayOfWeek.Sunday.value - 1):
                if self.settings.start_time[day_index]:
                    self.schedule_sunrise_start(self.settings.start_time[weekday])
                    break
                day_index = (day_index + 1) % DayOfWeek.Sunday.value

        self.data.set_display_mode(display_mode)

    def start_schedule(self, starting_percentage: int = 0):
        self.is_running = True
        # Calculate the end time based upon current time and length
        self.start = dt.datetime.now()
        self.sec_per_step: int = int(self.data.sunrise_duration_minutes.seconds / self.dimmer.get_num_steps())
        start_level = self.dimmer.get_min_level()
        if starting_percentage > 0:
            start_level = int(self.dimmer.get_max_level() * starting_percentage)
        self.dimmer.set_level(start_level)
        self.check_schedule()

    def check_schedule(self):
        if (self.dimmer.get_level() < self.dimmer.get_max_level()) and not self.cancel:
            self.dimmer.increment_level()
            t = Timer(self.sec_per_step, self.check_schedule)
            t.start()
        self.is_running = False

    def set_schedule(self):
        pass

    def cancel_schedule(self):
        if self.sunrise_event_id:
            scheduler.cancel(self.sunrise_event_id)
        self.sunrise_event_id = None
        self.cancel = True
        self.dimmer.set_level(self.dimmer.get_min_level())

    def schedule_sunrise_start(self, start_time):
        # Create a new scheduler
        sunrise_scheduler = scheduler(time.time, time.sleep)

        # Schedule the backup to run at 1:00 AM every day
        start_time = time.strptime(start_time, '%H:%M:%S')
        self.sunrise_event_id = sunrise_scheduler.enterabs(time.mktime(start_time), 1, self.start_schedule, ())

        # Start the scheduler
        sunrise_scheduler.run()

    def set_display_on(self, mode):
        self.data.set_display_mode(mode)
        self.view.turn_display_on()

    def set_clock(self):
        pass

    def display_on(self) -> bool:
        if not self.data.is_display_on():
            if self.is_running:
                self.data.set_display_mode(DisplayMode.running)
            else:
                self.data.set_display_mode(DisplayMode.idle)

            return False

        return True

    def button1_press(self, channel):
        if not self.display_on():
            return


    def button2_press(self, channel):
        if not self.display_on():
            return

    def button3_press(self, channel):
        if not self.display_on():
            return

    def button4_press(self, channel):
        if not self.display_on():
            return

    def signal_handler(self, sig, frame):
        self.dimmer.shutdown()
        sys.exit(0)
