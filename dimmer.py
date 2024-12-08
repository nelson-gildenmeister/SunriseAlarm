# Need to use pigpio for HW dimmer control.  Software libraries such as lgpio results in major flicking.


import pigpio

class Dimmer:
    __frequency__: int = 1000
    # TODO - Debug
    #__max_dutycycle__: int = 255
    __max_dutycycle__: int = 25
    __min_dutycycle__: int = 0
    __num_steps__: int = __max_dutycycle__ - __min_dutycycle__

    def __init__(self):
        self.is_enabled: bool = False
        self.pwm_gpio = 13
        self.dutycycle: int = 0
        self.pi = pigpio.pi()
        self.pi.set_PWM_frequency(self.pwm_gpio, self.__frequency__)
        self.pi.set_PWM_dutycycle(self.pwm_gpio, 0)

    def set_level(self, level) -> None:
        """
        Sets the dimming level.  The level must range from 0 to 255 inclusive.

        :param level: Value from 0 (off) through 255 (full brightness).
        :raises: ValueError
        :return: None
        """
        if self.is_enabled:
            if 0 <= level <= __max_dutycycle__:
                self.dutycycle = level
                self.pi.set_PWM_dutycycle(self.pwm_gpio, level)
            else:
                raise ValueError
        else:
            # Not enabled, set to off
            if self.dutycycle > 0:
                self.dutycycle = 0
                self.pi.set_PWM_dutycycle(self.pwm_gpio, self.dutycycle)

    def get_level(self) -> int:
        return self.dutycycle

    def enable(self):
        self.is_enabled = True

    def disable(self):
        self.is_enabled = False

    def is_enabled(self):
        return self.is_enabled

    def shutdown(self):
        self.pi.set_PWM_dutycycle(self.pwm_gpio, self.dutycycle)
        self.pi.set_PWM_frequency(self.pwm_gpio, 0)
        self.pi.stop()

    def get_max_level(self) -> int:
        return self.__max_dutycycle__

    def get_min_level(self) -> int:
        return self.__min_dutycycle__

    def turn_off(self):
        self.pi.set_PWM_dutycycle(self.pwm_gpio, 0)

    def turn_on(self):
        self.pi.set_PWM_dutycycle(self.pwm_gpio, self.__max_dutycycle__)

    def get_num_steps(self) -> int:
        return self.__num_steps__

    def increment_level(self):
        if self.dutycycle < self.__max_dutycycle__:
            self.dutycycle = self.dutycycle + 1
            print(f'Setting duty cycle to {self.dutycycle}')
            self.pi.set_PWM_dutycycle(self.pwm_gpio, self.dutycycle)
