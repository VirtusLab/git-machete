from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_success, fixed_author_and_committer_date_in_past,
                      launch_command, mock__run_cmd_and_forward_stdout)
from .mockers_git_repository import (commit, create_repo,
                                     get_current_commit_hash, new_branch)


class TestLog(BaseTest):

    def test_log(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.utils._run_cmd', mock__run_cmd_and_forward_stdout)

        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch("root")
            commit("1")
            roots_only_commit_hash = get_current_commit_hash()

            new_branch("child")
            commit("2")
            child_first_commit_hash = get_current_commit_hash()
            commit("3")
            child_second_commit_hash = get_current_commit_hash()

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
            "e5d8837 3\n"
            "83df70a 2\n"
        )

        assert_success(
            ["log", "child", "--", "--oneline"],
            "e5d8837 3\n"
            "83df70a 2\n"
        )
