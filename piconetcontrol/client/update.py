import re
import zlib
from base64 import b64encode
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PATH_SERVER_CODE = Path(__file__).parents[1] / "server"


def _find_code_version(file_content: str) -> str:
    res = re.search(r"\s+_?VERSION = \"(.+)\"", file_content)
    if not res:
        raise ValueError("Could not find version in file")

    return res.group(1)


def _create_zip_from_files(file_paths: list[Path]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zipf:
        for file_path in file_paths:
            zipf.write(file_path)

    buffer.seek(0)
    return buffer.getvalue()


def get_local_version() -> str:
    return _find_code_version((PATH_SERVER_CODE / "server_base.py").read_text())


def get_update_files(compress: bool = True) -> dict[str, str]:
    def process_file(fpath: Path) -> str:
        contents = fpath.read_text()
        if compress:
            contents = zlib.compress(contents.encode())
            contents = b64encode(contents).decode()

        return contents

    # mapping remote_location -> local_location
    files = {
        "main.py": PATH_SERVER_CODE / "main.py",
        "server_base.py": PATH_SERVER_CODE / "server_base.py",
        "server_pico.py": PATH_SERVER_CODE / "server_pico.py",
    }
    # read local files
    file_contents = {rpath: process_file(lpath) for rpath, lpath in files.items()}

    return file_contents
