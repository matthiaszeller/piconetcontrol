import gc
import json
import os
from io import BytesIO
from time import sleep

import machine
import network
from deflate import DeflateIO
from server_base import GPIOControlServerBase, GPIOPinNotSetupError
from ubinascii import a2b_base64


class GPIOControlServerPicoW(GPIOControlServerBase):

    def __init__(
        self,
        path_wifi_credentials: str,
        port: int,
        path_ssl_cert: str = None,
        path_ssl_key: str = None,
    ):
        self.led = machine.Pin("LED", machine.Pin.OUT)
        super().__init__(port, path_ssl_cert, path_ssl_key)
        self.pins = dict()

        with open(path_wifi_credentials, "r") as fh:
            credentials = json.load(fh)

        self.wlan_ssid = credentials["ssid"]
        self.wlan_pwd = credentials["pwd"]

    def configure_network(self):
        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected():
            wlan.active(True)
            wlan.connect(self.wlan_ssid, self.wlan_pwd)

            while not wlan.isconnected():
                print("waiting for connection...")
                self.blink_led(100, 3, 200)
                sleep(1)

    def led_on(self):
        self.led.on()

    def led_off(self):
        self.led.off()

    def __process_pin(self, pin: int, check_setup=True):
        # attempt casting to int
        try:
            pin = int(pin)
        except ValueError:
            pass

        if check_setup and pin not in self.pins:
            raise GPIOPinNotSetupError(f"pin {pin} not setup")

        return pin

    def _decompress(self, file_contents: str) -> str:
        with DeflateIO(BytesIO(a2b_base64(file_contents))) as f:
            return f.read().decode()

    def setup_pin(self, pin: int, mode):
        mode = {"input": machine.Pin.IN, "output": machine.Pin.OUT}[mode]
        pin = self.__process_pin(pin, check_setup=False)
        self.pins[pin] = machine.Pin(pin, mode)

    def write_pin(self, pin: int, value: int):
        pin = self.__process_pin(pin)
        self.pins[pin].value(value)

    def read_pin(self, pin: int) -> int:
        pin = self.__process_pin(pin)
        return self.pins[pin].value()

    def get_info(self) -> dict:
        uname = os.uname()
        return {
            "mem_free": gc.mem_free(),
            "mem_alloc": gc.mem_alloc(),
            "micropython_version": uname.release,
            "micropython_version_info": uname.version,
            "board": uname.machine,
        }

    def sleep(self, time_ms: int, deep: bool):
        # make sure board stops blinking
        self._event_continuous_blink.clear()
        self.led_off()

        if deep:
            print(f"deepsleeping for {time_ms} ms...")
            machine.deepsleep(time_ms)
        else:
            print(f"lightsleeping for {time_ms} ms...")
            machine.lightsleep(time_ms)

        # to see the print appear, wait just a bit with time.sleep (software-based),
        # or it might not show up (probably depends on how microcontroller handles prints
        # when interrupts occur)
        sleep(0.1)
        print("woke up from sleep")
        self._event_continuous_blink.set()

    def reset_after_timeout(self, soft: bool, timeout_ms: int = 1000):
        if soft:
            print("soft resetting...")
            fun = machine.soft_reset
        else:
            print("resetting...")
            fun = machine.reset

        machine.Timer().init(
            period=timeout_ms, mode=machine.Timer.ONE_SHOT, callback=lambda t: fun()
        )
