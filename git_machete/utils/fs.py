"""File-system helpers.

Most of these are thin wrappers over `os` / `os.path`; a few handle
quirks that bit us in the wild (e.g., `os.path.isdir` returning a false
positive for the current directory after the directory has been deleted).
"""

import os
import sys
from typing import Optional

from .debug_log import debug


def does_directory_exist(path: str) -> bool:
    try:
        # Note that os.path.isdir itself (without os.path.abspath) isn't reliable
        # since it returns a false positive (True) for the current directory when it doesn't exist
        return os.path.isdir(os.path.abspath(path))
    except OSError:  # pragma: no cover
        return False


def get_current_directory_or_none() -> Optional[str]:
    try:
        return os.getcwd()
    except OSError:
        # This happens when current directory does not exist (typically: has been deleted)
        return None


def is_executable(path: str) -> bool:
    return os.access(path, os.X_OK)


def find_executable(executable: str) -> Optional[str]:
    base, ext = os.path.splitext(executable)

    if (sys.platform == 'win32' or os.name == 'os2') and (ext != '.exe'):
        executable += ".exe"  # pragma: no cover; we don't collect coverage on Windows due to poor performance

    if os.path.isfile(executable) and is_executable(executable):
        return executable

    path = os.environ.get('PATH', os.defpath)
    paths = path.split(os.pathsep)
    for p in paths:
        f = os.path.join(p, executable)
        if os.path.isfile(f) and is_executable(f):
            debug(f"found {executable} at {f}")
            return f
    return None


def slurp_file(path: str) -> str:
    with open(path, 'r') as file:
        return file.read()
