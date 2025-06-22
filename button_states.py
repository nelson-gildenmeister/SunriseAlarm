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


class ButtonsState:
    def __init__(self):
        global bs
        _button_symbol_map = {bs.Menu: "Menu"}
        m1 = "Menu   On   Off   Dim"
        m2 = " X     <     >   Back"
        b1_next_state
        b1_action
        b2_next_state
        b2_action
        b3_next_state
        b3_action
        b4_next_state
        b4_action
