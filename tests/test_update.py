from typing import Any

import pytest

from git_machete.exceptions import MacheteException

from .base_test import BaseTest, git, popen
from .mockers import (get_current_commit_hash, launch_command,
                      mock_exit_script, mock_run_cmd, overridden_environment,
                      rewrite_definition_file)


class TestUpdate(BaseTest):

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
        body: str = \
            """
            level-0-branch
                level-1-branch
                    level-2-branch
            """
        rewrite_definition_file(body)

        parents_new_commit_hash = get_current_commit_hash()
        self.repo_sandbox.check_out("level-1-branch")
        launch_command("update", "--no-interactive-rebase")
        new_fork_point_hash = launch_command("fork-point").strip()

        assert parents_new_commit_hash == new_fork_point_hash, \
            ("Verify that 'git machete update --no-interactive-rebase' perform "
             "'git rebase' to the parent branch of the current branch."
             )

    def test_update_drops_empty_commits(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete update' command.

        Verify that 'git machete update' drops effectively-empty commits if the underlying git supports that behavior.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit("Basic commit.")
            .new_branch("level-1-branch")
            .commit("level-1 commit")
            .commit("level-1 commit... but to be cherry-picked onto level-0-branch")
            .check_out("level-0-branch")
            .commit("New commit on level-0-branch")
            .execute("git cherry-pick level-1-branch")
        )
        body: str = \
            """
            level-0-branch
                level-1-branch
            """
        rewrite_definition_file(body)

        parents_new_commit_hash = get_current_commit_hash()
        self.repo_sandbox.check_out("level-1-branch")
        # Note that `--empty=drop` is the default in NON-interactive mode.
        # We want to check if effectively empty commits are dropped in interactive mode as well.
        # Let's substitute the editor opened by git for interactive rebase to-do list
        # so that the test can run in a fully automated manner.
        with overridden_environment(GIT_SEQUENCE_EDITOR=":"):
            if git.get_git_version() >= (2, 26, 0):
                launch_command("update")
            else:
                mocker.patch('git_machete.cli.exit_script', mock_exit_script)
                with pytest.raises(MacheteException) as e:
                    launch_command("update")
                assert "git rebase --interactive --onto refs/heads/level-0-branch" in e.value.parameter
                assert "level-1-branch returned 1" in e.value.parameter
                self.repo_sandbox.execute("git rebase --continue")

        new_fork_point_hash = launch_command("fork-point").strip()
        assert parents_new_commit_hash == new_fork_point_hash, \
            "Verify that 'git machete update' drops effectively-empty commits."
        branch_history = popen('git log level-0-branch..level-1-branch')
        assert "level-1 commit" in branch_history
        assert "level-1 commit... but to be cherry-picked onto level-0-branch" not in branch_history

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
        body: str = \
            """
            root
                branch-1
            """
        rewrite_definition_file(body)

        launch_command(
            "update", "--no-interactive-rebase", "-f", branch_second_commit_hash)
        new_fork_point_hash = launch_command("fork-point").strip()
        branch_history = popen('git log -10 --oneline')

        assert roots_second_commit_hash == new_fork_point_hash, \
            ("Verify that 'git machete update --no-interactive-rebase -f "
             "<commit_hash>' performs 'git rebase' to the upstream branch."
             )
        assert branchs_first_commit_msg not in branch_history, \
            ("Verify that 'git machete update --no-interactive-rebase -f "
             "<commit_hash>' drops the commits until (included) fork point "
             "specified by the option '-f' from the current branch."
             )
        assert branchs_second_commit_msg not in branch_history, \
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

        body: str = \
            """
            branch-0
                branch-1a
                branch-1b
            """
        rewrite_definition_file(body)

        with pytest.raises(SystemExit):
            # First exception MacheteException is raised, followed by SystemExit.
            launch_command('update', '-f', branch_1a_hash)
