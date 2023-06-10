from pytest_mock import MockerFixture

from git_machete.exceptions import UnderlyingGitException

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, launch_command,
                      mock_input_returning, mock_run_cmd_and_discard_output,
                      rewrite_definition_file)


class TestAdvance(BaseTest):

    def test_advance_for_no_downstream_branches(self) -> None:
        self.repo_sandbox.new_branch("root").commit()
        rewrite_definition_file("root")

        assert_failure(["advance"], "root does not have any downstream (child) branches to advance towards")

    def test_advance_when_detached_head(self) -> None:
        (
            self.repo_sandbox
            .new_branch("master")
            .commit()
            .new_branch("develop")
            .commit()
        )
        rewrite_definition_file("master\n  develop")
        self.repo_sandbox.check_out("HEAD~")

        assert_failure(["advance"], "Not currently on any branch", expected_exception=UnderlyingGitException)

    def test_advance_for_no_applicable_downstream_branches(self) -> None:
        (
            self.repo_sandbox
            .new_branch("master")
            .commit()
            .new_branch("develop")
            .commit()
            .check_out("master")
            .commit()
        )
        rewrite_definition_file("master\n  develop")

        assert_failure(["advance"], "No downstream (child) branch of master is connected to master with a green edge")

    def test_advance_with_immediate_cancel(self, mocker: MockerFixture) -> None:
        (
            self.repo_sandbox
            .new_branch("master")
            .commit()
            .new_branch("develop")
            .commit()
            .check_out("master")
        )
        rewrite_definition_file("master\n  develop")

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        assert_success(["advance"], "Fast-forward master to match develop? (y, N) \n")

    def test_advance_with_push_for_one_downstream_branch(self, mocker: MockerFixture) -> None:
        """
        Verify that when there is only one, rebased downstream branch of a
        current branch 'git machete advance' merges commits from that branch,
        pushes the current branch and slides out child branches of the downstream branch.
        Also, it modifies the branch layout to reflect new dependencies.
        """
        self.patch_symbol(mocker, 'git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

        (
            self.repo_sandbox.new_branch("root")
            .commit()
            .new_branch("level-1-branch")
            .commit()
        )
        body: str = \
            """
            root
                level-1-branch
            """
        rewrite_definition_file(body)
        level_1_commit_hash = self.repo_sandbox.get_current_commit_hash()

        self.repo_sandbox.check_out("root")
        self.repo_sandbox.push()
        launch_command("advance", "-y")

        root_commit_hash = self.repo_sandbox.get_current_commit_hash()
        origin_root_commit_hash = self.repo_sandbox.get_commit_hash("origin/root")

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

    def test_advance_without_push_for_one_downstream_branch(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

        (
            self.repo_sandbox
            .remove_remote()
            .new_branch("root")
            .commit()
            .new_branch("level-1-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-1-branch")
            .new_branch("level-2b-branch")
            .commit()
        )

        body: str = \
            """
            root
                level-1-branch
                    level-2a-branch
                    level-2b-branch
            """
        rewrite_definition_file(body)

        self.repo_sandbox.check_out("root")
        launch_command("advance", "-y")

        assert self.repo_sandbox.get_commit_hash("level-1-branch") == self.repo_sandbox.get_commit_hash("root")

        assert_success(
            ["status", "-l"],
            """
            root *
            |
            | Some commit message.
            o-level-2a-branch
            |
            | Some commit message.
            o-level-2b-branch
            """
        )

    def test_advance_for_a_few_possible_downstream_branches_and_yes_option(self, mocker: MockerFixture) -> None:
        """
        Verify that 'git machete advance -y' raises an error when current branch
        has more than one synchronized downstream branch and option '-y' is passed.
        """
        self.patch_symbol(mocker, 'git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

        (
            self.repo_sandbox.new_branch("root")
            .commit()
            .push()
            .new_branch("level-1a-branch")
            .commit()
            .check_out("root")
            .new_branch("level-1b-branch")
            .commit()
            .check_out("root")
        )

        body: str = \
            """
            root
                level-1a-branch
                level-1b-branch
            """
        rewrite_definition_file(body)

        expected_error_message = "More than one downstream (child) branch of root " \
                                 "is connected to root with a green edge and -y/--yes option is specified"
        assert_failure(['advance', '-y'], expected_error_message)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("1", "N", "n"))
        assert_success(
            ["advance"],
            """
            [1] level-1a-branch
            [2] level-1b-branch
            Specify downstream branch towards which root is to be fast-forwarded or hit <return> to skip: 

            Branch root is now fast-forwarded to match level-1a-branch. Push root to origin? (y, N) 

            Branch root is now fast-forwarded to match level-1a-branch. Slide level-1a-branch out of the tree of branch dependencies? (y, N) 
            """
        )

        assert_success(
            ["status"],
            """
            root * (ahead of origin)
            |
            m-level-1a-branch (untracked)
            |
            x-level-1b-branch (untracked)
            """
        )
