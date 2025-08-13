import calendar
import datetime as dt
import queue
import threading
import time
from abc import ABC, abstractmethod
from calendar import MONDAY, FRIDAY, SATURDAY, SUNDAY
from dataclasses import dataclass
from enum import Enum
from sched import scheduler, Event
from threading import Timer
from typing import List, Dict, Any, Self

import pigpio

from dimmer import Dimmer
from sunrise_data import SunriseData, SunriseSettings
from sunrise_view import OledDisplay

BRIGHTNESS_CHANGE_PERCENT: int = 5
DISPLAY_MSG_Q_SIZE: int = 12
SWITCH_DEBOUNCE_MICROSEC: int = 400
DEFAULT_BUTTON_LABEL = ' X     <     >    Prev'

btn1_gpio = 12
btn2_gpio = 16
btn3_gpio = 20
btn4_gpio = 21
button_map = {btn1_gpio: 1, btn2_gpio: 2, btn3_gpio: 3, btn4_gpio: 4}


class MenuName(Enum):
    top = "top"
    main = 'Main'
    schedule = 'Schedule'
    set_weekday = 'Weekday'
    set_weekend = 'Weekend'
    set_daily = 'Daily'
    day_of_week = "Day of Week"
    set_start = 'Start Time'
    set_duration = 'Duration'
    enable = 'Enable Schedule'
    display_timer = "Display Auto-Off"
    enable_sub = 'Weekday   Weekend   Daily'
    monday = 'Monday'
    tuesday = 'Tuesday'
    wednesday = 'Wednesday'
    thursday = 'Thursday'
    friday = 'Friday'
    saturday = 'Saturday'
    sunday = 'Sunday'
    set_date = 'Date/Time'
    network = 'Network Settings'


@dataclass
class DisplayState:
    status = {'idle_no_prog': ['No sunrise program set'],
              'idle_prog_set': ['Next sunrise starts in: %1'],
              'in_progress': ['Sunrise started %1 minutes ago...%2 minutes remaining'],
              'main_menu': ['Set Schedule', 'Set Clock']}


def calc_start_datetime(start_time: str, increment_from_today: int) -> dt.datetime:
    """ Settings for start are day of week and hour:minute. To figure out actual date/time of start, need to
        add in the number of days from today's date.  E.g., if it is Tuesday and next sunrise is next Tuesday, the
        increment will be 7 days.
    """
    month = dt.datetime.now().month
    day = dt.datetime.now().day
    year = dt.datetime.now().year

    start = f'{month} {day} {year} {start_time}'
    wtm = time.strptime(start, '%m %d %Y %H:%M')
    epoch_start = time.mktime(wtm)
    dt_start = dt.datetime.fromtimestamp(epoch_start)

    dt_start = dt_start + dt.timedelta(days=increment_from_today)
    return dt_start


class SchedulingThread(threading.Thread):
    def __init__(self, scheduler):
        threading.Thread.__init__(self)
        self.scheduler = scheduler

    def run(self):
        # This call will block until finished or cancelled
        self.scheduler.run()


class DisplayThread(threading.Thread):
    def __init__(self, view, data, event):
        threading.Thread.__init__(self)
        self._view = view
        self.data = data
        self.event = event
        self.line1 = ''
        self.line2 = ''
        self.line3 = ''
        self.line4 = ''
        self.scroll = True
        self.at_end = False
        self.msg_q = queue.Queue(DISPLAY_MSG_Q_SIZE)

    class DisplayThreadMessages(Enum):
        Wake = 1
        Update = 2

    wake = DisplayThreadMessages.Wake
    update = DisplayThreadMessages.Update

    def run(self):
        print("ENTER DisplayThread run()")
        # Display event loop - updates display while it is on
        self._view.turn_display_on()
        self._view.set_display_lines(self.line1, self.line2, self.line3, self.line4)
        self._view.update_display()
        self.at_end = False
        while True:
            while self._view.is_display_on():

                if self.event.is_set():
                    print('DisplayThread got event, exiting...')
                    return

                max_wait_time = 1
                if self.scroll:
                    if self.at_end:
                        incremental_wait_time = 2.0
                    else:
                        incremental_wait_time = 0.1
                    try:
                        msg = self.msg_q.get(True, incremental_wait_time)
                        if msg == self.update:
                            self._view.update_display()
                    except queue.Empty:
                        # Okay for no display changes
                        self.at_end = self._view.scroll_line3()
                        pass
                else:
                    # Delay display update unless someone gives us a new update
                    try:
                        msg = self.msg_q.get(True, max_wait_time)
                        if msg == self.update:
                            self._view.update_display()
                    except queue.Empty:
                        # Okay for no display changes
                        pass

                self._view.check_display_idle_off()

            # Wait for something to wake up the display
            msg = self.msg_q.get(True)
            if msg == self.wake:
                print('Waking Display...')
                self._view.turn_display_on()

    # Send a message to unblock the display thread and start display updates again.
    def turn_on_display(self):
        self.msg_q.put(self.wake, False)

    def update_display(self):
        self._view.set_display_lines(self.line1, self.line2, self.line3, self.line4)
        self._view.scroll = self.scroll
        self.msg_q.put(self.update, False)

    def update_line2_display(self, line2):
        self.line2 = line2
        self._view.set_line2(line2)
        self.msg_q.put(self.update, False)

    def update_line3_display(self, line3):
        self.line3 = line3
        self._view.set_line3(line3)
        self.msg_q.put(self.update, False)

    def update_line4_display(self, line4):
        self.line4 = line4
        self._view.set_line4(line4)
        self.msg_q.put(self.update, False)

    def update_status_line(self, status):
        self._view.set_status_display_line(status)
        self.msg_q.put(self.update, False)

    def enable_status(self):
        self._view.enable_status_display()

    def disable_status(self):
        self._view.disable_status_display()


