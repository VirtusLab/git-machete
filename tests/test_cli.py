import os
from tempfile import mkdtemp

import pytest
from pytest_mock import MockerFixture

from git_machete.cli import main
from git_machete.utils.exceptions import ExitCode

from .base_test import BaseTest
from .cli_runner import (assert_argparse_failure,
                         launch_command_capturing_output_and_exception)
from .git_repository import create_repo


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

    # ─── Missing required positional WITHOUT `choices=` ──────────────────────

    def test_missing_required_positional_without_choices(self) -> None:
        """`git machete rename` requires `<new_name>` but has no `choices=`, so
        the "Possible values" follow-up line MUST NOT be appended - we just
        report which positional is missing."""
        assert_argparse_failure(
            ["rename"],
            "The following arguments are required: new_name")

    # ─── Excess / unrecognized positionals ───────────────────────────────────

    def test_excess_positionals_after_last_scalar(self) -> None:
        """`add` accepts at most one positional (`<branch>`). Extras must be
        reported as unrecognized arguments, matching argparse-era behaviour.
        """
        assert_argparse_failure(
            ["add", "foo", "bar"],
            "Unrecognized arguments: bar\n"
            "See `git machete help add` for usage.")

    def test_positionals_on_command_without_positional_specs(self) -> None:
        """`advance` takes no positionals at all; anything passed is rejected
        as unrecognized."""
        assert_argparse_failure(
            ["advance", "foo"],
            "Unrecognized arguments: foo\n"
            "See `git machete help advance` for usage.")

    # ─── Type-converted positionals ──────────────────────────────────────────

    def test_invalid_int_positional_for_github_pr_number(self) -> None:
        """`github checkout-prs` takes one or more PR numbers (`type_conv=int`).
        A non-integer must surface argparse-style "invalid int value"
        wording with the user-facing `PR number` label, not the internal
        `request_id` storage key."""
        assert_argparse_failure(
            ["github", "checkout-prs", "not-a-number"],
            "Argument PR number: invalid int value: 'not-a-number'")

    # ─── Mutex group WITHOUT a custom message ────────────────────────────────

    def test_mutex_group_default_argparse_style_message(self) -> None:
        """`fork-point` declares a 5-way mutex group on the override flags with
        NO custom message; that path emits the argparse-style
        `Argument X: not allowed with argument Y` wording. Picking two
        long-only flags here also covers `OptSpec.canonical_name`'s
        long-only branch."""
        # The wording lists the two flags in their MutexGroup-declaration
        # order (not the user's argv order): `("override-to-inferred",
        # "override-to-parent")` is the declared order, so the error
        # complains about `--override-to-parent` against
        # `--override-to-inferred` regardless of which the user typed first.
        assert_argparse_failure(
            ["fork-point", "--override-to-parent", "--override-to-inferred"],
            "Argument --override-to-parent: not allowed with argument --override-to-inferred")

    # ─── Boolean flag passed WITH a value ────────────────────────────────────

    def test_boolean_flag_passed_with_value(self) -> None:
        """`--yes` is a boolean flag (no `takes_value`). Passing `--yes=true`
        must produce an argparse-style argument error, not let getopt's
        raw `GetoptError` propagate."""
        assert_argparse_failure(
            ["add", "--yes=true"],
            "Argument -y/--yes: must not have an argument")

    # ─── Value-taking flag passed without a value ────────────────────────────

    def test_value_taking_flag_without_value(self) -> None:
        """`getopt` raises "option requires argument" for `-o` / `--onto` with
        no value after it. The parser must catch this rather than let the
        raw `GetoptError` propagate, and re-cast it in argparse-style
        wording with the canonical option label."""
        # Short form.
        assert_argparse_failure(
            ["add", "-o"],
            "Argument -o/--onto: expected one argument")
        # Long form. `gnu_getopt`'s "long with =" parsing would accept an
        # explicit empty `--onto=`, so we exercise the no-`=`, end-of-argv
        # case to actually trigger the recovery path.
        assert_argparse_failure(
            ["add", "--onto"],
            "Argument -o/--onto: expected one argument")

    # ─── Unknown-flag recovery preserves adjacent KNOWN options ──────────────

    def test_unknown_flag_recovery_skips_over_known_separated_value(self) -> None:
        """When the unknown-token recovery path walks argv after getopt has
        failed, it must NOT mistake the value of a *known* long option
        (passed in separated form like `--color always`) for a positional
        and append it to the unknown list. Same idea for short options
        like `-o develop`. We feed both forms next to an unknown
        `--definitely-not-a-flag` and assert only the unknown surfaces."""
        # Long-form: `--color always` adjacent to the unknown flag.
        assert_argparse_failure(
            ["status", "--color", "always", "--definitely-not-a-flag"],
            "Unrecognized arguments: --definitely-not-a-flag\n"
            "See `git machete help status` for usage.")
        # Short-form: `-o develop` (short option of `add` that takes a value).
        assert_argparse_failure(
            ["add", "-o", "develop", "--definitely-not-a-flag"],
            "Unrecognized arguments: --definitely-not-a-flag\n"
            "See `git machete help add` for usage.")
