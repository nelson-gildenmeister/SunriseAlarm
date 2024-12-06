import datetime as dt
import signal
import sys
import time
from dataclasses import dataclass
from enum import Enum
from sched import scheduler, Event
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
                     'main_menu': ['Sel', '<', '>', 'Bck']}
    status_menus = {'main_menu'}
    status = {'idle_no_prog': ['No sunrise program set'],
              'idle_prog_set': ['Next sunrise starts in: %1'],
              'in_progress': ['Sunrise started %1 minutes ago...%2 minutes remaining'],
              'main_menu': ['Set Schedule', 'Set Clock']}


def calc_start_datetime(start_time: str, increment_from_today: int) -> dt.datetime:
    #start_time = "09:05"
    month = dt.datetime.now().month
    day = dt.datetime.now().day
    year = dt.datetime.now().year

    start = f'{month} {day} {year} {start_time}'
    wtm = time.strptime(start, '%m %d %Y %H:%M')
    print(f'wtm: {wtm}')

    epoch_start = time.mktime(wtm)
    dt_start = dt.datetime.fromtimestamp(epoch_start)

    dt_start= dt_start + dt.timedelta(days=increment_from_today)
    print(f'Next Day: {dt_start}')
    return dt_start


class SunriseController:
    sunrise_event: Event

    def __init__(self, view: OledDisplay, data: SunriseData, dimmer: Dimmer):
        self.sunrise_scheduler = None
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

        self.handle_schedule_change()

        while True:
            # TODO - Block waiting for an event that is set whenever schedule is changed
            pass

    def handle_schedule_change(self):
        # Default to idle
        display_mode = DisplayMode.idle

        # Either sunrise start is in the future or are in the middle of a sunrise.
        # First, get the day and time of the next scheduled sunrise.
        now = dt.datetime.now()
        weekday = now.weekday()
        if self.settings.start_time[weekday]:
            # TODO - put this line back in after done testing
            # start_time = dt.datetime.strptime(self.settings.start_time[weekday], '%H:%M')
            st = '10:00'
            start_time = dt.datetime.strptime(st, '%H:%M')
            if (start_time > now) and (start_time < (now + dt.timedelta(minutes=self.settings.minutes[weekday]))):
                # In the middle of sunrise, set to proper level
                display_mode = DisplayMode.running
                minutes_remaining = (now - dt.timedelta(minutes=self.settings.minutes[weekday])).minute
                #percent_brightness = int(minutes_remaining / self.settings.minutes[weekday])
                #self.start_schedule(minutes_remaining, percent_brightness)
                self.start_schedule(minutes_remaining, 50)
            elif start_time < now:
                # Sunrise start is today but in the future, set up an event to start
                # print(f'Scheduling start at: {self.settings.start_time[weekday]}')
                # dt_start = calc_start_datetime(self.settings.start_time[weekday], 0)
                print(f'Scheduling start at: {start_time.time()}')
                dt_start = calc_start_datetime(st, 0)
                self.schedule_sunrise_start(dt_start, self.settings.minutes[weekday])
                #print(f"Starting schedule. Duration: {self.settings.minutes[weekday]}")
                #self.start_schedule(self.settings.minutes[weekday], 0)
        else:
            # No scheduled time for today, look for the next scheduled time and set up an event for it
            # Start tomorrow. Be sure to wrap around if end of week (Sunday) and include today's day in
            # case it is the only scheduled time (i.e., next week on same day)
            day_index = (weekday + 1) % DayOfWeek.Sunday.value
            day_increment = 1
            for day in range(DayOfWeek.Sunday.value):
                if self.settings.start_time[day_index]:
                    print(f"Setting schedule. Start: {self.settings.start_time[weekday]}")
                    dt_start = calc_start_datetime(self.settings.start_time[weekday], day_increment)
                    self.schedule_sunrise_start(dt_start, self.settings.minutes[weekday])
                    break
                day_index = (day_index + 1) % DayOfWeek.Sunday.value
                day_increment = day_increment + 1

        self.data.set_display_mode(display_mode)

    def start_schedule(self, duration_minutes: int, starting_percentage: int = 0):
        self.is_running = True
        self.dimmer.enable()
        # Calculate the end time based upon current time and length
        self.start = dt.datetime.now()
        self.sec_per_step: int = int((duration_minutes * 60) / self.dimmer.get_num_steps())
        # Minimum is 1 second per step no matter what the duration
        if self.sec_per_step == 0:
            self.sec_per_step = 1
        start_level = self.dimmer.get_min_level()
        if starting_percentage > 0:
            start_level = int(self.dimmer.get_max_level() * (starting_percentage * 0.01))
        self.dimmer.set_level(start_level)
        self.check_schedule()

    def check_schedule(self):
        if (self.dimmer.get_level() < self.dimmer.get_max_level()) and not self.cancel:
            self.dimmer.increment_level()
            t = Timer(self.sec_per_step, self.check_schedule)
            t.start()
        else:
            # Either we are done or cancelled
            self.is_running = False
            self.cancel = False
            self.dimmer.turn_off()

    def set_schedule(self):
        pass

    def cancel_schedule(self):
        # If scheduled event is not yet running, cancel it
        if self.sunrise_scheduler.queue:
            try:
                scheduler.cancel(self.sunrise_event)
            except ValueError:
                # no event in the queue to cancel
                pass

        # If scheduled event is running, stop it
        if self.is_running:
            self.cancel = True
            self.dimmer.set_level(self.dimmer.get_min_level())

    def schedule_sunrise_start(self, start_time: dt.datetime, duration_minutes: int):
        # Create a new scheduler
        self.sunrise_scheduler = scheduler(time.time, time.sleep)

        # Schedule the start
        #epoch_start_time = time.mktime(time.strptime(start_time, '%H:%M'))
        epoch_start_time = start_time.timestamp()
        self.sunrise_event = self.sunrise_scheduler.enterabs(epoch_start_time, 1,
                                                             self.start_schedule, (duration_minutes,))

        # Start the scheduler
        self.sunrise_scheduler.run()

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

    def display_run(self):
        # Display event loop - run until display is off
        self.view.turn_display_on()
        while self.data.is_display_on():
            self.view.update_display("TODO")

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

    # def update_status(self):
    #     current = time.time()
    #     elapsed_minutes = int((current - start_time) / 60)
    #     remain_minutes = int(end_time - elapsed_minutes)
    #     if elapsed_minutes == 0:
    #         status_str = f"Sunrise just started...less than {end_time} minutes remaining"
    #     elif remain_minutes <= 0:
    #         status_str = "Waiting for next sunrise"
    #     else:
    #         status_str = f"Sunrise started {elapsed_minutes} minutes ago...{remain_minutes} minutes remaining"
