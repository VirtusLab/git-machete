import os
import subprocess

import pytest
from pytest_mock import MockerFixture

from git_machete.git_version_thresholds import (REBASE_EMPTY_DROP,
                                                WORKTREE_COMMAND)
from git_machete.utils.exceptions import UnderlyingGitException
from git_machete.utils.paths import AbsPath
from tests.base_test import BaseTest
from tests.cli_runner import (assert_failure, assert_success, launch_command,
                              rewrite_branch_layout_file)
from tests.git_repository import (add_file_and_commit, add_worktree, check_out,
                                  commit, create_repo_with_remote,
                                  get_current_branch, get_git_version,
                                  get_worktree_dirs, new_branch, push,
                                  set_git_config_key)
from tests.mockers import (fixed_author_and_committer_date_in_past,
                           mock_input_returning)

# pytestmark is a special variable that pytest recognizes automatically.
# It applies the specified marks to all test functions in this module.
# This skips all tests in this file if git version < 2.5 (when worktree was introduced).
pytestmark = pytest.mark.skipif(  # noqa: F841
    get_git_version() < WORKTREE_COMMAND,
    reason="git worktree command was introduced in git 2.5"
)


class TestTraverseWorktrees(BaseTest):

    def test_traverse_with_worktrees(self) -> None:
        """Test that traverse can handle branches checked out in separate worktrees."""
        from tests.shell import execute

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
        normalized_feature_1_worktree = AbsPath(feature_1_worktree)
        normalized_feature_2_worktree = AbsPath(feature_2_worktree)
        # Both linked worktrees live under the same OS tempdir; strip_longest_common_path_prefix
        # collapses them to their basenames.
        feature_1_label = os.path.basename(normalized_feature_1_worktree)
        feature_2_label = os.path.basename(normalized_feature_2_worktree)

        # Assert the full output to verify proper messaging:
        # - When branch is not checked out anywhere: "Checking out ... OK"
        # - When branch is already checked out in a worktree: "Changing directory ..." (no OK, chdir is instant)
        # - When already in correct worktree with correct branch: no message
        assert_success(
            ["traverse", "-y", "--start-from=first-root"],
            f"""

            Changing directory to {normalized_feature_1_worktree} worktree where feature-1 is checked out

              develop [<main worktree>]
              |
              x-feature-1 * [<this worktree>] (ahead of origin)
                |
                x-feature-2 [{feature_2_label}]

            Rebasing feature-1 onto develop...

            Branch feature-1 diverged from (and has newer commits than) its remote counterpart origin/feature-1.
            Pushing feature-1 with force-with-lease to origin...

            Changing directory to {normalized_feature_2_worktree} worktree where feature-2 is checked out

              develop [<main worktree>]
              |
              o-feature-1 [{feature_1_label}]
                |
                x-feature-2 * [<this worktree>]

            Rebasing feature-2 onto feature-1...

            Branch feature-2 diverged from (and has newer commits than) its remote counterpart origin/feature-2.
            Pushing feature-2 with force-with-lease to origin...

              develop [<main worktree>]
              |
              o-feature-1 [{feature_1_label}]
                |
                o-feature-2 * [<this worktree>]

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
        normalized_local_path = AbsPath(local_path)
        # Single linked worktree: strip_longest_common_path_prefix falls back to the basename.
        branch_1_label = os.path.basename(AbsPath(branch_1_worktree))

        # This test verifies the worktree cache update logic and cd'ing from linked to main worktree
        assert_success(
            ["traverse", "-y", "--start-from=first-root"],
            f"""
            Changing directory to main worktree at {normalized_local_path}
            Checking out the root branch (root)... OK

            Checking out branch-2... OK

              root
              |
              o-branch-1 [{branch_1_label}]
              |
              o-branch-2 * [<this worktree>] (untracked)

            Pushing untracked branch branch-2 to origin...

              root
              |
              o-branch-1 [{branch_1_label}]
              |
              o-branch-2 * [<this worktree>]

            Reached branch branch-2 which has no successor; nothing left to update
            Warn: branch branch-2 is checked out in worktree at {normalized_local_path}
            You may want to change directory with:
              cd {normalized_local_path}
            """
        )

    def test_traverse_reflects_post_checkout_worktree_state_in_status(self) -> None:
        """After traverse checks out a new branch in the current worktree, the worktree label
        rendered by the post-rebase status block must reflect the new checkout (`branch-2` is
        now in the main worktree, not `root`). This exercises the live re-query of
        `git worktree list --porcelain` inside `_find_worktree_for_branch`/`_compute_worktree_label_by_branch`
        - any stale snapshot would still report `root` as the branch held by the main worktree
        and the `[<this worktree>]` label would land on the wrong row."""
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

        # Setup: Main worktree on root, create a linked worktree for branch-1.
        check_out("root")
        branch_1_worktree = add_worktree("branch-1")
        # Single linked worktree: strip_longest_common_path_prefix falls back to the basename.
        branch_1_label = os.path.basename(AbsPath(branch_1_worktree))

        # Traverse plan:
        # 1. Visit root (already checked out in main worktree) - no operation.
        # 2. Visit branch-1 (in linked worktree, no action needed - don't cd).
        # 3. Visit branch-2 (not checked out anywhere) - checkout branch-2 in main worktree.
        # The post-checkout status block (printed after the rebase/push step) must show
        # `branch-2 * [<this worktree>]` because the main worktree now holds branch-2.
        #
        # Note: branch-2 was created on top of branch-1, so it appears yellow (?) - the fork
        # point inference sees that branch-2 doesn't contain branch-1.
        assert_success(
            ["traverse", "-y"],
            f"""
            Checking out branch-2... OK

              root
              |
              o-branch-1 [{branch_1_label}]
              |
              ?-branch-2 * [<this worktree>] (untracked)

            Warn: yellow edge indicates that fork point for branch-2 is probably incorrectly inferred,
            or that some extra branch should be between root and branch-2.

            Run git machete status --list-commits or git machete status --list-commits-with-hashes to see more details.

            Rebasing branch-2 onto root...

            Pushing untracked branch branch-2 to origin...

              root
              |
              o-branch-1 [{branch_1_label}]
              |
              o-branch-2 * [<this worktree>]

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
        normalized_branch_2_worktree = AbsPath(branch_2_worktree)
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

        normalized_branch_1_worktree = AbsPath(branch_1_worktree)

        # This corner case tests that when user quits mid-traverse,
        # the final warning is shown if ended in a different worktree
        assert_success(
            ["traverse"],
            f"""
            Changing directory to {normalized_branch_1_worktree} worktree where branch-1 is checked out

              root [<main worktree>]
              |
              x-branch-1 * [<this worktree>]

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

        normalized_local_path = AbsPath(local_path)
        normalized_branch_2_worktree = AbsPath(branch_2_worktree)
        # Two linked worktrees sharing the OS tempdir parent collapse to their basenames.
        root_label = os.path.basename(AbsPath(root_worktree))
        branch_2_label = os.path.basename(normalized_branch_2_worktree)

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

              root [{root_label}] (untracked)
              |
              x-branch-1 * [<this worktree>]
              |
              x-branch-2 [{branch_2_label}]

            Rebase branch-1 onto root? (y, N, q, yq)

            Changing directory to {normalized_branch_2_worktree} worktree where branch-2 is checked out

              root [{root_label}] (untracked)
              |
              x-branch-1 [<main worktree>]
              |
              x-branch-2 * [<this worktree>]

            Rebase branch-2 onto root? (y, N, q, yq)

              root [{root_label}] (untracked)
              |
              x-branch-1 [<main worktree>]
              |
              x-branch-2 * [<this worktree>]

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
        # After the in-worktree checkout, `root_worktree` holds branch-1 (no longer root),
        # so root is no longer in any worktree and gets no label; the linked-prefix calculation
        # still produces the same basenames since both linked-worktree paths are unchanged.
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n", "n", "n"))
        assert_success(
            ["traverse"],
            f"""
            Push untracked branch root to origin? (y, N, q, yq)

            Checking out branch-1... OK

              root (untracked)
              |
              x-branch-1 * [<this worktree>]
              |
              x-branch-2 [{branch_2_label}]

            Rebase branch-1 onto root? (y, N, q, yq)

            Changing directory to {normalized_branch_2_worktree} worktree where branch-2 is checked out

              root (untracked)
              |
              x-branch-1 [{root_label}]
              |
              x-branch-2 * [<this worktree>]

            Rebase branch-2 onto root? (y, N, q, yq)

              root (untracked)
              |
              x-branch-1 [{root_label}]
              |
              x-branch-2 * [<this worktree>]

            Reached branch branch-2 which has no successor; nothing left to update
            Warn: branch branch-2 is checked out in worktree at {normalized_branch_2_worktree}
            You may want to change directory with:
              cd {normalized_branch_2_worktree}
            """
        )

    def test_traverse_cd_into_temporary_worktree_when_branch_not_checked_out(self, mocker: MockerFixture) -> None:
        """Test that traverse creates a temporary worktree for branches not checked out anywhere."""
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

        # Setup: Main worktree on root, linked worktree also for root.
        # branch-1 and branch-2 are NOT checked out anywhere.
        check_out("root")
        root_worktree = add_worktree("root")

        os.chdir(root_worktree)

        set_git_config_key("machete.traverse.whenBranchNotCheckedOutInAnyWorktree", "cd-into-temporary-worktree")

        normalized_root_worktree = AbsPath(root_worktree)
        # `root` is checked out in both the main worktree and `root_worktree` (forced via -f);
        # `git worktree list --porcelain` lists main first, so the linked entry wins in the
        # branch-to-worktree mapping and `root` ends up labeled with `root_worktree`'s basename.
        root_label = os.path.basename(normalized_root_worktree)

        # The temp worktree gets a random `git-machete-worktree-XXXX` basename, but it's also the
        # *current* worktree (traverse cd's into it), so its label collapses to the literal
        # `<this worktree>` -- which keeps this whole assertion deterministic.
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n", "n", "n"))
        assert_success(
            ["traverse"],
            f"""
            Push untracked branch root to origin? (y, N, q, yq)

            Creating a temporary worktree to check out branch-1... OK

              root [{root_label}] (untracked)
              |
              x-branch-1 * [<this worktree>]
              |
              x-branch-2

            Rebase branch-1 onto root? (y, N, q, yq)

            Removing the temporary worktree; changing directory back to {normalized_root_worktree}
            Creating a temporary worktree to check out branch-2... OK

              root [{root_label}] (untracked)
              |
              x-branch-1
              |
              x-branch-2 * [<this worktree>]

            Rebase branch-2 onto root? (y, N, q, yq)

              root [{root_label}] (untracked)
              |
              x-branch-1
              |
              x-branch-2 * [<this worktree>]

            Reached branch branch-2 which has no successor; nothing left to update
            Removing the temporary worktree; changing directory back to {normalized_root_worktree}
            """
        )

        # Verify the checked-out branch in existing worktrees hasn't changed
        os.chdir(local_path)
        assert get_current_branch() == "root"
        os.chdir(root_worktree)
        assert get_current_branch() == "root"

        # Verify no temporary worktree lingers after traverse
        assert len(get_worktree_dirs()) == 2
        assert "git-machete-worktree-" not in " ".join(get_worktree_dirs())

    def test_traverse_cd_into_temporary_worktree_with_rebase(self) -> None:
        """Test that traverse with temporary worktrees correctly performs rebase operations."""
        (local_path, _) = create_repo_with_remote()
        new_branch("root")
        commit()
        push()
        new_branch("feature")
        commit()
        push()

        body = """
        root
          feature
        """
        rewrite_branch_layout_file(body)

        check_out("root")
        commit("root additional commit")
        push()

        set_git_config_key("machete.traverse.whenBranchNotCheckedOutInAnyWorktree", "cd-into-temporary-worktree")

        normalized_local_path = AbsPath(local_path)

        assert_success(
            ["traverse", "-y"],
            f"""
            Creating a temporary worktree to check out feature... OK

              root [<main worktree>]
              |
              x-feature * [<this worktree>]

            Rebasing feature onto root...

            Branch feature diverged from (and has newer commits than) its remote counterpart origin/feature.
            Pushing feature with force-with-lease to origin...

              root [<main worktree>]
              |
              o-feature * [<this worktree>]

            Reached branch feature which has no successor; nothing left to update
            Removing the temporary worktree; changing directory back to {normalized_local_path}
            """
        )

        assert get_current_branch() == "root"

        # Verify no temporary worktree lingers after traverse
        assert len(get_worktree_dirs()) == 1
        assert "git-machete-worktree-" not in " ".join(get_worktree_dirs())

    def test_traverse_cd_into_temporary_worktree_warns_when_started_from_linked_worktree(self) -> None:
        """Test that the end-of-traverse warning fires when temp worktree cleanup lands us in main worktree,
        which is different from the linked worktree where traverse started."""
        (local_path, _) = create_repo_with_remote()
        new_branch("root")
        commit()
        push()
        new_branch("feature")
        commit()
        push()

        body = """
        root
          feature
        """
        rewrite_branch_layout_file(body)

        check_out("root")
        commit("root additional commit")
        push()

        # Create a linked worktree on a separate (unmanaged) branch.
        # Main worktree stays on root, linked worktree gets `other`.
        new_branch("other")
        check_out("root")
        other_worktree = add_worktree("other")

        set_git_config_key("machete.traverse.whenBranchNotCheckedOutInAnyWorktree", "cd-into-temporary-worktree")

        # Start traverse from the linked worktree (on `other`).
        os.chdir(other_worktree)

        normalized_local_path = AbsPath(local_path)

        # Traverse visits:
        # - root: already checked out in main worktree -> cd there
        # - feature: not checked out anywhere -> temp worktree
        # After traverse, temp worktree is removed and we end up in main worktree,
        # which differs from the linked worktree where we started -> warning fires.
        assert_success(
            ["traverse", "-y", "--start-from=first-root"],
            f"""
            Changing directory to {normalized_local_path} worktree where root is checked out

            Creating a temporary worktree to check out feature... OK

              root [<main worktree>]
              |
              x-feature * [<this worktree>]

            Rebasing feature onto root...

            Branch feature diverged from (and has newer commits than) its remote counterpart origin/feature.
            Pushing feature with force-with-lease to origin...

              root [<main worktree>]
              |
              o-feature * [<this worktree>]

            Reached branch feature which has no successor; nothing left to update
            Removing the temporary worktree; changing directory back to {normalized_local_path}
            Warn: branch root is checked out in worktree at {normalized_local_path}
            You may want to change directory with:
              cd {normalized_local_path}
            """
        )

        # Verify no temporary worktree lingers after traverse
        assert len(get_worktree_dirs()) == 2
        assert "git-machete-worktree-" not in " ".join(get_worktree_dirs())

    # The expected error message includes `--empty=drop` which is only passed on git >= 2.26.0.
    @pytest.mark.skipif(get_git_version() < REBASE_EMPTY_DROP, reason="--empty=drop is only passed to git rebase since git 2.26.0")
    def test_traverse_rebase_conflict_in_worktree(self) -> None:
        create_repo_with_remote()
        with fixed_author_and_committer_date_in_past():
            new_branch("base")
            add_file_and_commit("file.txt", "base content\n", "Base commit")
            push()
            new_branch("feature")
            add_file_and_commit("file.txt", "feature content\n", "Feature commit")
            push()

        body: str = \
            """
            base
                feature
            """
        rewrite_branch_layout_file(body)

        # Create a worktree for feature
        check_out("base")
        feature_worktree = add_worktree("feature")
        normalized_feature_worktree = AbsPath(feature_worktree)

        # Make a conflicting change on base
        check_out("base")
        with fixed_author_and_committer_date_in_past():
            add_file_and_commit("file.txt", "conflicting base content\n", "Conflicting base commit")
            push()

        assert_failure(
            ["traverse", "-y"],
            "git -c log.showSignature=false rebase --empty=drop"
            " --onto refs/heads/base 77b81e64de792099dad58d67756b66cda9e80aa7 feature returned 1",
            expected_type=UnderlyingGitException,
            expected_output=f"""
            Changing directory to {normalized_feature_worktree} worktree where feature is checked out

              base [<main worktree>]
              |
              x-feature * [<this worktree>]

            Rebasing feature onto base...
            Warn: branch feature is checked out in worktree at {normalized_feature_worktree}
            You may want to change directory with:
              cd {normalized_feature_worktree}
            """
        )

    # Regression test for https://github.com/VirtusLab/git-machete/issues/1681.
    #
    # When `traverse` auto-slides out a branch that's checked out in a
    # linked worktree, it `os.chdir`s into that worktree first. Previously
    # the layout file path was computed at client construction time as a
    # cwd-relative path (e.g. `.git/machete`); inside a linked worktree
    # `.git` is a gitdir-pointer file, so `save_branch_layout_file`'s
    # subsequent `open(path, "w")` raised `NotADirectoryError`. The path is
    # now stored as absolute, so it survives any mid-traverse `chdir`.
    def test_traverse_auto_slide_out_in_worktree(self) -> None:
        from tests.shell import execute

        create_repo_with_remote()
        new_branch("main")
        commit("M1")
        push()
        # Create `a` as a plain branch ref at M1 (no checkout, so it doesn't
        # diverge from `main`), then advance `main` to M2 and fast-forward
        # `a` in its worktree to match. After this `a` is at M2 (== main),
        # which makes traverse classify it as "merged into main" and
        # auto-slide-out eligible.
        execute("git branch a")
        commit("M2")
        push()

        body: str = \
            """
            main
                a
            """
        rewrite_branch_layout_file(body)

        # Put `a` in a linked worktree so traverse `chdir`s into it on
        # visit. Pre-fix, the subsequent layout-file save would have
        # raised `NotADirectoryError` because the path was cached as
        # `.git/machete` relative to the main-worktree cwd.
        a_worktree = add_worktree("a")

        initial_dir = os.getcwd()
        os.chdir(a_worktree)
        execute("git merge --ff-only main")
        os.chdir(initial_dir)

        normalized_a_worktree = AbsPath(a_worktree)

        assert_success(
            ["traverse", "-y"],
            f"""
            Changing directory to {normalized_a_worktree} worktree where a is checked out

              main [<main worktree>]
              |
              m-a * [<this worktree>] (untracked)

            Branch a is merged into main. Sliding a out of the tree of branch dependencies...

              main [<main worktree>]

            No successor of a needs to be slid out or synced with upstream branch or remote; nothing left to update
            Warn: branch a is checked out in worktree at {normalized_a_worktree}
            You may want to change directory with:
              cd {normalized_a_worktree}
            """
        )
