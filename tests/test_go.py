import os

from pytest_mock import MockerFixture

from git_machete.exceptions import ExitCode

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, launch_command,
                      launch_command_capturing_output_and_exception,
                      mock_input_returning, rewrite_branch_layout_file)
from .mockers_git_repository import (add_worktree, check_out, commit,
                                     create_repo, get_git_version, new_branch,
                                     new_orphan_branch)


class TestGo(BaseTest):

    def test_go_current(self) -> None:
        create_repo()
        new_branch("level-0-branch")
        commit()

        output, e = launch_command_capturing_output_and_exception("go", "current")
        assert type(e) is SystemExit
        assert e.code == ExitCode.ARGUMENT_ERROR

    def test_go_invalid_direction(self) -> None:
        create_repo()
        new_branch("level-0-branch")
        commit()

        output, e = launch_command_capturing_output_and_exception("go", "invalid")
        assert type(e) is SystemExit
        assert e.code == ExitCode.ARGUMENT_ERROR

    def test_go_up(self) -> None:
        """Verify behaviour of a 'git machete go up' command.

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
        )
        assert 'level-1-branch' == launch_command("show", "current").strip()

    def test_go_down(self, mocker: MockerFixture) -> None:
        """Verify behaviour of a 'git machete go down' command.

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
        launch_command("go", "down")
        assert launch_command("show", "current").strip() == "level-1-branch"

        check_out("level-0-branch")
        launch_command("g", "d")
        assert launch_command("show", "current").strip() == "level-1-branch"

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("2"))
        launch_command("go", "down")
        assert launch_command("show", "current").strip() == "level-2b-branch"

    def test_go_first_root_with_downstream(self) -> None:
        """Verify behaviour of a 'git machete go first' command.

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
        launch_command("go", "first")
        assert 'level-1a-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete go first' performs 'git checkout' to "
             "the first downstream branch of a root branch if root branch "
             "has any downstream branches.")

        check_out("level-3b-branch")
        launch_command("g", "f")
        assert 'level-1a-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete g d' performs 'git checkout' to "
             "the child/downstream branch of the current branch.")

    def test_go_first_root_without_downstream(self) -> None:
        """Verify behaviour of a 'git machete go first' command.

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
        # check short command behaviour
        launch_command("g", "f")

        assert 'level-0-branch' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete g f' set current branch to root "
             "if root branch has no downstream.")

    def test_go_last(self) -> None:
        """Verify behaviour of a 'git machete go last' command.

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
        launch_command("g", "l")
        assert 'branch-from-x-additional-root' == launch_command("show", "current").strip()

    def test_go_next_successor_exists(self) -> None:
        """Verify behaviour of a 'git machete go next' command.

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
        """Verify behaviour of a 'git machete go next' command.

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
        """Verify behaviour of a 'git machete go prev' command.

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
        """Verify behaviour of a 'git machete go prev' command.

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
        """Verify behaviour of a 'git machete go root' command.

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

    def test_go_root_no_branches(self) -> None:
        create_repo()
        expected_error_message = """
          No branches listed in .git/machete. Consider one of:
          * git machete discover
          * git machete edit or edit .git/machete manually
          * git machete github checkout-prs --mine
          * git machete gitlab checkout-mrs --mine"""
        assert_failure(["g", "root"], expected_error_message)

    def test_go_with_worktree(self) -> None:
        """Test that go fails gracefully when target branch is checked out in a worktree."""
        if get_git_version() < (2, 5):
            # git worktree command was introduced in git 2.5
            return

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

        # Create a worktree for feature-1
        check_out("develop")
        add_worktree("feature-1")

        # Now try to `go down` from develop to feature-1
        # feature-1 is already checked out in a worktree
        check_out("develop")
        initial_dir = os.getcwd()
        output, exception = launch_command_capturing_output_and_exception("go", "down")

        # Verify that `go` command fails when trying to checkout a branch in a worktree
        # Git checkout fails with exit code 128 and stderr: "fatal: 'feature-1' is already used by worktree..."
        assert exception is not None, "Expected go command to fail when target branch is in a worktree"
        from git_machete.exceptions import UnderlyingGitException
        assert isinstance(exception, UnderlyingGitException)
        assert "returned 128" in str(exception)  # Git checkout failure
        assert "checkout" in str(exception).lower()

        # Also verify the directory hasn't changed (unlike traverse which cd's into worktrees)
        assert os.getcwd() == initial_dir, "go should not change directory"