class SunriseController:
    sunrise_event: Event | None

    def __init__(self, view: OledDisplay, data: SunriseData, dimmer: Dimmer):
        self.running_duration_minutes = None
        self.disp_thread = None
        global btn1_gpio, btn2_gpio, btn3_gpio, btn4_gpio
        threading.Thread.__init__(self)
        self.dimmer_step_size: int = 1
        self.pi = pigpio.pi()
        self.sunrise_scheduler = None
        self.time_increment_sched = None
        # All view control should be through the Display thread
        self._view = view
        self.data: SunriseData = data
        self.settings: SunriseSettings = data.settings
        self.dimmer: Dimmer = dimmer
        self.cancel: bool = False
        self.sec_per_step: int = 0
        self.is_running: bool = False
        self.running_start_time: dt.datetime = dt.datetime.now()
        self.running_duration_minutes: int = 0
        self.ctrl_event: threading.Event = threading.Event()
        self.current_menu: Menu = TopMenu(self)
        self.hookup_buttons(self.pi, [btn1_gpio, btn2_gpio, btn3_gpio, btn4_gpio])

    def hookup_buttons(self, pi, gpio_list: List[int]):
        for gpio in gpio_list:
            pi.set_pull_up_down(gpio, pigpio.PUD_UP)
            # Debounce the switches
            pi.set_glitch_filter(gpio, SWITCH_DEBOUNCE_MICROSEC)
            pi.callback(gpio, pigpio.FALLING_EDGE, self.button_press)

    def startup(self):
        # Start display thread
        self.disp_thread = DisplayThread(self._view, self.data, self.ctrl_event)
        self.disp_thread.start()
        print(f'current_menu_name: {self.current_menu.get_menu_name().value}')
        self.current_menu.update_display()

        print("Entering Event loop...")
        # This event loop does not have any events to process but could be added in the future.
        # Its primary purpose is to block so that a keyboard interrupt can be used to shut everything down.
        while True:
            self.handle_schedule_change()
            print("Event Loop: Waiting for event....")
            # Block and wait for an event that, right now, will never come
            self.ctrl_event.wait()
            print("GOT EVENT!!!!!!!!!!!!")
            self.ctrl_event.clear()

    def is_schedule_enabled(self) -> bool:
        if self.settings.weekday_sched_enabled or self.settings.weekend_sched_enabled or self.settings.daily_sched_enabled:
            return True

        return False

    def is_schedule_enabled_for_day(self, day: int) -> bool:
        # See if enabled for this day of the week
        if not self.settings.daily_sched_enabled:
            if not (self.settings.weekday_sched_enabled and day < SATURDAY):
                if not (self.settings.weekend_sched_enabled and day > FRIDAY):
                    # Not enabled for today
                    return False

        return True

    def handle_schedule_change(self):
        """ Called upon startup and whenever a change is made to the saved schedule. Sends an"""
        # Default to idle
        self.is_running = False
        now = dt.datetime.now()
        today = now.weekday()

        # Since a change might have affected a scheduled sunrise, go ahead and cancel.  It will get re-scheduled
        # below if no change was made.
        self.cancel_pending_schedule()

        # No need for any checks if not enabled for sunrise
        if not self.is_schedule_enabled():
            return

        if self.is_schedule_enabled_for_day(today):
            # There is a sunrise scheduled for today.
            # Handle 2 cases: 1) In the middle of a sunrise , 2) scheduled for later today.
            # No need to do anything if already missed today's schedule sunrise.
            dt_start = calc_start_datetime(self.settings.start_time[today], 0)

            # Sunrise resolution is 1 minute so don't include last minute duration in check to prevent race conditions.
            if dt_start < now < (dt_start + dt.timedelta(minutes=self.settings.duration_minutes[today] - 1)):
                # In the middle of sunrise, set to proper level
                print('In the middle of sunrise...')
                self.is_running = True
                self.running_start_time = now
                minutes_remaining = (now - dt.timedelta(minutes=self.settings.duration_minutes[today])).minute
                percent_brightness = int(minutes_remaining / self.settings.duration_minutes[today])
                self.start_schedule(minutes_remaining, percent_brightness)
                return
            elif dt_start > now:
                # Sunrise start is today but in the future - set up an event to start
                print(f'Scheduling start today at: {self.settings.start_time[today]}')
                self.schedule_sunrise_start(dt_start, self.settings.duration_minutes[today])
                t = dt.datetime.strptime(self.settings.start_time[today], "%H:%M")
                t2 = t.strftime("%I:%M %p")
                self.disp_thread.update_status_line(f'Next sunrise: today at {t2}')
                return

        # No sunrise scheduled for today so look for the next scheduled sunrise and set up an event for it.
        # Go through every day of the week starting tomorrow and wrap around to hit every day
        # of the week including the day of week that matches today to cover the case where next sunrise is next week
        # on the same day (E.g., It's Tuesday and next sunrise is 7 days from now on next Tuesday).
        have_scheduled_start = False
        day_index = (today + 1) % (SUNDAY + 1)
        day_increment = 1
        for day in range(SUNDAY):
            if self.is_schedule_enabled_for_day(day_index):
                have_scheduled_start = True
                dt_start = calc_start_datetime(self.settings.start_time[day_index], day_increment)
                print(
                    f'Scheduling future start: {dt_start}, duration: {self.settings.duration_minutes[day_index]} minutes')
                self.schedule_sunrise_start(dt_start, self.settings.duration_minutes[day_index])
                self.disp_thread.update_status_line(
                    f'Next sunrise: {calendar.day_name[dt_start.weekday()]} at {dt_start.hour:02d}:{dt_start.minute:02d}')
                break
            day_index = (day_index + 1) % (SUNDAY + 1)
            day_increment = day_increment + 1

        if not have_scheduled_start:
            self.disp_thread.update_status_line('Idle, no sunrise scheduled')

    def start_schedule(self, duration_minutes: int, starting_percentage: int = 0):
        """
        Called from an event thread or directly.
        :param duration_minutes:
        :param starting_percentage:
        :return:
        """
        print('Sunrise starting....')
        self.is_running = True
        self.sunrise_event = None
        self.dimmer.enable()
        # Calculate the end time based upon current time and duration setting.
        self.running_start_time = dt.datetime.now()
        self.running_duration_minutes = duration_minutes
        self.sec_per_step: int = int((duration_minutes * 60) / self.dimmer.get_num_steps())
        self.dimmer_step_size = 1

        # If duration is too short for number of steps, calculate step size and set minimum seconds per step.
        if self.sec_per_step == 0:
            self.sec_per_step = 1
            self.dimmer_step_size = int(self.dimmer.get_num_steps() / (duration_minutes * 60))

        start_level = self.dimmer.get_min_level()
        if starting_percentage > 0:
            start_level = int(self.dimmer.get_max_level() * (starting_percentage * 0.01))
        self.dimmer.set_level(start_level)
        # Turn on the display
        self.display_on()
        self.check_schedule()

    def check_schedule(self):
        if self.dimmer.increment_level(self.dimmer_step_size) and not self.cancel:
            minutes_remain = 60 / (
                    self.sec_per_step * ((self.dimmer.get_max_level() - self.dimmer.get_level())/self.dimmer_step_size))
            self.disp_thread.update_status_line(f'Sunrise in progress, {minutes_remain} minutes remaining')
            self.time_increment_sched = Timer(self.sec_per_step, self.check_schedule)
            self.time_increment_sched.start()
        else:
            # Either we are done or were cancelled
            print("Sunrise complete")
            self.disp_thread.update_status_line('Sunrise complete')
            self.is_running = False
            self.cancel = False
            # TODO - Do we turn off lamp at end or leave on?  Perhaps this is a setting?
            self.dimmer.turn_off()
            #self.ctrl_event.set()
            # Queue up the next sunrise event
            self.handle_schedule_change()

    def cancel_pending_schedule(self):
        # If queue already created and a scheduled event is queued up to run, cancel it
        if self.sunrise_scheduler and self.sunrise_scheduler.queue:
            try:
                if self.sunrise_event:
                    self.sunrise_scheduler.cancel(self.sunrise_event)
                    #scheduler.cancel(self.sunrise_event)
                    self.sunrise_event = None
            except ValueError:
                # no event in the queue to cancel
                pass

    def cancel_running_schedule(self):
        # If scheduled event is running, stop it
        try:
            self.time_increment_sched.cancel()
        except:
            pass

        if self.is_running:
            self.cancel = True
            # No need to clear out the event we track since it is cleared when start running
            self.dimmer.set_level(self.dimmer.get_min_level())
            self.update_status()

    def schedule_sunrise_start(self, start_time: dt.datetime, duration_minutes: int):
        # Create a new scheduler
        self.sunrise_scheduler = scheduler(time.time, time.sleep)

        # Schedule the start
        epoch_start_time = start_time.timestamp()
        print('Creating new sunrise event')
        self.sunrise_event = self.sunrise_scheduler.enterabs(epoch_start_time, 1,
                                                             self.start_schedule, (duration_minutes,))

        # Start the scheduler in its own thread so we don't block here
        st = SchedulingThread(self.sunrise_scheduler)
        st.start()

    def set_clock(self):
        pass

    def display_on(self):
        self.disp_thread.turn_on_display()

    def button_press(self, gpio, level, tick):
        global button_map
        btn = button_map[gpio]
        print(f'Button {btn} pressed...')
        # If display is not on, any button press will turn on the display and go back to the top menu
        if not self._view.is_display_on():
            self.display_on()
            if self.current_menu.get_menu_name() != MenuName.top:
                self.current_menu = TopMenu(self)
                self.current_menu.update_display()
            return

        # Call the handler for the current menu
        new_menu = self.current_menu.button_handler(btn)
        # if button action changed the menu, update the display with new menu
        print(f'current_menu name = {self.current_menu.get_menu_name().value}')
        print(f'new_menu_name = {new_menu.get_menu_name().value}')

        # If the menu changed, record it as the current and update the display to reflect the new menu
        if new_menu.get_menu_name() != self.current_menu.get_menu_name():
            self.current_menu = new_menu
            self.current_menu.update_display()

    def shutdown(self):
        self.dimmer.shutdown()

    def update_status(self):
        status_str = "No sunrise scheduled"
        if self.is_running:
            now = dt.datetime.now()
            elapsed_minutes = (now - self.running_start_time).total_seconds() / 60
            remain_minutes = self.running_duration_minutes - elapsed_minutes
            if elapsed_minutes == 0:
                status_str = f"Sunrise just started...less than {remain_minutes} minutes remaining"
            else:
                status_str = f"Sunrise started {elapsed_minutes} minutes ago...{remain_minutes} minutes remaining"
        else:
            # idle - see if there is a sunrise scheduled
            if self.sunrise_event:
                pass


