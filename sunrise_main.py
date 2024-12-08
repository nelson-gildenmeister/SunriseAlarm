import os
import sys

from os import __init__
from dimmer import Dimmer
from sunrise_controller import SunriseController
from sunrise_data import SunriseData
from sunrise_view import OledDisplay



if __name__ == '__main__':
    ctrl: SunriseController = None
    try:
        oled = OledDisplay(3, True)
        data = SunriseData()
        dimmer = Dimmer()
        ctrl = SunriseController(view=oled, data=data, dimmer=dimmer)
        ctrl.start()
        ctrl.join()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            if ctrl:
                ctrl.shutdown()
            sys.exit(130)
        except SystemExit:
            os._exit(os.EX_SOFTWARE)

