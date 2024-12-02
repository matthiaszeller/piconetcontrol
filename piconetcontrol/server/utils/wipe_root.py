import os

def delete_recursive(path):
    if os.stat(path)[0] & 0x4000:  # Directory check
        for item in os.listdir(path):
            item_path = f"{path}/{item}"
            delete_recursive(item_path)
        os.rmdir(path)  # Remove the now-empty directory
        print(f"Deleted directory: {path}")
    else:
        os.remove(path)  # Remove file
        print(f"Deleted file: {path}")

def wipe_root():
    for item in os.listdir():
        delete_recursive(item)


if __name__ == '__main__':
    # safeguard
    import sys
    assert 'micropython' in sys.version.lower(), 'no micropython detected'

    wipe_root()
