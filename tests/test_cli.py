import os
from tempfile import mkdtemp
from typing import List

import pytest
from pytest_mock import MockerFixture

from git_machete.cli import main
from git_machete.utils import ExitCode

from .base_test import BaseTest
from .cli_runner import launch_command_capturing_output_and_exception
from .git_repository import create_repo


def assert_argparse_failure(cmd_and_args: List[str], expected_output: str) -> None:
    """Run the CLI and assert it exits with `ARGUMENT_ERROR` after emitting
    exactly `expected_output` (a literal multi-line string) on stdout/stderr.

    The shared `assert_failure` helper from `tests.cli_runner` reads the failure
    text from `MacheteException.msg`, but argparse failures bubble up as
    `SystemExit` (which carries only an exit code) with the actual message
    written to stdout/stderr - hence this dedicated helper for `test_cli`.
    """
    output, e = launch_command_capturing_output_and_exception(*cmd_and_args)
    assert type(e) is SystemExit
    assert e.code == ExitCode.ARGUMENT_ERROR
    assert output is not None
    expected = expected_output if expected_output.endswith("\n") else expected_output + "\n"
    assert output == expected


class TestCLI(BaseTest):
    @pytest.mark.parametrize("flag", ["--debug", "-v", "--verbose"])
    def test_verbose_no_command(self, flag: str) -> None:
        # Asserting on the full help output here would be brittle (the listing
        # tracks every (sub)command); we only smoke-check that `--help`-style
        # output is what we get instead of a stack trace.
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
    # Order: general (top-level command/flag handling) -> specific (per-subcommand).

    # ─── Top-level command typo ──────────────────────────────────────────────

    def test_unknown_subcommand_suggests_close_match(self) -> None:
        """`git machete travers` should suggest `traverse`."""
        assert_argparse_failure(
            ["travers"],
            "Invalid command: 'travers'\n"
            "Did you mean: `traverse`?")

    def test_unknown_subcommand_no_close_match(self) -> None:
        """A garbage top-level command without a near-miss should steer the
        user to `git machete help` (the help hint is suppressed when there IS
        a close match - that match is the actionable suggestion)."""
        assert_argparse_failure(
            ["xyzzy"],
            "Invalid command: 'xyzzy'\n"
            "Run `git machete help` to see all available commands.")

    # ─── Unknown flag ────────────────────────────────────────────────────────

    def test_unknown_flag_no_subcommand(self) -> None:
        """An unknown top-level flag still falls back to the top-level parser."""
        assert_argparse_failure(
            ["--debg"],
            "Unrecognized arguments: --debg\n"
            "Did you mean: `--debug`?")

    def test_unknown_flag_suggests_close_match(self) -> None:
        """`git machete traverse --srart-from foo` should suggest `--start-from`."""
        assert_argparse_failure(
            ["traverse", "--srart-from", "foo"],
            "Unrecognized arguments: --srart-from foo\n"
            "Did you mean: `--start-from`?")

    def test_unknown_flag_with_equals_suggests_close_match(self) -> None:
        """`--srart-from=foo` is split on `=` before fuzzy-matching."""
        assert_argparse_failure(
            ["traverse", "--srart-from=foo"],
            "Unrecognized arguments: --srart-from=foo\n"
            "Did you mean: `--start-from`?")

    def test_unknown_flag_with_uppercase_letter_suggests_close_match(self) -> None:
        """A wrong-case typo (`--list-commitS` vs `--list-commits`) is still
        within difflib's similarity threshold and should be suggested.

        Also serves as the regression test for the message prefix being
        sentence-cased (`Unrecognized`, not `unrecognized`).
        """
        assert_argparse_failure(
            ["status", "--list-commitS"],
            "Unrecognized arguments: --list-commitS\n"
            "Did you mean: `--list-commits`, `--list-commits-with-hashes`?")

    def test_unknown_flag_scoped_to_subparser(self) -> None:
        """Suggestions only consider options of the active subcommand.

        `--checked-out-since` exists on `discover` but not on `traverse`. A typo
        of it under `traverse` must NOT trigger a suggestion based on `discover`'s
        vocabulary - otherwise we'd be telling the user to use a flag that the
        active subcommand rejects.

        Since there is no spelling-correction hint, the message falls back to
        pointing the user at the subcommand's help page.
        """
        assert_argparse_failure(
            ["traverse", "--checked-out-snc", "foo"],
            "Unrecognized arguments: --checked-out-snc foo\n"
            "See `git machete help traverse` for usage.")

    def test_unknown_flag_scoped_to_subparser_positive(self) -> None:
        """Conversely, when the typo is under the right subparser, suggest."""
        assert_argparse_failure(
            ["discover", "--checked-out-snc", "foo"],
            "Unrecognized arguments: --checked-out-snc foo\n"
            "Did you mean: `--checked-out-since`?")

    def test_two_unknown_flags_each_with_suggestion(self) -> None:
        """When multiple unrecognized flags each have a close match, every
        suggestion line is prefixed with the originating flag name so the
        user can tell them apart."""
        assert_argparse_failure(
            ["traverse", "--srart-from", "foo", "--debugg"],
            "Unrecognized arguments: --srart-from foo --debugg\n"
            "For `--srart-from`: did you mean: `--start-from`?\n"
            "For `--debugg`: did you mean: `--debug`?")

    def test_unknown_short_flag_points_to_help(self) -> None:
        """Short flags like `-q` or `-gs` have no long-option close match,
        so the message falls back to the subcommand help page."""
        assert_argparse_failure(
            ["status", "-q"],
            "Unrecognized arguments: -q\n"
            "See `git machete help status` for usage.")

    def test_unknown_short_flags_nested_subcommand_points_to_help(self) -> None:
        """For a two-level subcommand (`github create-pr`), the hint points
        at the top-level subcommand (`github`) since that is what
        `git machete help` accepts as its argument."""
        assert_argparse_failure(
            ["github", "create-pr", "-gs"],
            "Unrecognized arguments: -gs\n"
            "See `git machete help github` for usage.")

    def test_unknown_flag_no_subcommand_no_hint(self) -> None:
        """At the top level (no subcommand selected), there is no help page
        to point at, so no hint is appended when there is also no suggestion."""
        assert_argparse_failure(
            ["-q"],
            "Unrecognized arguments: -q")

    # ─── Invalid choice for positional ───────────────────────────────────────

    def test_invalid_choice_for_positional_suggests_close_match(self) -> None:
        """`git machete go dwn` should suggest `down`."""
        assert_argparse_failure(
            ["go", "dwn"],
            "Invalid go direction: 'dwn'\n"
            "Did you mean: `down`?")

    def test_invalid_nested_choice_no_close_match_lists_all(self) -> None:
        """Nested invalid choices without a near-miss list every option.

        The top-level "Run `git machete help`" hint would point the user at
        the wrong help topic for nested subcommands, and the choice sets here
        are small enough that printing them all is the friendlier option.
        """
        # github subcommand
        assert_argparse_failure(
            ["github", "xyzzy"],
            "Invalid github subcommand: 'xyzzy'\n"
            "Possible values for github subcommand are: "
            "anno-prs, checkout-prs, create-pr, restack-pr, retarget-pr, update-pr-descriptions")
        # gitlab subcommand
        assert_argparse_failure(
            ["gitlab", "xyzzy"],
            "Invalid gitlab subcommand: 'xyzzy'\n"
            "Possible values for gitlab subcommand are: "
            "anno-mrs, checkout-mrs, create-mr, restack-mr, retarget-mr, update-mr-descriptions")
        # `go` direction (note: aliases like `d`, `f` are part of the choice set
        # and so legitimately show up here, mirroring the missing-required path)
        assert_argparse_failure(
            ["go", "xyzzy"],
            "Invalid go direction: 'xyzzy'\n"
            "Possible values for go direction are: "
            "d, down, f, first, l, last, n, next, p, prev, r, root, u, up")
        # `show` direction
        assert_argparse_failure(
            ["show", "xyzzy"],
            "Invalid show direction: 'xyzzy'\n"
            "Possible values for show direction are: "
            "c, current, d, down, f, first, l, last, n, next, p, prev, r, root, u, up")

    # ─── Missing required choice ─────────────────────────────────────────────

    def test_missing_required_choice_lists_possible_values(self) -> None:
        """Missing positional with `choices=` should list the possible values."""
        assert_argparse_failure(
            ["show"],
            "The following arguments are required: show direction\n"
            "Possible values for show direction are: "
            "c, current, d, down, f, first, l, last, n, next, p, prev, r, root, u, up")

    def test_missing_required_choice_for_completion(self) -> None:
        """`git machete completion` lists possible shells."""
        assert_argparse_failure(
            ["completion"],
            "The following arguments are required: shell\n"
            "Possible values for shell are: bash, fish, zsh")

    def test_missing_required_choice_for_list(self) -> None:
        """`git machete list` lists the categories."""
        assert_argparse_failure(
            ["list"],
            "The following arguments are required: category\n"
            "Possible values for category are: "
            "addable, childless, managed, slidable, slidable-after, unmanaged, with-overridden-fork-point")

    # ─── github-specific ─────────────────────────────────────────────────────

    def test_missing_required_choice_for_github(self) -> None:
        """`git machete github` lists subcommands.

        `sync` is intentionally omitted from the listing - see
        `test_github_sync_hidden_from_close_match_suggestions` for the rationale.
        """
        assert_argparse_failure(
            ["github"],
            "The following arguments are required: github subcommand\n"
            "Possible values for github subcommand are: "
            "anno-prs, checkout-prs, create-pr, restack-pr, retarget-pr, update-pr-descriptions")

    def test_invalid_choice_for_subcommand_positional(self) -> None:
        """`git machete github creat-pr` should suggest `create-pr`.

        Several `*-pr` subcommands are similar enough that difflib returns more
        than one candidate; we pin down the full ordered list since the order
        is deterministic (best match first by difflib's similarity ratio).
        """
        assert_argparse_failure(
            ["github", "creat-pr"],
            "Invalid github subcommand: 'creat-pr'\n"
            "Did you mean: `create-pr`, `retarget-pr`, `restack-pr`?")

    def test_github_sync_hidden_from_close_match_suggestions(self) -> None:
        """`github sync` is deep into deprecation. It must remain accepted by
        the parser, but a typo close to `sync` must NOT suggest it - that
        would advertise a command we're trying to retire. Same goes for the
        `Possible values` listing in `test_missing_required_choice_for_github`.
        """
        # `snc` is similar to `sync` (and to nothing else under github), so
        # without the `_hidden_from_listing` filter we'd suggest `sync` here.
        # With the filter, no close-match line is produced and we fall through
        # to the "Possible values" listing instead.
        assert_argparse_failure(
            ["github", "snc"],
            "Invalid github subcommand: 'snc'\n"
            "Possible values for github subcommand are: "
            "anno-prs, checkout-prs, create-pr, restack-pr, retarget-pr, update-pr-descriptions")

    # ─── gitlab-specific ─────────────────────────────────────────────────────

    def test_missing_required_choice_for_gitlab(self) -> None:
        """`git machete gitlab` lists subcommands."""
        assert_argparse_failure(
            ["gitlab"],
            "The following arguments are required: gitlab subcommand\n"
            "Possible values for gitlab subcommand are: "
            "anno-mrs, checkout-mrs, create-mr, restack-mr, retarget-mr, update-mr-descriptions")
