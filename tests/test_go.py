import os

import pytest
from pytest_mock import MockerFixture

from git_machete.git_version_thresholds import WORKTREE_COMMAND
from git_machete.utils.paths import AbsPath
from tests.base_test import BaseTest
from tests.cli_runner import (assert_failure, assert_success, launch_command,
                              rewrite_branch_layout_file)
from tests.git_repository import (add_worktree, check_out, commit, create_repo,
                                  get_commit_hash, get_git_version, new_branch,
                                  new_orphan_branch)
from tests.mockers import mock_input_returning


class TestGo(BaseTest):

    def test_go_up(self) -> None:
        """Verify behavior of a 'git machete go up' command.

        Verify that 'git machete go up' performs 'git checkout' to the
        parent/upstream branch of the current branch.
        """

        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1-branch")
        commit()
        new_branch("level-2-branch")

        body: str = \
            """
            level-0-branch
                level-1-branch
            """
        rewrite_branch_layout_file(body)

        check_out("level-0-branch")
        assert_failure(["go", "up"], "Branch level-0-branch has no upstream branch")

        check_out("level-1-branch")
        launch_command("go", "up")
        assert 'level-0-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete go up' performs 'git checkout' to "
             "the parent/upstream branch of the current branch.")

        check_out("level-1-branch")
        launch_command("g", "u")
        assert 'level-0-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete g u' performs 'git checkout' to "
             "the parent/upstream branch of the current branch.")

        check_out("level-2-branch")
        assert_success(
            ["g", "u"],
            "Warn: branch level-2-branch not found in the tree of branch dependencies; "
            "the upstream has been inferred to level-1-branch\n"
            "Checking out level-1-branch... OK\n"
        )
        assert 'level-1-branch' == launch_command("show", "current").strip()

    def test_go_down(self, mocker: MockerFixture) -> None:
        """Verify behavior of a 'git machete go down' command.

        Verify that 'git machete go down' performs 'git checkout' to the
        child/downstream branch of the current branch.
        """

        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1-branch")
        commit()
        new_branch("level-2a-branch")
        commit()
        check_out("level-1-branch")
        new_branch("level-2b-branch")
        commit()

        body: str = \
            """
            level-0-branch
                level-1-branch
                    level-2a-branch
                    level-2b-branch
            """
        rewrite_branch_layout_file(body)

        check_out("level-0-branch")
        assert_success(
            ["go", "down"],
            "Checking out level-1-branch... OK\n"
            "Tip: run git machete go (without a direction) to pick a branch interactively.\n",
        )
        assert launch_command("show", "current").strip() == "level-1-branch"

        check_out("level-0-branch")
        assert_success(
            ["g", "d"],
            "Checking out level-1-branch... OK\n"
            "Tip: run git machete go (without a direction) to pick a branch interactively.\n",
        )
        assert launch_command("show", "current").strip() == "level-1-branch"

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("2"))
        launch_command("go", "down")
        assert launch_command("show", "current").strip() == "level-2b-branch"

    def test_go_first_root_with_downstream(self) -> None:
        """Verify behavior of a 'git machete go first' command.

        Verify that 'git machete go first' performs 'git checkout' to
        the first downstream branch of a root branch in the config file
        if root branch has any downstream branches.
        """

        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1a-branch")
        commit()
        new_branch("level-2a-branch")
        commit()
        check_out("level-0-branch")
        new_branch("level-1b-branch")
        commit()
        new_branch("level-2b-branch")
        commit()
        new_branch("level-3b-branch")
        commit()
        # a added so root will be placed in the config file after the level-0-branch
        new_orphan_branch("a-additional-root")
        commit()
        new_branch("branch-from-a-additional-root")
        commit()

        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
                    level-2b-branch
            a-additional-root
                branch-from-a-additional-root
            """
        rewrite_branch_layout_file(body)

        check_out("level-3b-branch")
        assert_success(
            ["go", "first"],
            "Warn: level-3b-branch is not a managed branch, assuming "
            "level-0-branch (the first root) instead as root\n"
            "Checking out level-1a-branch... OK\n",
        )
        assert 'level-1a-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete go first' performs 'git checkout' to "
             "the first downstream branch of a root branch if root branch "
             "has any downstream branches.")

        check_out("level-3b-branch")
        assert_success(
            ["g", "f"],
            "Warn: level-3b-branch is not a managed branch, assuming "
            "level-0-branch (the first root) instead as root\n"
            "Checking out level-1a-branch... OK\n",
        )
        assert 'level-1a-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete g f' performs 'git checkout' to "
             "the first downstream branch of a root branch if root branch "
             "has any downstream branches.")

    def test_go_first_root_without_downstream(self) -> None:
        """Verify behavior of a 'git machete go first' command.

        Verify that 'git machete go first' set current branch to root
        if root branch has no downstream.
        """
        create_repo()
        new_branch("level-0-branch")
        commit()

        body: str = \
            """
            level-0-branch
            """
        rewrite_branch_layout_file(body)
        launch_command("go", "first")

        assert 'level-0-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete go first' set current branch to root "
             "if root branch has no downstream.")
        # check short command behavior
        launch_command("g", "f")

        assert 'level-0-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete g f' set current branch to root "
             "if root branch has no downstream.")

    def test_go_last(self) -> None:
        """Verify behavior of a 'git machete go last' command.

        Verify that 'git machete go last' performs 'git checkout' to
        the last downstream branch of a root branch if root branch
        has any downstream branches.
        """
        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1a-branch")
        commit()
        new_branch("level-2a-branch")
        commit()
        check_out("level-0-branch")
        new_branch("level-1b-branch")
        commit()
        new_branch("level-2b-branch")
        commit()
        # x added so root will be placed in the config file after the level-0-branch
        new_orphan_branch("x-additional-root")
        commit()
        new_branch("branch-from-x-additional-root")
        commit()

        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
            x-additional-root
                branch-from-x-additional-root
            """
        rewrite_branch_layout_file(body)

        check_out("level-1a-branch")
        launch_command("go", "last", "--debug")
        assert 'level-1b-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete go last' performs 'git checkout' to "
             "the last downstream branch of a root branch if root branch "
             "has any downstream branches.")

        check_out("level-1a-branch")
        launch_command("g", "l", "-v")
        assert 'level-1b-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete g l' performs 'git checkout' to "
             "the last downstream branch of a root branch if root branch "
             "has any downstream branches.")

        check_out("level-2b-branch")
        assert_success(
            ["g", "l"],
            "Warn: level-2b-branch is not a managed branch, assuming "
            "x-additional-root (the last root) instead as root\n"
            "Checking out branch-from-x-additional-root... OK\n",
        )
        assert 'branch-from-x-additional-root' == launch_command("show", "current").strip()

    def test_go_next_successor_exists(self) -> None:
        """Verify behavior of a 'git machete go next' command.

        Verify that 'git machete go next' performs 'git checkout' to
        the branch right after the current one in the config file
        when successor branch exists within the root tree.

        """

        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1a-branch")
        commit()
        new_branch("level-2a-branch")
        commit()
        check_out("level-0-branch")
        new_branch("level-1b-branch")
        commit()
        check_out("level-2a-branch")

        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
            """
        rewrite_branch_layout_file(body)
        launch_command("go", "next")

        assert 'level-1b-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete go next' performs 'git checkout' to "
             "the next downstream branch right after the current one in the "
             "config file if successor branch exists.")

        check_out("level-2a-branch")
        launch_command("g", "n")

        assert 'level-1b-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete g n' performs 'git checkout' to "
             "the next downstream branch right after the current one in the "
             "config file if successor branch exists.")

    def test_go_next_successor_on_another_root_tree(self) -> None:
        """Verify behavior of a 'git machete go next' command.

        Verify that 'git machete go next' can checkout to branch that doesn't
        share root with the current branch.
        """

        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1-branch")
        commit()
        # x added so root will be placed in the config file after the level-0-branch
        new_orphan_branch("x-additional-root")
        commit()
        check_out("level-1-branch")

        body: str = \
            """
            level-0-branch
                level-1-branch
            x-additional-root
            """
        rewrite_branch_layout_file(body)
        launch_command("go", "next")

        assert 'x-additional-root' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete go next' can checkout to branch that doesn't "
             "share root with the current branch."
             )

        check_out("level-1-branch")
        launch_command("g", "n")

        assert 'x-additional-root' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete g n' can checkout to branch that doesn't "
             "share root with the current branch.")

    def test_go_prev_successor_exists(self) -> None:
        """Verify behavior of a 'git machete go prev' command.

        Verify that 'git machete go prev' performs 'git checkout' to
        the branch right before the current one in the config file
        when predecessor branch exists within the root tree.
        """

        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1a-branch")
        commit()
        new_branch("level-2a-branch")
        commit()
        check_out("level-0-branch")
        new_branch("level-1b-branch")
        commit()

        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
            """
        rewrite_branch_layout_file(body)
        launch_command("go", "prev")

        assert 'level-2a-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete go prev' performs 'git checkout' to "
             "the branch right before the current one in the config file "
             "when predecessor branch exists within the root tree."
             )

        check_out("level-1b-branch")
        launch_command("g", "p")

        assert 'level-2a-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete g p' performs 'git checkout' to "
             "the branch right before the current one in the config file "
             "when predecessor branch exists within the root tree.")

    def test_go_prev_successor_on_another_root_tree(self) -> None:
        """Verify behavior of a 'git machete go prev' command.

        Verify that 'git machete go prev' raises an error when predecessor
        branch doesn't exist.
        """

        create_repo()
        new_branch("level-0-branch")
        commit()
        # a added so root will be placed in the config file before the level-0-branch
        new_orphan_branch("a-additional-root")
        commit()
        check_out("level-0-branch")

        body: str = \
            """
            a-additional-root
            level-0-branch
            """
        rewrite_branch_layout_file(body)
        launch_command("go", "prev")

        assert 'a-additional-root' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete go prev' can checkout to branch that doesn't "
             "share root with the current branch.")

        check_out("level-0-branch")
        launch_command("g", "p")

        assert 'a-additional-root' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete g p' can checkout to branch that doesn't "
             "share root with the current branch."
             )

    def test_go_root(self) -> None:
        """Verify behavior of a 'git machete go root' command.

        Verify that 'git machete go root' performs 'git checkout' to
        the root of the current branch.
        """

        create_repo()
        new_branch("level-0-branch")
        commit()
        new_branch("level-1a-branch")
        commit()
        new_branch("level-2a-branch")
        commit()
        check_out("level-0-branch")
        new_branch("level-1b-branch")
        commit()
        new_orphan_branch("additional-root")
        commit()
        new_branch("branch-from-additional-root")
        commit()
        check_out("level-2a-branch")

        body: str = \
            """
            level-0-branch
                level-1a-branch
                    level-2a-branch
                level-1b-branch
            additional-root
                branch-from-additional-root
            """
        rewrite_branch_layout_file(body)
        launch_command("go", "root")

        assert 'level-0-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete go root' performs 'git checkout' to "
             "the root of the current branch.")

        check_out("level-2a-branch")
        launch_command("g", "r")

        assert 'level-0-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete g r' performs 'git checkout' to "
             "the root of the current branch.")

        new_branch("not-in-machete-layout")
        commit()
        check_out("not-in-machete-layout")
        assert_success(
            ["go", "root"],
            "Warn: not-in-machete-layout is not a managed branch, assuming "
            "level-0-branch (the first root) instead as root\n"
            "Checking out level-0-branch... OK\n",
        )
        assert 'level-0-branch' == launch_command("show", "current").strip()

    def test_go_root_no_branches(self) -> None:
        create_repo()
        expected_error_message = """
          No branches listed in .git/machete. Consider one of:
          * git machete discover
          * git machete edit or edit .git/machete manually
          * git machete github checkout-prs --mine
          * git machete gitlab checkout-mrs --mine"""
        assert_failure(["g", "root"], expected_error_message)

    @pytest.mark.skipif(get_git_version() < WORKTREE_COMMAND, reason="git worktree command was introduced in git 2.5")
    def test_go_with_worktree(self) -> None:
        """`go down` fails with an actionable machete-level error (not the raw `git checkout` error)
        when the target branch is already checked out in a linked worktree, and the user's cwd is
        left untouched (we deliberately do NOT silently `cd` into the linked worktree - `os.chdir`
        can never propagate back to the user's shell, so doing so + exiting 0 would mislead both
        interactive users and scripts/agents into thinking the checkout succeeded)."""
        create_repo()
        new_branch("develop")
        commit()
        new_branch("feature-1")
        commit()
        new_branch("feature-2")
        commit()

        body: str = \
            """
            develop
                feature-1
                    feature-2
            """
        rewrite_branch_layout_file(body)

        check_out("develop")
        feature_1_worktree = add_worktree("feature-1")

        check_out("develop")
        initial_dir = os.getcwd()

        normalized_feature_1_worktree = AbsPath(feature_1_worktree)
        assert_failure(
            ["go", "down"],
            f"Branch feature-1 is already checked out in another worktree at {normalized_feature_1_worktree}.\n"
            f"Run cd {normalized_feature_1_worktree} to work on it there,\n"
            f"or git worktree remove {normalized_feature_1_worktree} to drop that worktree.",
        )

        assert os.getcwd() == initial_dir, "go should not change directory"
        assert launch_command("show", "current").strip() == "develop", \
            "HEAD should remain on develop - the failed `go down` must not silently leave a partial state."

    def test_go_directions_when_detached_head(self) -> None:
        """Verify behavior of 'git machete go' commands when in detached HEAD mode.

        Expected behavior:
        - first, root, last should work (navigate to absolute positions)
          - first: go to first downstream of first root (child-1a)
          - root: go to first root (root-1)
          - last: go to last branch under last root (child-2a)
        - down, next, prev, up should fail (require current branch context)
        """
        create_repo()
        new_branch("root-1")
        commit()
        new_branch("child-1a")
        commit()
        new_branch("child-1b")
        commit()
        check_out("root-1")
        new_orphan_branch("root-2")
        commit()
        new_branch("child-2a")
        commit()

        body: str = \
            """
            root-1
                child-1a
                child-1b
            root-2
                child-2a
            """
        rewrite_branch_layout_file(body)

        # Get a commit hash to checkout in detached HEAD mode
        detached_commit = get_commit_hash("root-2")

        # These should work (navigate to absolute positions):
        check_out(detached_commit)
        launch_command("go", "first")
        assert 'child-1a' == launch_command("show", "current").strip(), \
            "go first should work in detached HEAD mode and go to first downstream of first root"

        # Re-enter detached HEAD
        check_out(detached_commit)

        launch_command("go", "root")
        assert 'root-1' == launch_command("show", "current").strip(), \
            "go root should work in detached HEAD mode and go to first root"

        # Re-enter detached HEAD
        check_out(detached_commit)

        launch_command("go", "last")
        assert 'child-2a' == launch_command("show", "current").strip(), \
            "go last should work in detached HEAD mode and go to last branch under last root"

        # Re-enter detached HEAD for the failing commands
        check_out(detached_commit)

        # These should fail (require current branch context):
        assert_failure(["go", "down"], "Not currently on any branch")
        assert_failure(["go", "next"], "Not currently on any branch")
        assert_failure(["go", "prev"], "Not currently on any branch")
        assert_failure(["go", "up"], "Not currently on any branch")
