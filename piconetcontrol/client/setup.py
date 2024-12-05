
import shlex
from getpass import getpass
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
import sys
import json
from time import sleep
import pyudev
import re
from urllib.request import urlopen
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from colorama import Fore, Style

from piconetcontrol.utils import logger
from simple_term_menu import TerminalMenu

FILE_WIFI = 'config/config_wlan.json'

PATH_SERVER_CODE = Path(__file__).parents[1].joinpath('server')
PATH_MICROPYTHON_UTILS = PATH_SERVER_CODE / 'utils'
FILE_TEST_WIFI = PATH_MICROPYTHON_UTILS / 'test_wifi.py'
FILE_WIPE_ROOT = PATH_MICROPYTHON_UTILS / 'wipe_root.py'
FILE_GEN_SSH = Path(__file__).with_name('gen_ssl.sh')
REGEX_VERSION = re.compile(r'v(\d+\.\d+\.\d+)')
URL_FIRMWARE = 'https://micropython.org/download/RPI_PICO_W/'


def run_command(cmd: str, cwd: str = None):
    logger.debug(f'running command `{cmd}`')
    return subprocess.check_output(
        shlex.split(cmd),
        text=True,
        cwd=cwd
    )


def fetch_available_firmwares() -> list[tuple[str, str, str]]:
    """Fetch online the list of firmware versions for PicoW"""
    soup = BeautifulSoup(
        urlopen(URL_FIRMWARE).read(),
        'html.parser'
    )
    versions = soup.select('div a[href$=".uf2"]')
    if not versions:
        raise RuntimeError(f'could not parse {URL_FIRMWARE}')
    
    out = []
    for tag in versions:
        text = tag.text.removesuffix('.uf2').strip()
        version = REGEX_VERSION.search(text).groups(1)[0]
        url = urljoin(URL_FIRMWARE, tag.attrs['href'])
        out.append((version, text, url))

    return out


def detect_bootloader_mode() -> str | None:
    context = pyudev.Context()
    for device in context.list_devices(subsystem='block', DEVTYPE='disk'):
        if 'RPI_RP2' in device.properties.get('ID_USB_SERIAL', ''):
            return device.device_node
        
    return None


def install_firmware(download_url: str, device_path: str):
    with NamedTemporaryFile('wb') as file:
        # download
        data = urlopen(download_url).read()
        file.write(data)
        file.seek(0)
        # copy file to bootloader
        run_command(
            f'sudo dd if={file.name} of={device_path} bs=512 status=progress'
        )   


def show_menu(options: list[str], title: str = None) -> int:
    return TerminalMenu(
        options, 
        clear_menu_on_exit=False, 
        raise_error_on_interrupt=True,
        title=title
    ).show()


def mp_list_devices() -> list[str]:
    output = run_command('mpremote devs').strip()
    if not output:
        return []
    
    return [
        line.split()[0]
        for line in output.split('\n')
    ]


def mp_get_version() -> str:
    out = run_command('mpremote exec "import sys; print(sys.version)"')
    version = REGEX_VERSION.search(out)

    if not version:
        raise RuntimeError('could not detect version')
    
    return version.groups(1)[0]


def mp_mkdir(folder: str):
    try:
        run_command(f'mpremote fs mkdir {folder}')
    except subprocess.CalledProcessError:
        pass  # already exists


def mp_file_exists(file: str) -> bool:
    try:
        run_command(f'mpremote fs cat {file}')
        return True
    except subprocess.CalledProcessError:
        return False


def mp_test_wifi() -> bool:
    output = run_command(f'mpremote run {FILE_TEST_WIFI}').strip()
    logger.debug('result of wifi test:', output)
    return output == 'True'


def mp_write_string(content: str, file: str):
    with NamedTemporaryFile('w') as tmp:
        tmp.write(content)
        tmp.seek(0)

        run_command(f'mpremote cp {tmp.name} :{file}')


def list_wifis() -> list[str]:
    if sys.platform.lower() != 'linux':
        raise NotImplementedError('not implemented for other than linux')

    # run_command('sudo nmcli device wifi rescan')
    wifis = run_command('nmcli -t -f SSID dev wifi').strip().split('\n')
    return list(set(wifis))


