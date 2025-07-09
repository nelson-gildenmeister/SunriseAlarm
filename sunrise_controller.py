import datetime as dt
import queue
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from sched import scheduler, Event
from threading import Timer
from typing import List, Dict, Any

import pigpio

from dimmer import Dimmer
from sunrise_data import SunriseData, SunriseSettings, DisplayMode
from sunrise_view import OledDisplay

BRIGHTNESS_CHANGE_PERCENT: int = 5

btn1_gpio = 12
btn2_gpio = 16
btn3_gpio = 20
btn4_gpio = 21
button_map = {btn1_gpio: 1, btn2_gpio: 2, btn3_gpio: 3, btn4_gpio: 4}


class DayOfWeek(Enum):
    Monday = 0
    Tuesday = 1
    Wednesday = 2
    Thursday = 3
    Friday = 4
    Saturday = 5
    Sunday = 6

class MenuStateName(Enum):
    top = "top"
    main = "main"
    set_program = "set_program"
    set_weekday = "set_weekday"
    set_weekend = "set_weekend"
    set_daily = "set_daily"
    set_start = "set_start"
    set_duration = "set_duration"
    enable = "enable"
    display_timer = "display_timer"
    set_date = "set_date"
    network = "network"

class MenuNames(Enum):
    main = 'Main'
    schedule = 'Schedule'
    set_weekday = 'Weekday'
    set_weekend = 'Weekend'
    set_daily = 'Daily'
    set_start = 'Start Time'
    set_duration = 'Duration'
    enable = 'Enable Schedules'
    enable_sub = 'Weekday   Weekend   Daily'
    sunday = 'Sunday'
    monday = 'Monday'
    tuesday = 'Tuesday'
    wednesday = 'Wednesday'
    thursday = 'Thursday'
    friday = 'Friday'
    saturday = 'Saturday'
    time_set = ''
    set_date = 'Date/Time'
    network = 'Network'

@dataclass
class DisplayState:
    status = {'idle_no_prog': ['No sunrise program set'],
              'idle_prog_set': ['Next sunrise starts in: %1'],
              'in_progress': ['Sunrise started %1 minutes ago...%2 minutes remaining'],
              'main_menu': ['Set Schedule', 'Set Clock']}


def calc_start_datetime(start_time: str, increment_from_today: int) -> dt.datetime:
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
        self.view = view
        self.data = data
        self.event = event
        self.line1 = ''
        self.line2 = ''
        self.line3 = ''
        self.line4 = ''
        self.scroll = True
        self.at_end = False
        self.msg_q = queue.Queue(2)

    class DisplayThreadMessages(Enum):
        Wake = 1
        Update = 2

    wake = DisplayThreadMessages.Wake
    update = DisplayThreadMessages.Update

    def run(self):
        print("ENTER DisplayThread run()")
        # Display event loop - updates display while it is on
        self.view.turn_display_on()
        self.view.set_display_lines(self.line1, self.line2, self.line3, self.line4)
        self.view.update_display()
        self.at_end = False
        while True:
            while self.data.is_display_on():
                #self.view.update_display(self.line1, self.line2, self.line3, self.line4, self.scroll)

                if self.event.is_set():
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
                            self.view.update_display()
                    except queue.Empty:
                        # Okay for no display changes
                        self.at_end = self.view.scroll_line3()
                        pass
                else:
                    # Delay display update unless someone gives us a new update
                    try:
                        msg = self.msg_q.get(True, max_wait_time)
                        if msg == self.update:
                            self.view.update_display()
                    except queue.Empty:
                        # Okay for no display changes
                        pass

            # Wait for something to wake up the display
            msg = self.msg_q.get(True)

    # Send a message to unblock the display thread and start display updates again.
    def turn_on_display(self):
        self.msg_q.put(self.wake, False)

    def update_display(self, line1, line2, line3, line4, scroll=True):
        print("Enter update_display()")
        self.line1 = line1
        self.line2 = line2
        self.line3 = line3
        self.line4 = line4
        self.scroll = scroll
        self.view.set_display_lines(line1, line2, line3, line4)
        self.msg_q.put(self.update, False)

    def update_line3_display(self, line3):
        self.line3 = line3
        self.view.set_line3(line3)
        self.msg_q.put(self.update, False)

    def update_line4_display(self, line4):
        self.line4 = line4
        self.view.set_line4(line4)
        self.msg_q.put(self.update, False)


