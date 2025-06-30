import datetime as dt
import queue
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from sched import scheduler, Event
from threading import Timer
from typing import List

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
        self.line1 = ""
        self.line2 = ""
        self.line3 = ""
        self.line4 = ""
        self.scroll = True
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
        self.view.update_display(self.line1, self.line2, self.line3, self.line4, self.scroll)
        while True:
            while self.data.is_display_on():
                #self.view.update_display(self.line1, self.line2, self.line3, self.line4, self.scroll)

                if self.event.is_set():
                    return

                max_wait_time = 1
                if self.scroll:
                    incremental_wait_time = 0.05
                    xs = (x * incremental_wait_time for x in range(0, max_wait_time))
                    for _ in xs:
                        try:
                            msg = self.msg_q.get(False, incremental_wait_time)
                            if msg == self.update:
                                self.view.update_display(self.line1, self.line2, self.line3, self.line4, self.scroll)
                            self.view.scroll_line3()
                        except queue.Empty:
                            # Okay for no display changes
                            pass
                else:
                    # Delay display update unless someone gives us a new update
                    try:
                        msg = self.msg_q.get(False, max_wait_time)
                        if msg == self.update:
                            self.view.update_display(self.line1, self.line2, self.line3, self.line4, self.scroll)
                    except queue.Empty:
                        # Okay for no display changes
                        pass

            # Wait for something to wake up the display
            msg = self.msg_q.get(True)

    # Send a message to unblock the display thread and start display updates again.
    def turn_on_display(self):
        self.msg_q.put(self.wake, False)

    def update_display(self, line1, line2, line3, line4, scroll = True):
        print("Enter update_display()")
        self.line1 = line1
        self.line2 = line2
        self.line3 = line3
        self.line4 = line4
        self.scroll = scroll
        self.msg_q.put(self.wake, False)