def prompt_wifi_credentials() -> tuple[str, str]:
    wifis = list_wifis()
    assert wifis, 'no detected wifi'
    idx = show_menu(wifis, title='WiFi SSID')
    pwd = getpass('Wifi password: ')

    return wifis[idx], pwd


def setup_ssl():
    with TemporaryDirectory() as folder:
        run_command(f'bash {FILE_GEN_SSH}', cwd=folder)
        run_command(f'mpremote fs cp {folder}/ec_key.der :config/ec_key.der')
        run_command(f'mpremote fs cp {folder}/ec_cert.der :config/ec_cert.der')


def main():
    # Figure out connected device with vs without installed firmware
    bootloader_device = detect_bootloader_mode()
    devices = mp_list_devices()

    if not bootloader_device and not devices:
        logger.error('No pico device detected')
        return
    elif len(devices) > 1:
        # if more than one device, would need to specify which device to run with `mpremote`,
        # the whole script would require refacoring
        raise NotImplementedError('more than one micropython device found')
    
    firmwares = fetch_available_firmwares()
    do_install_firmware = True
    
    if bootloader_device:
        logger.info(f'picoW detected in {Fore.BLUE}booloader mode{Style.RESET_ALL}: {bootloader_device}')
        logger.info('Either firmware is not installed, or you pressed bootsel button')
    
    else:
        devname = devices[0].split()[0]
        version = mp_get_version()
        logger.info(f'Device found on {devname} with version {version}')
        logger.warning(f'Latest available firmware version: {firmwares[0][0]}')

        idx = show_menu(
            ['Yes', 'No'],
            title='Do you want to install another firmware version?'
        )
        if idx == 1:
            do_install_firmware = False
        else:
            # put device in bootloader mode
            run_command(f'mpremote bootloader')
            bootloader_device = detect_bootloader_mode()
            sleep(2)
            logger.info(f'put device in bootloader mode, available at {bootloader_device}')

    # Install firmware
    if do_install_firmware:
        idx = show_menu(
            [e[1] for e in firmwares],
            title='Select the firmware version to download and install'
        )
        firmware_url = firmwares[idx][2]
        install_firmware(firmware_url, bootloader_device)
        sleep(2)
        devices = mp_list_devices()
        assert len(devices) == 1, f'expected 1 pico W device after firmware installation, found {len(devices)}'
        logger.info(f'New firmware version: {mp_get_version()}')
    
    # Warn user
    logger.warning("Running this script will wipe the device's filesystem.")
    idx = show_menu(
        ['Yes', 'No'],
        title="Are you sure you wanna continue?"
    )
    if idx != 0:
        return

    # Clear filesystem
    logger.info('wiping out microcontroller filesystem ...')
    run_command(f'mpremote run {FILE_WIPE_ROOT}')

    # Reset board
    # WARNING: this might prevent a bug when connecting to a WiFi with a wrong password,
    #          where `wlan.isconnected` is True if the board connected to the same Wifi 
    #          with correct password
    logger.info('Resetting the board ...')
    run_command('mpremote reset')
    sleep(1)  # give some time for reset

    # Wifi
    logger.info('Setting up Wifi ...')
    mp_mkdir('config')

    while True:
        ssid, pwd = prompt_wifi_credentials()
        wifi_cfg = json.dumps({'ssid': ssid, 'pwd': pwd}, indent=2)
        mp_write_string(wifi_cfg, FILE_WIFI)

        logger.info('Attempting connection ...')
        if mp_test_wifi():
            break

        logger.info('Connection failed. Try again.')
    
    logger.info('Connection sucessfull')

    # Copy python files
    logger.info('Setting up server files ...')
    for file in ('main.py', 'server_base.py', 'server_pico.py'):
        run_command(f'mpremote fs cp {PATH_SERVER_CODE / file} :{file}')
    
    setup_ssl()

    # Reset to run the server
    run_command(f'mpremote reset')
