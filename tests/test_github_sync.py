from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.mockers import (assert_success, launch_command,
                           mock_input_returning_y, rewrite_branch_layout_file)
from tests.mockers_github import (MockGitHubAPIState, mock_from_url,
                                  mock_github_token_for_domain_fake,
                                  mock_repository_info, mock_urlopen)


class TestGitHubSync(BaseTest):

    github_api_state_for_test_github_sync = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'snickers', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'master'},
                'number': '7',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ]
    )

    def test_github_sync(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_github_sync))

        (
            self.repo_sandbox
                .new_branch('master')
                .commit()
                .push()
                .new_branch('bar')
                .commit()
                .new_branch('bar2')
                .commit()
                .check_out("master")
                .new_branch('foo')
                .commit()
                .push()
                .new_branch('foo2')
                .commit()
                .check_out("master")
                .new_branch('moo')
                .commit()
                .new_branch('moo2')
                .commit()
                .check_out("master")
                .new_branch('snickers')
                .push()
        )
        body: str = \
            """
            master
                bar
                    bar2
                foo
                    foo2
                moo
                    moo2
                snickers
            """
        rewrite_branch_layout_file(body)

        (
            self.repo_sandbox
                .check_out("master")
                .new_branch('mars')
                .commit()
                .check_out("master")
        )
        launch_command('github', 'sync')

        expected_status_output = (
            """
            Warning: sliding invalid branches: bar2, foo2, moo2 out of the branch layout file
              master
              |
              o-bar (untracked)
              |
              o-foo
              |
              o-moo (untracked)
              |
              o-snickers *  PR #7
            """
        )
        assert_success(['status'], expected_status_output)

        branches = self.repo_sandbox.get_local_branches()
        assert 'foo' in branches
        assert 'mars' not in branches
