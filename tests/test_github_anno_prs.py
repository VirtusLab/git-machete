from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.mockers import (assert_success, launch_command,
                           rewrite_definition_file)
from tests.mockers_github import (MockGitHubAPIState,
                                  mock_github_token_for_domain_fake,
                                  mock_repository_info, mock_urlopen)


class TestGitHubAnnoPRs(BaseTest):

    github_api_state_for_test_anno_prs = MockGitHubAPIState(
        [{
            'head': {'ref': head, 'repo': mock_repository_info},
            'user': {'login': user},
            'base': {'ref': base},
            'number': str(number),
            'html_url': 'www.github.com',
            'state': 'open'
        } for (number, user, head, base) in (
            (3, 'some_other_user', 'ignore-trailing', 'hotfix/add-trigger'),
            (7, 'some_other_user', 'allow-ownership-link', 'develop'),
            (31, 'github_user', 'call-ws', 'develop'),
            (37, 'github_user', 'develop', 'master'),
        )]
    )

    def test_github_anno_prs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_anno_prs))

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
                .amend_commit("HOTFIX Add the trigger (amended)")
                .new_branch("ignore-trailing")
                .commit("Ignore trailing data")
                .sleep(1)
                .amend_commit("Ignore trailing data (amended)")
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
              o-ignore-trailing *  PR #3 (some_other_user) rebase=no push=no (diverged from & older than origin)

            develop  PR #37 WRONG PR BASE or MACHETE PARENT? PR has master
            |
            x-allow-ownership-link  PR #7 (some_other_user) rebase=no (ahead of origin)
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
              o-ignore-trailing *  PR #3 (some_other_user) rebase=no push=no (diverged from & older than origin)

            develop  PR #37 WRONG PR BASE or MACHETE PARENT? PR has master
            |
            x-allow-ownership-link  PR #7 (some_other_user) rebase=no (ahead of origin)
            | |
            | x-build-chain  rebase=no push=no (untracked)
            |
            o-call-ws  PR #31 (ahead of origin)
              |
              x-drop-constraint (untracked)
            """,
        )

    github_api_state_for_test_local_branch_name_different_than_tracking_branch_name = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'feature_repo', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'root'}, 'number': '15',
                'html_url': 'www.github.com', 'state': 'open'
            },
            {
                'head': {'ref': 'feature_1', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'feature_repo'}, 'number': '20',
                'html_url': 'www.github.com', 'state': 'open'
            }
        ]
    )

    def test_github_anno_prs_local_branch_name_different_than_tracking_branch_name(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'urllib.request.urlopen',
                          mock_urlopen(self.github_api_state_for_test_local_branch_name_different_than_tracking_branch_name))

        (
            self.repo_sandbox.new_branch("root")
            .commit("First commit on root.")
            .push()
            .new_branch('feature_repo')
            .commit('introduce feature')
            .push()
            .new_branch('feature')
            .commit('introduce feature')
            .push(tracking_branch='feature_repo')
            .new_branch('feature_1')
            .commit('introduce feature')
            .push()
            .delete_branch('feature_repo')
            .add_remote('new_origin', 'https://github.com/user/repo.git')
        )

        body: str = \
            """
            root
                feature
                    feature_1
            """
        rewrite_definition_file(body)
        launch_command("github", "anno-prs")

        expected_status_output = """
        root
        |
        o-feature
          |
          o-feature_1 *  PR #20 (some_other_user) rebase=no push=no
        """
        assert_success(
            ['status'],
            expected_result=expected_status_output
        )
