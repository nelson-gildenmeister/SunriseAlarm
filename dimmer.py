# Need to use pigpio for HW dimmer control.  Software libraries such as lgpio results in major flicking.


import pigpio

class Dimmer:
    __frequency__: int = 1000
    __max_duty_cycle__: int = 255
    __min_duty_cycle__: int = 0
    __num_steps__: int = __max_duty_cycle__ - __min_duty_cycle__

    def __init__(self):
        self.is_enabled: bool = False
        self.pwm_gpio = 13
        self.duty_cycle: int = 0
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
            if 0 <= level <= self.__max_duty_cycle__:
                self.duty_cycle = level
                self.pi.set_PWM_dutycycle(self.pwm_gpio, level)
            else:
                raise ValueError
        else:
            # Not enabled, set to off
            if self.duty_cycle > 0:
                self.duty_cycle = 0
                self.pi.set_PWM_dutycycle(self.pwm_gpio, self.duty_cycle)

    def get_level(self) -> int:
        return self.duty_cycle

    def enable(self):
        self.is_enabled = True

    def disable(self):
        self.is_enabled = False

    def is_enabled(self):
        return self.is_enabled

    def shutdown(self):
        self.pi.set_PWM_dutycycle(self.pwm_gpio, self.duty_cycle)
        self.pi.set_PWM_frequency(self.pwm_gpio, 0)
        self.pi.stop()

    def get_max_level(self) -> int:
        return self.__max_duty_cycle__

    def get_min_level(self) -> int:
        return self.__min_duty_cycle__

    def turn_off(self):
        self.pi.set_PWM_dutycycle(self.pwm_gpio, 0)

    def turn_on(self):
        self.pi.set_PWM_dutycycle(self.pwm_gpio, self.__max_duty_cycle__)

    def get_num_steps(self) -> int:
        return self.__num_steps__

    # Positive or negative change in brightness level.  Returns False if unable to change the
    # brightness level due to already being at maximum or minimum.
    def increment_level(self, steps: int = 1) -> bool:
        new_duty_cycle = self.duty_cycle + steps
        if new_duty_cycle > self.__max_duty_cycle__ or new_duty_cycle < self.__min_duty_cycle__:
            return False

        self.duty_cycle = new_duty_cycle
        print(f'Setting duty cycle to {self.duty_cycle}')
        self.pi.set_PWM_dutycycle(self.pwm_gpio, self.duty_cycle)
        return True
