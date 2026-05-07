import os
import subprocess
import sys
from contextlib import AbstractContextManager, contextmanager
from tempfile import mkdtemp
from typing import Any, Callable, Iterator

from tests.shell import set_file_executable, write_to_file


@contextmanager
def overridden_environment(**environ: str) -> Iterator[None]:
    old_environ = dict(os.environ)
    os.environ.update(environ)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)


# Not including [None] type argument to maintain compatibility with Python <= 3.8
def fixed_author_and_committer_date_in_past() -> AbstractContextManager:  # type: ignore[type-arg]
    # It doesn't matter WHAT this fixed timestamp is, as long as it's fixed
    # (and hence, commit hashes are fixed).
    fixed_committer_and_author_date = 'Mon 20 Aug 2018 20:19:19 +0200'
    return overridden_environment(
        GIT_COMMITTER_DATE=fixed_committer_and_author_date,
        GIT_AUTHOR_DATE=fixed_committer_and_author_date
    )


@contextmanager
def temporary_home_directory() -> Iterator[str]:
    """Override `HOME` (POSIX) and `USERPROFILE` (Windows) to point at a
    fresh empty temp directory, and yield its path.

    Both `os.path.expanduser('~/...')` and `pathlib.Path.home()` consult
    these env vars on every call (no caching), so anything resolving paths
    relative to `~` will see the temp dir for the duration of the
    with-block. The test can then drop real files (e.g. `.github-token`,
    `.config/hub`) into the yielded path - which is preferable to mocking
    `os.path.isfile` / `git_machete.utils.fs.slurp_file`."""
    home = mkdtemp()
    with overridden_environment(HOME=home, USERPROFILE=home):
        yield home


@contextmanager
def fake_executables_on_path(**executables: str) -> Iterator[str]:
    """For the duration of the with-block, write fake executables to a
    fresh temporary directory and PREPEND that directory to `PATH`.

    Each keyword argument maps an executable name (e.g. `gh`, `glab`) to a
    Python script body. The wrappers invoke the body with the original CLI
    args, so the body can inspect `sys.argv[1:]`, `print()` to
    stdout/stderr, and set the exit code via `sys.exit(...)` - mimicking a
    real CLI tool from the SUT's perspective.

    Two wrappers are written per executable so `shutil.which(name)` finds
    the fake on either platform:
      - POSIX: an extensionless `name` shell script with the executable
        bit set.
      - Windows: a `name.cmd` batch file (Windows resolves the `.cmd`
        extension via `PATHEXT`).

    Both wrappers force `PYTHONIOENCODING=utf-8` so `print()` works
    consistently across hosts (especially Windows, whose default stdio
    encoding is locale-dependent).

    `PATH` is only PREPENDED to (not replaced), so other tools the test
    relies on - notably `git` - keep working through the rest of `PATH`.
    Yields the path of the bin directory in case the test needs to inspect
    or amend it."""
    bin_dir = mkdtemp()
    py = sys.executable
    for name, body in executables.items():
        impl_path = os.path.join(bin_dir, f'{name}_impl.py')
        write_to_file(impl_path, body)
        posix_path = os.path.join(bin_dir, name)
        write_to_file(posix_path,
                      f'#!/bin/sh\nPYTHONIOENCODING=utf-8 exec "{py}" "{impl_path}" "$@"\n')
        set_file_executable(posix_path)
        windows_path = os.path.join(bin_dir, f'{name}.cmd')
        write_to_file(windows_path,
                      f'@echo off\r\nset PYTHONIOENCODING=utf-8\r\n"{py}" "{impl_path}" %*\r\n')
    new_path = bin_dir + os.pathsep + os.environ.get('PATH', '')
    with overridden_environment(PATH=new_path):
        yield bin_dir


def mock__run_cmd_and_forward_stdout(cmd: str, *args: str, **kwargs: Any) -> int:
    """Drop-in replacement for `git_machete.utils._subproc._run_cmd` that makes a
    subprocess's stdout observable to the `redirect_stdout(...)` context
    manager used by `launch_command()` in tests.

    The real `_run_cmd` runs `subprocess.run(..., stdout=None, stderr=None)`,
    so the subprocess inherits the parent's file descriptors and writes
    straight to FD 1 / FD 2. `contextlib.redirect_stdout` only rebinds the
    Python-level `sys.stdout` object and cannot intercept bytes written to
    FD 1 by a subprocess - which means commands run via `_run_cmd` (e.g.
    `git diff`, `git log`) would otherwise produce no output that the test
    helpers can assert on.

    This mock works around that by:
      1. capturing the subprocess's stdout via `stdout=subprocess.PIPE`,
      2. decoding it and re-emitting it through `sys.stdout.write(...)`,
         which IS observable by `redirect_stdout`.

    Stderr is intentionally left inherited (`stderr=None`); subprocess error
    output still flows to the real stderr.

    Returns the subprocess's exit code, matching the real `_run_cmd`'s
    contract. The captured stdout itself surfaces in tests indirectly:
    `launch_command()` returns whatever `redirect_stdout` accumulated, which
    now includes what this mock wrote into `sys.stdout`."""
    completed_process: subprocess.CompletedProcess[bytes] = subprocess.run(
        [cmd] + list(args), stdout=subprocess.PIPE, stderr=None, **kwargs)
    sys.stdout.write(completed_process.stdout.decode('utf-8'))
    return completed_process.returncode


def mock_input_returning_y(msg: str) -> str:
    print(msg)
    return 'y'


def mock_input_returning(*answers: str) -> Callable[[str], str]:
    gen = (ans for ans in answers)

    def inner(msg: str) -> str:
        print(msg)
        return next(gen)
    return inner
