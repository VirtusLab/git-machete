from typing import Any

import pytest

from .mockers import (GitRepositorySandbox, get_current_commit_hash,
                      launch_command, mock_run_cmd, popen)


class TestUpdate:

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

    def test_update_with_fork_point_not_specified(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete update --no-interactive-rebase' command.

        Verify that 'git machete update --no-interactive-rebase' performs
        'git rebase' to the parent branch of the current branch.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit("Basic commit.")
            .new_branch("level-1-branch")
            .commit("Only level-1 commit.")
            .new_branch("level-2-branch")
            .commit("Only level-2 commit.")
            .check_out("level-0-branch")
            .commit("New commit on level-0-branch")
        )
        launch_command("discover", "-y")

        parents_new_commit_hash = get_current_commit_hash()
        self.repo_sandbox.check_out("level-1-branch")
        launch_command("update", "--no-interactive-rebase")
        new_fork_point_hash = launch_command("fork-point").strip()

        assert parents_new_commit_hash == \
            new_fork_point_hash, \
            ("Verify that 'git machete update --no-interactive-rebase' perform"
             "'git rebase' to the parent branch of the current branch."
             )

    def test_update_with_fork_point_specified(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete update --no-interactive-rebase -f <commit_hash>' cmd.

        Verify that 'git machete update --no-interactive-rebase -f <commit_hash>'
        performs 'git rebase' to the upstream branch and drops the commits until
        (included) fork point specified by the option '-f'.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        branchs_first_commit_msg = "First commit on branch."
        branchs_second_commit_msg = "Second commit on branch."
        (
            self.repo_sandbox.new_branch("root")
            .commit("First commit on root.")
            .new_branch("branch-1")
            .commit(branchs_first_commit_msg)
            .commit(branchs_second_commit_msg)
        )
        branch_second_commit_hash = get_current_commit_hash()
        (
            self.repo_sandbox.commit("Third commit on branch.")
            .check_out("root")
            .commit("Second commit on root.")
        )
        roots_second_commit_hash = get_current_commit_hash()
        self.repo_sandbox.check_out("branch-1")
        launch_command("discover", "-y")

        launch_command(
            "update", "--no-interactive-rebase", "-f", branch_second_commit_hash)
        new_fork_point_hash = launch_command("fork-point").strip()
        branch_history = popen('git log -10 --oneline')

        assert roots_second_commit_hash == \
            new_fork_point_hash, \
            ("Verify that 'git machete update --no-interactive-rebase -f "
             "<commit_hash>' performs 'git rebase' to the upstream branch."
             )
        assert branchs_first_commit_msg not in \
            branch_history, \
            ("Verify that 'git machete update --no-interactive-rebase -f "
             "<commit_hash>' drops the commits until (included) fork point "
             "specified by the option '-f' from the current branch."
             )
        assert branchs_second_commit_msg not in \
            branch_history, \
            ("Verify that 'git machete update --no-interactive-rebase -f "
             "<commit_hash>' drops the commits until (included) fork point "
             "specified by the option '-f' from the current branch."
             )

    def test_update_with_invalid_fork_point(self, mocker: Any) -> None:
        (
            self.repo_sandbox.new_branch('branch-0')
                .commit("Commit on branch-0.")
                .new_branch("branch-1a")
                .commit("Commit on branch-1a.")
        )
        branch_1a_hash = get_current_commit_hash()
        (
            self.repo_sandbox.check_out('branch-0')
                .new_branch("branch-1b")
                .commit("Commit on branch-1b.")
        )

        launch_command('discover', '-y')

        with pytest.raises(SystemExit):
            # First exception MacheteException is raised, followed by SystemExit.
            launch_command('update', '-f', branch_1a_hash)
