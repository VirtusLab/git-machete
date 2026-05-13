"""High-level wrappers around subprocess that respect verbose/debug mode.

Compared to `._subproc` (used internally for capability detection),
the helpers here:

* log the command being run when `verbose_mode` / `debug_mode` /
  `measure_command_time` is set (via `print_fmt`),
* redact GitHub / GitLab access tokens from captured stdout/stderr,
* update the cached "current directory still exists" flag,
* delegate the actual `subprocess` call to `_subproc._run_cmd` /
  `_subproc._popen_cmd` so that tests can patch the former without
  losing the surrounding logic.
"""

import os
import re
import sys
import time
from typing import Dict, Optional

from . import _subproc, debug_log
from ._subproc import PopenResult, _popen_cmd
from .debug_log import debug
from .fs import get_current_directory_or_none
from .markup import escape_markup, print_fmt
from .paths import AbsPath, Path

# === Mutable runtime flags ===
#
# `verbose_mode` / `measure_command_time` toggle command logging; set by
# `cli.py` (and the env var `GIT_MACHETE_MEASURE_COMMAND_TIME`).
# `current_directory_confirmed_to_exist` is an internal cache used to
# avoid a `getcwd()` syscall before every command.
current_directory_confirmed_to_exist: bool = False
measure_command_time: bool = os.environ.get('GIT_MACHETE_MEASURE_COMMAND_TIME') == 'true'  # undocumented, internal
verbose_mode: bool = False


def run_cmd(cmd: str, *args: str, cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None) -> int:
    chdir_upwards_until_current_directory_exists()

    flat_cmd: str = get_cmd_shell_repr(cmd, *args, env=env)
    escaped_flat_cmd = escape_markup(flat_cmd)

    def print_command(markup: str) -> None:
        if measure_command_time:  # pragma: no cover
            print_fmt(markup + " ... ", file=sys.stderr, newline=False)
        else:
            print_fmt(markup, file=sys.stderr)

    if debug_log.debug_mode:
        print_command(f"<b>>>> {escaped_flat_cmd}</b>")
    elif verbose_mode or measure_command_time:
        print_command(escaped_flat_cmd)

    start = time.time()
    # Looked up via the `_subproc` module so that
    # `mock.patch('git_machete.utils._subproc._run_cmd', ...)` is honoured.
    exit_code: int = _subproc._run_cmd(cmd, *args, cwd=cwd, env=env)
    if measure_command_time:  # pragma: no cover
        end = time.time()
        elapsed_ms = int((end - start) * 1e3)
        print(f"{elapsed_ms} ms")

    # Let's defensively assume that every command executed via run_cmd
    # (but not via popen_cmd) can make the current directory disappear.
    # In practice, it's mostly 'git checkout' that carries such risk.
    mark_current_directory_as_possibly_non_existent()

    if debug_log.debug_mode and exit_code != 0:
        print_fmt(f"<dim>&lt;exit code: {exit_code}>\n</dim>", file=sys.stderr)
    return exit_code


def mark_current_directory_as_possibly_non_existent() -> None:
    global current_directory_confirmed_to_exist
    current_directory_confirmed_to_exist = False


def chdir_upwards_until_current_directory_exists() -> None:
    global current_directory_confirmed_to_exist
    if not current_directory_confirmed_to_exist:
        current_directory: Optional[AbsPath] = get_current_directory_or_none()
        if not current_directory:
            while not current_directory:
                # Note: 'os.chdir' only affects the current process and its subprocesses;
                # it doesn't propagate to the parent process (which is typically a shell).
                os.chdir(os.path.pardir)
                current_directory = get_current_directory_or_none()
            debug(f"current directory did not exist, chdired up into {current_directory}")
        current_directory_confirmed_to_exist = True


def popen_cmd(cmd: str, *args: str, cwd: Optional[Path] = None,
              env: Optional[Dict[str, str]] = None, hide_debug_output: bool = False, input: Optional[str] = None) -> PopenResult:
    chdir_upwards_until_current_directory_exists()

    flat_cmd = get_cmd_shell_repr(cmd, *args, env=env)
    escaped_flat_cmd = escape_markup(flat_cmd)

    def print_command(markup: str) -> None:
        if measure_command_time:  # pragma: no cover
            print_fmt(markup + " ... ", file=sys.stderr, newline=False)
        else:
            print_fmt(markup, file=sys.stderr)

    if debug_log.debug_mode:
        print_command(f"<b>>>> {escaped_flat_cmd}</b>")
    elif verbose_mode or measure_command_time:
        print_command(escaped_flat_cmd)

    start = time.time()
    exit_code, stdout, stderr = result = _popen_cmd(cmd, *args, cwd=cwd, env=env, input=input)
    if measure_command_time:  # pragma: no cover
        end = time.time()
        elapsed_ms = int((end - start) * 1e3)
        print(f"{elapsed_ms} ms")

    # GitHub tokens are likely to appear e.g. in the output of `git config -l`:
    # `https://<TOKEN>@github.com/org/repo.git` is a supported URL format for git remotes.
    def redact_tokens(input: str) -> str:
        return re.sub(debug_log.CODE_HOSTING_TOKEN_PREFIX_REGEX + '[a-zA-Z0-9]+', '<REDACTED>', input)
    stdout = redact_tokens(stdout)
    stderr = redact_tokens(stderr)

    if debug_log.debug_mode:
        if exit_code != 0:
            print_fmt(f"<red>&lt;exit code: {exit_code}>\n</red>", file=sys.stderr)
        if stdout:
            if hide_debug_output:
                print_fmt("<dim>&lt;stdout>:</dim>\n<dim>&lt;REDACTED></dim>", file=sys.stderr)
            else:
                print_fmt(f"<dim>&lt;stdout>:</dim>\n<dim>{escape_markup(stdout)}</dim>", file=sys.stderr)
        if stderr:
            if hide_debug_output:
                print_fmt("<dim>&lt;stderr>:</dim>\n<dim>&lt;REDACTED></dim>", file=sys.stderr)
            else:
                print_fmt(f"<dim>&lt;stderr>:</dim>\n<red>{escape_markup(stderr)}</red>", file=sys.stderr)

    return result


def get_cmd_shell_repr(cmd: str, *args: str, env: Optional[Dict[str, str]]) -> str:
    def shell_escape(arg: str) -> str:
        return re.sub("[() <>$]", r"\\\g<0>", arg) \
            .replace("\t", "$'\\t'") \
            .replace("\n", "$'\\n'")

    env = env if env is not None else {}
    # We don't want to include the env vars that are inherited from the environment of git-machete process
    env_repr = [k + "=" + shell_escape(v) for k, v in env.items() if k not in os.environ]
    return " ".join(env_repr + [cmd] + [shell_escape(arg) for arg in args])
