from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_success, launch_command, mock_input_returning_y,
                      read_branch_layout_file, rewrite_branch_layout_file)
from .mockers_git_repository import (add_remote, check_out, commit,
                                     create_repo, create_repo_with_remote,
                                     get_local_branches, new_branch, push)
from .mockers_github import mock_github_token_for_domain_none


class TestClean(BaseTest):

    def test_clean(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        create_repo_with_remote()
        new_branch('master')
        commit()
        push()
        new_branch('bar')
        commit()
        new_branch('bar2')
        commit()
        check_out('master')
        new_branch('foo')
        commit()
        push()
        new_branch('foo2')
        commit()
        check_out('master')
        new_branch('moo')
        commit()
        new_branch('moo2')
        commit()
        check_out('master')
        new_branch('mars')
        commit()
        check_out('master')

        body: str = \
            """
            master
                bar
                    bar2
                foo
                    foo2
                moo
                    moo2
            mars
            """
        rewrite_branch_layout_file(body)

        launch_command('clean')

        assert read_branch_layout_file() == "master\n    bar\n    foo\n    moo\n"

        expected_status_output = (
            """
              master *
              |
              o-bar (untracked)
              |
              o-foo
              |
              o-moo (untracked)
            """
        )
        assert_success(['status'], expected_status_output)

        branches = get_local_branches()
        assert 'foo' in branches
        assert 'mars' not in branches

    def test_clean_with_checkout_my_github_prs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        create_repo()
        add_remote("new_origin", "https://github.com/user/repo.git")
        assert_success(
            ["clean", "--checkout-my-github-prs"],
            """
            Warn: could not determine current user name, please check that the GitHub API token provided by one of the:
                1. GITHUB_TOKEN environment variable
                2. Content of the ~/.github-token file
                3. Current auth token from the gh GitHub CLI
                4. Current auth token from the hub GitHub CLI
            is valid.
            Checking for unmanaged branches...
            No branches to delete
            Checking for untracked managed branches with no downstream...
            No branches to delete
            """  # noqa: E501
        )
