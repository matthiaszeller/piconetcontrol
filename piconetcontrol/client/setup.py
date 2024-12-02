
import shlex
from getpass import getpass
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
import sys
import json
from time import sleep

from simple_term_menu import TerminalMenu

FILE_WIFI = 'config/config_wlan.json'

PATH_SERVER_CODE = Path(__file__).parents[1].joinpath('server')
PATH_MICROPYTHON_UTILS = PATH_SERVER_CODE / 'utils'
FILE_TEST_WIFI = PATH_MICROPYTHON_UTILS / 'test_wifi.py'
FILE_WIPE_ROOT = PATH_MICROPYTHON_UTILS / 'wipe_root.py'
FILE_GEN_SSH = Path(__file__).with_name('gen_ssl.sh')


def run_command(cmd: str, cwd: str = None):
    print('running', cmd)
    return subprocess.check_output(
        shlex.split(cmd),
        text=True,
        cwd=cwd
    )


def show_menu(options: list[str], title: str = None) -> int:
    return TerminalMenu(
        options, 
        clear_menu_on_exit=False, 
        raise_error_on_interrupt=True,
        title=title
    ).show()


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
    print('result of wifi test:', output)
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
    # Ensure found devices
    devices = run_command('mpremote devs').strip().split('\n')
    if not devices:
        raise RuntimeError('no micropython device found')
    elif len(devices) > 1:
        # if more than one device, would need to specify which device to run with `mpremote`,
        # the whole script would require refacoring
        raise NotImplementedError('more than one micropython device found')

    devname = devices[0].split()[0]
    print('detected device', devname)
    
    # Warn user
    idx = show_menu(
        ['Yes', 'No'],
        title='Running this script will reset the device. Are you sure you wanna continue?'
    )
    if idx != 0:
        return

    # Clear filesystem
    print('wiping out microcontroller filesystem ...')
    run_command(f'mpremote run {FILE_WIPE_ROOT}')

    # Reset board
    # WARNING: this might prevent a bug when connecting to a WiFi with a wrong password,
    #          where `wlan.isconnected` is True if the board connected to the same Wifi 
    #          with correct password
    print('Resetting the board ...')
    run_command('mpremote reset')
    sleep(1)  # give some time for reset

    # Wifi
    print('Setting up Wifi ...')
    mp_mkdir('config')

    while True:
        ssid, pwd = prompt_wifi_credentials()
        wifi_cfg = json.dumps({'ssid': ssid, 'pwd': pwd}, indent=2)
        mp_write_string(wifi_cfg, FILE_WIFI)

        print('Attempting connection ...')
        if mp_test_wifi():
            break

        print('Connection failed. Try again.')
    
    print('Connection sucessfull')

    # Copy python files
    print('Setting up server files ...')
    for file in ('main.py', 'server_base.py', 'server_pico.py'):
        run_command(f'mpremote fs cp {PATH_SERVER_CODE / file} :{file}')
    
    setup_ssl()

    # Reset to run the server
    run_command(f'mpremote reset')


if __name__ == '__main__':
    main()
