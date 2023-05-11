from typing import Any

from .base_test import BaseTest, git, popen
from .mockers import (assert_failure, fixed_author_and_committer_date,
                      launch_command, mock_run_cmd_and_discard_output,
                      overridden_environment, rewrite_definition_file)


class TestUpdate(BaseTest):

    def test_update_with_fork_point_not_specified(self, mocker: Any) -> None:
        """
        Verify that 'git machete update --no-interactive-rebase' performs
        'git rebase' to the parent branch of the current branch.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

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

        parents_new_commit_hash = self.repo_sandbox.get_current_commit_hash()
        self.repo_sandbox.check_out("level-1-branch")
        launch_command("update", "--no-interactive-rebase")
        new_fork_point_hash = launch_command("fork-point").strip()

        assert parents_new_commit_hash == new_fork_point_hash, \
            ("Verify that 'git machete update --no-interactive-rebase' perform "
             "'git rebase' to the parent branch of the current branch."
             )

    def test_update_by_merge(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

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

        self.repo_sandbox.check_out("level-1-branch")
        old_level_1_commit_hash = self.repo_sandbox.get_current_commit_hash()
        launch_command("update", "--merge", "--no-edit-merge")

        assert self.repo_sandbox.is_ancestor(old_level_1_commit_hash, "level-1-branch")
        assert self.repo_sandbox.is_ancestor("level-0-branch", "level-1-branch")

    def test_update_drops_empty_commits(self, mocker: Any) -> None:
        """
        Verify that 'git machete update' drops effectively-empty commits if the underlying git supports that behavior.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

        with fixed_author_and_committer_date():
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

        parents_new_commit_hash = self.repo_sandbox.get_current_commit_hash()
        self.repo_sandbox.check_out("level-1-branch")
        # Note that `--empty=drop` is the default in NON-interactive mode.
        # We want to check if effectively empty commits are dropped in interactive mode as well.
        # Let's substitute the editor opened by git for interactive rebase to-do list
        # so that the test can run in a fully automated manner.
        with overridden_environment(GIT_SEQUENCE_EDITOR=":"):
            if git.get_git_version() >= (2, 26, 0):
                launch_command("update")
            else:
                with fixed_author_and_committer_date():
                    expected_error_message = "git rebase --interactive --onto refs/heads/level-0-branch " \
                                             "c0306cdd500fc39869505592200258055407bcc6 level-1-branch returned 1"
                    assert_failure(["update"], expected_error_message)
                self.repo_sandbox.execute("git rebase --continue")

        new_fork_point_hash = launch_command("fork-point").strip()
        assert parents_new_commit_hash == new_fork_point_hash, \
            "Verify that 'git machete update' drops effectively-empty commits."
        branch_history = popen('git log level-0-branch..level-1-branch')
        assert "level-1 commit" in branch_history
        assert "level-1 commit... but to be cherry-picked onto level-0-branch" not in branch_history

    def test_update_with_fork_point_specified(self, mocker: Any) -> None:
        """
        Verify that 'git machete update --no-interactive-rebase -f <commit_hash>'
        performs 'git rebase' to the upstream branch and drops the commits until
        (included) fork point specified by the option '-f'.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

        branchs_first_commit_msg = "First commit on branch."
        branchs_second_commit_msg = "Second commit on branch."
        (
            self.repo_sandbox.new_branch("root")
            .commit("First commit on root.")
            .new_branch("branch-1")
            .commit(branchs_first_commit_msg)
            .commit(branchs_second_commit_msg)
        )
        branch_second_commit_hash = self.repo_sandbox.get_current_commit_hash()
        (
            self.repo_sandbox.commit("Third commit on branch.")
            .check_out("root")
            .commit("Second commit on root.")
        )
        roots_second_commit_hash = self.repo_sandbox.get_current_commit_hash()
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
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

        with fixed_author_and_committer_date():
            (
                self.repo_sandbox.new_branch('branch-0')
                    .commit("Commit on branch-0.")
                    .new_branch("branch-1a")
                    .commit("Commit on branch-1a.")
            )
            branch_1a_hash = self.repo_sandbox.get_current_commit_hash()
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

        expected_error_message = "Fork point 807bcd9f5e9c7e52e7866eedcb58c2e000526700 " \
                                 "is not ancestor of or the tip of the branch-1b branch."
        assert_failure(['update', '-f', branch_1a_hash], expected_error_message)

    def test_update_with_stop_for_edit(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

        (
            self.repo_sandbox.new_branch('branch-0')
            .commit()
            .new_branch("branch-1")
            .commit()
        )
        rewrite_definition_file("branch-0\n\tbranch-1")

        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '1s/^pick /edit /'"):
            launch_command("update")
        # See https://github.com/VirtusLab/git-machete/issues/935, which can only be reproduced on Windows
        # when some file is staged before `git rebase --continue` is executed.
        self.repo_sandbox.execute("touch bar.txt")
        self.repo_sandbox.execute("git add bar.txt")
        with overridden_environment(GIT_EDITOR="cat"):
            self.repo_sandbox.execute("git rebase --continue")
