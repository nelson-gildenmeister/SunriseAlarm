from abc import ABC, abstractmethod
from enum import Enum


def noop_func(dummy_param):
    pass


class MenuStateName(Enum):
    initial = "initial"
    main = "main"
    set_program = "set_program"
    enable = "enable"
    set_date = "set_date"
    network = "network"


class MenuState:
    def __init__(self, name, handler = noop_func(None)):
        self.name:MenuStateName = name
        self.handler = handler


    def get_handler(self) -> ():
        return self.handler


class Menu(ABC):
    def button_handler(self, btn:int):
        pass

class InitialMenu(Menu):
    def __init__(self):
        self.menu_line3 = " Menu  0% - 100%  On/Off"
        self.menu_line4 = "  X     <     >     X"

    @abstractmethod
    def button_handler(self, btn:int):
        pass

class MainMenu(Menu):
    def __init__(self):
        self.current_sub_menu = MenuStateName.main

    def button_handler(self, btn:int):
        pass

class SetProgramMenu(Menu):
    def __init__(self):
        self.current_sub_menu = "weekday"

    def button_handler(self, btn:int):
        pass

class EnableMenu(Menu):
    def __init__(self):
        self.current_sub_menu = ""

    def button_handler(self, btn:int):
        pass

class SetDateMenu(Menu):
    def __init__(self):
        self.current_sub_menu = ""

    def button_handler(self, btn:int):
        pass

class NetworkMenu(Menu):
    def __init__(self):
        self.current_sub_menu = ""

    def button_handler(self, btn:int):
        pass
