import asyncio

from server_base import GPIOControlServerBase, is_raspberrypi_pico

if is_raspberrypi_pico():
    from server_pico import GPIOControlServerPicoW

    Server = GPIOControlServerPicoW
    args = {
        "port": 12345,
        "path_wifi_credentials": "config/config_wlan.json",
        "path_ssl_cert": "config/ec_cert.der",
        "path_ssl_key": "config/ec_key.der",
    }

else:
    from server_rpi import GPIOControlServerRPI

    Server = GPIOControlServerRPI


async def main(app: GPIOControlServerBase):
    await app.run()


if __name__ == "__main__":
    app = Server(**args)

    try:
        asyncio.run(main(app))
    finally:
        app.cleanup()
