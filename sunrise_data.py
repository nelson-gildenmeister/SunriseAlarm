import datetime as dt
import json

from sunrise_main import start_display_time


class SunriseSettings:
    def __init__(self, auto_enabled, mode, start_time, minutes):
        self.auto_enabled: bool = auto_enabled
        self.mode: str = mode
        self.start_time: [str] = start_time
        self.minutes: [int] = minutes


    def is_program_running(self) -> bool:
        if self.mode == "program":
            return True

        return False

def setting_decoder(obj):
    if '__type__' in obj and obj['__type__'] == 'SunriseSettings':
        return SunriseSettings(obj['auto_enabled'], obj['mode'], obj['start_time'], obj['minutes'])

    return obj


class SunriseData:
    def __init__(self):
        self.sunrise_duration_minutes: dt.timedelta = dt.timedelta(minutes=0)
        self.sunrise_settings_filename = "settings.json"
        self.settings: SunriseSettings = self.load_settings()

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
