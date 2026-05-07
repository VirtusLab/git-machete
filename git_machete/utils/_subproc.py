"""Lowest-level subprocess wrappers used elsewhere in :mod:`git_machete.utils`.

These helpers deliberately do **not** print anything (no debug/verbose
logging), so they can be safely called from code paths that themselves
implement that logging - in particular from
:func:`git_machete.utils.terminal.is_terminal_fully_fledged`, whose result
the logging path itself depends on.
"""

import subprocess
from typing import Dict, NamedTuple, Optional


class PopenResult(NamedTuple):
    exit_code: int
    stdout: str
    stderr: str


def _run_cmd(cmd: str, *args: str, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> int:
    return subprocess.run([cmd] + list(args), stdout=None, stderr=None, cwd=cwd, env=env).returncode


def _popen_cmd(cmd: str, *args: str,
               cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None, input: Optional[str] = None) -> PopenResult:
    stdin = subprocess.PIPE if input is not None else None
    input_bytes = input.encode('utf-8') if input else None

    process = subprocess.Popen([cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=stdin, cwd=cwd, env=env)
    stdout_bytes, stderr_bytes = process.communicate(input_bytes)
    exit_code: int = process.returncode  # must be retrieved after process.communicate()
    stdout: str = stdout_bytes.decode('utf-8')
    stderr: str = stderr_bytes.decode('utf-8')
    return PopenResult(exit_code, stdout, stderr)
