
def noop_func(dummy_param):
    pass

class MenuState:
    def __init__(self, previous_state, status_line, handler = noop_func(None), button_line = "X   <   >   Bck", second_line = ""):
        self.previous_state: MenuState = previous_state
        self.next_state: MenuState = None
        self.handler = handler
        self.second_line = second_line
        self.status_line = status_line
        self.button_line = button_line

    def get_handler(self) -> ():
        return self.handler

    def set_next_state(self, state):
        self.next_state = state


    def is_prev_state(self) -> bool:
        if self.previous_state:
            return True

        return False

    def is_next_state(self) -> bool:
        if self.next_state:
            return True

        return False

