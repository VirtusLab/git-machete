import io
import os
import subprocess
import sys
import textwrap
from contextlib import (AbstractContextManager, contextmanager,
                        redirect_stderr, redirect_stdout)
from typing import Any, Callable, Iterable, Iterator, Type

import pytest

from git_machete import cli, utils
from git_machete.exceptions import MacheteException


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
                utils.debug_mode = False
                utils.verbose_mode = False
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
    actual_result = textwrap.dedent(launch_command(*cmds))
    assert actual_result == expected_result


def assert_failure(cmds: Iterable[str], expected_result: str, expected_exception: Type[Exception] = MacheteException) -> None:
    if expected_result.startswith("\n"):
        # removeprefix is only available since Python 3.9
        expected_result = expected_result[1:]
    expected_result = textwrap.dedent(expected_result)

    with pytest.raises(expected_exception) as e:
        launch_command(*cmds)
    error_message = e.value.msg  # type: ignore[attr-defined]
    if sys.platform == 'win32':
        error_message = error_message.replace('.git\\machete', '.git/machete')
    assert error_message == expected_result


def rewrite_definition_file(new_body: str) -> None:
    new_body = textwrap.dedent(new_body)
    with open(".git/machete", 'w') as def_file:
        def_file.writelines(new_body)


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
    class Wrapper(object):
        def __init__(self) -> None:
            self.index = -1

        def __call__(self, msg: str) -> str:
            print(msg)
            self.index += 1
            return answers[self.index]

    return Wrapper()
