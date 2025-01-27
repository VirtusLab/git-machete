import os
from typing import Any, Dict, List

from pytest_mock import MockerFixture

from git_machete.code_hosting import OrganizationAndRepository
from git_machete.gitlab import GitLabClient
from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success, execute,
                           launch_command, rewrite_branch_layout_file)
from tests.mockers_code_hosting import mock_from_url
from tests.mockers_git_repository import (add_remote, check_out, commit,
                                          create_repo, create_repo_with_remote,
                                          delete_branch, new_branch, push,
                                          set_git_config_key, set_remote_url)
from tests.mockers_gitlab import (MockGitLabAPIState,
                                  mock_gitlab_token_for_domain_fake,
                                  mock_gitlab_token_for_domain_none,
                                  mock_mr_json, mock_urlopen)


class TestGitLabCheckoutMRs(BaseTest):
    @staticmethod
    def mrs_for_test_checkout_mrs() -> List[Dict[str, Any]]:
        return [
            mock_mr_json(head='chore/redundant_checks', base='restrict_access', number=18),
            mock_mr_json(head='restrict_access', base='allow-ownership-link', number=17),
            mock_mr_json(head='allow-ownership-link', base='bugfix/feature', number=12),
            mock_mr_json(head='bugfix/feature', base='enhance/feature', number=6),
            mock_mr_json(head='enhance/add_user', base='develop', number=19),
            mock_mr_json(head='testing/add_user', base='bugfix/add_user', number=22),
            mock_mr_json(head='chore/comments', base='testing/add_user', number=24),
            mock_mr_json(head='ignore-trailing', base='hotfix/add-trigger', number=3),
            mock_mr_json(head='bugfix/remove-n-option', base='develop', number=5, state='closed', repo_id=2)
        ]

    @staticmethod
    def projects_for_test_gitlab_checkout_prs(second_remote_path: str) -> Dict[int, Dict[str, Any]]:
        return {
            1: {'namespace': {'full_path': 'tester/tester'}, 'name': 'repo_sandbox',
                'http_url_to_repo': 'https://gitlab.com/tester/tester/repo_sandbox.git'},
            2: {'namespace': {'full_path': 'tester'}, 'name': 'repo_sandbox',
                'http_url_to_repo': second_remote_path},
        }

    def test_gitlab_checkout_mrs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)

        (local_path, remote_path) = create_repo_with_remote()
        second_remote_path = create_repo("second-remote", bare=True, switch_dir_to_new_repo=False)
        gitlab_api_state = MockGitLabAPIState(
            self.projects_for_test_gitlab_checkout_prs(second_remote_path),
            *self.mrs_for_test_checkout_mrs())
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

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
        check_out('master')

        for branch in ('chore/redundant_checks', 'restrict_access', 'allow-ownership-link', 'bugfix/feature', 'enhance/add_user',
                       'testing/add_user', 'chore/comments', 'bugfix/add_user'):
            delete_branch(branch)

        body: str = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing
                        chore/fields
            develop
                enhance/feature
            """
        rewrite_branch_layout_file(body)

        # not broken chain of merge requests (root found in dependency tree)
        launch_command('gitlab', 'checkout-mrs', '18')
        assert_success(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
              |
              o-bugfix/feature  MR !6 (some_other_user) rebase=no push=no
                |
                o-allow-ownership-link  MR !12 (some_other_user) rebase=no push=no
                  |
                  o-restrict_access  MR !17 (some_other_user) rebase=no push=no
                    |
                    o-chore/redundant_checks *  MR !18 (some_other_user) rebase=no push=no
            """
        )
        # broken chain of merge requests (add new root)
        launch_command('gitlab', 'checkout-mrs', '24')
        assert_success(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
              |
              o-bugfix/feature  MR !6 (some_other_user) rebase=no push=no
                |
                o-allow-ownership-link  MR !12 (some_other_user) rebase=no push=no
                  |
                  o-restrict_access  MR !17 (some_other_user) rebase=no push=no
                    |
                    o-chore/redundant_checks  MR !18 (some_other_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  MR !22 (some_other_user) rebase=no push=no
              |
              o-chore/comments *  MR !24 (some_other_user) rebase=no push=no
            """
        )

        # broken chain of merge requests (branches already added)
        launch_command('gitlab', 'checkout-mrs', '24')
        assert_success(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
              |
              o-bugfix/feature  MR !6 (some_other_user) rebase=no push=no
                |
                o-allow-ownership-link  MR !12 (some_other_user) rebase=no push=no
                  |
                  o-restrict_access  MR !17 (some_other_user) rebase=no push=no
                    |
                    o-chore/redundant_checks  MR !18 (some_other_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  MR !22 (some_other_user) rebase=no push=no
              |
              o-chore/comments *  MR !24 (some_other_user) rebase=no push=no
            """
        )

        # all MRs
        launch_command('gitlab', 'checkout-mrs', '--all')
        assert_success(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  MR !3 (some_other_user) rebase=no push=no
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
            | |
            | o-bugfix/feature  MR !6 (some_other_user) rebase=no push=no
            |   |
            |   o-allow-ownership-link  MR !12 (some_other_user) rebase=no push=no
            |     |
            |     o-restrict_access  MR !17 (some_other_user) rebase=no push=no
            |       |
            |       o-chore/redundant_checks  MR !18 (some_other_user) rebase=no push=no
            |
            o-enhance/add_user  MR !19 (some_other_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  MR !22 (some_other_user) rebase=no push=no
              |
              o-chore/comments *  MR !24 (some_other_user) rebase=no push=no
            """
        )

        # check against wrong MR number
        org_repo = OrganizationAndRepository.from_url(
            domain=GitLabClient.DEFAULT_GITLAB_DOMAIN,
            url=remote_path)

        assert org_repo is not None
        expected_error_message = f"MR !100 is not found in project {org_repo.organization}/{org_repo.repository}"
        assert_failure(['gitlab', 'checkout-mrs', '100'], expected_error_message)

        assert_failure(['gitlab', 'checkout-mrs', '19', '100'], expected_error_message)

        expected_msg = "Checking for open GitLab MRs... OK\n"
        assert_success(['gitlab', 'checkout-mrs', '--by', 'some_other_user'], expected_msg)

        # Check against closed merge request with source branch deleted from remote
        create_repo("other-local", bare=False, switch_dir_to_new_repo=True)
        add_remote("origin", second_remote_path)
        new_branch('main')
        commit('initial commit')
        push()

        expected_error_message = "Could not check out MR !5 because branch bugfix/remove-n-option " \
                                 "is already deleted from tester."
        assert_failure(['gitlab', 'checkout-mrs', '5'], expected_error_message)

        # Check against MR coming from fork
        new_branch('bugfix/remove-n-option')
        commit('first commit')
        push()
        os.chdir(local_path)

        expected_msg = ("Checking for open GitLab MRs... OK\n"
                        "Warn: MR !5 is already closed.\n"
                        "MR !5 checked out at local branch bugfix/remove-n-option\n")
        assert_success(['gitlab', 'checkout-mrs', '5'], expected_msg)

        # Check against multiple MRs
        expected_msg = 'Checking for open GitLab MRs... OK\n'
        assert_success(['gitlab', 'checkout-mrs', '3', '12'], expected_msg)

    @staticmethod
    def gitlab_api_state_for_test_gitlab_checkout_mrs_from_fork_with_deleted_repo() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='feature/allow_checkout', base='develop', number=2, repo_id=0, state='closed'),
            mock_mr_json(head='bugfix/allow_checkout', base='develop', number=3)
        )

    def test_gitlab_checkout_mrs_from_fork_with_deleted_repo(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen',
                          mock_urlopen(self.gitlab_api_state_for_test_gitlab_checkout_mrs_from_fork_with_deleted_repo()))

        (local_path, remote_path) = create_repo_with_remote()
        new_branch("root")
        commit('initial master commit')
        push()
        new_branch('develop')
        commit('initial develop commit')
        push()

        os.chdir(remote_path)
        execute("git branch merge-requests/2/head develop")
        os.chdir(local_path)

        body: str = \
            """
            root
            develop
            """
        rewrite_branch_layout_file(body)
        expected_msg = ("Checking for open GitLab MRs... OK\n"
                        "Warn: MR !2 comes from fork and its project is already deleted. "
                        "No remote tracking data will be set up for feature/allow_checkout branch.\n"
                        "Warn: MR !2 is already closed.\n"
                        "MR !2 checked out at local branch feature/allow_checkout\n")
        assert_success(
            ['gitlab', 'checkout-mrs', '2'],
            expected_msg
        )

        assert 'feature/allow_checkout' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete gitlab checkout-mrs' performs 'git checkout' to "
             "the source branch of given merge request.")

    @staticmethod
    def gitlab_api_state_for_test_gitlab_checkout_mrs_of_current_user_and_other_users() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='chore/redundant_checks', base='restrict_access', number=18),
            mock_mr_json(head='restrict_access', base='allow-ownership-link', number=17, user='gitlab_user'),
            mock_mr_json(head='allow-ownership-link', base='bugfix/feature', number=12),
            mock_mr_json(head='bugfix/feature', base='enhance/feature', number=6, user='gitlab_user'),
            mock_mr_json(head='enhance/add_user', base='develop', number=19),
            mock_mr_json(head='testing/add_user', base='bugfix/add_user', number=22, user='gitlab_user'),
            mock_mr_json(head='chore/comments', base='testing/add_user', number=24),
            mock_mr_json(head='ignore-trailing', base='hotfix/add-trigger', number=3, user='gitlab_user'),
            mock_mr_json(head='bugfix/remove-n-option', base='develop', number=5, state='closed', repo_id=2)
        )

    def test_gitlab_checkout_mrs_of_current_user_and_other_users(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen',
                          mock_urlopen(self.gitlab_api_state_for_test_gitlab_checkout_mrs_of_current_user_and_other_users()))

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
        check_out('master')

        for branch in ('chore/redundant_checks', 'restrict_access', 'allow-ownership-link', 'bugfix/feature', 'enhance/add_user',
                       'testing/add_user', 'chore/comments', 'bugfix/add_user'):
            delete_branch(branch)

        body: str = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing
                        chore/fields
            develop
                enhance/feature
            """
        rewrite_branch_layout_file(body)

        # test that `checkout-mrs` add `rebase=no push=no` qualifiers to branches associated with the MRs whose owner
        # is different than the current user
        launch_command('gitlab', 'checkout-mrs', '--all')
        assert_success(
            ["status"],
            """
            master *
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  MR !3
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
            | |
            | o-bugfix/feature  MR !6
            |   |
            |   o-allow-ownership-link  MR !12 (some_other_user) rebase=no push=no
            |     |
            |     o-restrict_access  MR !17
            |       |
            |       o-chore/redundant_checks  MR !18 (some_other_user) rebase=no push=no
            |
            o-enhance/add_user  MR !19 (some_other_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  MR !22
              |
              o-chore/comments  MR !24 (some_other_user) rebase=no push=no
            """
        )

        # test that `checkout-mrs` doesn't overwrite annotation qualifiers but overwrites annotation text
        launch_command('anno', '-b=allow-ownership-link', 'branch_annotation rebase=no')
        launch_command('gitlab', 'checkout-mrs', '--all')
        assert_success(
            ["status"],
            """
            master *
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  MR !3
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
            | |
            | o-bugfix/feature  MR !6
            |   |
            |   o-allow-ownership-link  MR !12 (some_other_user) rebase=no
            |     |
            |     o-restrict_access  MR !17
            |       |
            |       o-chore/redundant_checks  MR !18 (some_other_user) rebase=no push=no
            |
            o-enhance/add_user  MR !19 (some_other_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  MR !22
              |
              o-chore/comments  MR !24 (some_other_user) rebase=no push=no
            """
        )

    def test_gitlab_checkout_mrs_misc_failures_and_warns(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitLabAPIState.with_mrs()))

        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)
        create_repo_with_remote()
        assert_success(
            ["gitlab", "checkout-mrs", "--all"],
            """
            Checking for open GitLab MRs... OK
            Warn: Currently there are no merge requests opened in project example-org/example-repo
            """
        )

        assert_success(
            ["gitlab", "checkout-mrs", "--by=gitlab_user"],
            """
            Checking for open GitLab MRs... OK
            Warn: User gitlab_user has no open merge request in project example-org/example-repo
            """
        )

        assert_failure(
            ["gitlab", "checkout-mrs", "--mine"],
            """
            Could not determine current user name, please check that the GitLab API token provided by one of the:
            \t1. GITLAB_TOKEN environment variable
            \t2. Content of the ~/.gitlab-token file
            \t3. Current auth token from the glab GitLab CLI
            is valid."""
        )

        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        assert_success(
            ["gitlab", "checkout-mrs", "--mine"],
            """
            Checking for open GitLab MRs... OK
            Warn: User gitlab_user has no open merge request in project example-org/example-repo
            """
        )

    @staticmethod
    def gitlab_api_state_with_mr_cycle() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='bugfix/feature', base='chore/redundant_checks', number=6),
            mock_mr_json(head='chore/redundant_checks', base='restrict_access', number=18),
            mock_mr_json(head='restrict_access', base='allow-ownership-link', number=17),
            mock_mr_json(head='allow-ownership-link', base='chore/redundant_checks', number=12)
        )

    def test_gitlab_checkout_mrs_forming_a_cycle(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.gitlab_api_state_with_mr_cycle()))

        create_repo_with_remote()
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

        assert_failure(
            ['gitlab', 'checkout-mrs', '--all'],
            'There is a cycle between GitLab MRs: '
            'bugfix/feature -> chore/redundant_checks -> restrict_access -> allow-ownership-link -> chore/redundant_checks'
        )

    @staticmethod
    def gitlab_api_state_for_test_gitlab_checkout_mrs_single_mr() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='develop', base='master', number=18)
        )

    def test_gitlab_checkout_mrs_remote_already_added(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.git_operations.GitContext.fetch_remote', lambda _self, _remote: None)
        gitlab_api_state = self.gitlab_api_state_for_test_gitlab_checkout_mrs_single_mr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))
        create_repo()
        add_remote("origin-1", gitlab_api_state.projects[1]['http_url_to_repo'])

        assert_failure(
            ["gitlab", "checkout-mrs", "--all"],
            "Could not check out MR !18 because branch develop is already deleted from tester/tester/repo_sandbox."
        )

    def test_gitlab_checkout_mrs_org_and_repo_from_config(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.git_operations.GitContext.fetch_remote', lambda _self, _remote: None)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(
            self.gitlab_api_state_for_test_gitlab_checkout_mrs_single_mr()))

        create_repo_with_remote()

        new_branch("master")
        commit()

        new_branch("develop")
        commit()
        push()

        set_remote_url("origin", "https://gitlab.com/example-org/example-repo.git")
        set_git_config_key('machete.gitlab.organization', "example-org")
        set_git_config_key('machete.gitlab.repository', "example-repo")
        assert_success(
            ['gitlab', 'checkout-mrs', '--all'],
            'Checking for open GitLab MRs... OK\n'
            'MR !18 checked out at local branch develop\n'
        )

    def test_gitlab_checkout_mrs_remote_from_config(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.git_operations.GitContext.fetch_remote', lambda _self, _remote: None)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(
            self.gitlab_api_state_for_test_gitlab_checkout_mrs_single_mr()))

        create_repo_with_remote()

        new_branch("master")
        commit()

        new_branch("develop")
        commit()
        push()

        set_remote_url("origin", "https://gitlab.com/example-org/example-repo.git")
        set_git_config_key('machete.gitlab.remote', "origin")
        assert_success(
            ['gitlab', 'checkout-mrs', '--all'],
            'Checking for open GitLab MRs... OK\n'
            'MR !18 checked out at local branch develop\n'
        )

    @staticmethod
    def mrs_for_test_checkout_mrs_main_to_main_pr() -> List[Dict[str, Any]]:
        return [
            mock_mr_json(head='fix-10341', base='main', number=2),
            mock_mr_json(head='main', base='main', number=1, repo_id=2)
        ]

    def test_gitlab_checkout_mrs_main_to_main_mr(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.git_operations.GitContext.fetch_remote', lambda _self, _remote: None)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)

        create_repo_with_remote()

        second_remote_path = create_repo("second-remote", bare=True, switch_dir_to_new_repo=False)
        gitlab_api_state = MockGitLabAPIState(
            self.projects_for_test_gitlab_checkout_prs(second_remote_path),
            *self.mrs_for_test_checkout_mrs_main_to_main_pr())
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

        new_branch("main")
        commit()
        push()
        new_branch("fix-10341")
        commit()
        push()

        assert_success(
            ['gitlab', 'checkout-mrs', '2'],
            'Checking for open GitLab MRs... OK\n'
            'MR !2 checked out at local branch fix-10341\n'
        )