class SunriseController:
    sunrise_event: Event

    def __init__(self, view: OledDisplay, data: SunriseData, dimmer: Dimmer):
        self.disp_thread = None
        global btn1_gpio, btn2_gpio, btn3_gpio, btn4_gpio
        threading.Thread.__init__(self)
        self.dimmer_step_size: int = 1
        self.pi = pigpio.pi()
        self.sunrise_scheduler = None
        self.time_increment_sched = None
        self.view = view
        self.data: SunriseData = data
        self.settings: SunriseSettings = data.settings
        self.dimmer: Dimmer = dimmer
        self.start: dt.datetime = dt.datetime.now()
        self.cancel: bool = False
        self.sec_per_step: int = 0
        self.is_running: bool = False
        self.ctrl_event: threading.Event = threading.Event()
        self.current_menu_name: MenuStateName = MenuStateName.top
        self.menus = self.initialize_menus()
        self.hookup_buttons(self.pi, [btn1_gpio, btn2_gpio, btn3_gpio, btn4_gpio])

    def initialize_menus(self) -> Dict[Any, Any]:
        # First create the menu objects
        main_menu = Menu([MenuNames.schedule, MenuNames.enable, MenuNames.set_date, MenuNames.network])
        schedule_menu = Menu([MenuNames.set_weekday, MenuNames.set_weekend, MenuNames.set_daily])
        enable_menu = Menu()
        date_time_menu = Menu()
        network_menu = Menu()
        weekday_menu = Menu()
        weekend_menu = Menu()
        daily_menu = Menu()
        start_time_menu = TimeMenu()
        set_time_menu = TimeMenu()
        duration_menu = TimeMenu()
        set_duration_minutes_menu = TimeMenu()
        enable_sub_menu = Menu([MenuNames.enable_sub])

        # Fill in the data members of the menu objects
        schedule_menu.set_prev_menu(main_menu)

        weekday_menu.set_prev_menu(schedule_menu)
        weekend_menu.set_prev_menu(schedule_menu)
        daily_menu.set_prev_menu(schedule_menu)

        enable_sub_menu.set_line4('Disabled Disabled Disabled Prev')


        main_menu.set_next_menu()
        return {MenuStateName.top: TopMenu(self), MenuStateName.main: MainMenu(self),
                MenuStateName.set_program: ScheduleMenu(self), MenuStateName.enable: EnableMenu,
                MenuStateName.display_timer: SetDisplayOffTimeMenu(self), MenuStateName.set_date: SetDateMenu(self),
                MenuStateName.network: NetworkMenu}

    def hookup_buttons(self, pi, gpio_list: List[int]):
        for gpio in gpio_list:
            pi.set_pull_up_down(gpio, pigpio.PUD_UP)
            # Debounce the switches
            pi.set_glitch_filter(gpio, 300)
            pi.callback(gpio, pigpio.FALLING_EDGE, self.button_press)

    def startup(self):
        # Start display thread
        self.disp_thread = DisplayThread(self.view, self.data, self.ctrl_event)
        self.disp_thread.start()
        current_menu = self.menus[self.current_menu_name]
        print(f'current_menu_name: {self.current_menu_name},  current_menu: {current_menu}')
        current_menu.update_display()

        print("Entering Event loop...")

        while True:
            self.handle_schedule_change()
            print("Event Loop: Waiting for event....")
            # Block waiting for an event that is set whenever a sunrise completes or schedule is changed.
            self.ctrl_event.wait()
            print("GOT EVENT!!!!!!!!!!!!")
            self.ctrl_event.clear()

    def handle_schedule_change(self):
        # Default to idle
        self.data.set_display_mode(DisplayMode.idle)
        now = dt.datetime.now()
        weekday = now.weekday()

        if self.settings.start_time[weekday]:
            # There is a sunrise scheduled for today.
            # Handle 2 cases: 1) In the middle of a sunrise , 2) scheduled for later today.
            # No need to do anything if already missed today's schedule sunrise.
            dt_start = calc_start_datetime(self.settings.start_time[weekday], 0)

            # Sunrise resolution is 1 minute so don't include last minute duration in check to prevent race conditions.
            if dt_start < now < (dt_start + dt.timedelta(minutes=self.settings.minutes[weekday] - 1)):
                # In the middle of sunrise, set to proper level
                print('In the middle of sunrise...')
                display_mode = DisplayMode.running
                minutes_remaining = (now - dt.timedelta(minutes=self.settings.minutes[weekday])).minute
                percent_brightness = int(minutes_remaining / self.settings.minutes[weekday])
                self.start_schedule(minutes_remaining, percent_brightness)
                return
            elif dt_start > now:
                # Sunrise start is today but in the future - set up an event to start
                print(f'Scheduling start today at: {self.settings.start_time[weekday]}')
                self.schedule_sunrise_start(dt_start, self.settings.minutes[weekday])
                return

        # Look for the next scheduled sunrise and set up an event for it.
        # Start tomorrow. Be sure to wrap around if end of week (Sunday) and include today's day in
        # case it is the only scheduled time (i.e., next week on same day)
        day_index = (weekday + 1) % (DayOfWeek.Sunday.value + 1)
        day_increment = 1
        have_scheduled_start = False
        for day in range(DayOfWeek.Sunday.value):
            if self.settings.start_time[day_index]:
                have_scheduled_start = True
                dt_start = calc_start_datetime(self.settings.start_time[day_index], day_increment)
                print(f'Scheduling future start: {dt_start}, duration: {self.settings.minutes[day_index]} minutes')
                self.schedule_sunrise_start(dt_start, self.settings.minutes[day_index])
                #self.disp_thread.update_line3_display(f'Next sunrise: {dt_start.ctime()}')
                self.disp_thread.update_line3_display(f'Next sunrise: Tuesday at 05:30 AM')
                break
            day_index = (day_index + 1) % (DayOfWeek.Sunday.value + 1)
            day_increment = day_increment + 1

        if not have_scheduled_start:
            self.disp_thread.update_line3_display('Idle, no sunrise scheduled')

    def start_schedule(self, duration_minutes: int, starting_percentage: int = 0):
        print('Sunrise starting....')
        self.is_running = True
        self.dimmer.enable()
        # Calculate the end time based upon current time and duration setting.
        self.start = dt.datetime.now()
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
        self.check_schedule()

    def check_schedule(self):
        if self.dimmer.increment_level(self.dimmer_step_size) and not self.cancel:
            self.time_increment_sched = Timer(self.sec_per_step, self.check_schedule)
            self.time_increment_sched.start()
        else:
            # Either we are done or cancelled
            print("Sunrise complete")
            self.is_running = False
            self.cancel = False
            self.dimmer.turn_off()
            self.ctrl_event.set()

    def set_schedule(self):
        pass

    def cancel_pending_schedule(self):
        # If scheduled event is queued up to run, cancel it
        if self.sunrise_scheduler.queue:
            try:
                if self.sunrise_event:
                    scheduler.cancel(self.sunrise_event)
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
            self.dimmer.set_level(self.dimmer.get_min_level())
            # TODO - update status correctly
            #self.disp_thread.update_line3_display('Next sunrise: TBD')

    def schedule_sunrise_start(self, start_time: dt.datetime, duration_minutes: int):
        # Create a new scheduler
        self.sunrise_scheduler = scheduler(time.time, time.sleep)

        # Schedule the start
        epoch_start_time = start_time.timestamp()
        self.sunrise_event = self.sunrise_scheduler.enterabs(epoch_start_time, 1,
                                                             self.start_schedule, (duration_minutes,))

        # Start the scheduler in its own thread so we don't block here
        st = SchedulingThread(self.sunrise_scheduler)
        st.start()

    def set_clock(self):
        pass

    def display_on(self):
        if self.is_running:
            self.data.set_display_mode(DisplayMode.running)
        else:
            self.data.set_display_mode(DisplayMode.idle)

        self.disp_thread.turn_on_display()

    def button_press(self, gpio, level, tick):
        global button_map
        btn = button_map[gpio]
        print(f'Button {btn} pressed...')
        # If display is not on, any button press will turn on the display but not do anything else.
        if not self.data.is_display_on():
            # Default back to initial menu - If we want to pick up where we left off, remove this line
            self.reinit_menus()
            self.display_on()
            return

        # Call the handler for the current menu
        new_menu_name = self.menus[self.current_menu_name].button_handler(btn)
        # if button action changed the menu, update the display with new menu
        print(f'new_menu_name = {new_menu_name}')
        print(f'current_menu_name = {self.current_menu_name}')
        if self.current_menu_name != new_menu_name:
            self.current_menu_name = new_menu_name
            menu = self.menus[self.current_menu_name]
            menu.reset()
            menu.update_display()


    def reinit_menus(self):
        # Iterate through the menu objects and reset them
        for key in self.menus.keys():
            self.menus[key].reset()

        self.current_menu_name = self.menus[MenuStateName.top]

    def shutdown(self):
        self.dimmer.shutdown()

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

