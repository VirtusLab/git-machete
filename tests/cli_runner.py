import io
import re
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from typing import Iterable, Optional, Tuple, Type

from git_machete import cli
from git_machete.utils import MacheteException


def launch_command_capturing_output_and_exception(*cmd_and_args: str) -> Tuple[Optional[str], Optional[BaseException]]:
    with io.StringIO() as out:
        try:
            with redirect_stdout(out):
                with redirect_stderr(out):
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
