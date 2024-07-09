"""
Server-side script for automatic plant watering system.
"""

import argparse
import json
import logging
import socket
import ssl
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from update import get_local_version, get_update_files


class Client:

    VERSION = "1.5.0"

    CMD_TYPE = dict[str, Any]

    def __init__(self, path_config: str | Path = None, use_ssl: bool = True):
        if path_config is None:
            path_config = Path("config") / "config_connection.json"

        with open(path_config) as fh:
            config = json.load(fh)

        self.client = config["client_address"]
        self.port = config["port"]
        if use_ssl:
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
        else:
            self.ssl_context = None

    @contextmanager
    def _create_socket(self):
        with socket.create_connection((self.client, self.port)) as sock:
            if self.ssl_context:
                with self.ssl_context.wrap_socket(sock) as ss:
                    yield ss
            else:
                yield sock

    def _send_single_command(
        self,
        sock: socket.socket,
        command: CMD_TYPE,
        raise_exception: bool = False,
        timeout: float = 3.0,
    ) -> CMD_TYPE:
        try:
            # renew timeout for each command
            sock.settimeout(timeout)

            command["time_sent"] = time.time_ns()
            # Add linebreak to signify end of data packet
            command = json.dumps(command) + "\n"
            logging.debug(f"sending command {command}")
            sock.sendall(command.encode())
            response = self._receive_response(sock, raise_exception)
        except Exception as e:
            logging.error(f"client-side error for command {command}: {e}")
            response = {
                "error": str(e),
                "exception": e.__class__.__name__,
                "command": command,
            }

        return response

    def _receive_response(self, sock: socket.socket, raise_exception: bool) -> CMD_TYPE:
        buffer = bytearray()
        while True:
            data = sock.recv(1024)
            if not data:
                # means server closed the connection
                break

            buffer.extend(data)

        response = json.loads(buffer.decode())
        response["time_responded"] = time.time_ns()
        if "error" in response:
            logfun = logging.critical if raise_exception else logging.error
            logfun(f"server-side error: {response}")
            if raise_exception:
                # TODO
                raise NotImplementedError("refactor this try/except block")
                # raise __builtins__[response['exception']](response['error'])

        return response

    def send_commands(
        self, cmds: list[CMD_TYPE], raise_exception: bool = False, timeout: float = 3.0
    ) -> list[CMD_TYPE]:
        """Send several commands through a single connection."""
        responses = []
        with self._create_socket() as sock:
            # logging.debug(f'connected to {self.client} on port {self.port}')
            for command in cmds:
                response = self._send_single_command(
                    sock, command, raise_exception, timeout
                )
                responses.append(response)

        return responses

    def send_command(self, raise_exception: bool = False, **kwargs) -> CMD_TYPE:
        return self.send_commands([kwargs], raise_exception=raise_exception)[0]

    def send_ping(self, n: int = 5):
        def avg(lst: list[float]) -> float:
            return sum(lst) / len(lst)

        responses = self.send_commands([dict(action="ping") for _ in range(n)])
        error = any("error" in r for r in responses)
        # compute stats
        rtt, tsend = [], []
        for r in responses:
            rtt.append(r["time_responded"] - r["time_sent"])
            tsend.append(r["time_received"] - r["time_sent"])

        return {"rtt": avg(rtt) / 1e9, "tsend": avg(tsend) / 1e9, "error": error}

    def poll_command_response(
        self,
        cmd: CMD_TYPE,
        fun_validate: Callable[[CMD_TYPE], bool],
        dt: float,
        timeout: float,
        allow_connection_refused: bool = False,
    ) -> bool:
        # TODO: refactor this with send_commands to avoid code redundancy
        assert dt > 0 and timeout > 0
        try:
            with self._create_socket() as sock:
                start = time.time()
                while time.time() - start < timeout:
                    response = self._send_single_command(sock, cmd)

                    if fun_validate(response):
                        return True

                    time.sleep(dt)
        except ConnectionRefusedError:
            if allow_connection_refused:
                time.sleep(dt)
                return self.poll_command_response(
                    cmd, fun_validate, dt, timeout, allow_connection_refused
                )

            raise

        return False

    def update_server(self, compress_transfer: bool = True):
        info = self.send_command(action="get_info")["info"]
        print("Server info:")
        print(json.dumps(info, indent=2))
        if "pico" not in info["board"].lower():
            raise NotImplementedError("Server is not running on a Pico board")

        server_version = self.send_command(action="get_version")["version"]
        print("Server version:", server_version)

        local_version = get_local_version()
        if local_version == server_version:
            print("Server is up to date")
            return
        print("Local version:", local_version)

        files: dict = get_update_files(compress=compress_transfer)
        print("Files to update:", list(files.keys()))
        sumchar = sum(map(len, files.values()))
        print("Payload size:", sumchar, "bytes")

        self.send_command(action="update", files=files, compress=compress_transfer)
        print("Waiting for server to restart")
        time.sleep(3)
        print("Attempting to reconnect")
        connected = self.poll_command_response(
            dict(action="ping"),
            lambda x: x.get("action") == "ping",
            1,
            10,
            allow_connection_refused=True,
        )
        if not connected:
            print("Could not connect to server after update")
            return

        new_version = self.send_command(action="get_version")["version"]
        if new_version != local_version:
            print("Update failed, current server version:", new_version)
            return

        print("Server updated successfully")


def main(args):
    use_ssl = not args.no_ssl
    client = Client(use_ssl=use_ssl)

    assert not (args.command and args.file), "Cannot send both a command and a file"

    if args.update:
        client.update_server()
        return

    if args.command:
        res = client.send_commands(args.command, timeout=args.timeout)
    elif args.file:
        with args.file as f:
            commands = json.load(f)
        res = client.send_commands(commands, timeout=args.timeout)
    else:
        res = client.send_ping()

    print("Response:")
    print(json.dumps(res, indent=2))


class KwargsAppendAction(argparse.Action):
    """
    Argparse action to split an argument into KEY=VALUE form
    on append to a list of dictionaries.
    """

    def __call__(self, parser, args, values, option_string=None):
        try:
            d = dict(map(lambda x: x.split("="), values))
        except ValueError:
            raise argparse.ArgumentError(
                self, f'Could not parse argument "{values}" as k1=v1 k2=v2 ... format'
            )

        if getattr(args, self.dest) is None:
            setattr(args, self.dest, [])

        getattr(args, self.dest).append(d)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-ssl",
        action="store_true",
    )
    parser.add_argument(
        "-c",
        "--command",
        nargs="*",
        required=False,
        action=KwargsAppendAction,
        metavar="KEY=VALUE",
        help="Command set to server. If not sent, sends a ping",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=argparse.FileType("r"),
        help="File containing commands to send to the server",
        required=False,
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="TCP socket timeout in seconds (for each command)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update server and ignore other arguments",
    )
    args = parser.parse_args()
    print(args)
    main(args)