class Menu:
    def __init__(self, menu_list):
        self.current_sub_menu_idx = 0
        self.sub_menu_list = menu_list
        self.line4 = ' X     <     >    Prev'
        self.prev_menu = None
        self.next_menu = None
        self.select_action = None
        self.left_action = None
        self.right_action = None
        self.prev_action = None


    def set_line4(self, line4):
        self.line4 = line4

    def set_prev_menu(self, prev_menu):
        self.prev_menu = prev_menu

    def set_next_menu(self, next_menu):
        self.next_menu = next_menu

    def set_select_action(self, select_action):
        self.select_action = select_action

    def set_left_action(self, left_action):
        self.left_action = left_action

    def set_right_action(self, right_action):
        self.right_action = right_action

    def set_prev_action(self, prev_action):
        self.prev_action = prev_action


class TimeMenu(Menu):
    def __init__(self):
        super().__init__(None)
        self.day = None

    def set_day(self, day):
        self.day = day

class TestMenu(ABC):
    def __init__(self, controller: SunriseController, menu_state_name: MenuStateName):
        self.controller = controller
        self.menu_state_name = menu_state_name

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def update_display(self):
        pass

    @abstractmethod
    def button_handler(self, btn: int) -> MenuStateName | None:
        pass


class TopMenu(TestMenu):
    def __init__(self, controller):
        super().__init__(controller, MenuStateName.top)
        self.menu_line3 = ''
        self.menu_line4 = ''

        self.scroll = True
        self.reset()

    def reset(self):
        self.menu_line4 = ''
        if self.controller.dimmer.get_level():
            self.menu_line4 = 'Menu  Dim-  Dim+  Off'
        else:
            self.menu_line4 = 'Menu  Dim-  Dim+  On'
        self.scroll = True

    def update_display(self):
        self.controller.disp_thread.update_line4_display(self.menu_line4)

    def button_handler(self, btn: int) -> MenuStateName | None:

        self.controller.view.turn_display_on()

        # TODO - Menu button changes to main menu
        if btn == 1:
            return MenuStateName.main

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
                    self.controller.dimmer.turn_off()
                else:
                    line4 = 'Menu  Dim-  Dim+  Off'
                    self.controller.dimmer.turn_on()
                print("Updating display...")
                self.controller.disp_thread.update_line4_display(line4)
            case _:
                print("Invalid button number")

        return self.menu_state_name

