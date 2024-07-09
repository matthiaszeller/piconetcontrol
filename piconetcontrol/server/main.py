import asyncio
import os

import machine


def restore_file(file_path: str):
    print("restoring file", file_path)
    os.rename("_" + file_path, file_path)


try:
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

except Exception:
    # check if update has just been made
    try:
        with open("update.txt", "r") as fh:
            updated = fh.read().split(",")
    except Exception:
        # no update just made
        updated = None

    if updated:
        with open("logs.txt", "w") as fh:
            fh.write("update failed, attempting rollback...")

        for file in updated:
            restore_file(file)

        os.remove("update.txt")
        with open("logs.txt", "a") as fh:
            fh.write("rollback successful... resetting")

        machine.reset()
