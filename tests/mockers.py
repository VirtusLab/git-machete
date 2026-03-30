import io
import os
import re
import subprocess
import sys
import textwrap
import time
from contextlib import (AbstractContextManager, contextmanager,
                        redirect_stderr, redirect_stdout)
from typing import Any, Callable, Iterable, Iterator, Optional, Tuple, Type

from git_machete import cli, utils
from git_machete.utils import MacheteException, PopenResult


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


def launch_command_capturing_output_and_exception(*cmd_and_args: str) -> Tuple[Optional[str], Optional[BaseException]]:
    with io.StringIO() as out:
        try:
            with redirect_stdout(out):
                with redirect_stderr(out):
                    utils.displayed_warnings = set()
                    cli.launch(list(cmd_and_args))
                output = out.getvalue()
                return output, None
        except BaseException as e:
            output = out.getvalue()
            return output, e


def launch_command(*cmd_and_args: str) -> str:
    with io.StringIO() as out:
        with redirect_stdout(out):
            with redirect_stderr(out):
                utils.displayed_warnings = set()
                cli.launch(list(cmd_and_args))
        output = out.getvalue()
        return output


def strip_trailing_spaces(text: str) -> str:
    return re.sub(" +$", "", text, flags=re.MULTILINE)


def assert_success(cmd_and_args: Iterable[str], expected_result: str) -> None:
    if expected_result.startswith("\n"):
        # removeprefix is only available since Python 3.9
        expected_result = expected_result[1:]
    expected_result = textwrap.dedent(expected_result)
    actual_result = strip_trailing_spaces(textwrap.dedent(launch_command(*cmd_and_args)))
    assert actual_result == expected_result


def assert_failure(cmd_and_args: Iterable[str], expected_message: str, expected_type: Type[BaseException] = MacheteException,
                   expected_output: Optional[str] = None) -> None:
    if expected_message.startswith("\n"):
        # removeprefix is only available since Python 3.9
        expected_message = expected_message[1:]
    expected_message = textwrap.dedent(expected_message)

    if expected_output is not None:
        if expected_output.startswith("\n"):
            expected_output = expected_output[1:]
        expected_output = textwrap.dedent(expected_output)

    output, e = launch_command_capturing_output_and_exception(*cmd_and_args)
    assert e is not None, f"Expected {expected_type.__name__} but no exception was raised"
    assert isinstance(e, expected_type), f"Expected {expected_type.__name__} but got {type(e).__name__}: {e}"
    error_message = strip_trailing_spaces(e.msg)  # type: ignore[attr-defined]
    assert error_message == expected_message

    if expected_output is not None:
        actual_output = strip_trailing_spaces(textwrap.dedent(output or ""))
        assert actual_output == expected_output


def read_branch_layout_file() -> str:
    with open(".git/machete") as def_file:
        return def_file.read()


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


def execute_ignoring_exit_code(command: str) -> None:
    subprocess.call(command, shell=True)


def set_file_executable(file_name: str) -> None:
    os.chmod(file_name, 0o700)


def sleep(seconds: int) -> None:
    time.sleep(seconds)


def remove_directory(file_path: str) -> None:
    execute(f'rm -rf "./{file_path}"')


def read_file(file_name: str) -> str:
    with open(file_name) as f:
        return f.read()


def execute(command: str) -> None:
    subprocess.check_call(command, shell=True)


def write_to_file(file_path: str, file_content: str) -> None:
    dirname = os.path.dirname(file_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(file_path, 'w') as f:
        f.write(file_content)


def popen(command: str) -> str:
    return subprocess.check_output(command, shell=True, timeout=5).decode("utf-8").strip()
