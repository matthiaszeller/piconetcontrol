"""
Client-side script for operating GPIO pins on the Rasperry Pi Pico W.
Communication adheres to a defined communication protocol, see `README.md`.
"""

import asyncio
import json
import os
import ssl

# time.time() in micropython has no sub-second precision
from time import sleep
from time import time_ns as time

import machine

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
                print("error in function", fun.__name__, e)
                res["error"] = e

        # MicroPython throws ValueError, Python a JSONDecodeError
        # but JSONDecodeError is a subclass of ValueError
        except ValueError as e:
            print("error decoding JSON", e)
            res = {"error": e}

        if "error" in res:
            res["exception"] = res["error"].__class__.__name__
            res["error"] = str(res["error"])

        return json.dumps(res)

    return wrapper


def update_file(file_path: str, content: str):
    # if file already exists, rename it for backup
    try:
        os.rename(file_path, "_" + file_path)
    except OSError:
        # nothing to do if file doesn't exist
        pass

    with open(file_path, "w") as f:
        f.write(content)


class GPIOControlServerBase:

    _VERSION = "1.13.0"

    _IDLING_BLINK_DURATION = 1.5
    _IDLING_BLINK_DT = 1.5

    def __init__(
        self,
        port: int,
        path_ssl_cert: str = None,
        path_ssl_key: str = None,
    ):
        self.connection_port = port

        assert (path_ssl_cert is None) == (
            path_ssl_key is None
        ), "both or none of ssl_cert and ssl_key must be provided"
        if path_ssl_cert:
            self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.ssl_context.load_cert_chain(path_ssl_cert, path_ssl_key)
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
            buffer = bytearray()
            while True:
                data = await reader.read(1024)
                if not data:
                    # No data means the client has closed the connection
                    break

                buffer.extend(data)

                # check if we have received a full command
                if data.endswith(b"\n"):
                    print("received data", buffer)
                    response = await self.handle_command(buffer.decode())
                    writer.write(response.encode())
                    await writer.drain()
                    # exit loop after sending response
                    break

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

    def reset_after_timeout(self, soft: bool, timeout_ms: int = 1000):
        pass

    def reset(self, soft: bool):
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
        self.reset_after_timeout(soft=False)

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

    def _decompress(self, file_contents: str) -> str:
        pass

    def _action_update(self, command: dict):
        files, compress = self._validate_command(
            command, ("files", dict), ("compress", bool)
        )
        # decompress
        if compress:
            files = {k: self._decompress(v) for k, v in files.items()}

        # signal update is in progress
        with open("update.txt", "w") as f:
            f.write(",".join(files.keys()))

        for k, v in files.items():
            print("writing file", k, len(v))
            update_file(k, v)

        self.reset_after_timeout(soft=False)

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
        "update": _action_update,
    }


class GPIOPinNotSetupError(RuntimeError):
    pass
