from pathlib import Path


def pack_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent
