import os
import subprocess

import pytest
from pytest_mock import MockerFixture

from git_machete.utils import abspath_posix

from .base_test import BaseTest
from .mockers import (assert_success, launch_command, mock_input_returning,
                      rewrite_branch_layout_file)
from .mockers_git_repository import (add_worktree, check_out, commit,
                                     create_repo_with_remote, get_git_version,
                                     new_branch, push, set_git_config_key)

# pytestmark is a special variable that pytest recognizes automatically.
# It applies the specified marks to all test functions in this module.
# This skips all tests in this file if git version < 2.5 (when worktree was introduced).
pytestmark = pytest.mark.skipif(  # noqa: F841
    get_git_version() < (2, 5),
    reason="git worktree command was introduced in git 2.5"
)


class TestTraverseWorktrees(BaseTest):

    def test_traverse_with_worktrees(self) -> None:
        """Test that traverse can handle branches checked out in separate worktrees."""
        from .mockers import execute

        create_repo_with_remote()
        new_branch("develop")
        commit("develop commit")
        push()
        new_branch("feature-1")
        commit("feature-1 commit")
        push()
        new_branch("feature-2")
        commit("feature-2 commit")
        push()

        body: str = \
            """
            develop
                feature-1
                    feature-2
            """
        rewrite_branch_layout_file(body)

        # Create worktrees for feature-1 and feature-2 in temp directories
        check_out("develop")
        feature_1_worktree = add_worktree("feature-1")
        feature_2_worktree = add_worktree("feature-2")

        # Modify feature-1 so it needs to be pushed (ahead of remote)
        initial_dir = os.getcwd()
        os.chdir(feature_1_worktree)
        # In worktrees, .git is a file not a directory, so use git command directly
        execute("touch feature-1-file.txt")
        execute("git add feature-1-file.txt")
        execute('git commit -m "feature-1 additional commit"')
        os.chdir(initial_dir)

        # Modify develop so feature-2 needs to be rebased
        check_out("develop")
        commit("develop additional commit")
        push()

        # Now run traverse - it should cd into the worktrees automatically
        # Using -y flag so no need to mock input
        normalized_feature_1_worktree = abspath_posix(feature_1_worktree)
        normalized_feature_2_worktree = abspath_posix(feature_2_worktree)

        # Assert the full output to verify proper messaging:
        # - When branch is not checked out anywhere: "Checking out ... OK"
        # - When branch is already checked out in a worktree: "Changing directory ..." (no OK, chdir is instant)
        # - When already in correct worktree with correct branch: no message
        assert_success(
            ["traverse", "-y", "--start-from=first-root"],
            f"""

            Changing directory to {normalized_feature_1_worktree} worktree where feature-1 is checked out

              develop
              |
              x-feature-1 * (ahead of origin)
                |
                x-feature-2

            Rebasing feature-1 onto develop...

            Branch feature-1 diverged from (and has newer commits than) its remote counterpart origin/feature-1.
            Pushing feature-1 with force-with-lease to origin...

            Changing directory to {normalized_feature_2_worktree} worktree where feature-2 is checked out

              develop
              |
              o-feature-1
                |
                x-feature-2 *

            Rebasing feature-2 onto feature-1...

            Branch feature-2 diverged from (and has newer commits than) its remote counterpart origin/feature-2.
            Pushing feature-2 with force-with-lease to origin...

              develop
              |
              o-feature-1
                |
                o-feature-2 *

            Reached branch feature-2 which has no successor; nothing left to update
            Warn: branch feature-2 is checked out in worktree at {normalized_feature_2_worktree}
            You may want to change directory with:
              cd {normalized_feature_2_worktree}
            """
        )

        # Verify that feature-1 was pushed in its worktree
        os.chdir(feature_1_worktree)
        feature_1_local = subprocess.check_output("git rev-parse feature-1", shell=True).decode().strip()
        feature_1_remote = subprocess.check_output("git rev-parse origin/feature-1", shell=True).decode().strip()
        assert feature_1_local == feature_1_remote

        # Verify that feature-2 was rebased in its worktree
        os.chdir(feature_2_worktree)
        # feature-2 should now be based on the updated feature-1
        feature_2_log = subprocess.check_output("git log --oneline feature-2", shell=True).decode()
        assert "feature-1 additional commit" in feature_2_log

    def test_traverse_cd_from_linked_to_main_worktree(self) -> None:
        """Test traverse cd from linked worktree to main worktree for non-checked-out branch."""
        (local_path, _) = create_repo_with_remote()
        new_branch("root")
        commit()
        push()
        new_branch("branch-1")
        commit()
        push()

        body: str = \
            """
            root
              branch-1
            """
        rewrite_branch_layout_file(body)

        check_out("root")
        new_branch("branch-2")
        commit()
        # Don't push branch-2 so it will be pushed during traverse

        body = """
        root
          branch-1
          branch-2
        """
        rewrite_branch_layout_file(body)

        # Setup: Main worktree on branch-2, linked worktree for branch-1
        check_out("branch-2")  # Main worktree on branch-2
        branch_1_worktree = add_worktree("branch-1")  # Linked worktree for branch-1

        # cd into branch-1 linked worktree
        os.chdir(branch_1_worktree)

        # Now run traverse --start-from=first-root
        # This will:
        # 1. Checkout root (not in any worktree) in main worktree - triggers cache update
        # 2. Visit branch-1 (already in linked worktree, but no action needed so don't cd)
        # 3. Checkout branch-2 (not in any worktree) in main worktree - triggers cache update
        normalized_local_path = abspath_posix(local_path)

        # This test verifies the worktree cache update logic and cd'ing from linked to main worktree
        assert_success(
            ["traverse", "-y", "--start-from=first-root"],
            f"""
            Changing directory to main worktree at {normalized_local_path}
            Checking out the root branch (root)... OK

            Checking out branch-2... OK

              root
              |
              o-branch-1
              |
              o-branch-2 * (untracked)

            Pushing untracked branch branch-2 to origin...

              root
              |
              o-branch-1
              |
              o-branch-2 *

            Reached branch branch-2 which has no successor; nothing left to update
            Warn: branch branch-2 is checked out in worktree at {normalized_local_path}
            You may want to change directory with:
              cd {normalized_local_path}
            """
        )

    def test_traverse_updates_worktree_cache_on_checkout(self) -> None:
        """Test that the worktree cache is properly updated when checking out in the same worktree."""
        (local_path, _) = create_repo_with_remote()
        new_branch("root")
        commit()
        push()
        new_branch("branch-1")
        commit()
        push()
        new_branch("branch-2")
        commit()
        # Don't push branch-2 so it will be pushed during traverse

        body: str = \
            """
            root
              branch-1
              branch-2
            """
        rewrite_branch_layout_file(body)

        # Setup: Main worktree on root, create a linked worktree for branch-1
        check_out("root")
        add_worktree("branch-1")

        # Run traverse from root in main worktree
        # This will:
        # 1. Initial cache: {root: main_worktree_path, branch-1: linked_worktree_path}
        # 2. Visit root (already checked out in main worktree) - no operation
        # 3. Visit branch-1 (in linked worktree, but no action needed so don't cd)
        # 4. Visit branch-2 (not checked out anywhere) - checkout branch-2 in main worktree
        #    - When checking out branch-2, _update_worktrees_cache_after_checkout is called
        #    - Tests the cache update logic (deletes old entry, adds new entry)

        # Note: branch-2 was created on top of branch-1, so it will appear yellow (?)
        # because the fork point inference will see that branch-2 doesn't contain branch-1
        assert_success(
            ["traverse", "-y"],
            """
            Checking out branch-2... OK

              root
              |
              o-branch-1
              |
              ?-branch-2 * (untracked)

            Warn: yellow edge indicates that fork point for branch-2 is probably incorrectly inferred,
            or that some extra branch should be between root and branch-2.

            Run git machete status --list-commits or git machete status --list-commits-with-hashes to see more details.

            Rebasing branch-2 onto root...

            Pushing untracked branch branch-2 to origin...

              root
              |
              o-branch-1
              |
              o-branch-2 *

            Reached branch branch-2 which has no successor; nothing left to update
            """
        )

    def test_traverse_warns_when_final_branch_in_different_worktree(self) -> None:
        create_repo_with_remote()
        new_branch("root")
        commit("root")
        push()
        new_branch("branch-1")
        commit("branch-1")
        push()
        new_branch("branch-2")
        commit("branch-2")
        push()

        body: str = \
            """
            root
                branch-1
                    branch-2
            """
        rewrite_branch_layout_file(body)

        # Create a worktree for branch-2
        check_out("root")
        branch_2_worktree = add_worktree("branch-2")

        # Make root have an additional commit so branch-1 needs rebase
        check_out("root")
        commit("root additional commit")
        push()

        # Start from root (main worktree), traverse should process through branch-2
        check_out("root")
        output = launch_command("traverse", "-y")

        # Verify the warning is emitted
        assert "branch branch-2 is checked out in worktree at" in output
        normalized_branch_2_worktree = abspath_posix(branch_2_worktree)
        assert f"You may want to change directory with:\n  cd {normalized_branch_2_worktree}" in output

    def test_traverse_no_warn_when_final_branch_in_same_worktree(self) -> None:
        create_repo_with_remote()
        new_branch("root")
        commit("root")
        push()
        new_branch("branch-1")
        commit("branch-1")
        push()

        body: str = \
            """
            root
                branch-1
            """
        rewrite_branch_layout_file(body)

        # Create a worktree for branch-1
        check_out("root")
        add_worktree("branch-1")

        # Start from root (main worktree), traverse ends on root (same worktree)
        check_out("root")
        output = launch_command("traverse", "-y", "--return-to=here")

        # Verify the warning is NOT emitted
        assert "Note: branch" not in output
        assert "You may want to change directory with:" not in output

    def test_traverse_warns_when_quitting_on_branch_in_different_worktree(self, mocker: MockerFixture) -> None:
        create_repo_with_remote()
        new_branch("root")
        commit("root")
        push()
        new_branch("branch-1")
        commit("branch-1")
        push()

        body: str = \
            """
            root
                branch-1
            """
        rewrite_branch_layout_file(body)

        # Create a worktree for branch-1
        check_out("root")
        branch_1_worktree = add_worktree("branch-1")

        # Make root have an additional commit so branch-1 needs rebase
        check_out("root")
        commit("root additional commit")
        push()

        # Start from root (main worktree), traverse will ask to rebase branch-1, user quits
        check_out("root")
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))

        normalized_branch_1_worktree = abspath_posix(branch_1_worktree)

        # This corner case tests that when user quits mid-traverse,
        # the final warning is shown if ended in a different worktree
        assert_success(
            ["traverse"],
            f"""
            Changing directory to {normalized_branch_1_worktree} worktree where branch-1 is checked out

              root
              |
              x-branch-1 *

            Rebase branch-1 onto root? (y, N, q, yq)
            Warn: branch branch-1 is checked out in worktree at {normalized_branch_1_worktree}
            You may want to change directory with:
              cd {normalized_branch_1_worktree}
            """
        )

    def test_traverse_stay_in_same_worktree_when_branch_not_checked_out(self, mocker: MockerFixture) -> None:
        """Test that traverse can stay in the same worktree when branch not checked out, based on config."""
        (local_path, _) = create_repo_with_remote()
        new_branch("root")
        commit()

        new_branch("branch-1")
        commit()
        push()

        check_out("root")
        new_branch("branch-2")
        commit()
        push()

        # Modify root so both branch-1 and branch-2 need rebase
        check_out("root")
        commit("root additional commit")

        body = """
        root
          branch-1
          branch-2
        """
        rewrite_branch_layout_file(body)

        # Setup: Main worktree on some other branch, linked worktrees for root and branch-2
        # branch-1 is NOT checked out anywhere
        check_out("root")  # Start with root in main worktree
        check_out("branch-2")  # Then branch-2 in main worktree
        root_worktree = add_worktree("root")  # Linked worktree for root
        branch_2_worktree = add_worktree("branch-2")  # Linked worktree for branch-2

        # cd into root linked worktree to start traverse from there
        os.chdir(root_worktree)

        normalized_local_path = abspath_posix(local_path)
        normalized_branch_2_worktree = abspath_posix(branch_2_worktree)

        # First test: default behavior (without config key set)
        # We're in root linked worktree
        # Traverse visits: root (already here) -> branch-1 (not checked out anywhere) -> branch-2 (in  worktree)
        # The key difference is when visiting branch-1 (in the MIDDLE of traverse):
        # - Default: cd to main worktree before checking out branch-1
        # - With config: stay in current (root linked) worktree and check out branch-1 there
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n", "n", "n"))
        assert_success(
            ["traverse"],
            f"""
            Push untracked branch root to origin? (y, N, q, yq)

            Changing directory to main worktree at {normalized_local_path}
            Checking out branch-1... OK

              root (untracked)
              |
              x-branch-1 *
              |
              x-branch-2

            Rebase branch-1 onto root? (y, N, q, yq)

            Changing directory to {normalized_branch_2_worktree} worktree where branch-2 is checked out

              root (untracked)
              |
              x-branch-1
              |
              x-branch-2 *

            Rebase branch-2 onto root? (y, N, q, yq)

              root (untracked)
              |
              x-branch-1
              |
              x-branch-2 *

            Reached branch branch-2 which has no successor; nothing left to update
            Warn: branch branch-2 is checked out in worktree at {normalized_branch_2_worktree}
            You may want to change directory with:
              cd {normalized_branch_2_worktree}
            """
        )

        # Reset state: checkout a temporary branch in main worktree so branch-1 is not checked out anywhere
        os.chdir(local_path)  # Go to main worktree
        new_branch("temp-branch")  # Create and checkout temp branch, so branch-1 is no longer checked out
        os.chdir(root_worktree)  # Go back to root linked worktree for the second test

        # Set config to stay in the same worktree
        set_git_config_key("machete.traverse.whenBranchNotCheckedOutInAnyWorktree", "stay-in-the-current-worktree")

        # Second test: with config key set to stay-in-the-current-worktree
        # Now when visiting branch-1 in the MIDDLE, it stays in the current (root linked) worktree instead of cd'ing to main
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n", "n", "n"))
        assert_success(
            ["traverse"],
            f"""
            Push untracked branch root to origin? (y, N, q, yq)

            Checking out branch-1... OK

              root (untracked)
              |
              x-branch-1 *
              |
              x-branch-2

            Rebase branch-1 onto root? (y, N, q, yq)

            Changing directory to {normalized_branch_2_worktree} worktree where branch-2 is checked out

              root (untracked)
              |
              x-branch-1
              |
              x-branch-2 *

            Rebase branch-2 onto root? (y, N, q, yq)

              root (untracked)
              |
              x-branch-1
              |
              x-branch-2 *

            Reached branch branch-2 which has no successor; nothing left to update
            Warn: branch branch-2 is checked out in worktree at {normalized_branch_2_worktree}
            You may want to change directory with:
              cd {normalized_branch_2_worktree}
            """
        )
