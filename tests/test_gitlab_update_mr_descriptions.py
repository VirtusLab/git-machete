import textwrap
from typing import Any, Dict, List

from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success,
                           rewrite_branch_layout_file)
from tests.mockers_code_hosting import mock_from_url
from tests.mockers_git_repository import (check_out, commit,
                                          create_repo_with_remote,
                                          delete_branch, new_branch, push,
                                          set_git_config_key)
from tests.mockers_gitlab import (MockGitLabAPIState,
                                  mock_gitlab_token_for_domain_fake,
                                  mock_gitlab_token_for_domain_none,
                                  mock_mr_json, mock_urlopen)


class TestGitLabUpdateMRDescriptions(BaseTest):
    @staticmethod
    def mrs_for_test_update_mr_descriptions() -> List[Dict[str, Any]]:
        return [
            mock_mr_json(head='chore/redundant_checks', base='restrict_access', number=18),
            mock_mr_json(head='restrict_access', base='allow-ownership-link', number=17, user='gitlab_user'),
            mock_mr_json(head='allow-ownership-link', base='bugfix/feature', number=12, user='other_user', body="# Summary\n\n"),
            mock_mr_json(head='bugfix/feature', base='enhance/feature', number=6, body="# Summary\n"),
            mock_mr_json(head='enhance/add_user', base='develop', number=19),
            mock_mr_json(head='testing/add_user', base='bugfix/add_user', number=22),
            mock_mr_json(head='chore/comments', base='testing/add_user', number=24),
            mock_mr_json(head='ignore-trailing', base='hotfix/add-trigger', number=3),
            mock_mr_json(head='bugfix/remove-n-option', base='develop', number=5, state='closed', repo_id=2)
        ]

    def test_gitlab_update_mr_descriptions(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        gitlab_api_state = MockGitLabAPIState.with_mrs(*self.mrs_for_test_update_mr_descriptions())
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))
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
            ['gitlab', 'update-mr-descriptions', '--mine'],
            """
            Checking for open GitLab MRs... OK
            Description of MR !17 (restrict_access -> allow-ownership-link) has been updated
            """
        )

        assert_success(
            ['gitlab', 'update-mr-descriptions', '--by=other_user'],
            """
            Checking for open GitLab MRs... OK
            Description of MR !12 (allow-ownership-link -> bugfix/feature) has been updated
            """
        )

        assert_success(
            ['gitlab', 'update-mr-descriptions', '--related'],
            """
            Checking for open GitLab MRs... OK
            Description of MR !18 (chore/redundant_checks -> restrict_access) has been updated
            """
        )
        set_git_config_key("machete.gitlab.mrDescriptionIntroStyle", "full")
        assert_success(
            ['gitlab', 'update-mr-descriptions', '--related'],
            """
            Checking for open GitLab MRs... OK
            Description of MR !6 (bugfix/feature -> enhance/feature) has been updated
            Description of MR !12 (allow-ownership-link -> bugfix/feature) has been updated
            Description of MR !17 (restrict_access -> allow-ownership-link) has been updated
            """
        )

        assert_success(
            ['gitlab', 'update-mr-descriptions', '--all'],
            """
            Checking for open GitLab MRs... OK
            Description of MR !22 (testing/add_user -> bugfix/add_user) has been updated
            Description of MR !24 (chore/comments -> testing/add_user) has been updated
            """
        )

        mr = gitlab_api_state.get_mr_by_number(6)
        assert mr is not None
        assert mr['description'] == textwrap.dedent("""
            <!-- start git-machete generated -->

            ## Tree of downstream MRs as of 2023-12-31

            * **MR !6 _MR title_ (THIS ONE)**: <br>
              `enhance/feature` ← `bugfix/feature`

                * MR !12 _MR title_: <br>
                  `bugfix/feature` ← `allow-ownership-link`

                  * MR !17 _MR title_: <br>
                    `allow-ownership-link` ← `restrict_access`

                    * MR !18 _MR title_: <br>
                      `restrict_access` ← `chore/redundant_checks`

            <!-- end git-machete generated -->

            # Summary
        """)[1:]

        mr = gitlab_api_state.get_mr_by_number(12)
        assert mr is not None
        assert mr['description'] == textwrap.dedent("""
            <!-- start git-machete generated -->

            # Based on MR !6

            ## Chain of upstream MRs & tree of downstream MRs as of 2023-12-31

            * MR !6 _MR title_: <br>
              `enhance/feature` ← `bugfix/feature`

              * **MR !12 _MR title_ (THIS ONE)**: <br>
                `bugfix/feature` ← `allow-ownership-link`

                  * MR !17 _MR title_: <br>
                    `allow-ownership-link` ← `restrict_access`

                    * MR !18 _MR title_: <br>
                      `restrict_access` ← `chore/redundant_checks`

            <!-- end git-machete generated -->

            # Summary

        """)[1:]

        mr = gitlab_api_state.get_mr_by_number(19)
        assert mr is not None
        assert mr['description'] == "# Summary"

    def test_gitlab_update_mr_descriptions_misc_failures_and_warns(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitLabAPIState.with_mrs()))
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)

        create_repo_with_remote()

        assert_success(
            ["gitlab", "update-mr-descriptions", "--all"],
            """
            Checking for open GitLab MRs... OK
            Warn: Currently there are no merge requests opened in project example-org/example-repo
            """
        )

        assert_failure(
            ["gitlab", "update-mr-descriptions", "--mine"],
            """
            Could not determine current user name, please check that the GitLab API token provided by one of the:
            \t1. GITLAB_TOKEN environment variable
            \t2. Content of the ~/.gitlab-token file
            \t3. Current auth token from the glab GitLab CLI
            is valid."""
        )

        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        assert_success(
            ["gitlab", "update-mr-descriptions", "--mine"],
            """
            Checking for open GitLab MRs... OK
            Warn: User gitlab_user has no open merge request in project example-org/example-repo
            """
        )
