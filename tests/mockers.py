import os
import subprocess
import sys
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Callable, Iterator, Tuple

from git_machete.utils import PopenResult


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


def mock__popen_cmd_with_fixed_results(*results: Tuple[int, str, str]) -> Callable[..., PopenResult]:
    gen = (i for i in results)

    def inner(*args: Any, **kwargs: Any) -> PopenResult:  # noqa: U100
        return PopenResult(*next(gen))
    return inner


def mock__run_cmd_and_forward_stdout(cmd: str, *args: str, **kwargs: Any) -> int:
    """Drop-in replacement for `git_machete.utils._run_cmd` that makes a
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
