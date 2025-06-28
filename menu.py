from abc import ABC, abstractmethod
from enum import Enum

from sunrise_controller import SunriseController

BRIGHTNESS_CHANGE_PERCENT: int = 10

class MenuStateNamej(Enum):
    initial = "initial"
    main = "main"
    set_program = "set_program"
    enable = "enable"
    set_date = "set_date"
    network = "network"

class MenuJ(ABC):
    def __init__(self, controller: SunriseController):
        self.controller = controller

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def button_handler(self, btn:int):
        pass


class InitialMenu(MenuJ):
    def __init__(self, controller: SunriseController):
        super().__init__(controller)
        self.menu_line4 = None
        self.menu_line3 = None
        self.reset()

    def reset(self):
        self.menu_line3 = " Menu  0% - 100%  On/Off"
        self.menu_line4 = "  X     <     >     X"

    def button_handler(self, btn:int) -> MenuStateNamej | None:
        # TODO - Menu button changes to main menu
        if btn == 1:
            return MenuStateNamej.main

        # Other buttons cancel a running schedule
        if self.controller.is_running:
            self.controller.cancel_running_schedule()

        # Handle other button actions
        match btn:
            case 2:
                self.controller.dimmer.decrease_brightness_by_percent(BRIGHTNESS_CHANGE_PERCENT)
            case 3:
                self.controller.dimmer.increase_brightness_by_percent(BRIGHTNESS_CHANGE_PERCENT)
            case 4:
                if self.controller.dimmer.get_level():
                    self.controller.dimmer.turn_off()
                else:
                    self.controller.dimmer.turn_on()
            case _:
                print("Invalid button number")

        return MenuStateNamej.initial


class MainMenu(MenuJ):
    def __init__(self, controller: SunriseController):
        super().__init__(controller)
        self.current_sub_menu: MenuStateNamej = MenuStateNamej.main

    def reset(self):
        self.current_sub_menu = MenuStateNamej.main

    def button_handler(self, btn:int):
        pass


class SetProgramMenu(MenuJ):
    def __init__(self, controller: SunriseController):
        super().__init__(controller)
        self.current_sub_menu = "weekday"

    def reset(self):
        self.current_sub_menu = "weekday"

    def button_handler(self, btn:int) -> MenuStateNamej:
        pass


class EnableMenu(MenuJ):
    def __init__(self, controller: SunriseController):
        super().__init__(controller)
        self.current_sub_menu = ""

    def reset(self):
        self.current_sub_menu = ""

    def button_handler(self, btn:int) -> MenuStateNamej:
        pass


class SetDateMenu(MenuJ):
    def __init__(self, controller: SunriseController):
        super().__init__(controller)
        self.current_sub_menu = ""

    def reset(self):
        self.current_sub_menu = ""

    def button_handler(self, btn:int) -> MenuStateNamej:
        pass


class NetworkMenu(MenuJ):
    def __init__(self, controller: SunriseController):
        super().__init__(controller)
        self.current_sub_menu = ""

    def reset(self):
        self.current_sub_menu = ""

    def button_handler(self, btn:int) -> MenuStateNamej:
        pass
