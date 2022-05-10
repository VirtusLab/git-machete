from typing import Any

import pytest

from git_machete.git_operations import LocalBranchShortName

from .mockers import (GitRepositorySandbox, get_current_commit_hash,
                      launch_command, mock_run_cmd)


def mock_push(remote: str, branch: LocalBranchShortName, force_with_lease: bool = False) -> None:
    pass


class TestAdvance:

    def setup_method(self) -> None:

        self.repo_sandbox = GitRepositorySandbox()

        (
            self.repo_sandbox
            # Create the remote and sandbox repos, chdir into sandbox repo
            .new_repo(self.repo_sandbox.remote_path, "--bare")
            .new_repo(self.repo_sandbox.local_path)
            .execute(f"git remote add origin {self.repo_sandbox.remote_path}")
            .execute('git config user.email "tester@test.com"')
            .execute('git config user.name "Tester Test"')
        )

    def test_advance_with_no_downstream_branches(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete advance' command.

        Verify that 'git machete advance' raises an error when current branch
        has no downstream branches.

        """

        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("root")
            .commit()
        )
        launch_command("discover", "-y")

        with pytest.raises(SystemExit):
            launch_command("advance")

    def test_advance_with_one_downstream_branch(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete advance' command.

        Verify that when there is only one, rebased downstream branch of a
        current branch 'git machete advance' merges commits from that branch
        and slides out child branches of the downstream branch. It edits the git
        machete discovered tree to reflect new dependencies.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('git_machete.git_operations.GitContext.push', mock_push)

        (
            self.repo_sandbox.new_branch("root")
            .commit()
            .new_branch("level-1-branch")
            .commit()
            .new_branch("level-2-branch")
            .commit()
            .check_out("level-1-branch")
        )
        launch_command("discover", "-y")
        level_1_commit_hash = get_current_commit_hash()

        self.repo_sandbox.check_out("root")
        launch_command("advance", "-y")

        root_top_commit_hash = get_current_commit_hash()

        assert level_1_commit_hash == \
            root_top_commit_hash, \
            ("Verify that when there is only one, rebased downstream branch of a"
             "current branch 'git machete advance' merges commits from that branch"
             "and slides out child branches of the downstream branch."
             )
        assert "level-1-branch" not in \
            launch_command("status"), \
            ("Verify that branch to which advance was performed is removed "
             "from the git-machete tree and the structure of the git machete "
             "tree is updated."
             )

    def test_advance_with_few_possible_downstream_branches_and_yes_option(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete advance' command.

        Verify that 'git machete advance -y' raises an error when current branch
        has more than one synchronized downstream branch and option '-y' is passed.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("root")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .check_out("root")
            .new_branch("level-1b-branch")
            .commit()
            .check_out("root")
        )
        launch_command("discover", "-y")

        with pytest.raises(SystemExit):
            launch_command("advance", '-y')
