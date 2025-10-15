import textwrap
from typing import Any, Dict, List

from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success, launch_command,
                           rewrite_branch_layout_file)
from tests.mockers_code_hosting import mock_from_url
from tests.mockers_git_repository import (check_out, commit,
                                          create_repo_with_remote,
                                          delete_branch, new_branch, push,
                                          set_git_config_key)
from tests.mockers_github import (MockGitHubAPIState,
                                  mock_github_token_for_domain_fake,
                                  mock_github_token_for_domain_none,
                                  mock_pr_json, mock_urlopen)


class TestGitHubUpdatePRDescriptions(BaseTest):
    @staticmethod
    def prs_for_test_update_pr_descriptions() -> List[Dict[str, Any]]:
        return [
            mock_pr_json(head='chore/redundant_checks', base='restrict_access', number=18),
            mock_pr_json(head='restrict_access', base='allow-ownership-link', number=17, user='github_user'),
            mock_pr_json(head='allow-ownership-link', base='bugfix/feature', number=12, user='other_user', body="# Summary\n\n"),
            mock_pr_json(head='bugfix/feature', base='enhance/feature', number=6, body="# Summary\n"),
            mock_pr_json(head='enhance/add_user', base='develop', number=19),
            mock_pr_json(head='testing/add_user', base='bugfix/add_user', number=22),
            mock_pr_json(head='chore/comments', base='testing/add_user', number=24),
            mock_pr_json(head='ignore-trailing', base='hotfix/add-trigger', number=3),
            mock_pr_json(head='bugfix/remove-n-option', base='develop', number=5, state='closed', repo_id=2)
        ]

    def test_github_update_pr_descriptions(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        github_api_state = MockGitHubAPIState.with_prs(*self.prs_for_test_update_pr_descriptions())
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')

        create_repo_with_remote()
        new_branch("root")
        commit("initial commit")
        new_branch("develop")
        commit("first commit")
        push()
        new_branch("enhance/feature")
        commit("introduce feature")
        push()
        new_branch("bugfix/feature")
        commit("bugs removed")
        push()
        new_branch("allow-ownership-link")
        commit("fixes")
        push()
        new_branch('restrict_access')
        commit('authorized users only')
        push()
        new_branch("chore/redundant_checks")
        commit('remove some checks')
        push()
        check_out("root")
        new_branch("master")
        commit("Master commit")
        push()
        new_branch("hotfix/add-trigger")
        commit("HOTFIX Add the trigger")
        push()
        new_branch("ignore-trailing")
        commit("Ignore trailing data")
        push()
        delete_branch("root")
        new_branch('chore/fields')
        commit("remove outdated fields")
        push()
        check_out('develop')
        new_branch('enhance/add_user')
        commit('allow externals to add users')
        push()
        new_branch('bugfix/add_user')
        commit('first round of fixes')
        push()
        new_branch('testing/add_user')
        commit('add test set for add_user feature')
        push()
        new_branch('chore/comments')
        commit('code maintenance')
        push()
        check_out('allow-ownership-link')

        body: str = \
            """
            develop
              enhance/feature
                bugfix/feature
                  allow-ownership-link
                    restrict_access
                      chore/redundant_checks
            bugfix/add_user
              testing/add_user
                chore/comments
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'update-pr-descriptions', '--mine'],
            """
            Checking for open GitHub PRs... OK
            Description of PR #17 (restrict_access -> allow-ownership-link) has been updated
            """
        )

        assert_success(
            ['github', 'update-pr-descriptions', '--by=other_user'],
            """
            Checking for open GitHub PRs... OK
            Description of PR #12 (allow-ownership-link -> bugfix/feature) has been updated
            """
        )

        check_out('chore/redundant_checks')
        assert_success(
            ['github', 'update-pr-descriptions', '--related'],
            """
            Checking for open GitHub PRs... OK
            Description of PR #18 (chore/redundant_checks -> restrict_access) has been updated
            """
        )
        set_git_config_key("machete.github.prDescriptionIntroStyle", "full")
        assert_success(
            ['github', 'update-pr-descriptions', '--related'],
            """
            Checking for open GitHub PRs... OK
            Description of PR #6 (bugfix/feature -> enhance/feature) has been updated
            Description of PR #12 (allow-ownership-link -> bugfix/feature) has been updated
            Description of PR #17 (restrict_access -> allow-ownership-link) has been updated
            """
        )

        assert_success(
            ['github', 'update-pr-descriptions', '--all'],
            """
            Checking for open GitHub PRs... OK
            Description of PR #22 (testing/add_user -> bugfix/add_user) has been updated
            Description of PR #24 (chore/comments -> testing/add_user) has been updated
            """
        )

        pr = github_api_state.get_pull_by_number(6)
        assert pr is not None
        assert pr['body'] == textwrap.dedent("""
            <!-- start git-machete generated -->

            ## Tree of downstream PRs as of 2023-12-31

            * **PR #6 (THIS ONE)**:
              `enhance/feature` ← `bugfix/feature`

                * PR #12:
                  `bugfix/feature` ← `allow-ownership-link`

                  * PR #17:
                    `allow-ownership-link` ← `restrict_access`

                    * PR #18:
                      `restrict_access` ← `chore/redundant_checks`

            <!-- end git-machete generated -->

            # Summary
        """)[1:]

        pr = github_api_state.get_pull_by_number(12)
        assert pr is not None
        assert pr['body'] == textwrap.dedent("""
            <!-- start git-machete generated -->

            # Based on PR #6

            ## Chain of upstream PRs & tree of downstream PRs as of 2023-12-31

            * PR #6:
              `enhance/feature` ← `bugfix/feature`

              * **PR #12 (THIS ONE)**:
                `bugfix/feature` ← `allow-ownership-link`

                  * PR #17:
                    `allow-ownership-link` ← `restrict_access`

                    * PR #18:
                      `restrict_access` ← `chore/redundant_checks`

            <!-- end git-machete generated -->

            # Summary

        """)[1:]

        pr = github_api_state.get_pull_by_number(19)
        assert pr is not None
        assert pr['body'] == "# Summary"

        set_git_config_key("machete.github.prDescriptionIntroStyle", "up-only-no-branches")

        launch_command('github', 'update-pr-descriptions', '--all')
        pr = github_api_state.get_pull_by_number(12)
        assert pr is not None
        assert pr['body'] == textwrap.dedent("""
            <!-- start git-machete generated -->

            # Based on PR #6

            ## Chain of upstream PRs as of 2023-12-31

            * PR #6

              * **PR #12 (THIS ONE)**

            <!-- end git-machete generated -->

            # Summary

        """)[1:]

        set_git_config_key("machete.github.prDescriptionIntroStyle", "full-no-branches")

        launch_command('github', 'update-pr-descriptions', '--all')
        pr = github_api_state.get_pull_by_number(12)
        assert pr is not None
        assert pr['body'] == textwrap.dedent("""
            <!-- start git-machete generated -->

            # Based on PR #6

            ## Chain of upstream PRs & tree of downstream PRs as of 2023-12-31

            * PR #6

              * **PR #12 (THIS ONE)**

                  * PR #17

                    * PR #18

            <!-- end git-machete generated -->

            # Summary

        """)[1:]

    def test_github_update_pr_descriptions_misc_failures_and_warns(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitHubAPIState.with_prs()))
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)

        create_repo_with_remote()

        assert_success(
            ["github", "update-pr-descriptions", "--all"],
            """
            Checking for open GitHub PRs... OK
            Warn: currently there are no pull requests opened in repository example-org/example-repo
            """
        )

        assert_failure(
            ["github", "update-pr-descriptions", "--mine"],
            """
            could not determine current user name, please check that the GitHub API token provided by one of the:
                1. GITHUB_TOKEN environment variable
                2. Content of the ~/.github-token file
                3. Current auth token from the gh GitHub CLI
                4. Current auth token from the hub GitHub CLI
            is valid."""
        )

        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        assert_success(
            ["github", "update-pr-descriptions", "--mine"],
            """
            Checking for open GitHub PRs... OK
            Warn: user github_user has no open pull request in repository example-org/example-repo
            """
        )
