import RPi.GPIO as GPIO
from server_base import GPIOControlServerBase


class GPIOControlServerRPI(GPIOControlServerBase):

    GPIO_PIN_LED = 3

    def configure_gpio(self):
        GPIO.setmode(GPIO.BOARD)
        # config LED
        GPIO.setup(self.GPIO_PIN_LED, GPIO.OUT)
        GPIO.output(self.GPIO_PIN_LED, 0)

    def write_pin(self, pin: int, value: int):
        GPIO.output(pin, value)

    def setup_pin(self, pin: int, mode):
        mode = {"input": GPIO.IN, "output": GPIO.OUT}[mode]
        GPIO.setup(pin, mode)

    def read_pin(self, pin: int) -> int:
        return GPIO.input(pin)

    def led_on(self):
        self.write_pin(self.GPIO_PIN_LED, 1)

    def led_off(self):
        self.write_pin(self.GPIO_PIN_LED, 0)
