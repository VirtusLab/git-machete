from typing import Any

from tests.base_test import BaseTest
from tests.mockers import (assert_success, launch_command,
                           mock_input_returning_y,
                           mock_run_cmd_and_discard_output,
                           rewrite_definition_file)
from tests.mockers_github import (FakeCommandLineOptions, MockGitHubAPIState,
                                  mock_for_domain_fake, mock_from_url,
                                  mock_repository_info, mock_urlopen)


class TestGitHubSync(BaseTest):

    git_api_state_for_test_github_sync = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'snickers', 'repo': mock_repository_info},
                'user': {'login': 'other_user'},
                'base': {'ref': 'master'},
                'number': '7',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ]
    )

    def test_github_sync(self, mocker: Any) -> None:
        mocker.patch('builtins.input', mock_input_returning_y)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
        mocker.patch('git_machete.github.RemoteAndOrganizationAndRepository.from_url', mock_from_url)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_for_domain_fake)
        mocker.patch('urllib.request.urlopen', mock_urlopen)
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_github_sync.new_request())

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
        rewrite_definition_file(body)

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
            Warning: sliding invalid branches: bar2, foo2, moo2 out of the definition file
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
