from dimmer import Dimmer
from sunrise_controller import SunriseController
from sunrise_data import SunriseData
from sunrise_view import OledDisplay



if __name__ == '__main__':
    oled = OledDisplay(3)
    data = SunriseData()
    dimmer = Dimmer()
    ctrl = SunriseController(view=oled, data=data, dimmer=dimmer)
    ctrl.startup()
