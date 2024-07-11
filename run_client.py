import argparse
import json

from piconetcontrol.client import Client


def main(args):
    use_ssl = not args.no_ssl
    client = Client(host=args.host, port=args.port, use_ssl=use_ssl)

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
        "host",
        type=str,
        help="Server hostname or IP address",
    )
    parser.add_argument(
        "port",
        type=int,
        help="Server port",
    )
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
