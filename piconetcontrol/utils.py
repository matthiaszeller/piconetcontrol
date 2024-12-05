from pathlib import Path
from appdirs import user_config_dir
import json
import logging
from colorama import Fore, Style

_PATH_APP_CONFIG = None


class ColorFormatter(logging.Formatter):

    COLORS = {
        logging.DEBUG: Style.DIM,
        logging.INFO: '',
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Style.BRIGHT + Fore.RED
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, '')
        msg = super().format(record)

        return f'{color}{msg}{Style.RESET_ALL}'
    

def setup_logger() -> logging.Logger:
    logger = logging.getLogger('piconetcontrol')
    logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    fmt = ColorFormatter()
    ch.setFormatter(fmt)

    logger.addHandler(ch)

    return logger


logger = setup_logger()


def get_config_path() -> Path:
    global _PATH_APP_CONFIG

    if _PATH_APP_CONFIG:
        return _PATH_APP_CONFIG
    
    _PATH_APP_CONFIG = Path(user_config_dir('piconetcontrol'))
    _PATH_APP_CONFIG.mkdir(exist_ok=True)
    return _PATH_APP_CONFIG


def load_config() -> dict | None:
    try:
        return json.loads(get_config_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None

