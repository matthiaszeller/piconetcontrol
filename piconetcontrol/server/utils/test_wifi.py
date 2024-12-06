import json
from time import sleep, time

import network


def test_wifi(timeout: float = 15.0):
    with open("config/config_wlan.json") as fh:
        wifi = json.load(fh)

    wlan = network.WLAN(network.STA_IF)

    if wlan.isconnected():
        wlan.disconnect()

    wlan.active(True)
    wlan.connect(wifi["ssid"], wifi["pwd"])

    start = time()
    while time() - start < timeout and not wlan.isconnected():
        sleep(1)

    print(wlan.isconnected())


if __name__ == "__main__":
    test_wifi()
