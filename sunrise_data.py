import datetime as dt
import json


class SunriseSettings:
    def __init__(self, auto_enabled, mode, monday_start, tuesday_start, wednesday_start, thursday_start, friday_start,
                 saturday_start, sunday_start, weekday_start, weekend_start, monday_duration, tuesday_duration,
                 wednesday_duration, thursday_duration, friday_duration, saturday_duration, sunday_duration,
                 weekday_duration, weekend_duration):
        self.auto_enabled: bool = auto_enabled
        self.mode: str = mode
        self.monday_start: str = monday_start
        self.tuesday_start: str = tuesday_start
        self.wednesday_start: str = wednesday_start
        self.thursday_start: str = thursday_start
        self.friday_start: str = friday_start
        self.saturday_start: str = saturday_start
        self.sunday_start: str = sunday_start
        self.weekday_start: str = weekday_start
        self.weekend_start: str = weekend_start
        self.monday_duration: int = monday_duration
        self.tuesday_duration: int = tuesday_duration
        self.wednesday_duration: int = wednesday_duration
        self.thursday_duration: int = thursday_duration
        self.friday_duration: int = friday_duration
        self.saturday_duration: int = saturday_duration
        self.sunday_duration: int = sunday_duration
        self.weekday_duration: int = weekday_duration
        self.weekend_duration: int = weekend_duration

    def is_program_mode(self) -> bool:
        if self.mode == "program":
            return True

        return False

def setting_decoder(obj):
    if '__type__' in obj and obj['__type__'] == 'SunriseSettings':
        return SunriseSettings(obj['auto_enabled'], obj['mode'], obj['monday_start'], obj['tuesday_start'],
                               obj['wednesday_start'], obj['thursday_start'], obj['friday_start'],
                               obj['saturday_start'], obj['sunday_start'],
                               obj['weekday_start'], obj['weekend_start'], obj['monday_duration'],
                               obj['tuesday_duration'], obj['wednesday_duration'], obj['thursday_duration'],
                               obj['friday_duration'], obj['saturday_duration'], obj['sunday_duration'],
                               obj['weekday_duration'], obj['weekend_duration'])
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
