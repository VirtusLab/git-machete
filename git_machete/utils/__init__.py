"""Public surface of `git_machete.utils`.

The implementation is split across submodules (see the `# === ... ===`
boundaries in the original `utils.py` for the historical layout):

* `._subproc` - bare `subprocess` wrappers that never log
* `.terminal` - TTY detection and ANSI escape-code constants
* `.paths`    - POSIX-style path helpers
* `.collections_utils` - generic iterable / sequence helpers
* `.markup`   - markup language and styled output (`print_fmt`, ...)
* `.debug_log` - `debug()` and friends
* `.fs`       - file-system helpers
* `.cmd`      - high-level `run_cmd` / `popen_cmd` (with logging)
* `.exceptions` - exception classes and small enums

This module re-exports every public symbol that used to live in `utils.py`
so that `from git_machete.utils import X` and `utils.X` continue to work
unchanged across the codebase. The mutable runtime flags (`debug_mode`,
`verbose_mode`, the two `use_ansi_escapes_in_*` flags, ...) are owned by
this package object so that submodules and external callers (e.g.
`cli.py`) all read and write the same single binding via `utils.X`.

Submodules access the mutable flags through a *lazy* (function-local)
`from git_machete import utils as _utils` import - this is what lets pylint's
`cyclic-import` checker stay happy while still preserving the
"single source of truth on the package" invariant.

The re-exported names are listed in `__all__` so that `autoflake` (run from
the `isort` testenv) doesn't strip them as "unused".
"""

import os
import sys

from ._subproc import PopenResult, _popen_cmd, _run_cmd
from .cmd import (chdir_upwards_until_current_directory_exists,
                  get_cmd_shell_repr,
                  mark_current_directory_as_possibly_non_existent, popen_cmd,
                  run_cmd)
from .collections_utils import (excluding, find_or_none, flat_map,
                                get_non_empty_lines, get_second, index_or_none,
                                map_truthy_only, tupled)
from .debug_log import compact_dict, debug, hex_repr
from .exceptions import (NEW_ISSUE_LINK, ExitCode, InteractionStopped,
                         MacheteException, ParsableEnum,
                         UnderlyingGitException, UnexpectedMacheteException)
from .fs import (does_directory_exist, find_executable, get_current_date,
                 get_current_directory_or_none, is_executable, slurp_file)
from .markup import (_fmt, colored_yes_no, escape_markup, green_ok, input_fmt,
                     pretty_choices, print_fmt, warn)
from .paths import abspath_posix, join_paths_posix, relpath_posix
from .terminal import (AnsiInputCodes, BasicTerminalAnsiOutputCodes,
                       FullTerminalAnsiOutputCodes, get_terminal_height,
                       is_stderr_a_tty, is_stdout_a_tty,
                       is_terminal_fully_fledged)

__all__ = [
    # Token-redaction constants (defined below)
    "CODE_HOSTING_TOKEN_PREFIXES",
    "CODE_HOSTING_TOKEN_PREFIX_REGEX",
    # ._subproc
    "PopenResult", "_popen_cmd", "_run_cmd",
    # .cmd
    "chdir_upwards_until_current_directory_exists", "get_cmd_shell_repr",
    "mark_current_directory_as_possibly_non_existent", "popen_cmd", "run_cmd",
    # .collections_utils
    "excluding", "find_or_none", "flat_map", "get_non_empty_lines",
    "get_second", "index_or_none", "map_truthy_only", "tupled",
    # .debug_log
    "compact_dict", "debug", "hex_repr",
    # .exceptions
    "NEW_ISSUE_LINK", "ExitCode", "InteractionStopped", "MacheteException",
    "ParsableEnum", "UnderlyingGitException", "UnexpectedMacheteException",
    # .fs
    "does_directory_exist", "find_executable", "get_current_date",
    "get_current_directory_or_none", "is_executable", "slurp_file",
    # .markup
    "_fmt", "colored_yes_no", "escape_markup", "green_ok", "input_fmt",
    "pretty_choices", "print_fmt", "warn",
    # .paths
    "abspath_posix", "join_paths_posix", "relpath_posix",
    # .terminal
    "AnsiInputCodes", "BasicTerminalAnsiOutputCodes",
    "FullTerminalAnsiOutputCodes", "get_terminal_height", "is_stderr_a_tty",
    "is_stdout_a_tty", "is_terminal_fully_fledged",
    # Mutable runtime flags (defined below)
    "current_directory_confirmed_to_exist", "debug_mode",
    "measure_command_time", "use_ansi_escapes_in_stderr",
    "use_ansi_escapes_in_stdout", "verbose_mode",
]

# === Mutable runtime flags ===
#
# These live on the *package* (not on a leaf submodule) so:
#  * external callers can read/write them via `git_machete.utils.X`,
#  * submodules can do the same via a function-local
#    `from git_machete import utils as _utils` and observe the latest value
#    at every call.

# Avoid checking for current directory's existence every time any command is
# being popened or run.
current_directory_confirmed_to_exist: bool = False

use_ansi_escapes_in_stdout: bool = sys.stdout.isatty()
use_ansi_escapes_in_stderr: bool = sys.stderr.isatty()
debug_mode: bool = False
measure_command_time: bool = os.environ.get('GIT_MACHETE_MEASURE_COMMAND_TIME') == 'true'  # undocumented, internal
verbose_mode: bool = False

# === Token-redaction constants ===
#
# https://github.blog/2021-04-05-behind-githubs-new-authentication-token-formats/
# https://docs.gitlab.com/ee/security/token_overview.html#gitlab-tokens
CODE_HOSTING_TOKEN_PREFIXES = ['ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_', 'glpat-']
CODE_HOSTING_TOKEN_PREFIX_REGEX = '(' + '|'.join(CODE_HOSTING_TOKEN_PREFIXES) + ')'
