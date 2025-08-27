import datetime as dt
import json

DEFAULT_START_TIME = '05:00'


class SunriseSettings:

    def __init__(self, weekday_sched_enabled: bool, weekend_sched_enabled: bool, daily_sched_enabled: bool,
                 days, start_time: list[str], duration_minutes: list[int], auto_off_minutes):
        self.weekday_sched_enabled: bool = weekday_sched_enabled
        self.weekend_sched_enabled: bool = weekend_sched_enabled
        self.daily_sched_enabled: bool = daily_sched_enabled
        self.days: str = days
        self.start_time: list[str] = start_time
        self.duration_minutes: list[int] = duration_minutes
        self.auto_off_minutes = auto_off_minutes


def setting_decoder(obj):
    if '__type__' in obj and obj['__type__'] == 'SunriseSettings':
        return SunriseSettings(obj['weekday_sched_enabled'], obj['weekend_sched_enabled'], obj['daily_sched_enabled'],
                               obj['days'], obj['start_time'], obj['duration_minutes'], obj['auto_off_minutes'])

    return obj


class SunriseData:
    def __init__(self):
        # self.sunrise_duration_minutes: dt.timedelta = dt.timedelta(minutes=0)
        self.sunrise_settings_filename = "settings.json"
        self.settings: SunriseSettings = self.load_settings()
        self.consistency_checks()

    def consistency_checks(self):
        need_to_save_settings = False
        # Daily schedule can't be enabled with any other schedule type:
        if self.settings.daily_sched_enabled:
            if self.settings.weekday_sched_enabled or self.settings.weekend_sched_enabled:
                print(f'ERROR: Daily schedule type enabled along with another: weekday:'
                      f' {self.settings.weekday_sched_enabled}, weekend: {self.settings.weekend_sched_enabled}')
                print('   Disabling daily schedule')
                self.settings.daily_sched_enabled = False
                need_to_save_settings = True

        # Start times must be within range
        for idx in range(len(self.settings.start_time)):
            start_time_str = self.settings.start_time[idx]
            try:
                _ = dt.datetime.strptime(start_time_str, '%H:%M')
            except ValueError:
                print(f'ERROR - invalid time format setting for entry {idx}: {start_time_str}')
                print('   Setting to default time')
                need_to_save_settings = True
                self.settings.start_time[idx] = DEFAULT_START_TIME

        if need_to_save_settings:
            self.save_settings()

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
