"""Top-level package for piconetcontrol."""

__author__ = """Matthias Gilles Zeller"""
__author_email__ = "matthias.gilles.zeller@gmail.com"
__version__ = "0.0.2"
__description__ = "Client-server package to remotely control a Raspberrypi Pi."
__long_description__ = """This packages provides two classes (`Client` and `Server`)
to manage a Raspberry Pi board (acting as server) via Wifi.

The server is meant to be a Raspberrypi Pico W, but it is meant to also work on e.g.
a Raspberrypi 4. Therefore, the `server.py` is compatible with both Python and MicroPython.
Some functionalities might not be available for both interpreters, though."""
__url__ = "https://github.com/matthiaszeller/picoserver"
