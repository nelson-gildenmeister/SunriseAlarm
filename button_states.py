from enum import Enum

class ButtonStates(Enum):
    Menu = 1
    Select = 2
    On = 3
    Left = 4
    Off = 5
    Right = 6
    Dim = 7
    Back = 8

bs: ButtonStates


class ButtonState:
    def __init__(self):
        global bs
        _button_symbol_map = {bs.Menu: "Menu"}