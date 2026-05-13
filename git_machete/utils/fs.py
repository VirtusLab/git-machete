"""File-system helpers.

Most of these are thin wrappers over `os` / `os.path`; a few handle
quirks that bit us in the wild (e.g., `os.path.isdir` returning a false
positive for the current directory after the directory has been deleted).
"""

import os
import sys
from typing import Optional

from .debug_log import debug
from .paths import AbsPath, Path, abs_path, join_paths


def does_directory_exist(path: Path) -> bool:
    try:
        # Note that os.path.isdir itself (without os.path.abspath) isn't reliable
        # since it returns a false positive (True) for the current directory when it doesn't exist
        return os.path.isdir(os.path.abspath(path))
    except OSError:  # pragma: no cover
        return False


def get_current_directory_or_none() -> Optional[AbsPath]:
    try:
        return AbsPath.of(os.getcwd())
    except OSError:
        # This happens when current directory does not exist (typically: has been deleted)
        return None


def is_executable(path: Path) -> bool:
    return os.access(path, os.X_OK)


def find_executable(executable: str) -> Optional[AbsPath]:
    base, ext = os.path.splitext(executable)

    if (sys.platform == 'win32' or os.name == 'os2') and (ext != '.exe'):
        executable += ".exe"  # pragma: no cover; we don't collect coverage on Windows due to poor performance

    if os.path.isfile(executable) and is_executable(Path.of(executable)):
        return abs_path(executable)

    path = os.environ.get('PATH', os.defpath)
    paths = path.split(os.pathsep)
    for p in paths:
        f: Path = join_paths(p, executable)
        if os.path.isfile(f) and is_executable(f):
            debug(f"found {executable} at {f}")
            return abs_path(f)
    return None


def slurp_file(path: Path) -> str:
    with open(path, 'r') as file:
        return file.read()
