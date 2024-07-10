==========
picoserver
==========


.. image:: https://img.shields.io/pypi/v/piconetcontrol.svg
        :target: https://pypi.python.org/pypi/piconetcontrol


.. image:: https://img.shields.io/github/license/matthiaszeller/piconetcontrol.svg
   :target: https://github.com/matthiaszeller/piconetcontrol/blob/main/LICENSE



Client-server package to remotely control a Raspberrypi Pico W.


About
-----

This package provides a client-server architecture to remotely control a Raspberry Pi Pico W.
The server runs on the Pico W and the client on a computer.
For testing/debugging purpose, the server can also run on e.g. a Raspberrypi 4, with limited functionality.

The goal is to handle logic on the client side, while the server is responsible for direct hardware interaction.
This enables using more powerful hardware for orchestration with greater functionalities,
as the server is executed with MicroPython on the Pico W.

Server Blinking Patterns
------------------------

The Pico W board is equipped with an LED that can be used to indicate the status of the server.

.. list-table::
   :header-rows: 1

   * - **Status**
     - **Pattern**
   * - **Connecting to WiFi**
     - 3 blinks of 100ms, 200ms apart, then 1s pause
   * - **Server Listening (Idling)**
     - Infinite blinks of 1.5s on, 1.5s off
   * - **Ongoing Connection**
     - Continuous 20ms blinks, 100ms apart

If the board isn't blinking:

* Server might not be running
* Board might be in light or deep sleep mode
  * If in light sleep, the server wakes up upon receiving a command


Client-Server Communication Protocol
------------------------------------

The server and the Raspberry Pi Pico W (client) communicate over a TCP/IP connection.
Message exchange occurs via *JSON-encoded dictionaries*.

Commands
~~~~~~~~

GPIO Control
++++++++++++

**Setup pin**
    Instructs client to configure a GPIO pin as input or output, optionally set its value.

    **Command structure**:
    .. code-block:: json

        {
            "action": "setup_pin",
            "pin": <pin_number>,
            "mode": <"input"|"output">,
            # optional
            "value": <0|1>
        }

    **Success Response**: Client echoes back the command.

**Set pin value**
    Instructs client to set a specified GPIO pin to specified value (high or low) during some specified time.

    **Command structure**:
    .. code-block:: json

        {
            "action": "write_pin",
            "pin": <pin_number>,
            "value": <0|1>,
            "timeout": <duration_in_seconds>
        }

    **Success Response**: Client echoes back the command (does not wait for timeout).

**Read pin value**
    Requests the current value (high or low) of a specified GPIO pin.

    **Command structure**:
    .. code-block:: json

        {
            "action": "read_pin",
            "pin": <pin_number>
        }

    **Success Response**: Client echoes back the command and adds the `value` field (high/low).


Board Management
++++++++++++++++

**Reset board**
    Instructs client to reset the board, using the `machine.reset()` method.

    **Command structure**:
    .. code-block:: json

        {
            "action": "reset"
        }

    **Success Response**: Client echoes back the command.

**Sleep for low power**
    Instructs client to enter a low-power state mode for a specified duration.

    **Command structure**:
    .. code-block:: json

        {
            "action": "sleep",
            "deep": <0|1>,
            "time_ms": <duration_in_ms>
        }

    **Success Response**: Client echoes back the command.

**Get resource info**
    Requests information about the client's resources (e.g., memory, CPU).

    **Command structure**:
    .. code-block:: json

        {
            "action": "get_resource_info"
        }

    **Success Response**: Client echoes back the command and adds the `info` field.

**Get server version**
    Requests the version of the server software.

    **Command structure**:
    .. code-block:: json

        {
            "action": "get_version"
        }

    **Success Response**: Client echoes back the command and adds the `version` field.

**List actions**
    Requests a list of available actions supported by the client.

    **Command structure**:
    .. code-block:: json

        {
            "action": "list_actions"
        }

    **Success Response**: Client echoes back the command and adds the `actions` field.

**Update server software**
    Instructs the client to update the server software.

    **Command structure**:
    .. code-block:: json

        {
            "action": "update"
        }

    The client will update the server software and restart the server.
    In case of failure after restart, the server will revert to the previous version.
