from pytest_mock import MockerFixture

from .base_test import BaseTest, GitRepositorySandbox
from .mockers import (assert_success, fixed_author_and_committer_date_in_past,
                      launch_command, mock__run_cmd_and_forward_stdout)


class TestLog(BaseTest):

    def test_log(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.utils._run_cmd', mock__run_cmd_and_forward_stdout)

        repo_sandbox = GitRepositorySandbox()
        with fixed_author_and_committer_date_in_past():
            repo_sandbox.new_branch('root')
            repo_sandbox.commit()
            roots_only_commit_hash = repo_sandbox.get_current_commit_hash()

            repo_sandbox.new_branch('child')
            repo_sandbox.commit()
            child_first_commit_hash = repo_sandbox.get_current_commit_hash()
            repo_sandbox.commit()
            child_second_commit_hash = repo_sandbox.get_current_commit_hash()

        log_contents = [launch_command('log'), launch_command('log', 'child'), launch_command('log', 'refs/heads/child')]

        assert all(child_first_commit_hash in log_content for log_content in log_contents), \
            ("Verify that oldest commit from current branch is visible when "
             "executing `git machete log`.")
        assert all(child_second_commit_hash in log_content for log_content in log_contents), \
            ("Verify that youngest commit from current branch is visible when "
             "executing `git machete log`.")
        assert all(roots_only_commit_hash not in log_content for log_content in log_contents), \
            ("Verify that commits from parent branch are not visible when "
             "executing `git machete log`.")

        assert_success(
            ["log", "--", "--oneline"],
            "47d565d Some commit message.\n"
            "dcd2db5 Some commit message.\n"
        )

        assert_success(
            ["log", "child", "--", "--oneline"],
            "47d565d Some commit message.\n"
            "dcd2db5 Some commit message.\n"
        )
