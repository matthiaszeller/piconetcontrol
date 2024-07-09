"""
Client-side script for operating GPIO pins on the Rasperry Pi Pico W.
Communication adheres to a defined communication protocol, see `README.md`.
"""

import gc
import json
import os
import ssl

# time.time() in micropython has no sub-second precision
from time import sleep
from time import time_ns as time

# micropython has no sleep_ms
try:
    from time import sleep_ms
except ImportError:

    def sleep_ms(time_ms: int):
        sleep(time_ms / 1000)


def is_raspberrypi_pico() -> bool:
    try:
        import machine  # noqa F401

        return True
    except ImportError:
        return False


def json_decorator(fun):
    async def wrapper(*args, **kwargs) -> str:
        try:
            dic = json.loads(args[1])  # args[0] is self
            args = list(args)
            args[1] = dic
            try:
                res = await fun(*args, **kwargs)
            except Exception as e:
                res = dic.copy()
                res["error"] = e

        # MicroPython throws ValueError
        except (json.JSONDecodeError, ValueError) as e:
            res = {"error": e}

        if "error" in res:
            res["exception"] = res["error"].__class__.__name__
            res["error"] = str(res["error"])

        return json.dumps(res)

    return wrapper


class GPIOControlServerBase:

    _VERSION = "1.9.3"

    _IDLING_BLINK_DURATION = 1.5
    _IDLING_BLINK_DT = 1.5

    def __init__(self, use_ssl: bool = True):
        # server settings
        with open("config/config_connection.json", "r") as fh:
            cfg = json.load(fh)
        self.connection_port = cfg["port"]
        if use_ssl:
            self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.ssl_context.load_cert_chain("config/ec_cert.der", "config/ec_key.der")
        else:
            self.ssl_context = None

        self._event_continuous_blink = asyncio.Event()
        self._event_continuous_blink.set()
        self.__continuous_blink_duration = None
        self.__continuous_blink_dt = None

    async def run(self):
        self.configure_gpio()
        self.configure_network()
        task_blink = asyncio.create_task(self.__blink_led_infinite())
        try:
            await self.server_listen()
        finally:
            task_blink.cancel()

    def cleanup(self):
        # critical to correctly shut down LED if code has terminated (e.g. error)
        self.led_off()

    def configure_network(self):
        pass

    def configure_gpio(self):
        pass

    def blink_led(self, duration_ms: int = 50, n: int = 1, dt: int = 50):
        for _ in range(n):
            self.led_on()
            sleep_ms(duration_ms)
            self.led_off()
            sleep_ms(dt)

    async def blink_led_async(
        self, duration_s: float = 0.05, n: int = 3, dt_s: float = 0.1
    ):
        # TODO: could use machine.Timer instead, but be careful with infinite blink
        #       could probably play with Timer.init and Timer.deinit
        try:
            self._event_continuous_blink.clear()  # pause infinite blinking
            for _ in range(n):
                self.led_on()
                await asyncio.sleep(duration_s)
                self.led_off()
                await asyncio.sleep(dt_s)
        finally:
            self._event_continuous_blink.set()  # resume infinite blinking

    def update_continuous_blink(self, duration_s: float = None, dt_s: float = None):
        self.__continuous_blink_duration = duration_s or self._IDLING_BLINK_DURATION
        self.__continuous_blink_dt = dt_s or self._IDLING_BLINK_DT

    async def __blink_led_infinite(self, duration_s: float = None, dt_s: float = None):
        self.update_continuous_blink(duration_s, dt_s)

        while True:
            await self._event_continuous_blink.wait()
            self.led_on()
            await asyncio.sleep(self.__continuous_blink_duration)
            self.led_off()
            await asyncio.sleep(self.__continuous_blink_dt)

    def led_on(self):
        pass

    def led_off(self):
        pass

    async def handle_client(
        self, reader: "asyncio.StreamReader", writer: "asyncio.StreamWriter"
    ):
        print("agent connected", reader.get_extra_info("peername"))
        task_blink = asyncio.create_task(self.blink_led_async(0.020, 100000, 0.1))
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    # No data means the client has closed the connection
                    break

                print("received data", data)
                response = await self.handle_command(data.decode())
                writer.write(response.encode())
                await writer.drain()
        finally:
            task_blink.cancel()
            writer.close()
            await writer.wait_closed()

    async def server_listen(self):
        addr = "0.0.0.0"
        server = await asyncio.start_server(
            self.handle_client, addr, self.connection_port, ssl=self.ssl_context
        )
        print("listening on", addr, "port", self.connection_port)
        async with server:
            await server.wait_closed()

    def setup_pin(self, pin: int, mode):
        pass

    def write_pin(self, pin: int, value: int):
        pass

    def read_pin(self, pin: int) -> int:
        pass

    def get_info(self) -> dict:
        pass

    def sleep(self, time_ms: int, deep: bool):
        pass

    async def reset_after_timeout(self, soft: bool, timeout: float = 1.0):
        pass

    @staticmethod
    def _validate_command(command: dict, *fields: tuple[str, type]):
        missing_fields = set(varname for varname, _ in fields).difference(
            command.keys()
        )
        if len(missing_fields) > 0:
            raise ValueError(
                f'incomplete command, missing fields: {", ".join(missing_fields)}'
            )

        res = (
            [fieldtype(command[field]) for field, fieldtype in fields]
            if len(fields) > 1
            else fields[0][1](command[fields[0][0]])
        )
        return res

    def _action_setup_pin(self, command: dict):
        pin, mode = self._validate_command(command, ("pin", int), ("mode", str))
        self.setup_pin(pin, mode)
        # optionally set pin value
        if "value" in command:
            value = self._validate_command(command, ("value", int))
            self.write_pin(pin, value)

    def _action_write_pin(self, command: dict):
        pin, value, timeout = self._validate_command(
            command, ("pin", int), ("value", int), ("timeout", float)
        )
        # check if pin already has desired value
        if self.read_pin(pin) == value:
            return

        self.write_pin(pin, value)
        # reset pin after timeout
        reset_value = 1 - value
        asyncio.create_task(self.write_pin_after_timeout(pin, reset_value, timeout))

    def _action_read_pin(self, command: dict):
        pin = self._validate_command(command, ("pin", int))
        command["value"] = self.read_pin(pin)

    def _action_ping(self, command: dict):
        pass

    def _action_reset(self, command: dict):
        asyncio.create_task(self.reset_after_timeout(soft=False))

    def _action_sleep(self, command: dict):
        time_ms, deep = self._validate_command(command, ("time_ms", int), ("deep", int))
        # sleep after some time to allow response to be sent
        machine.Timer().init(
            mode=machine.Timer.ONE_SHOT,
            period=1000,
            callback=lambda t: self.sleep(time_ms, deep),
        )

    # Disable soft reset: main.py doesn't seem to run after soft reset
    # def _action_soft_reset(self, command: dict):
    #     asyncio.create_task(self.reset_after_timeout(soft=True))

    def _action_get_version(self, command: dict):
        command["version"] = self._VERSION

    def _action_get_info(self, command: dict):
        command["info"] = self.get_info()

    def _action_list_actions(self, command: dict):
        command["actions"] = list(self._ACTIONS.keys())

    @json_decorator
    async def handle_command(self, command: dict[str]) -> dict[str]:
        command = command.copy()
        command["time_received"] = time()

        fun = self._ACTIONS.get(command["action"])
        if fun is None:
            raise ValueError(
                f'unknown action "{command["action"]}", use "list_actions" to list available actions'
            )

        fun(self, command)

        return command

    async def write_pin_after_timeout(self, pin: int, value: int, timeout: float):
        # TODO replace async callback with machine.Timer
        await asyncio.sleep(timeout)
        print("resetting pin", pin, "to value", value)
        self.write_pin(pin, value)

    _ACTIONS = {
        "setup_pin": _action_setup_pin,
        "write_pin": _action_write_pin,
        "read_pin": _action_read_pin,
        "ping": _action_ping,
        # "soft_reset": _action_soft_reset,
        "reset": _action_reset,
        "get_version": _action_get_version,
        "get_info": _action_get_info,
        "sleep": _action_sleep,
        "list_actions": _action_list_actions,
    }


class GPIOPinNotSetupError(RuntimeError):
    pass


class GPIOControlServerPicoW(GPIOControlServerBase):

    def __init__(self, use_ssl: bool = True):
        self.led = machine.Pin("LED", machine.Pin.OUT)
        super().__init__(use_ssl=use_ssl)
        self.pins = dict()

        with open("config/config_wlan.json", "r") as fh:
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

    async def reset_after_timeout(self, soft: bool, timeout: float = 1.0):
        await asyncio.sleep(timeout)
        if soft:
            print("soft resetting...")
            machine.soft_reset()
        else:
            print("resetting...")
            machine.reset()


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


async def main(app: GPIOControlServerBase):
    await app.run()


if __name__ == "__main__":
    if is_raspberrypi_pico():
        import asyncio as asyncio

        import machine
        import network

        app = GPIOControlServerPicoW()

    else:
        import asyncio

        import RPi.GPIO as GPIO

        app = GPIOControlServerRPI()

    try:
        asyncio.run(main(app))
    finally:
        app.cleanup()
