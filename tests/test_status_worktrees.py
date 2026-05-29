import os
import shutil

import pytest
from pytest_mock import MockerFixture

from git_machete.utils.paths import AbsPath
from git_machete.utils.terminal import FullTerminalAnsiOutputCodes
from tests.base_test import BaseTest
from tests.cli_runner import (assert_success, launch_command,
                              rewrite_branch_layout_file)
from tests.git_repository import (add_worktree, check_out, commit, create_repo,
                                  get_git_version, new_branch)

pytestmark = pytest.mark.skipif(  # noqa: F841
    get_git_version() < (2, 5),
    reason="git worktree command was introduced in git 2.5"
)


class TestStatusWorktrees(BaseTest):

    def test_status_no_worktree_label_when_branch_only_in_current_worktree(self) -> None:
        """Without any linked worktrees there's nothing to disambiguate; status looks exactly as before."""
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        rewrite_branch_layout_file(
            """
            master
              develop
            """
        )
        assert_success(
            ["status"],
            """
              master
              |
              o-develop *
            """,
        )

    def test_status_labels_branch_checked_out_in_linked_worktree(self) -> None:
        """A branch checked out in a linked worktree is annotated `[<worktree-basename>]` when status is run from main.
        Master (the current branch, sitting in the main worktree) carries the self-explanatory `[<this worktree>]` label."""
        create_repo()
        new_branch("master")
        commit()
        check_out("master")
        new_branch("develop")
        commit()
        check_out("master")
        new_branch("feature")
        commit()

        rewrite_branch_layout_file(
            """
            master
              develop
              feature
            """
        )

        check_out("master")
        feature_worktree = add_worktree("feature")
        # With a single linked worktree the strip-common-prefix utility falls back to the basename.
        label = os.path.basename(AbsPath(feature_worktree))

        assert_success(
            ["status"],
            f"""
              master * [<this worktree>]
              |
              o-develop
              |
              o-feature [{label}]
            """,
        )

    def test_status_labels_branch_checked_out_in_main_worktree_from_linked(self) -> None:
        """When status is run from a linked worktree, the branch sitting in main worktree is labeled `[<main worktree>]`,
        and the current branch (here `feature`, in the linked worktree) carries the self-explanatory `[<this worktree>]`."""
        create_repo()
        new_branch("master")
        commit()
        check_out("master")
        new_branch("develop")
        commit()
        check_out("master")
        new_branch("feature")
        commit()

        rewrite_branch_layout_file(
            """
            master
              develop
              feature
            """
        )

        # Main worktree stays on `master`; cd into a linked worktree on `feature`.
        check_out("master")
        feature_worktree = add_worktree("feature")
        os.chdir(feature_worktree)

        # `feature` (current) -> `<this worktree>`; `master` (main, we're elsewhere) -> `<main worktree>`.
        # The two literal labels mean the rendering is fully deterministic regardless of the random
        # `mkdtemp` basename of the linked worktree.
        assert_success(
            ["status"],
            """
              master [<main worktree>]
              |
              o-develop
              |
              o-feature * [<this worktree>]
            """,
        )

    def test_status_strips_common_prefix_across_multiple_linked_worktrees(self) -> None:
        """Multiple linked worktrees sharing a parent directory collapse to just their basenames.
        The current branch additionally carries `[<this worktree>]` rather than its own basename."""
        create_repo()
        new_branch("master")
        commit()
        check_out("master")
        new_branch("develop")
        commit()
        check_out("master")
        new_branch("feature")
        commit()

        rewrite_branch_layout_file(
            """
            master
              develop
              feature
            """
        )

        check_out("master")
        develop_worktree = add_worktree("develop")
        feature_worktree = add_worktree("feature")

        develop_label = os.path.basename(AbsPath(develop_worktree))
        feature_label = os.path.basename(AbsPath(feature_worktree))
        # Sanity-check: each worktree path indeed shares the OS temp dir as a parent,
        # so the stripped label is just the trailing component.
        assert "/" not in develop_label
        assert "/" not in feature_label

        # We're in main (master is current) -> master has `<this worktree>`, the linked branches have their basenames.
        assert_success(
            ["status"],
            f"""
              master * [<this worktree>]
              |
              o-develop [{develop_label}]
              |
              o-feature [{feature_label}]
            """,
        )

    def test_status_worktree_label_is_green_in_ansi_mode(self, mocker: MockerFixture) -> None:
        """Verify the worktree label is wrapped in the green ANSI escape - the dedicated visual cue
        promised by the feature (and the user-visible difference between "worktree info" and any other
        in-line annotation, all of which are emitted dim or unstyled)."""
        E = FullTerminalAnsiOutputCodes
        self.patch_symbol(mocker, "git_machete.utils.terminal.is_terminal_fully_fledged", lambda: True)

        create_repo()
        new_branch("master")
        commit()
        check_out("master")
        new_branch("feature")
        commit()

        rewrite_branch_layout_file(
            """
            master
              feature
            """
        )

        check_out("master")
        feature_worktree = add_worktree("feature")
        label = os.path.basename(AbsPath(feature_worktree))

        raw_output = launch_command("status", "--color=always")
        expected_ansi = (
            f"  {E.BOLD}{E.UNDERLINE}master{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}"
            f" {E.GREEN}[<this worktree>]{E.ENDC}\n"
            f"  {E.GREEN}│{E.ENDC}\n"
            f"  {E.GREEN}└─{E.ENDC}{E.BOLD}feature{E.ENDC_BOLD_DIM}"
            f" {E.GREEN}[{label}]{E.ENDC}\n"
        )
        assert raw_output == expected_ansi

    def test_status_main_worktree_label_is_green_in_ansi_mode(self, mocker: MockerFixture) -> None:
        """When status is run from a linked worktree, the literal `<main worktree>` label must also be green-wrapped -
        the angle brackets are intentionally part of the visible text (so they need `escape_markup` to survive
        `_fmt`'s tag parser); this test pins down that they don't accidentally get parsed as markup.
        `feature` (current, sitting in the linked worktree) also carries the `<this worktree>` literal,
        which exercises the same `escape_markup` path."""
        E = FullTerminalAnsiOutputCodes
        self.patch_symbol(mocker, "git_machete.utils.terminal.is_terminal_fully_fledged", lambda: True)

        create_repo()
        new_branch("master")
        commit()
        check_out("master")
        new_branch("feature")
        commit()

        rewrite_branch_layout_file(
            """
            master
              feature
            """
        )

        check_out("master")
        feature_worktree = add_worktree("feature")
        os.chdir(feature_worktree)

        raw_output = launch_command("status", "--color=always")
        # `<` / `>` must appear literally in the output, not be eaten by `_fmt`'s tag parser.
        expected_ansi = (
            f"  {E.BOLD}master{E.ENDC_BOLD_DIM}"
            f" {E.GREEN}[<main worktree>]{E.ENDC}\n"
            f"  {E.GREEN}│{E.ENDC}\n"
            f"  {E.GREEN}└─{E.ENDC}{E.BOLD}{E.UNDERLINE}feature{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}"
            f" {E.GREEN}[<this worktree>]{E.ENDC}\n"
        )
        assert raw_output == expected_ansi

    def test_status_labels_current_branch_as_this_worktree(self) -> None:
        """The branch checked out in the current worktree always renders as `[<this worktree>]`,
        whether the current worktree is linked or main. The literal label is self-explanatory so users
        encountering it for the first time can interpret it without any in-band PSA from the status output,
        and as a bonus it sidesteps any randomness from the linked worktree's `mkdtemp` basename."""
        create_repo()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()

        rewrite_branch_layout_file(
            """
            master
              feature
            """
        )

        check_out("master")
        feature_worktree = add_worktree("feature")
        os.chdir(feature_worktree)

        assert_success(
            ["status"],
            """
              master [<main worktree>]
              |
              o-feature * [<this worktree>]
            """,
        )

    def test_status_labels_fire_when_only_unmanaged_branch_sits_in_linked_worktree(self) -> None:
        """The gate on whether to render worktree labels is "any linked worktree exists" - *not*
        "managed branches are spread across 2+ worktrees". So even if the lone linked worktree holds
        an unmanaged branch (invisible to the branch layout), labels still fire for every managed
        branch that happens to be checked out somewhere - here just `master` in the main worktree,
        rendered as `[<this worktree>]` because we're standing in main.

        `develop` and `feature` aren't checked out anywhere, so they get no label - this pins down that
        the gate fires once, then per-branch presence in *any* worktree dictates whether that row carries
        a label, independent of where the *other* managed branches live.
        """
        create_repo()
        new_branch("master")
        commit()
        check_out("master")
        new_branch("develop")
        commit()
        check_out("master")
        new_branch("feature")
        commit()
        # Unmanaged branch - it will live in the linked worktree but never appear in the layout.
        check_out("master")
        new_branch("wip")
        commit()

        rewrite_branch_layout_file(
            """
            master
              develop
              feature
            """
        )

        check_out("master")
        add_worktree("wip")

        # `master` (current, in main) -> `<this worktree>`; `develop` and `feature` are not checked
        # out anywhere, so they get no label; `wip` doesn't appear at all (unmanaged).
        assert_success(
            ["status"],
            """
              master * [<this worktree>]
              |
              o-develop
              |
              o-feature
            """,
        )

    def test_status_no_labels_in_single_worktree_repo(self) -> None:
        """In a repo with no linked worktrees, the feature must not kick in - otherwise every plain
        `git machete status` would suddenly carry a `[<this worktree>]` tag on the current branch,
        polluting the output for users who haven't opted into the multi-worktree workflow.
        This is the contract spelled out in https://github.com/VirtusLab/git-machete/issues/1705."""
        create_repo()
        new_branch("master")
        commit()
        new_branch("feature")
        commit()

        rewrite_branch_layout_file(
            """
            master
              feature
            """
        )

        # No `[...]` brackets anywhere - the feature is a no-op in single-worktree repos,
        # and full-output equality nails this down better than `"[" not in output` ever could
        # (e.g. it would also catch a future regression that emits the label on the wrong row).
        assert_success(
            ["status"],
            """
              master
              |
              o-feature *
            """,
        )

    def test_status_same_branch_force_checked_out_in_two_worktrees(self) -> None:
        """Vanilla `git worktree add` refuses to share a branch across worktrees (`fatal: '<branch>' is already used
        by worktree at <path>`), but `-f` overrides that, and the test harness's `add_worktree` uses `-f` so it can
        set up arbitrary scenarios. This test pins down what `status` does when the foot-gun fires:

        `get_worktree_root_dirs_by_branch` collapses the branch->path mapping to "last porcelain entry wins". Since
        `git worktree list --porcelain` puts the main worktree first and linked worktrees after it, the linked entry
        wins - so a branch checked out in both main and a linked worktree is labeled as the *linked* one regardless
        of where the user is standing. That's why the `master` row below carries `[<linked basename>]` when status
        is run from main (even though `master` *is also* in the current/main worktree), and `[<this worktree>]`
        when run from the linked worktree (where the "last wins" winner happens to coincide with `current_path`).

        We don't try to be cleverer than that - the underlying state is one git itself disallows by default,
        and any in-band warning would just add noise for the much commoner unmanaged-branch-in-linked-worktree case.
        """
        create_repo()
        new_branch("master")
        commit()
        check_out("master")
        new_branch("develop")
        commit()

        rewrite_branch_layout_file(
            """
            master
              develop
            """
        )

        check_out("master")
        # `add_worktree("master")` uses `-f` to force-create a linked worktree on `master`,
        # which is also currently checked out in main. After this, `master` lives in two worktrees.
        linked_worktree = add_worktree("master")
        linked_label = os.path.basename(AbsPath(linked_worktree))
        assert "/" not in linked_label

        # Viewed from main worktree: `master *` is the current branch (asterisk by `*`-marker logic, which
        # is independent of the worktree label), but the label resolves to the *linked* worktree because of
        # the last-wins tiebreak - i.e. NOT `[<this worktree>]`, even though master is also right here.
        assert_success(
            ["status"],
            f"""
              master * [{linked_label}]
              |
              o-develop
            """,
        )

        # Viewed from the linked worktree: the last-wins winner is again the linked entry, which now coincides
        # with `current_path`, so master renders as `[<this worktree>]`.
        os.chdir(linked_worktree)
        assert_success(
            ["status"],
            """
              master * [<this worktree>]
              |
              o-develop
            """,
        )

    def test_status_skips_stale_prunable_linked_worktree(self) -> None:
        """If a user `rm -rf`s a linked worktree's directory (or moves it out-of-band) instead of running
        `git worktree remove`, the admin entry under `.git/worktrees/<id>/` hangs around until
        `git worktree prune` / `git worktree repair` clears it. In that interim state, `git worktree list --porcelain`
        keeps emitting the entry but the path it points to no longer exists.

        Rendering `[<stale_basename>]` for such an entry would just send the user `cd`-ing into a void, so the
        porcelain parser drops entries whose path no longer exists on disk (we check `os.path.isdir` ourselves
        rather than relying on `--porcelain`'s `prunable` annotation, which wasn't emitted by older git versions).
        With *only* a stale linked worktree in the repo, the "any healthy linked worktree exists" gate doesn't fire,
        and status reverts to its labels-free baseline - as if the broken worktree weren't there at all."""
        create_repo()
        new_branch("master")
        commit()
        check_out("master")
        new_branch("develop")
        commit()
        check_out("master")
        new_branch("feature")
        commit()

        rewrite_branch_layout_file(
            """
            master
              develop
              feature
            """
        )

        check_out("master")
        feature_worktree = add_worktree("feature")
        # Simulate the out-of-band removal that puts the admin entry into `prunable` state.
        shutil.rmtree(feature_worktree)

        # No `[...]` brackets anywhere - the stale worktree must not pollute the output, AND must not be enough
        # on its own to fire the gate (otherwise we'd see `[<this worktree>]` on `master` for an effectively
        # single-worktree repo, which the no-labels-in-single-worktree-repo test explicitly forbids).
        assert_success(
            ["status"],
            """
              master *
              |
              o-develop
              |
              o-feature
            """,
        )

    def test_status_skips_stale_worktree_but_keeps_healthy_one(self) -> None:
        """When a healthy linked worktree coexists with a stale one (working dir `rm -rf`'d), only the healthy
        one survives the parser. The gate still fires (one healthy linked worktree is enough), the healthy branch
        gets its basename label, and the branch whose worktree got `rm -rf`'d gets no label - same as if that
        branch had never been checked out anywhere except main."""
        create_repo()
        new_branch("master")
        commit()
        check_out("master")
        new_branch("develop")
        commit()
        check_out("master")
        new_branch("feature")
        commit()

        rewrite_branch_layout_file(
            """
            master
              develop
              feature
            """
        )

        check_out("master")
        develop_worktree = add_worktree("develop")
        feature_worktree = add_worktree("feature")
        # `feature`'s worktree goes stale; `develop`'s stays healthy.
        shutil.rmtree(feature_worktree)

        develop_label = os.path.basename(AbsPath(develop_worktree))
        assert "/" not in develop_label

        # `master` is current/main -> `<this worktree>`; `develop` keeps its basename label;
        # `feature` gets no label because its working dir is gone and the parser drops the entry.
        assert_success(
            ["status"],
            f"""
              master * [<this worktree>]
              |
              o-develop [{develop_label}]
              |
              o-feature
            """,
        )
