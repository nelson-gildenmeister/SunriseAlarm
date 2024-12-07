import json
from enum import Enum


class DisplayMode(Enum):
    off = 0
    idle = 1
    running = 2
    menu = 3


class SunriseSettings:

    def __init__(self, sched_enabled, mode, start_time: list[str], minutes: list[int]):
        self.sched_enabled: bool = sched_enabled
        self.mode: str = mode
        self.start_time: list[str] = start_time
        self.minutes: list[int] = minutes
        sd = {"Start": 0, "Duration": 0}
        self.menu = {'Schedule':
                         {'WkDay': sd,
                          'WkEnd': sd,
                          'Day':
                              {'Monday': sd, 'Tuesday': sd, 'Wednesday': sd, 'Thursday': sd, 'Friday': sd,
                                          'Saturday': sd, 'Sunday': sd}},
                     'Clock Set':
                          {'Date': 0, 'Time': 0},
                     'WiFi': {'SSID': 0, 'Password': 0}}

    def is_program_running(self) -> bool:
        if self.mode == "program":
            return True

        return False


def setting_decoder(obj):
    if '__type__' in obj and obj['__type__'] == 'SunriseSettings':
        return SunriseSettings(obj['sched_enabled'], obj['mode'], obj['start_time'], obj['minutes'])

    return obj


class SunriseData:
    def __init__(self):
        # self.sunrise_duration_minutes: dt.timedelta = dt.timedelta(minutes=0)
        self.sunrise_settings_filename = "settings.json"
        self.settings: SunriseSettings = self.load_settings()
        self.display_mode: DisplayMode = DisplayMode.idle
        self.display_status_line: str = "Idle"
        self.display_change: bool = False

    def save_settings(self):
        try:
            with open(self.sunrise_settings_filename, 'wt') as out_file:
                s = vars(self.settings)
                s["__type__"] = 'SunriseSettings'
                json.dump(s, out_file, sort_keys=True, indent=4,
                          ensure_ascii=True)
        except:
            raise FileNotFoundError(f"can't open settings file: {self.sunrise_settings_filename}")

    def load_settings(self):
        with open(self.sunrise_settings_filename, 'r') as in_file:
            j = json.load(in_file, object_hook=setting_decoder)
            return j

    def get_display_modde(self) -> DisplayMode:
        return self.display_mode

    def is_display_on(self) -> bool:
        return self.display_mode != DisplayMode.off

    def set_display_mode(self, mode: DisplayMode):
        self.display_mode = mode

    def set_display_status(self, status: str):
        self
