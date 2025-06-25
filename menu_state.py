from enum import Enum


def noop_func(dummy_param):
    pass


class MenuStateName(Enum):
    main = "main"
    set_program = "set_program"
    set_date = "set_date"
    network = "network"
    enable = "enable"


class MenuState:
    def __init__(self, name, handler = noop_func(None)):
        self.name:MenuStateName = name
        self.handler = handler


    def get_handler(self) -> ():
        return self.handler

