"""TTY detection and ANSI escape-code constants.

The module deliberately depends only on :mod:`._subproc`, never on
:mod:`.markup` or :mod:`.cmd` - because the markup/command-execution paths
themselves call :func:`is_terminal_fully_fledged` to decide on ANSI styling,
and pulling in those modules here would re-introduce the recursion that was
fixed by switching to :func:`_popen_cmd` below.
"""

import os
import sys
from typing import Optional

from ._subproc import _popen_cmd


def is_stdout_a_tty() -> bool:
    return sys.stdout.isatty()


def is_stderr_a_tty() -> bool:
    return sys.stderr.isatty()


def get_terminal_height() -> Optional[int]:
    """Return the height (number of lines) of the terminal, or `None` if unavailable."""
    try:
        return os.get_terminal_size().lines
    except (OSError, AttributeError):
        return None


_terminal_fully_fledged: Optional[bool] = None


def is_terminal_fully_fledged() -> bool:
    global _terminal_fully_fledged
    if _terminal_fully_fledged is None:
        # Note: we deliberately use the lower-level `_popen_cmd` here (rather than `popen_cmd` from
        # `git_machete.utils.cmd`) to avoid an infinite recursion in verbose/debug mode: `popen_cmd`
        # would log the command via `print_fmt` -> `_fmt` -> `is_terminal_fully_fledged`, which is
        # exactly the function we're inside (and the cache hasn't been populated yet at that point).
        try:
            stdout = _popen_cmd('tput', 'colors').stdout
            # In CI, this line is only covered by tests on macOS, which don't run on PRs by default.
            # Let's skip to keep coverage results consistent between develop/master and PRs.
            number_of_supported_colors = int(stdout)  # pragma: no cover
        except Exception:
            # If we cannot retrieve the number of supported colors, let's defensively assume it's low.
            number_of_supported_colors = 8
        _terminal_fully_fledged = number_of_supported_colors >= 256
    return _terminal_fully_fledged


# === ANSI escape code classes ===

class AnsiInputCodes:
    """Fixed escape sequences for reading keyboard input.

    These are standard VT100/xterm codes and are not affected by terminal
    capabilities (color depth, etc.).
    """
    ESCAPE = '\033'
    CSI = '\033['  # Control Sequence Introducer

    KEY_UP = '\033[A'
    KEY_DOWN = '\033[B'
    KEY_RIGHT = '\033[C'
    KEY_LEFT = '\033[D'
    KEY_SHIFT_UP = '\033[1;2A'
    KEY_SHIFT_DOWN = '\033[1;2B'

    KEYS_ENTER = ('\r', '\n')
    KEY_SPACE = ' '
    KEY_CTRL_C = '\003'


class FullTerminalAnsiOutputCodes:
    CSI = '\033['  # Control Sequence Introducer

    # Text styling
    ENDC = '\033[0m'
    ENDC_UNDERLINE = '\033[24m'
    ENDC_BOLD_DIM = '\033[22m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    ORANGE = '\033[00;38;5;208m'
    RED = '\033[91m'
    REVERSE_VIDEO = '\033[7m'

    # Cursor control
    HIDE_CURSOR = '\033[?25l'
    SHOW_CURSOR = '\033[?25h'
    CLEAR_TO_END = '\033[J'

    @classmethod
    def cursor_up(cls, num_lines: int) -> str:
        """CSI n A — move cursor up by num_lines."""
        return cls.CSI + str(num_lines) + "A"


class BasicTerminalAnsiOutputCodes(FullTerminalAnsiOutputCodes):
    """Output codes adapted to the 8-bit terminal's capabilities."""

    UNDERLINE = '\033[36m'  # cyan
    ENDC_UNDERLINE = FullTerminalAnsiOutputCodes.ENDC
    ORANGE = FullTerminalAnsiOutputCodes.YELLOW
    RED = '\033[31m'  # dark red
