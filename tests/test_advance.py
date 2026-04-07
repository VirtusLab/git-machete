# flake8: noqa: E501
import textwrap

from pytest_mock import MockerFixture

from git_machete.utils import (ExitCode, FullTerminalAnsiOutputCodes,
                               UnderlyingGitException)

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, launch_command,
                      launch_command_capturing_output_and_exception,
                      mock_input_returning, mock_input_returning_y,
                      rewrite_branch_layout_file)
from .mockers_git_repository import (check_out, commit, create_repo,
                                     create_repo_with_remote, get_commit_hash,
                                     get_current_commit_hash, new_branch, push)


class TestAdvance(BaseTest):

    def test_advance_for_no_downstream_branches(self) -> None:
        create_repo()
        new_branch("root")
        commit()
        rewrite_branch_layout_file("root")

        assert_failure(["advance"], "root does not have any downstream (child) branches to advance towards")

    def test_advance_when_detached_head(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()

        rewrite_branch_layout_file("master\n  develop")
        check_out("HEAD~")

        assert_failure(["advance"], "Not currently on any branch", expected_type=UnderlyingGitException)

    def test_advance_for_no_applicable_downstream_branches(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        check_out("master")
        commit()

        rewrite_branch_layout_file("master\n  develop")

        assert_failure(["advance"], "No downstream (child) branch of master is connected to master with a green edge")

    def test_advance_with_immediate_cancel(self, mocker: MockerFixture) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        check_out("master")

        rewrite_branch_layout_file("master\n  develop")

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        assert_success(["advance"], "Fast-forward master to match develop? (y, N)\n")

    def test_advance_with_push_for_one_downstream_branch(self) -> None:
        """
        Verify that when there is only one, rebased downstream branch of a
        current branch 'git machete advance' merges commits from that branch,
        pushes the current branch and slides out child branches of the downstream branch.
        Also, it modifies the branch layout to reflect new dependencies.
        """
        create_repo_with_remote()
        new_branch("root")
        commit()
        new_branch("level-1-branch")
        commit()

        body: str = \
            """
            root
                level-1-branch
            """
        rewrite_branch_layout_file(body)
        level_1_commit_hash = get_current_commit_hash()

        check_out("root")
        push()
        launch_command("advance", "-y")

        root_commit_hash = get_current_commit_hash()
        origin_root_commit_hash = get_commit_hash("origin/root")

        assert level_1_commit_hash == root_commit_hash, \
            ("Verify that when there is only one, rebased downstream branch of a "
             "current branch, then 'git machete advance' merges commits from that branch "
             "and slides out child branches of the downstream branch.")
        assert root_commit_hash == origin_root_commit_hash, \
            ("Verify that when there is only one, rebased downstream branch of a "
             "current branch, and the current branch is tracked, "
             "then 'git machete advance' pushes the current branch.")
        assert "level-1-branch" not in launch_command("status"), \
            ("Verify that branch to which advance was performed is removed "
             "from the git-machete tree and the structure of the git machete "
             "tree is updated.")

    def test_advance_without_push_for_one_downstream_branch(self) -> None:
        create_repo()
        new_branch("root")
        commit("root")
        new_branch("level-1-branch")
        commit("1 commit")
        new_branch("level-2a-branch")
        commit("2a commit")
        check_out("level-1-branch")
        new_branch("level-2b-branch")
        commit("2b commit")

        body: str = \
            """
            root
                level-1-branch
                    level-2a-branch
                    level-2b-branch
            """
        rewrite_branch_layout_file(body)

        check_out("root")
        launch_command("advance", "-y")

        assert get_commit_hash("level-1-branch") == get_commit_hash("root")

        assert_success(
            ["status", "-l"],
            """
            root *
            |
            | 2a commit
            o-level-2a-branch
            |
            | 2b commit
            o-level-2b-branch
            """
        )

    def test_advance_for_a_few_possible_downstream_branches_and_yes_option(self, mocker: MockerFixture) -> None:
        """
        Verify that 'git machete advance -y' raises an error when current branch
        has more than one synchronized downstream branch and option '-y' is passed.
        """
        create_repo_with_remote()
        new_branch("root")
        commit()
        push()
        new_branch("level-1a-branch")
        commit()
        check_out("root")
        new_branch("level-1b-branch")
        commit()
        check_out("root")

        body: str = \
            """
            root
                level-1a-branch
                level-1b-branch
            """
        rewrite_branch_layout_file(body)

        expected_error_message = "More than one downstream (child) branch of root " \
                                 "is connected to root with a green edge and -y/--yes option is specified"
        assert_failure(['advance', '-y'], expected_error_message)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning(""))
        output, e = launch_command_capturing_output_and_exception("advance")
        assert type(e) is SystemExit
        assert e.code == ExitCode.SUCCESS

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("not-a-valid-number"))
        output, e = launch_command_capturing_output_and_exception("advance")
        assert type(e) is SystemExit
        assert e.code == ExitCode.MACHETE_EXCEPTION

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("3"))
        assert_failure(["advance"], "Invalid index: 3")

        E = FullTerminalAnsiOutputCodes()
        self.patch_symbol(mocker, "git_machete.utils.is_stdout_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_stderr_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_terminal_fully_fledged", lambda: True)

        pc_yn = f"({E.GREEN}y{E.ENDC}, {E.RED}N{E.ENDC})"

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("1", "N", "n"))
        assert_success(
            ["advance"],
            textwrap.dedent(f"""\
            [1] level-1a-branch
            [2] level-1b-branch
            Specify downstream branch towards which {E.BOLD}root{E.ENDC_BOLD_DIM} is to be fast-forwarded or hit <return> to skip:

            Branch {E.BOLD}root{E.ENDC_BOLD_DIM} is now fast-forwarded to match {E.BOLD}level-1a-branch{E.ENDC_BOLD_DIM}. Push {E.BOLD}root{E.ENDC_BOLD_DIM} to {E.BOLD}origin{E.ENDC_BOLD_DIM}? {pc_yn}

            Branch {E.BOLD}root{E.ENDC_BOLD_DIM} is now fast-forwarded to match {E.BOLD}level-1a-branch{E.ENDC_BOLD_DIM}. Slide {E.BOLD}level-1a-branch{E.ENDC_BOLD_DIM} out of the tree of branch dependencies? {pc_yn}
            """)
        )

        assert_success(
            ["status"],
            textwrap.dedent(f"""\
              {E.BOLD}{E.UNDERLINE}root{E.ENDC_UNDERLINE}{E.ENDC_BOLD_DIM}{E.RED} (ahead of {E.BOLD}origin{E.ENDC_BOLD_DIM}){E.ENDC}
              {E.DIM}│{E.ENDC_BOLD_DIM}
              {E.DIM}└─{E.ENDC_BOLD_DIM}{E.BOLD}level-1a-branch{E.ENDC_BOLD_DIM}{E.ORANGE} (untracked){E.ENDC}
              {E.RED}│{E.ENDC}
              {E.RED}└─{E.ENDC}{E.BOLD}level-1b-branch{E.ENDC_BOLD_DIM}{E.ORANGE} (untracked){E.ENDC}
            """)
        )

    def test_advance_when_push_no_qualifier_present(self, mocker: MockerFixture) -> None:
        create_repo_with_remote()
        new_branch("root")
        commit()
        push()
        new_branch("level-1-branch")
        commit()
        check_out("root")

        body: str = \
            """
            root  push=no
                level-1-branch
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning_y)
        assert_success(
            ["advance"],
            """
            Fast-forward root to match level-1-branch? (y, N)

            Branch root is now fast-forwarded to match level-1-branch. Slide level-1-branch out of the tree of branch dependencies? (y, N)
            """
        )

        assert_success(
            ["status"],
            """
            root *  push=no (ahead of origin)
            """
        )

    def test_advance_when_slide_out_no_qualifier_present(self, mocker: MockerFixture) -> None:
        create_repo_with_remote()
        new_branch("root")
        commit()
        push()
        new_branch("level-1-branch")
        commit()
        check_out("root")

        body: str = \
            """
            root
                level-1-branch  slide-out=no
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning_y)
        assert_success(
            ["advance"],
            """
            Fast-forward root to match level-1-branch? (y, N)

            Branch root is now fast-forwarded to match level-1-branch. Push root to origin? (y, N)
            """
        )

        assert_success(
            ["status"],
            """
            root *
            |
            m-level-1-branch  slide-out=no (untracked)
            """
        )

    def test_advance_when_branch_in_sync_with_remote_after_ff(self, mocker: MockerFixture) -> None:
        """
        Verify that when the branch is in sync with remote after fast-forward,
        push is not suggested.
        """
        create_repo_with_remote()
        new_branch("root")
        commit("root-initial")
        push()

        # Create level-1-branch and push it to origin/root
        # This simulates the scenario where origin/root is already at the target commit
        new_branch("level-1-branch")
        commit("level-1-commit")
        push(tracking_branch="root", set_upstream=False)

        # Go back to root (which is behind origin/root now)
        check_out("root")

        body: str = \
            """
            root
                level-1-branch
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning_y)
        output = launch_command("advance")

        # After advance, root is at level-1-branch commit, which is same as origin/root
        # So they are in sync, and push should not be suggested
        assert "Push root to origin?" not in output

    def test_advance_when_branch_diverged_from_and_older_than_remote(self, mocker: MockerFixture) -> None:
        """
        Verify that when the branch diverged from and is older than remote after fast-forward,
        a warning is shown and push is not suggested.
        """
        import time

        from .mockers_git_repository import fetch, reset_to

        create_repo_with_remote()
        new_branch("root")
        commit("root-initial")
        push()

        # Get the commit hash before we diverge
        initial_hash = get_commit_hash("root")

        # Create level-1-branch (this will be the target of advance)
        new_branch("level-1-branch")
        commit("level-1-commit")

        # Go back to root
        check_out("root")

        # Create divergence on remote: push a different commit as origin/root (newer timestamp)
        new_branch("temp-diverge")
        reset_to(initial_hash)
        # Wait a bit to ensure newer timestamp
        time.sleep(1)
        commit("diverged-remote-newer")
        push(tracking_branch="root", set_upstream=False)

        # Now level-1-branch (where root will advance to) has diverged from origin/root
        # and is older (was created before the remote commit)
        check_out("root")
        reset_to(initial_hash)
        fetch()

        body: str = \
            """
            root
                level-1-branch
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning_y)
        output = launch_command("advance")

        assert "Branch root diverged from (and is older than) origin." in output
        assert "Push root to origin?" not in output

    def test_advance_when_branch_diverged_from_and_newer_than_remote(self, mocker: MockerFixture) -> None:
        """
        Verify that when the branch diverged from and is newer than remote after fast-forward,
        a warning is shown and push is not suggested.
        """
        import time

        from .mockers_git_repository import fetch, reset_to

        create_repo_with_remote()
        new_branch("root")
        commit("root-initial")
        push()
        root_hash = get_commit_hash("root")

        # Make remote commit (older timestamp)
        new_branch("temp-old-remote")
        reset_to(root_hash)
        commit("diverged-remote-older")
        push(tracking_branch="root", set_upstream=False)

        # Now make local diverge (newer timestamp) - this will be level-1-branch
        check_out("root")
        reset_to(root_hash)
        # Wait a bit to ensure newer timestamp
        time.sleep(1)
        new_branch("level-1-branch")
        commit("diverged-local-newer")

        # level-1-branch is now diverged from origin/root and newer
        check_out("root")
        fetch()

        body: str = \
            """
            root
                level-1-branch
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning_y)
        output = launch_command("advance")

        assert "Branch root diverged from (and is newer than) origin." in output
        assert "Push root to origin?" not in output