class Menu(ABC):
    def __init__(self, controller: SunriseController, menu_name: MenuName, previous_menu: Self = None):
        self.controller = controller
        self.menu_name = menu_name
        self.previous_menu: Self = previous_menu

    def get_menu_name(self) -> MenuName:
        return self.menu_name

    def start_duration_menu_factory(self, menu_type, day = MONDAY) -> Self:
        match menu_type:
            case MenuName.set_start:
                return ScheduleSunriseStart(self.controller, self, day)
            case MenuName.set_duration:
                return ScheduleSunriseDuration(self.controller, self, day)

        print(f'ERROR: {self.__class__.__name__} Unhandled menu type={menu_type}, returning to top menu')
        return TopMenu(self.controller)

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def update_display(self):
        pass

    @abstractmethod
    def button_handler(self, btn: int) -> Self:
        pass


def get_hierarchical_menu_string(current_menu: Menu, current_menu_name: str = None) -> str | None:
    """
    Returns back a string representing the current menu and its hierarchy. If current_menu_name is provided, it
    will be used instead of pulling the name from the current_menu subclass.
    E.g., Schedule->Weekday
    :param current_menu: The current Menu subclass.
    :param current_menu_name: If provided, use this name for the current menu
    :return: string with hierarchy up to and including the current menu.
    """

    # Don't put in anything for the main menu
    if current_menu.get_menu_name() == MenuName.main:
        return None

    # Recurse back to root item to get all the previous menus except Top and Main
    # If a current_menu_name is provided, use it instead of the name from the menu class
    if current_menu_name:
        menu_string = current_menu_name
    else:
        menu_string = current_menu.get_menu_name().value
    menu = current_menu.previous_menu
    while menu and (menu.menu_name != MenuName.top) and (menu.menu_name != MenuName.main):
        menu_string = menu.get_menu_name().value + '->' + menu_string
        menu = menu.previous_menu
    return menu_string


