import os
from tempfile import mkdtemp
from typing import List

import pytest
from pytest_mock import MockerFixture

from git_machete.cli import alias_by_command, main
from git_machete.utils import ExitCode

from .base_test import BaseTest
from .mockers import launch_command_capturing_output_and_exception
from .mockers_git_repository import create_repo


def _run_and_assert_argument_error(*cmd_and_args: str) -> str:
    """Run the CLI, assert it exits with ARGUMENT_ERROR, return non-None captured output."""
    output, e = launch_command_capturing_output_and_exception(*cmd_and_args)
    assert type(e) is SystemExit
    assert e.code == ExitCode.ARGUMENT_ERROR
    assert output is not None
    return output


def _assert_argparse_failure(cmd_and_args: List[str], expected_lines: List[str]) -> None:
    """Run the CLI and assert it exits with ARGUMENT_ERROR and emits exactly the given lines."""
    output = _run_and_assert_argument_error(*cmd_and_args)
    expected = "".join(line + "\n" for line in expected_lines)
    assert output == expected


class TestCLI(BaseTest):
    def test_aliases_unique(self) -> None:
        assert len(alias_by_command.values()) == len(set(alias_by_command.values()))

    @pytest.mark.parametrize("flag", ["--debug", "-v", "--verbose"])
    def test_verbose_no_command(self, flag: str) -> None:
        output, e = launch_command_capturing_output_and_exception(flag)
        assert output and "Usage: git machete" in output
        assert type(e) is SystemExit
        assert e.code == ExitCode.ARGUMENT_ERROR

    def test_main(self, mocker: MockerFixture) -> None:
        create_repo()
        self.patch_symbol(mocker, "sys.argv", ["", "show", "current"])
        main()

        with pytest.raises(SystemExit) as ei:
            self.patch_symbol(mocker, "sys.argv", ["", "go", "no-such-direction"])
            main()
        assert ExitCode.ARGUMENT_ERROR == ei.value.code

        with pytest.raises(SystemExit) as ei:
            self.patch_symbol(mocker, "sys.argv", ["", "status", "--", "--patch"])
            main()
        assert ExitCode.ARGUMENT_ERROR == ei.value.code

        os.chdir(mkdtemp())

        with pytest.raises(SystemExit) as ei:
            self.patch_symbol(mocker, "sys.argv", ["", "file"])
            main()
        assert ExitCode.MACHETE_EXCEPTION == ei.value.code

    # The tests below pin down the exact wording of argparse failure messages
    # so that future refactors of the parser do not silently regress UX.

    def test_unknown_subcommand_suggests_close_match(self) -> None:
        """`git machete travers` should suggest `traverse`."""
        output = _run_and_assert_argument_error("travers")
        assert "invalid choice: 'travers'" in output
        assert "Did you mean: `traverse`?" in output

    def test_unknown_subcommand_no_close_match(self) -> None:
        """A garbage subcommand still errors out, just without a suggestion."""
        output = _run_and_assert_argument_error("xyzzy")
        assert "invalid choice: 'xyzzy'" in output
        assert "Did you mean" not in output

    def test_unknown_flag_suggests_close_match(self) -> None:
        """`git machete traverse --srart-from foo` should suggest `--start-from`."""
        _assert_argparse_failure(
            ["traverse", "--srart-from", "foo"],
            [
                "unrecognized arguments: --srart-from foo",
                "For `--srart-from`: Did you mean: `--start-from`?",
            ])

    def test_unknown_flag_with_equals_suggests_close_match(self) -> None:
        """`--srart-from=foo` is split on `=` before fuzzy-matching."""
        output = _run_and_assert_argument_error("traverse", "--srart-from=foo")
        assert "For `--srart-from`: Did you mean: `--start-from`?" in output

    def test_unknown_flag_scoped_to_subparser(self) -> None:
        """Suggestions only consider options of the active subcommand.

        `--checked-out-since` exists on `discover` but not on `traverse`. A typo
        of it under `traverse` must NOT trigger a suggestion based on `discover`'s
        vocabulary - otherwise we'd be telling the user to use a flag that the
        active subcommand rejects.
        """
        _assert_argparse_failure(
            ["traverse", "--checked-out-snc", "foo"],
            ["unrecognized arguments: --checked-out-snc foo"])

    def test_unknown_flag_scoped_to_subparser_positive(self) -> None:
        """Conversely, when the typo is under the right subparser, suggest."""
        output = _run_and_assert_argument_error("discover", "--checked-out-snc", "foo")
        assert "For `--checked-out-snc`: Did you mean: `--checked-out-since`?" in output

    def test_unknown_flag_no_subcommand(self) -> None:
        """An unknown top-level flag still falls back to the top-level parser."""
        _assert_argparse_failure(
            ["--debg"],
            [
                "unrecognized arguments: --debg",
                "For `--debg`: Did you mean: `--debug`?",
            ])

    def test_invalid_choice_for_positional_suggests_close_match(self) -> None:
        """`git machete go dwn` should suggest `down`."""
        output = _run_and_assert_argument_error("go", "dwn")
        assert "argument go direction: invalid choice: 'dwn'" in output
        assert "Did you mean: `down`?" in output

    def test_invalid_choice_for_subcommand_positional(self) -> None:
        """`git machete github creat-pr` should suggest `create-pr`.

        Several `*-pr` subcommands are similar enough that difflib returns more
        than one candidate; we only require `create-pr` (the closest match) to
        appear, but allow further suggestions on the same line.
        """
        output = _run_and_assert_argument_error("github", "creat-pr")
        assert "argument github subcommand: invalid choice: 'creat-pr'" in output
        assert "Did you mean: `create-pr`" in output

    def test_missing_required_choice_lists_possible_values(self) -> None:
        """Missing positional with `choices=` should list the possible values."""
        _assert_argparse_failure(
            ["show"],
            [
                "the following arguments are required: show direction",
                "Possible values for show direction are: "
                "c, current, d, down, f, first, l, last, n, next, p, prev, r, root, u, up",
            ])

    def test_missing_required_choice_for_completion(self) -> None:
        """`git machete completion` lists possible shells."""
        _assert_argparse_failure(
            ["completion"],
            [
                "the following arguments are required: shell",
                "Possible values for shell are: bash, fish, zsh",
            ])

    def test_missing_required_choice_for_list(self) -> None:
        """`git machete list` lists the categories."""
        _assert_argparse_failure(
            ["list"],
            [
                "the following arguments are required: category",
                "Possible values for category are: "
                "addable, childless, managed, slidable, slidable-after, unmanaged, with-overridden-fork-point",
            ])