class SunriseController:
    sunrise_event: Event

    def __init__(self, view: OledDisplay, data: SunriseData, dimmer: Dimmer):
        self.disp_thread = None
        global btn1_gpio, btn2_gpio, btn3_gpio, btn4_gpio
        threading.Thread.__init__(self)
        self.dimmer_step_size: int = 1
        self.pi = pigpio.pi()
        self.sunrise_scheduler = None
        self.time_increment_sched: threading.Timer
        self.view = view
        self.data: SunriseData = data
        self.settings: SunriseSettings = data.settings
        self.dimmer: Dimmer = dimmer
        self.start: dt.datetime = dt.datetime.now()
        self.cancel: bool = False
        self.sec_per_step: int = 0
        self.is_running: bool = False
        self.ctrl_event: threading.Event = threading.Event()
        self.current_menu: MenuStateName = MenuStateName.initial
        self.menus = self.initialize_menus()
        self.hookup_buttons(self.pi, [btn1_gpio, btn2_gpio, btn3_gpio, btn4_gpio])


    def initialize_menus(self) -> {}:
        return {MenuStateName.initial: InitialMenu(self), MenuStateName.main: MainMenu(self),
         MenuStateName.set_program: SetProgramMenu(self), MenuStateName.enable: EnableMenu,
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
        current_menu = self. menus[self.current_menu]
        self.disp_thread.update_display("", "", "", Menu.menu_line4)

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
        for day in range(DayOfWeek.Sunday.value):
            if self.settings.start_time[day_index]:
                dt_start = calc_start_datetime(self.settings.start_time[day_index], day_increment)
                print(f'Scheduling future start: {dt_start}, duration: {self.settings.minutes[day_index]} minutes')
                self.schedule_sunrise_start(dt_start, self.settings.minutes[day_index])
                break
            day_index = (day_index + 1) % (DayOfWeek.Sunday.value + 1)
            day_increment = day_increment + 1

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

    def cancel_schedule(self):
        # If scheduled event is not yet running, cancel it
        if self.sunrise_scheduler.queue:
            try:
                if self.sunrise_event is not None:
                    scheduler.cancel(self.sunrise_event)
            except ValueError:
                # no event in the queue to cancel
                pass

        self.cancel_running_schedule()

    def cancel_running_schedule(self):
        # If scheduled event is running, stop it
        try:
            self.time_increment_sched.cancel()
        except:
            pass
        if self.is_running:
            self.cancel = True
            self.dimmer.set_level(self.dimmer.get_min_level())

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
        self.current_menu = self.menus[self.current_menu].button_handler(btn)

    def reinit_menus(self):
        # Iterate through the menu objects and reset them
        for key in self.menus.keys():
            self.menus[key].reset()

        self.current_menu = self.menus[MenuStateName.initial]

    def shutdown(self, sig, frame):
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

class MenuStateName(Enum):
    initial = "initial"
    main = "main"
    set_program = "set_program"
    enable = "enable"
    display_timer = "display_timer"
    set_date = "set_date"
    network = "network"

class Menu(ABC):
    menu_line4 = ""
    def __init__(self, controller: SunriseController):
        self.controller = controller

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def button_handler(self, btn: int):
        pass

class InitialMenu(Menu):
    def __init__(self, controller):
        super().__init__(controller)
        self.scroll = True
        self.reset()

    def reset(self):
        if self.controller.dimmer.get_level():
            Menu.menu_line4 = "Menu  Dim-  Dim+  Off"
        else:
            Menu.menu_line4 = "Menu  Dim-  Dim+  On"
        self.scroll = True

    def button_handler(self, btn: int) -> MenuStateName | None:
        # Every button push resets the time for display auto power off but if display is off, no action is performed.
        if not self.controller.view.is_display_on():
            self.controller.view.turn_display_on()
            return MenuStateName.initial

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
                    print("Updating display...")
                    self.controller.disp_thread.update_display("", "", "", "Menu  Dim-  Dim+  On")
            case 3:
                self.controller.dimmer.increase_brightness_by_percent(BRIGHTNESS_CHANGE_PERCENT)
                # Update display if it was off previously
                if not dimmer_prev_on:
                    print("Updating display...")
                    self.controller.disp_thread.update_display("", "", "", "Menu  Dim-  Dim+  Off")
            case 4:
                line4 = "Menu  Dim-  Dim+  On"
                if self.controller.dimmer.get_level():
                    self.controller.dimmer.turn_off()
                else:
                    line4 = "Menu  Dim-  Dim+  Off"
                    self.controller.dimmer.turn_on()
                print("Updating display...")
                self.controller.disp_thread.update_display("", "", "", line4)
            case _:
                print("Invalid button number")


        return MenuStateName.initial

class MainMenu(Menu):
    def __init__(self, controller):
        super().__init__(controller)
        self.current_sub_menu: MenuStateName = MenuStateName.main

    def reset(self):
        self.current_sub_menu = MenuStateName.main

    def button_handler(self, btn: int):
        pass

class SetProgramMenu(Menu):
    def __init__(self, controller):
        super().__init__(controller)
        self.current_sub_menu = "weekday"

    def reset(self):
        self.current_sub_menu = "weekday"

    def button_handler(self, btn: int) -> MenuStateName:
        pass

class EnableMenu(Menu):
    def __init__(self, controller):
        super().__init__(controller)
        self.current_sub_menu = ""

    def reset(self):
        self.current_sub_menu = ""

    def button_handler(self, btn: int) -> MenuStateName:
        pass

class SetDisplayOffTimeMenu(Menu):
    def __init__(self, controller):
        super().__init__(controller)
        self.current_sub_menu = ""

    def reset(self):
        self.current_sub_menu = ""

    def button_handler(self, btn: int) -> MenuStateName:
        pass

class SetDateMenu(Menu):
    def __init__(self, controller):
        super().__init__(controller)
        self.current_sub_menu = ""

    def reset(self):
        self.current_sub_menu = ""

    def button_handler(self, btn: int) -> MenuStateName:
        pass

class NetworkMenu(Menu):
    def __init__(self, controller):
        super().__init__(controller)
        self.current_sub_menu = ""

    def reset(self):
        self.current_sub_menu = ""

    def button_handler(self, btn: int) -> MenuStateName:
        pass