class TopMenu(Menu):
    def __init__(self, controller):
        super().__init__(controller, MenuName.top)
        self.menu_line3 = ''
        self.menu_line4 = ''

        self.reset()

    def reset(self):
        self.menu_line4 = ''
        if self.controller.dimmer.get_level():
            self.menu_line4 = 'Menu  Dim-  Dim+  Off'
        else:
            self.menu_line4 = 'Menu  Dim-  Dim+  On'

    def update_display(self):
        print('TopMenu:update_display()')
        self.controller.disp_thread.line2 = None
        self.controller.disp_thread.line4 = self.menu_line4
        self.controller.disp_thread.enable_status()
        self.controller.disp_thread.scroll = True
        self.controller.disp_thread.update_display()

    def button_handler(self, btn: int) -> Menu:
        if btn == 1:
            self.controller.disp_thread.disable_status()
            return MainMenu(self.controller, self)

        # Other buttons cancel a running schedule
        if self.controller.is_running:
            self.controller.cancel_running_schedule()

        dimmer_prev_on: bool = self.controller.dimmer.is_on()

        # Handle other button actions
        match btn:
            case 2:
                self.controller.dimmer.decrease_brightness_by_percent(BRIGHTNESS_CHANGE_PERCENT)
                dimmer_curr_on = self.controller.dimmer.is_on()
                # Update display if dimmer now off
                if dimmer_prev_on and not dimmer_curr_on:
                    self.controller.disp_thread.update_line4_display('Menu  Dim-  Dim+  On')
            case 3:
                self.controller.dimmer.increase_brightness_by_percent(BRIGHTNESS_CHANGE_PERCENT)
                # Update display if it was off previously
                if not dimmer_prev_on:
                    self.controller.disp_thread.update_line4_display('Menu  Dim-  Dim+  Off')
            case 4:
                line4 = 'Menu  Dim-  Dim+  On'
                if self.controller.dimmer.get_level():
                    print('Lamp OFF')
                    self.controller.dimmer.turn_off()
                else:
                    print('Lamp ON')
                    line4 = 'Menu  Dim-  Dim+  Off'
                    self.controller.dimmer.turn_on()
                self.controller.disp_thread.update_line4_display(line4)
            case _:
                print("Invalid button number")

        return self


