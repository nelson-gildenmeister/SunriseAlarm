import pigpio

class Dimmer:
    __frequency__: int = 1000

    def __init__(self):
        self.is_enabled: bool = False
        self.pwm_gpio = 13
        self.dutycycle: int = 0
        self.pi = pigpio.pi()
        self.pi.set_PWM_frequency(self.pwm_gpio, self.__frequency__)
        self.pi.set_PWM_dutycycle(self.pwm_gpio, 0)

    def set_level(self, level) -> None:
        """
        Sets the dimming level.  THe level must range from 0 to 255 inclusive.

        :param level: Value from 0 (off) through 255 (full brightness).
        :raises: ValueError
        :return: None
        """
        if self.is_enabled:
            if 0 <= level <= 255:
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