class MainSubMenus(Enum):
    program = 0
    enable = 1
    display = 2
    set_date = 3
    network = 4


class MainMenu(TestMenu):
    def __init__(self, controller):
        super().__init__(controller, MenuStateName.main)
        self.menu_line3 = ''
        self.menu_line4 = ''
        self.current_sub_menu = MainSubMenus.program
        self.current_sub_menu_idx: int = 0
        # The following two lists must correspond to each other. Both are indexed by self.current_sub_menu_idx
        self.sub_menu_list = ['Program', 'Enable Schedule', 'Display Auto-Off', 'Date/Time', 'Network Settings']
        self.sub_menu_key_list = [MenuStateName.set_program, MenuStateName.enable, MenuStateName.display_timer,
                                  MenuStateName.set_date, MenuStateName.network]
        self.sub_menus = self.reset()

    def reset(self)-> Dict[Any, Any]:
        self.current_sub_menu = MainSubMenus.program
        self.menu_line3 = self.sub_menu_list[MainSubMenus.program.value]
        self.menu_line4 = ' X     <     >    Prev'

        return {MainSubMenus.program: ScheduleMenu, MainSubMenus.enable: EnableMenu, MainSubMenus.display: EnableMenu,
                MainSubMenus.set_date: SetDateMenu, MainSubMenus.network: NetworkMenu}

    def update_display(self):
        self.controller.disp_thread.update_line3_display(self.menu_line3)
        self.controller.disp_thread.update_line4_display(self.menu_line4)

    def button_handler(self, btn: int) -> MenuStateName | None:
        match btn:
            case 1:
                # Select button pressed, go to new menu
                return self.sub_menu_key_list[self.current_sub_menu_idx]
            case 2:
                # Left arrow
                idx = (self.current_sub_menu_idx - 1) % len(self.sub_menu_list)
                self.menu_line3 = self.sub_menu_list[idx]
                self.controller.disp_thread.update_line3_display(self.menu_line3)
                self.current_sub_menu_idx = idx
            case 3:
                # Right arrow
                idx = (self.current_sub_menu_idx + 1) % len(self.sub_menu_list)
                self.menu_line3 = self.sub_menu_list[idx]
                self.controller.disp_thread.update_line3_display(self.menu_line3)
                self.current_sub_menu_idx = idx
                pass
            case 4:
                # Previous
                return MenuStateName.top

        return self.menu_state_name


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

