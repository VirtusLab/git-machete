from typing import Any

from tests.base_test import BaseTest
from tests.mockers import (assert_success, launch_command,
                           mock_run_cmd_and_discard_output,
                           rewrite_definition_file)
from tests.mockers_github import (MockContextManager, MockGitHubAPIState,
                                  mock_derive_current_user_login,
                                  mock_repository_info)


class TestGitHubAnnoPRs(BaseTest):

    git_api_state_for_test_anno_prs = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'hotfix/add-trigger'},
                'number': '3',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'allow-ownership-link', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '7',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'call-ws', 'repo': mock_repository_info},
                'user': {'login': 'very_complex_user_token'},
                'base': {'ref': 'develop'},
                'number': '31',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ]
    )

    def test_github_anno_prs(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('git_machete.github.GitHubClient.derive_current_user_login', mock_derive_current_user_login)
        mocker.patch('urllib.request.urlopen', MockContextManager)
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_anno_prs.new_request())

        (
            self.repo_sandbox.new_branch("root")
                .commit("root")
                .new_branch("develop")
                .commit("develop commit")
                .new_branch("allow-ownership-link")
                .commit("Allow ownership links")
                .push()
                .new_branch("build-chain")
                .commit("Build arbitrarily long chains")
                .check_out("allow-ownership-link")
                .commit("1st round of fixes")
                .check_out("develop")
                .commit("Other develop commit")
                .push()
                .new_branch("call-ws")
                .commit("Call web service")
                .commit("1st round of fixes")
                .push()
                .new_branch("drop-constraint")
                .commit("Drop unneeded SQL constraints")
                .check_out("call-ws")
                .commit("2nd round of fixes")
                .check_out("root")
                .new_branch("master")
                .commit("Master commit")
                .push()
                .new_branch("hotfix/add-trigger")
                .commit("HOTFIX Add the trigger")
                .push()
                .commit_amend("HOTFIX Add the trigger (amended)")
                .new_branch("ignore-trailing")
                .commit("Ignore trailing data")
                .sleep(1)
                .commit_amend("Ignore trailing data (amended)")
                .push()
                .reset_to("ignore-trailing@{1}")  # noqa: FS003
                .delete_branch("root")
                .add_remote('new_origin', 'https://github.com/user/repo.git')
        )
        body: str = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
            """
        rewrite_definition_file(body)

        # test that `anno-prs` add `rebase=no push=no` qualifiers to branches associated with the PRs whose owner
        # is different than the current user, overwrite annotation text but doesn't overwrite existing qualifiers
        launch_command('anno', '-b=allow-ownership-link', 'rebase=no')
        launch_command('anno', '-b=build-chain', 'rebase=no push=no')
        launch_command('github', 'anno-prs')
        assert_success(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing *  PR #3 (github_user) rebase=no push=no (diverged from & older than origin)

            develop
            |
            x-allow-ownership-link  PR #7 (github_user) rebase=no (ahead of origin)
            | |
            | x-build-chain  rebase=no push=no (untracked)
            |
            o-call-ws  PR #31 (ahead of origin)
              |
              x-drop-constraint (untracked)
            """
        )

        # Test anno-prs using custom remote URL provided by git config keys
        (
            self.repo_sandbox
                .remove_remote('new_origin')
                .set_git_config_key('machete.github.remote', 'custom_origin')
                .set_git_config_key('machete.github.organization', 'custom_user')
                .set_git_config_key('machete.github.repository', 'custom_repo')
        )

        launch_command('github', 'anno-prs')
        assert_success(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing *  PR #3 (github_user) rebase=no push=no (diverged from & older than origin)

            develop
            |
            x-allow-ownership-link  PR #7 (github_user) rebase=no (ahead of origin)
            | |
            | x-build-chain  rebase=no push=no (untracked)
            |
            o-call-ws  PR #31 (ahead of origin)
              |
              x-drop-constraint (untracked)
            """,
        )