class MainSubMenus(Enum):
    program = 0
    enable = 1
    display = 2
    set_date = 3
    network = 4


class MainMenu(Menu):
    def __init__(self, controller, prev_menu):
        super().__init__(controller, MenuName.main, prev_menu)

        self.menu_idx: int = 0
        self.menus = [MenuName.schedule, MenuName.enable, MenuName.display_timer,
                      MenuName.set_date, MenuName.network]
        self.menu_line4 = DEFAULT_BUTTON_LABEL

    def reset(self) -> Dict[Any, Any]:
        pass

    def update_display(self):
        print('MainMenu:update_display()')
        self.controller.disp_thread.line2 = get_hierarchical_menu_string(self)
        self.controller.disp_thread.line3 = self.menus[self.menu_idx].value
        self.controller.disp_thread.line4 = self.menu_line4
        self.controller.disp_thread.update_display()

    def button_handler(self, btn: int) -> Menu:
        match btn:
            case 1:
                # Select button pressed, go to new menu
                return self.new_menu_factory(self.menus[self.menu_idx])
            case 2:
                # Left arrow
                self.menu_idx = (self.menu_idx - 1) % len(self.menus)
                self.controller.disp_thread.update_line3_display(self.menus[self.menu_idx].value)
            case 3:
                # Right arrow
                self.menu_idx = (self.menu_idx + 1) % len(self.menus)
                self.controller.disp_thread.update_line3_display(self.menus[self.menu_idx].value)
                pass
            case 4:
                # Previous
                return self.previous_menu

        return self

    def new_menu_factory(self, menu_type) -> Menu:
        match menu_type:
            case MenuName.schedule:
                return ScheduleMenu(self.controller, self)
            case MenuName.enable:
                return EnableMenu(self.controller, self)
            case MenuName.display_timer:
                return SetDisplayOffTimeMenu(self.controller, self)
            case MenuName.set_date:
                return SetDateMenu(self.controller, self)
            case MainSubMenus.network:
                return NetworkMenu(self.controller, self)

        print('ERROR: MainMenu Unhandled menu type, returning to top menu')
        return TopMenu(self.controller)


class ScheduleTopMenu(Enum):
    invalid = -1
    weekday = 0
    weekend = 1
    daily = 2


class DailyMenu(Enum):
    invalid = -1
    sunday = 0
    monday = 1
    tuesday = 2
    wednesday = 3
    thursday = 4
    friday = 5
    saturday = 6


class TimeMenuState(Enum):
    invalid = -1
    start = 0
    duration = 1


