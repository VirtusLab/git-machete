import textwrap

import pytest

from git_machete.git_version_thresholds import WORKTREE_COMMAND
from git_machete.utils.paths import AbsPath
from tests.base_test import BaseTest
from tests.cli_runner import assert_failure, read_branch_layout_file, rewrite_branch_layout_file
from tests.git_repository import add_worktree, check_out, commit, create_repo, get_git_version, new_branch

# pytestmark is a special variable that pytest recognizes automatically.
# It applies the specified marks to all test functions in this module.
# This skips all tests in this file if git version < 2.5 (when worktree was introduced).
pytestmark = pytest.mark.skipif(  # noqa: F841
    get_git_version() < WORKTREE_COMMAND,
    reason="git worktree command was introduced in git 2.5"
)


class TestSlideOutWorktrees(BaseTest):

    def test_slide_out_fails_when_new_parent_is_in_another_worktree(self) -> None:
        """`slide-out` refuses upfront, before mutating `.git/machete`, when the new parent (which slide-out
        would `git checkout` after the layout update) is already held by another linked worktree. The
        error message points the user at the conflicting worktree directly (no raw `fatal: '<branch>' is
        already used by worktree at <path>` from git), and crucially the layout file stays intact so the
        user isn't left with a half-applied slide-out (see https://github.com/VirtusLab/git-machete/issues/1711).

        `slide-out` must also NOT silently `cd` into the conflicting worktree as a workaround - `os.chdir`
        from a Python subprocess cannot propagate back to the user's shell, so exit-0 + a silent chdir would
        mislead scripts/agents into thinking the slide-out completed in the current worktree."""
        create_repo()
        new_branch("develop")
        commit()
        new_branch("feature-1")
        commit()
        new_branch("feature-2")
        commit()

        original_layout = \
            """
            develop
                feature-1
                    feature-2
            """
        rewrite_branch_layout_file(original_layout)

        # Pin `develop` to a linked worktree, then move the main worktree off it
        # so `slide-out feature-1` (run from the main worktree, currently on `feature-1`)
        # would land us on `develop` here - which the preflight must refuse.
        check_out("develop")
        develop_worktree = add_worktree("develop")
        check_out("feature-1")

        normalized_develop_worktree = AbsPath(develop_worktree)
        assert_failure(
            ["slide-out", "--no-rebase"],  # `--no-rebase` keeps the scenario focused on the new-parent checkout.
            f"Branch develop is already checked out in another worktree at {normalized_develop_worktree}.\n"
            f"Run cd {normalized_develop_worktree} to work on it there,\n"
            f"or git worktree remove {normalized_develop_worktree} to drop that worktree.",
            # Preflight fires before any layout/checkout breadcrumb is printed - no "Checking out develop..."
            # should leak out (otherwise the user can't tell whether the slide-out partially happened).
            expected_output="",
        )
        # The actual fix: layout file is unchanged. Pre-fix this assertion would catch the regression where
        # `feature-1` got removed from `.git/machete` despite the checkout failing afterwards.
        assert read_branch_layout_file() == textwrap.dedent(original_layout)

    def test_slide_out_fails_when_child_is_in_another_worktree(self) -> None:
        """Same preflight, second source: when the user is *not* standing on a slid-out branch but the layout
        has children that the post-slide-out rebase loop will need to check out, the preflight must also catch
        a child held by another linked worktree - again before mutating `.git/machete`.

        This is the exact `master -> A -> B -> C, slide-out B from A's worktree` reproducer from #1711:
        we're on `feature-1` (the new parent), sliding out `feature-2`, and `feature-3` (the child that the
        rebase loop would check out) lives in a linked worktree."""
        create_repo()
        new_branch("develop")
        commit()
        new_branch("feature-1")
        commit()
        new_branch("feature-2")
        commit()
        new_branch("feature-3")
        commit()

        original_layout = \
            """
            develop
                feature-1
                    feature-2
                        feature-3
            """
        rewrite_branch_layout_file(original_layout)

        # `feature-3` goes to a linked worktree; we stand on `feature-1` (the new parent after sliding out
        # `feature-2`), so the rebase loop would otherwise `checkout_in_current_worktree(feature-3)` and fail
        # there - well after `.git/machete` had been rewritten.
        check_out("feature-3")
        feature_3_worktree = add_worktree("feature-3")
        check_out("feature-1")

        normalized_feature_3_worktree = AbsPath(feature_3_worktree)
        assert_failure(
            ["slide-out", "feature-2"],
            f"Branch feature-3 is already checked out in another worktree at {normalized_feature_3_worktree}.\n"
            f"Run cd {normalized_feature_3_worktree} to work on it there,\n"
            f"or git worktree remove {normalized_feature_3_worktree} to drop that worktree.",
            expected_output="",
        )
        assert read_branch_layout_file() == textwrap.dedent(original_layout)
