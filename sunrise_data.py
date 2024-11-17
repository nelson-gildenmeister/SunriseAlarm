import datetime as dt
import json
from dataclasses import dataclass

class SunriseSettings:
    def __init__(self):
        self.auto_enabled: bool = False
        self.monday_start: str = ""
        self.tuesday_start: str = ""
        self.wednesday_start: str = ""
        self.thursday_start: str = ""
        self.friday_start: str = ""
        self.saturday_start: str = ""
        self.sunday_start: str = ""
        self.weekday_start: str = ""
        self.weekend_start: str = ""
        self.monday_duration: int = 60
        self.tuesday_duration: int = 60
        self.wednesday_duration: int = 60
        self.thursday_duration: int = 60
        self.friday_duration: int = 60
        self.saturday_duration: int = 60
        self.sunday_duration: int = 60
        self.weekday_duration: int = 60
        self.weekend_duration: int = 60

class SunriseData:
    def __init__(self):
        self.sunrise_duration_minutes: dt.timedelta = dt.timedelta(minutes=0)
        self.settings: SunriseSettings = self.load_settings()

    def save_settings(self):
        with open('data.txt', 'w') as out_file:
            json.dump(self.settings, out_file, sort_keys=True, indent=4,
                      ensure_ascii=False)

    def load_settings(self):
        with open('data.txt', 'r') as in_file:
            return json.load(in_file)