class ScheduleMenu(Menu):
    def __init__(self, controller, prev_menu):
        super().__init__(controller, MenuName.schedule, prev_menu)
        self.menu_idx = 0
        self.menus = [MenuName.set_weekday, MenuName.set_weekend, MenuName.set_daily]
        self.menu_line4 = DEFAULT_BUTTON_LABEL

        self.set_start_time = False
        self.start_time: dt = dt.datetime.now()
        self.set_duration = False
        self.duration: dt.timedelta = dt.timedelta(0)

    def reset(self):
        pass

    def update_display(self):
        self.controller.disp_thread.line2 = get_hierarchical_menu_string(self)
        self.controller.disp_thread.line3 = self.menus[self.menu_idx].value
        self.controller.disp_thread.line4 = self.menu_line4
        self.controller.disp_thread.update_display()

    def button_handler(self, btn: int) -> Menu:
        match btn:
            case 1:
                # Select button pressed, go to new menu
                return self.new_menu_factory(self.menus[self.menu_idx])
            case 2:
                # Left
                self.menu_idx = (self.menu_idx - 1) % len(self.menus)
                self.controller.disp_thread.update_line3_display(self.menus[self.menu_idx].value)
            case 3:
                # Right
                self.menu_idx = (self.menu_idx + 1) % len(self.menus)
                self.controller.disp_thread.update_line3_display(self.menus[self.menu_idx].value)
            case 4:
                # Prev
                return self.previous_menu
        return self

    def new_menu_factory(self, menu_type) -> Menu:
        match menu_type:
            case MenuName.set_weekday:
                return ScheduleWeekdayMenu(self.controller, self)
            case MenuName.set_weekend:
                return ScheduleWeekendMenu(self.controller, self)
            case MenuName.set_daily:
                return ScheduleDailyMenu(self.controller, self)

        print('ERROR: ScheduleMenu Unhandled menu type, returning to top menu')
        return TopMenu(self.controller)


class ScheduleWeekdayMenu(Menu):
    def __init__(self, controller, prev_menu):
        super().__init__(controller, MenuName.set_weekday, prev_menu)
        self.menu_idx = 0
        self.menus = [MenuName.set_start, MenuName.set_duration]
        self.menu_line4 = DEFAULT_BUTTON_LABEL

    def reset(self):
        pass

    def update_display(self):
        self.controller.disp_thread.line2 = get_hierarchical_menu_string(self)
        self.controller.disp_thread.line3 = self.menus[self.menu_idx].value
        self.controller.disp_thread.line4 = self.menu_line4
        self.controller.disp_thread.update_display()

    def button_handler(self, btn: int) -> Menu:
        match btn:
            case 1:
                # Select button pressed, go to new menu
                return self.start_duration_menu_factory(self.menus[self.menu_idx])
            case 2:
                # Left
                self.menu_idx = (self.menu_idx - 1) % len(self.menus)
                self.controller.disp_thread.update_line3_display(self.menus[self.menu_idx].value)
            case 3:
                # Right
                self.menu_idx = (self.menu_idx + 1) % len(self.menus)
                self.controller.disp_thread.update_line3_display(self.menus[self.menu_idx].value)
            case 4:
                # Prev
                return self.previous_menu

        return self


class ScheduleWeekendMenu(Menu):
    def __init__(self, controller, prev_menu):
        super().__init__(controller, MenuName.set_weekend, prev_menu)
        self.menu_idx = 0
        self.menus = [MenuName.set_start, MenuName.set_duration]
        self.menu_line4 = DEFAULT_BUTTON_LABEL

    def reset(self):
        pass

    def update_display(self):
        self.controller.disp_thread.line2 = get_hierarchical_menu_string(self)
        self.controller.disp_thread.line3 = self.menus[self.menu_idx].value
        self.controller.disp_thread.line4 = self.menu_line4
        self.controller.disp_thread.update_display()

    def button_handler(self, btn: int) -> Menu:
        match btn:
            case 1:
                # Select button pressed, go to new menu
                return self.start_duration_menu_factory(self.menus[self.menu_idx])
            case 2:
                # Left
                self.menu_idx = (self.menu_idx - 1) % len(self.menus)
                self.controller.disp_thread.update_line3_display(self.menus[self.menu_idx].value)
            case 3:
                # Right
                self.menu_idx = (self.menu_idx + 1) % len(self.menus)
                self.controller.disp_thread.update_line3_display(self.menus[self.menu_idx].value)
            case 4:
                # Prev
                return self.previous_menu

        return self


class ScheduleDailyMenu(Menu):
    def __init__(self, controller, prev_menu):
        super().__init__(controller, MenuName.set_daily, prev_menu)
        self.menu_idx = 0
        self.menus = [MenuName.monday, MenuName.tuesday, MenuName.wednesday, MenuName.thursday, MenuName.friday,
                      MenuName.saturday, MenuName.sunday]
        self.menu_line4 = DEFAULT_BUTTON_LABEL

    def get_day_of_week(self) -> int:
        return self.menu_idx

    def reset(self):
        pass

    def update_display(self):
        print('ScheduleDailyMenu:update_display()')
        self.controller.disp_thread.line2 = get_hierarchical_menu_string(self)
        # self.controller.disp_thread.line3 = self.menus[self.menu_idx].value
        self.controller.disp_thread.line3 = calendar.day_name[self.menu_idx]
        self.controller.disp_thread.line4 = self.menu_line4
        self.controller.disp_thread.update_display()

    def button_handler(self, btn: int) -> Menu:
        match btn:
            case 1:
                # Select button pressed, go to new menu
                return DayOfWeek(self.controller, self, self.menu_idx)
            case 2:
                # Left
                self.menu_idx = (self.menu_idx - 1) % len(calendar.day_name)
                self.controller.disp_thread.update_line3_display(calendar.day_name[self.menu_idx])
            case 3:
                # Right
                self.menu_idx = (self.menu_idx + 1) % len(calendar.day_name)
                self.controller.disp_thread.update_line3_display(calendar.day_name[self.menu_idx])
            case 4:
                # Prev
                return self.previous_menu

        return self

