import argparse

from piconetcontrol.client import setup


def main():
    parser = argparse.ArgumentParser(description="PicoNetControl CLI")

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Setup command
    subparsers.add_parser("setup", help="Setup the connected board")

    # Parse arguments
    args = parser.parse_args()

    # Handle commands
    if args.command == "setup":
        setup.main()
    else:
        # If no command is specified, show help
        parser.print_help()


if __name__ == "__main__":
    main()