class TimeMenu(Enum):
    invalid = -1
    start = 0
    duration = 1



class ScheduleMenu(TestMenu):
    def __init__(self, controller):
        super().__init__(controller, MenuStateName.set_program)
        self.menu_line3 = 'Weekday'
        self.menu_line4 = 'X     <     >    Prev'

        self.top: ScheduleTopMenu = ScheduleTopMenu.weekday
        self.top_disp_list = ['Weekday', 'Weekend', 'Daily']

        self.day: DailyMenu = DailyMenu.sunday
        self.daily_disp_list = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        self.time: TimeMenu = TimeMenu.start
        self.time_disp_list = ['Start', 'Duration']

        self.set_start_time = False
        self.start_time:dt = dt.datetime.now()
        self.set_duration = False
        self.duration:dt.timedelta = dt.timedelta(0)

    def reset(self):
        pass

    def update_display(self):
        self.controller.disp_thread.update_line3_display(self.menu_line3)
        self.controller.disp_thread.update_line4_display(self.menu_line4)

    def button_handler(self, btn: int) -> MenuStateName | None:
        match btn:
            case 1:
                # Select
                pass
            case 2:
                # Left
                pass
            case 3:
                # Right
                # Handling depends upon what menu we are currently in
                match self.top:
                    case ScheduleTopMenu.weekday:
                        # How to determine leaf menu???????????
                        pass
                    case ScheduleTopMenu.weekend:
                        pass
                    case ScheduleTopMenu.daily:
                        pass
            case 4:
                # Prev
                pass




class EnableMenu(TestMenu):
    def __init__(self, controller):
        super().__init__(controller, MenuStateName.enable)
        self.menu_line3 = ''
        self.menu_line4 = 'X     <     >    Prev'


    def reset(self):
        self.current_sub_menu = ''

    def update_display(self):
        self.controller.disp_thread.update_line3_display(self.menu_line3)
        self.controller.disp_thread.update_line4_display(self.menu_line4)

    def button_handler(self, btn: int) -> MenuStateName:
        pass


class SetDisplayOffTimeMenu(TestMenu):
    def __init__(self, controller):
        super().__init__(controller, MenuStateName.display_timer)
        self.menu_line3 = ''
        self.menu_line4 = ''
        self.current_sub_menu = ''

    def reset(self):
        self.current_sub_menu = ""

    def update_display(self):
        self.controller.disp_thread.update_line3_display(self.menu_line3)
        self.controller.disp_thread.update_line4_display(self.menu_line4)

    def button_handler(self, btn: int) -> MenuStateName | None:
        pass


class SetDateMenu(TestMenu):
    def __init__(self, controller):
        super().__init__(controller, MenuStateName.set_date)
        self.menu_line3 = ''
        self.menu_line4 = ''
        self.current_sub_menu = ''

    def reset(self):
        self.current_sub_menu = ''

    def update_display(self):
        self.controller.disp_thread.update_line3_display(self.menu_line3)
        self.controller.disp_thread.update_line4_display(self.menu_line4)

    def button_handler(self, btn: int) -> MenuStateName | None:
        pass


class NetworkMenu(TestMenu):
    def __init__(self, controller):
        super().__init__(controller, MenuStateName.network)
        self.menu_line3 = ''
        self.menu_line4 = ''
        self.current_sub_menu = ''

    def reset(self):
        self.current_sub_menu = ''

    def update_display(self):
        self.controller.disp_thread.update_line3_display(self.menu_line3)
        self.controller.disp_thread.update_line4_display(self.menu_line4)

    def button_handler(self, btn: int) -> MenuStateName | None:
        pass
