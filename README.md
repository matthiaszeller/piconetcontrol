# piconetcontrol

![PyPI Version](https://img.shields.io/pypi/v/piconetcontrol.svg)
[![License](https://img.shields.io/github/license/matthiaszeller/piconetcontrol.svg)](https://github.com/matthiaszeller/piconetcontrol/blob/main/LICENSE)

Client-server package to remotely control a Raspberry Pi Pico W.


## About

This package provides a client-server architecture to remotely control a Raspberry Pi Pico W.
The *server* runs on the Pico W, handling direct hardware interaction, while the *client* runs on e.g. a Raspberrypi.

This design allows for lightweight "agents" (Pico W devices) 
to perform hardware-specific tasks, while the raspberrypi handles centralized orcheastration and higher-order logic. 

For testing/debugging purposes, the *server* can also run on the raspberrypi itself.


### Security

The current security model assumes the LAN is secure.  
mTLS might be implemented later (if even possible on the Pico W).

### Fail-Safe Mechanism

To handle scenarios where the client-server connection is disrupted after an actuator has been activated, changing a pin state (`write_pin` command) requires a timeout to be specified.  
After the timeout, the server will revert the pin state to its previous value.
Initial pin state must be set upon pin setup (`setup_pin` command).

## Installation


This package has been tested and is known to work with the following versions:

- **MicroPython**: v1.23.0
- **Firmware**: v1.23.0 on 2024-06-02 (GNU 13.2.0 MinSizeRel)
- **Python**: 3.11

Install the package with `pip`:

```shell
pip install piconetcontrol
```

## Setup the Pico W

1. Connect the PicoW to your laptop/desktop/raspberrypi via a cable (recommended: use a raspberrypi)

2. Run the setup CLI and follow the prompt:
    ```shell
    piconetcontrol setup
    ```

    This will install the firmware, connect the board to WiFi, generate SSL certificates and copy necessary files to run the server

Verify successful setup by checking the onboard LED's blinking patterns (see details below).


### Static Address and IP Reservation

It is recommended to reserve a static IP for the Pico W, see your router's documentation.
As of today, mDNS for using a hostname (instead of an IP) seems to not be supposed on Pico W.


## Example Usage

We show a simple example both the shell and in Python.

### Shell Example

```bash
$ python run_client.py 192.168.1.111 12345 -c action=setup_pin pin=2 mode=output value=0 \
    -c action=read_pin pin=2 \
    -c action=write_pin pin=2 value=1 timeout=5 \
    -c action=read_pin pin=2
$ sleep 5 # wait for the write_pin timeout to expire
$ python run_client.py 192.168.1.111 12345 -c action=read_pin pin=2
```

### Python Example

```python
from time import sleep
from piconetcontrol.client import Client

client = Client('192.168.1.111', 12345)
client.send_commands([
    {"action": "setup_pin", "pin": 2, "mode": "output", "value": 0},
    {"action": "read_pin", "pin": 2},
    {"action": "write_pin", "pin": 2, "value": 1, "timeout": 5},
    {"action": "read_pin", "pin": 2},
])
# wait for the write_pin timeout to expire
sleep(5)
client.send_commands([
    {"action": "read_pin", "pin": 2},
])
```


## Server Blinking Patterns

The Pico W board is equipped with an LED that can be used to indicate the status of the server.

| **Status**               | **Pattern**                                                      |
|---------------------------|------------------------------------------------------------------|
| **Connecting to WiFi**    | 3 blinks of 100ms, 200ms apart, then 1s pause                   |
| **Server Listening**      | Infinite blinks of 1.5s on, 1.5s off                            |
| **Ongoing Connection**    | Continuous 20ms blinks, 100ms apart                             |


If the board isn't blinking:

* Server might not be running
* Board might be in light or deep sleep mode

  * If in light sleep, the server wakes up upon receiving a command


## Client-Server Communication Protocol

The server and the Raspberry Pi Pico W (client) communicate over a TCP/IP connection.
Message exchange occurs via *JSON-encoded dictionaries*.
Multiple instructions can be sent through a single connection,
a `\n` EOF signal is used to indicate the end of a command.
This enables sending long messages more than 1024 bytes (the buffer size).
The client sends a `\n\n` EOF signal to indicate no more commands are to be sent,
following what the server will close the connection.


## Commands

### GPIO Control


<table>
  <thead>
    <tr>
      <th>Command</th>
      <th>Description</th>
      <th>JSON Structure</th>
      <th>Response</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><b>Setup Pin</b></td>
      <td>Configure a GPIO pin as input or output, optionally setting its value.</td>
      <td>
        <pre><code>{
  "action": "setup_pin",
  "pin": 2,
  "mode": "output",
  "value": 0
}</code></pre>
      </td>
      <td>Echoes back the command.</td>
    </tr>
    <tr>
      <td><b>Set Pin Value</b></td>
      <td>Set a GPIO pin to a specified value (high or low) for a given duration.</td>
      <td>
        <pre><code>{
  "action": "write_pin",
  "pin": 2,
  "value": 1,
  "timeout": 5
}</code></pre>
      </td>
      <td>Echoes back the command (does not wait for timeout).</td>
    </tr>
    <tr>
      <td><b>Read Pin Value</b></td>
      <td>Request the current value (high or low) of a GPIO pin.</td>
      <td>
        <pre><code>{
  "action": "read_pin",
  "pin": 2
}</code></pre>
      </td>
      <td>Echoes back the command and includes the <code>value</code> field (high/low).</td>
    </tr>
  </tbody>
</table>

### Board Management


<table>
  <thead>
    <tr>
      <th>Command</th>
      <th>Description</th>
      <th>JSON Structure</th>
      <th>Response</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><b>Reset Board</b></td>
      <td>Reset the board using the <code>machine.reset()</code> method.</td>
      <td>
        <pre><code>{
  "action": "reset"
}</code></pre>
      </td>
      <td>Echoes back the command.</td>
    </tr>
    <tr>
      <td><b>Sleep for Low Power</b></td>
      <td>Enter a low-power state for a specified duration.</td>
      <td>
        <pre><code>{
  "action": "sleep",
  "deep": 1,
  "time_ms": 5000
}</code></pre>
      </td>
      <td>Echoes back the command.</td>
    </tr>
    <tr>
      <td><b>Get Resource Info</b></td>
      <td>Request information about the client's resources (e.g., memory, CPU).</td>
      <td>
        <pre><code>{
  "action": "get_resource_info"
}</code></pre>
      </td>
      <td>Echoes back the command and includes the <code>info</code> field.</td>
    </tr>
    <tr>
      <td><b>Get Server Version</b></td>
      <td>Request the version of the server software.</td>
      <td>
        <pre><code>{
  "action": "get_version"
}</code></pre>
      </td>
      <td>Echoes back the command and includes the <code>version</code> field.</td>
    </tr>
    <tr>
      <td><b>List Actions</b></td>
      <td>Request a list of available actions supported by the client.</td>
      <td>
        <pre><code>{
  "action": "list_actions"
}</code></pre>
      </td>
      <td>Echoes back the command and includes the <code>actions</code> field.</td>
    </tr>
    <tr>
      <td><b>Update Server Software</b></td>
      <td>Instruct the client to update the server software.</td>
      <td>
        <pre><code>{
  "action": "update"
}</code></pre>
      </td>
      <td>
        Updates the software and restarts the server. Reverts to the previous version on failure.
      </td>
    </tr>
  </tbody>
</table>