class DayOfWeek(Menu):
    def __init__(self, controller, prev_menu, day):
        super().__init__(controller, MenuName.day_of_week, prev_menu)
        self.day = day
        self.menu_idx = 0
        self.menus = [MenuName.set_start, MenuName.set_duration]
        self.menu_line4 = DEFAULT_BUTTON_LABEL

    def reset(self):
        pass

    def update_display(self):
        print('DayOfWeek:update_display()')
        self.controller.disp_thread.line2 = get_hierarchical_menu_string(self, calendar.day_abbr[self.day])
        self.controller.disp_thread.line3 = self.menus[self.menu_idx].value
        self.controller.disp_thread.line4 = self.menu_line4
        self.controller.disp_thread.update_display()

    def button_handler(self, btn: int) -> Self:
        match btn:
            case 1:
                # Select button pressed, go to new menu
                return self.start_duration_menu_factory(self.menus[self.menu_idx], self.day)
            case 2:
                # Left
                self.menu_idx = (self.menu_idx - 1) % len(self.menus)
                self.controller.disp_thread.update_line3_display(self.menus[self.menu_idx].value)
            case 3:
                # Right
                self.menu_idx = (self.menu_idx + 1) % len(self.menus)
                self.controller.disp_thread.update_line3_display(self.menus[self.menu_idx].value)
            case 4:
                # Prev
                return self.previous_menu

        return self


def create_12hour_clock_display(hour: int, minute: int, is_pm: bool, field_idx: int) -> str:
    am_pm: str = 'AM'
    if is_pm:
        am_pm: str = "PM"

    match field_idx:
        case 0:
            return f'    [{hour:02d}]:{minute:02d} {am_pm}'
        case 1:
            return f'     {hour:02d}:[{minute:02d}] {am_pm}'
        case 2:
            return f'     {hour:02d}:{minute:02d} [{am_pm}]'

    print(f'Error - select_new_clock_field() invalid field index = {field_idx}')
    return f'ERROR:Bad field index'


class ScheduleSunriseStart(Menu):
    def __init__(self, controller, prev_menu, day_of_week: int):
        super().__init__(controller, MenuName.set_start, prev_menu)
        self.day_of_week: int = day_of_week
        # The clock field index indicates which clock field is being set
        self.clock_field_idx = 0
        self.num_clock_fields = 3
        self.is_pm: bool = False
        self.hour = 12
        self.minute = 0
        self.menu_line4 = 'Select  Up  Dn  Save'
        self.load_previous_clock()

    def load_previous_clock(self):
        """
        Loads the previous clock setting and updates the display with its value
        :return: None
        """
        print(f'Saved start time: {self.controller.settings.start_time[self.day_of_week]}')
        start_time_str = self.controller.settings.start_time[self.day_of_week]
        start_time = dt.datetime.strptime(start_time_str, '%H:%M')
        if start_time.hour > 12:
            self.is_pm = True
            self.hour = start_time.hour - 12
        else:
            self.hour = start_time.hour
        self.minute = start_time.minute
        self.update_display()

    def reset(self):
        pass

    def update_display(self):
        self.controller.disp_thread.line3 = (
            create_12hour_clock_display(self.hour, self.minute, self.is_pm, self.clock_field_idx))
        self.controller.disp_thread.line4 = self.menu_line4
        self.controller.disp_thread.update_display()

    def save_schedule(self):
        mil_hour = self.hour
        if self.is_pm:
            mil_hour = self.hour + 12
        parent_menu = self.previous_menu.get_menu_name()
        match parent_menu:
            case MenuName.set_weekday:
                print('Saving new Weekday start time')
                for day in range(MONDAY, FRIDAY + 1):
                    self.controller.data.settings.start_time[day] = f'{mil_hour:02d}:{self.minute:02d}'
               # self.controller.data.settings.start_time[MONDAY] = f'{mil_hour:02d}:{self.minute:02d}'
            case MenuName.set_weekend:
                print('Saving new Weekend start time')
                for day in range(SATURDAY, SUNDAY + 1):
                    self.controller.data.settings.start_time[day] = f'{mil_hour:02d}:{self.minute:02d}'
            case MenuName.day_of_week:
                print(f'Saving new Daily start time for {calendar.day_name[self.day_of_week]}')
                self.controller.data.settings.start_time[self.day_of_week] = f'{mil_hour:02d}:{self.minute:02d}'
            case _:
                print(f'ERROR: ScheduleSunriseStart:save_schedule() - invalid parent menu: {parent_menu}')

        self.controller.data.save_settings()
        self.controller.handle_schedule_change()

    def button_handler(self, btn: int) -> Menu:
        match btn:
            case 1:
                # Select - Move to next clock field
                self.clock_field_idx = (self.clock_field_idx + 1) % self.num_clock_fields
                self.update_display()
            case 2 | 3:
                # Up/Down
                increment = 1
                if btn == 3:
                    increment = -1

                match self.clock_field_idx:
                    case 0:
                        self.hour = (self.hour + increment) % 13
                        if self.hour == 0:
                            if increment > 0:
                                self.hour = 1
                            else:
                                self.hour = 12
                    case 1:
                        self.minute = (self.minute + increment) % 60
                    case 2:
                        self.is_pm = not self.is_pm
                self.update_display()
            case 4:
                # Save
                self.save_schedule()
                # Go back 2 menus to get to the schedule menu
                return self.previous_menu.previous_menu

        return self


