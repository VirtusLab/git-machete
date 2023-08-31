import io
import os
import re
import subprocess
import sys
import textwrap
from contextlib import (AbstractContextManager, contextmanager,
                        redirect_stderr, redirect_stdout)
from typing import Any, Callable, Iterable, Iterator, Tuple, Type

import pytest

from git_machete import cli, utils
from git_machete.exceptions import MacheteException
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


def launch_command(*args: str) -> str:
    with io.StringIO() as out:
        with redirect_stdout(out):
            with redirect_stderr(out):
                utils.displayed_warnings = set()
                cli.launch(list(args))
        output = out.getvalue()
        if sys.platform == 'win32':
            output = output.replace('.git\\machete', '.git/machete')
        return output


def assert_success(cmds: Iterable[str], expected_result: str) -> None:
    if expected_result.startswith("\n"):
        # removeprefix is only available since Python 3.9
        expected_result = expected_result[1:]
    expected_result = textwrap.dedent(expected_result)
    actual_result = re.sub(" +$", "", textwrap.dedent(launch_command(*cmds)), flags=re.MULTILINE)
    assert actual_result == expected_result


def assert_failure(cmds: Iterable[str], expected_result: str, expected_exception: Type[Exception] = MacheteException) -> None:
    if expected_result.startswith("\n"):
        # removeprefix is only available since Python 3.9
        expected_result = expected_result[1:]
    expected_result = textwrap.dedent(expected_result)

    with pytest.raises(expected_exception) as e:
        launch_command(*cmds)
    error_message = e.value.msg  # type: ignore[attr-defined]
    error_message = re.sub(" +$", "", error_message, flags=re.MULTILINE)
    if sys.platform == 'win32':
        error_message = error_message.replace('.git\\machete', '.git/machete')
    assert error_message == expected_result


def rewrite_branch_layout_file(new_body: str) -> None:
    new_body = textwrap.dedent(new_body)
    with open(".git/machete", 'w') as def_file:
        def_file.writelines(new_body)


def mock__popen_cmd_with_fixed_results(*results: Tuple[int, str, str]) -> Callable[..., PopenResult]:
    gen = (i for i in results)

    def inner(*args: Any, **kwargs: Any) -> PopenResult:  # noqa: U100
        return PopenResult(*next(gen))
    return inner


def mock__run_cmd_and_forward_stdout(cmd: str, *args: str, **kwargs: Any) -> int:
    """Execute command in the new subprocess but capture together process's stdout and print it into sys.stdout.
    This sys.stdout is later being redirected via the `redirect_stdout` in `launch_command()` and gets returned by this function.
    Below is shown the chain of function calls that presents this mechanism:
    1. `launch_command()` gets executed in the test case and evokes `cli.launch()`.
    2. `cli.launch()` executes `utils.run_cmd()` but `utils.run_cmd()` is being mocked by `mock_run_cmd_and_forward_stdout()`
       so the command's stdout and stderr is loaded into sys.stdout.
    3. After command execution we go back through `cli.launch()`(2) to `launch_command()`(1) which redirects just updated sys.stdout
       into variable and returns it."""
    # capture_output argument is only supported since Python 3.7
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
