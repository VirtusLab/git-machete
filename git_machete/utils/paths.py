"""POSIX-style path utilities.

Forward slashes are used consistently across platforms to match Git's own
representation; this works in all Windows environments (Git Bash,
PowerShell, CMD) as well as on Unix-like systems.
"""

import os
from pathlib import Path, PurePosixPath


def join_paths_posix(*paths: str) -> str:
    return str(PurePosixPath(*paths))


def abspath_posix(path: str) -> str:
    return Path(path).resolve().as_posix()


def relpath_posix(path: str) -> str:
    rel = os.path.relpath(path)
    return Path(rel).as_posix()