class ScheduleSunriseDuration(Menu):
    def __init__(self, controller, prev_menu, day_of_week: int):
        super().__init__(controller, MenuName.set_duration, prev_menu)
        self.day_of_week: int = day_of_week

    def reset(self):
        pass

    def update_display(self):
        pass

    def button_handler(self, btn: int) -> Menu:
        match btn:
            case 1:
                # Select
                pass
            case 2:
                # Left
                pass
            case 3:
                # Right
                pass
            case 4:
                # Prev
                return self.previous_menu

        return self


class EnableMenu(Menu):
    def __init__(self, controller, prev_menu):
        super().__init__(controller, MenuName.enable, prev_menu)
        self.menu_line4 = 'Enable  Enable  Enable  Prev'

    def reset(self):
        pass

    def update_display(self):
        self.controller.disp_thread.line3 = 'Weekday  Weekend  Daily  Prev'
        self.controller.disp_thread.line4 = self.menu_line4
        self.controller.disp_thread.update_display()

    def button_handler(self, btn: int) -> Menu:
        match btn:
            case 1:
                # Select
                pass
            case 2:
                # Left
                pass
            case 3:
                # Right
                pass
            case 4:
                # Prev
                return self.previous_menu

        return self


class TimeMenu(Menu):
    def reset(self):
        pass

    def update_display(self):
        pass

    def button_handler(self, btn: int) -> Menu:
        match btn:
            case 1:
                # Select
                pass
            case 2:
                # Left
                pass
            case 3:
                # Right
                pass
            case 4:
                # Prev
                return self.previous_menu

        return self

    def __init__(self, controller: SunriseController, menu_state_name: MenuName, prev_menu):
        super().__init__(controller, menu_state_name, prev_menu)
        self.time_disp_list = ['Start', 'Duration']
        self.day = None

    def set_day(self, day) -> Self:
        self.day = day
        return self


class SetDisplayOffTimeMenu(Menu):
    def __init__(self, controller, prev_menu):
        super().__init__(controller, MenuName.display_timer, prev_menu)
        self.menu_line3 = ''
        self.menu_line4 = ''
        self.current_sub_menu = ''

    def reset(self):
        pass

    def update_display(self):
        self.controller.disp_thread.line3(self.menu_line3)
        self.controller.disp_thread.line4(self.menu_line4)
        self.controller.disp_thread.update_display()

    def button_handler(self, btn: int) -> Menu:
        match btn:
            case 1:
                # Select
                pass
            case 2:
                # Left
                pass
            case 3:
                # Right
                pass
            case 4:
                # Prev
                return self.previous_menu

        return self


class SetDateMenu(Menu):
    def __init__(self, controller, prev_menu):
        super().__init__(controller, MenuName.set_date, prev_menu)
        self.menu_line3 = ''
        self.menu_line4 = ''
        self.current_sub_menu = ''

    def reset(self):
        self.current_sub_menu = ''

    def update_display(self):
        self.controller.disp_thread.line3(self.menu_line3)
        self.controller.disp_thread.line4(self.menu_line4)
        self.controller.disp_thread.update_display()

    def button_handler(self, btn: int) -> Menu:
        match btn:
            case 1:
                # Select
                pass
            case 2:
                # Left
                pass
            case 3:
                # Right
                pass
            case 4:
                # Prev
                return self.previous_menu

        return self


class NetworkMenu(Menu):
    def __init__(self, controller, prev_menu):
        super().__init__(controller, MenuName.network, prev_menu)
        self.menu_line3 = ''
        self.menu_line4 = ''
        self.current_sub_menu = ''

    def reset(self):
        self.current_sub_menu = ''

    def update_display(self):
        self.controller.disp_thread.line3(self.menu_line3)
        self.controller.disp_thread.line4(self.menu_line4)
        self.controller.disp_thread.update_display()

    def button_handler(self, btn: int) -> Menu:
        match btn:
            case 1:
                # Select
                pass
            case 2:
                # Left
                pass
            case 3:
                # Right
                pass
            case 4:
                # Prev
                return self.previous_menu

        return self
