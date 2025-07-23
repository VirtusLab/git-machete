import os
from typing import Any, Dict, List

from pytest_mock import MockerFixture

from git_machete.code_hosting import OrganizationAndRepository
from git_machete.github import GitHubClient
from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success, execute,
                           launch_command, rewrite_branch_layout_file)
from tests.mockers_code_hosting import mock_from_url
from tests.mockers_git_repository import (add_remote, check_out, commit,
                                          create_repo, create_repo_with_remote,
                                          delete_branch, new_branch, push,
                                          remove_remote, set_git_config_key,
                                          set_remote_url)
from tests.mockers_github import (MockGitHubAPIState,
                                  mock_github_token_for_domain_fake,
                                  mock_github_token_for_domain_none,
                                  mock_pr_json, mock_urlopen)


class TestGitHubCheckoutPRs(BaseTest):
    @staticmethod
    def prs_for_test_checkout_prs() -> List[Dict[str, Any]]:
        return [
            mock_pr_json(head='chore/redundant_checks', base='restrict_access', number=18),
            mock_pr_json(head='restrict_access', base='allow-ownership-link', number=17),
            mock_pr_json(head='allow-ownership-link', base='bugfix/feature', number=12),
            mock_pr_json(head='bugfix/feature', base='enhance/feature', number=6),
            mock_pr_json(head='enhance/add_user', base='develop', number=19),
            mock_pr_json(head='testing/add_user', base='bugfix/add_user', number=22),
            mock_pr_json(head='chore/comments', base='testing/add_user', number=24),
            mock_pr_json(head='ignore-trailing', base='hotfix/add-trigger', number=3),
            mock_pr_json(head='bugfix/remove-n-option', base='develop', number=5, state='closed', repo_id=2)
        ]

    @staticmethod
    def repositories_for_test_github_checkout_prs(second_remote_path: str) -> Dict[int, Dict[str, Any]]:
        return {
            1: {'owner': {'login': 'tester'}, 'name': 'repo_sandbox', 'clone_url': 'https://github.com/tester/repo_sandbox.git'},
            2: {'owner': {'login': 'tester'}, 'name': 'repo_sandbox', 'clone_url': second_remote_path},
        }

    def test_github_checkout_prs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        (local_path, remote_path) = create_repo_with_remote()
        second_remote_path = create_repo("second-remote", bare=True, switch_dir_to_new_repo=False)
        github_api_state = MockGitHubAPIState(
            self.repositories_for_test_github_checkout_prs(second_remote_path),
            *self.prs_for_test_checkout_prs())
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

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

        # not broken chain of pull requests (root found in dependency tree)
        launch_command('github', 'checkout-prs', '18')
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
              o-bugfix/feature  PR #6 (some_other_user) rebase=no push=no
                |
                o-allow-ownership-link  PR #12 (some_other_user) rebase=no push=no
                  |
                  o-restrict_access  PR #17 (some_other_user) rebase=no push=no
                    |
                    o-chore/redundant_checks *  PR #18 (some_other_user) rebase=no push=no
            """
        )
        # broken chain of pull requests (add new root)
        launch_command('github', 'checkout-prs', '24')
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
              o-bugfix/feature  PR #6 (some_other_user) rebase=no push=no
                |
                o-allow-ownership-link  PR #12 (some_other_user) rebase=no push=no
                  |
                  o-restrict_access  PR #17 (some_other_user) rebase=no push=no
                    |
                    o-chore/redundant_checks  PR #18 (some_other_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  PR #22 (some_other_user) rebase=no push=no
              |
              o-chore/comments *  PR #24 (some_other_user) rebase=no push=no
            """
        )

        # broken chain of pull requests (branches already added)
        launch_command('github', 'checkout-prs', '24')
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
              o-bugfix/feature  PR #6 (some_other_user) rebase=no push=no
                |
                o-allow-ownership-link  PR #12 (some_other_user) rebase=no push=no
                  |
                  o-restrict_access  PR #17 (some_other_user) rebase=no push=no
                    |
                    o-chore/redundant_checks  PR #18 (some_other_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  PR #22 (some_other_user) rebase=no push=no
              |
              o-chore/comments *  PR #24 (some_other_user) rebase=no push=no
            """
        )

        # all PRs
        launch_command('github', 'checkout-prs', '--all')
        assert_success(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  PR #3 (some_other_user) rebase=no push=no
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
            | |
            | o-bugfix/feature  PR #6 (some_other_user) rebase=no push=no
            |   |
            |   o-allow-ownership-link  PR #12 (some_other_user) rebase=no push=no
            |     |
            |     o-restrict_access  PR #17 (some_other_user) rebase=no push=no
            |       |
            |       o-chore/redundant_checks  PR #18 (some_other_user) rebase=no push=no
            |
            o-enhance/add_user  PR #19 (some_other_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  PR #22 (some_other_user) rebase=no push=no
              |
              o-chore/comments *  PR #24 (some_other_user) rebase=no push=no
            """
        )

        # check against wrong PR number
        org_repo = OrganizationAndRepository.from_url(
            domain=GitHubClient.DEFAULT_GITHUB_DOMAIN,
            url=remote_path)

        assert org_repo is not None
        expected_error_message = f"PR #100 is not found in repository {org_repo.organization}/{org_repo.repository}"
        assert_failure(['github', 'checkout-prs', '100'], expected_error_message)

        assert_failure(['github', 'checkout-prs', '19', '100'], expected_error_message)

        expected_msg = "Checking for open GitHub PRs... OK\n"
        assert_success(['github', 'checkout-prs', '--by', 'some_other_user'], expected_msg)

        # Check against closed pull request with head branch deleted from remote
        create_repo("other-local", bare=False, switch_dir_to_new_repo=True)

        add_remote("origin", second_remote_path)
        new_branch('main')
        commit('initial commit')
        push()

        expected_error_message = "Could not check out PR #5 because branch bugfix/remove-n-option " \
                                 "is already deleted from tester."
        assert_failure(['github', 'checkout-prs', '5'], expected_error_message)

        # Check against PR coming from fork
        new_branch('bugfix/remove-n-option')
        commit('first commit')
        push()
        os.chdir(local_path)

        expected_msg = ("Checking for open GitHub PRs... OK\n"
                        "Warn: PR #5 is already closed.\n"
                        "PR #5 checked out at local branch bugfix/remove-n-option\n")
        assert_success(['github', 'checkout-prs', '5'], expected_msg)

        # Check against multiple PRs
        expected_msg = 'Checking for open GitHub PRs... OK\n'
        assert_success(['github', 'checkout-prs', '3', '12'], expected_msg)

    @staticmethod
    def github_api_state_for_test_github_checkout_prs_from_fork_with_deleted_repo() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='feature/allow_checkout', base='develop', number=2, repo_id=0, state='closed'),
            mock_pr_json(head='bugfix/allow_checkout', base='develop', number=3)
        )

    def test_github_checkout_prs_from_fork_with_deleted_repo(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, "git_machete.github.GitHubToken.for_domain", mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen',
                          mock_urlopen(self.github_api_state_for_test_github_checkout_prs_from_fork_with_deleted_repo()))

        (local_path, remote_path) = create_repo_with_remote()
        new_branch("root")
        commit('initial master commit')
        push()
        new_branch('develop')
        commit('initial develop commit')
        push()

        os.chdir(remote_path)
        execute("git branch pull/2/head develop")
        os.chdir(local_path)

        body: str = \
            """
            root
            develop
            """
        rewrite_branch_layout_file(body)
        expected_msg = ("Checking for open GitHub PRs... OK\n"
                        "Warn: PR #2 comes from fork and its repository is already deleted. "
                        "No remote tracking data will be set up for feature/allow_checkout branch.\n"
                        "Warn: PR #2 is already closed.\n"
                        "PR #2 checked out at local branch feature/allow_checkout\n")
        assert_success(
            ['github', 'checkout-prs', '2'],
            expected_msg
        )

        assert 'feature/allow_checkout' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete github checkout-prs' performs 'git checkout' to "
             "the head branch of given pull request.")

    @staticmethod
    def github_api_state_for_test_github_checkout_prs_of_current_user_and_other_users() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='chore/redundant_checks', base='restrict_access', number=18),
            mock_pr_json(head='restrict_access', base='allow-ownership-link', number=17, user='github_user'),
            mock_pr_json(head='allow-ownership-link', base='bugfix/feature', number=12),
            mock_pr_json(head='bugfix/feature', base='enhance/feature', number=6, user='github_user'),
            mock_pr_json(head='enhance/add_user', base='develop', number=19),
            mock_pr_json(head='testing/add_user', base='bugfix/add_user', number=22, user='github_user'),
            mock_pr_json(head='chore/comments', base='testing/add_user', number=24),
            mock_pr_json(head='ignore-trailing', base='hotfix/add-trigger', number=3, user='github_user'),
            mock_pr_json(head='bugfix/remove-n-option', base='develop', number=5, state='closed', repo_id=2)
        )

    def test_github_checkout_prs_of_current_user_and_other_users(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen',
                          mock_urlopen(self.github_api_state_for_test_github_checkout_prs_of_current_user_and_other_users()))

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

        # test that `checkout-prs` add `rebase=no push=no` qualifiers to branches associated with the PRs whose owner
        # is different than the current user
        launch_command('github', 'checkout-prs', '--all')
        assert_success(
            ["status"],
            """
            master *
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  PR #3
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
            | |
            | o-bugfix/feature  PR #6
            |   |
            |   o-allow-ownership-link  PR #12 (some_other_user) rebase=no push=no
            |     |
            |     o-restrict_access  PR #17
            |       |
            |       o-chore/redundant_checks  PR #18 (some_other_user) rebase=no push=no
            |
            o-enhance/add_user  PR #19 (some_other_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  PR #22
              |
              o-chore/comments  PR #24 (some_other_user) rebase=no push=no
            """
        )

        # test that `checkout-prs` doesn't overwrite annotation qualifiers but overwrites annotation text
        launch_command('anno', '-b=allow-ownership-link', 'branch_annotation rebase=no')
        launch_command('github', 'checkout-prs', '--all')
        assert_success(
            ["status"],
            """
            master *
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  PR #3
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
            | |
            | o-bugfix/feature  PR #6
            |   |
            |   o-allow-ownership-link  PR #12 (some_other_user) rebase=no
            |     |
            |     o-restrict_access  PR #17
            |       |
            |       o-chore/redundant_checks  PR #18 (some_other_user) rebase=no push=no
            |
            o-enhance/add_user  PR #19 (some_other_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  PR #22
              |
              o-chore/comments  PR #24 (some_other_user) rebase=no push=no
            """
        )

    def test_github_checkout_prs_misc_failures_and_warns(self, mocker: MockerFixture) -> None:
        create_repo_with_remote()
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitHubAPIState.with_prs()))

        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        assert_success(
            ["github", "checkout-prs", "--all"],
            """
            Checking for open GitHub PRs... OK
            Warn: Currently there are no pull requests opened in repository example-org/example-repo
            """
        )

        assert_success(
            ["github", "checkout-prs", "--by=github_user"],
            """
            Checking for open GitHub PRs... OK
            Warn: User github_user has no open pull request in repository example-org/example-repo
            """
        )

        assert_failure(
            ["github", "checkout-prs", "--mine"],
            """
            Could not determine current user name, please check that the GitHub API token provided by one of the:
                1. GITHUB_TOKEN environment variable
                2. Content of the ~/.github-token file
                3. Current auth token from the gh GitHub CLI
                4. Current auth token from the hub GitHub CLI
            is valid."""
        )

        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        assert_success(
            ["github", "checkout-prs", "--mine"],
            """
            Checking for open GitHub PRs... OK
            Warn: User github_user has no open pull request in repository example-org/example-repo
            """
        )

    @staticmethod
    def github_api_state_with_pr_cycle() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='bugfix/feature', base='chore/redundant_checks', number=6),
            mock_pr_json(head='chore/redundant_checks', base='restrict_access', number=18),
            mock_pr_json(head='restrict_access', base='allow-ownership-link', number=17),
            mock_pr_json(head='allow-ownership-link', base='chore/redundant_checks', number=12)
        )

    def test_github_checkout_prs_forming_a_cycle(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, "git_machete.github.GitHubToken.for_domain", mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_with_pr_cycle()))

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
            ['github', 'checkout-prs', '--all'],
            'There is a cycle between GitHub PRs: '
            'bugfix/feature -> chore/redundant_checks -> restrict_access -> allow-ownership-link -> chore/redundant_checks'
        )

    @staticmethod
    def github_api_state_for_test_github_checkout_prs_single_pr() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='develop', base='master', number=18)
        )

    def test_github_checkout_prs_remote_already_added(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.git_operations.GitContext.fetch_remote', lambda _self, _remote: None)
        self.patch_symbol(mocker, "git_machete.github.GitHubToken.for_domain", mock_github_token_for_domain_fake)
        github_api_state = self.github_api_state_for_test_github_checkout_prs_single_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        create_repo()
        add_remote("origin-1", github_api_state.repositories[1]['clone_url'])

        assert_failure(
            ["github", "checkout-prs", "--all"],
            "Could not check out PR #18 because branch develop is already deleted from origin-1."
        )

        remove_remote("origin-1")
        add_remote("tester", 'https://github.com/tester/lolxd.git')

        assert_failure(
            ["github", "checkout-prs", "--all"],
            "Could not check out PR #18 because branch develop is already deleted from tester."
        )

    def test_github_checkout_prs_org_and_repo_from_config(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.git_operations.GitContext.fetch_remote', lambda _self, _remote: None)
        self.patch_symbol(mocker, "git_machete.github.GitHubToken.for_domain", mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(
            self.github_api_state_for_test_github_checkout_prs_single_pr()))

        create_repo_with_remote()
        new_branch("master")
        commit()

        new_branch("develop")
        commit()
        push()

        set_remote_url("origin", "https://github.com/example-org/example-repo.git")
        set_git_config_key('machete.github.organization', "example-org")
        set_git_config_key('machete.github.repository', "example-repo")
        assert_success(
            ['github', 'checkout-prs', '--all'],
            'Checking for open GitHub PRs... OK\n'
            'PR #18 checked out at local branch develop\n'
        )

    def test_github_checkout_prs_remote_from_config(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.git_operations.GitContext.fetch_remote', lambda _self, _remote: None)
        self.patch_symbol(mocker, "git_machete.github.GitHubToken.for_domain", mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(
            self.github_api_state_for_test_github_checkout_prs_single_pr()))

        create_repo_with_remote()
        new_branch("master")
        commit()

        new_branch("develop")
        commit()
        push()

        set_remote_url("origin", "https://github.com/example-org/example-repo.git")
        set_git_config_key('machete.github.remote', "origin")
        assert_success(
            ['github', 'checkout-prs', '--all'],
            'Checking for open GitHub PRs... OK\n'
            'PR #18 checked out at local branch develop\n'
        )

    @staticmethod
    def prs_for_test_checkout_prs_main_to_main_pr() -> List[Dict[str, Any]]:
        return [
            mock_pr_json(head='fix-10341', base='main', number=2),
            mock_pr_json(head='main', base='main', number=1, repo_id=2)
        ]

    def test_github_checkout_prs_main_to_main_pr(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.git_operations.GitContext.fetch_remote', lambda _self, _remote: None)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)

        create_repo_with_remote()
        second_remote_path = create_repo("second-remote", bare=True, switch_dir_to_new_repo=False)
        github_api_state = MockGitHubAPIState(
            self.repositories_for_test_github_checkout_prs(second_remote_path),
            *self.prs_for_test_checkout_prs_main_to_main_pr())
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        new_branch("main")
        commit()
        push()
        new_branch("fix-10341")
        commit()
        push()

        assert_success(
            ['github', 'checkout-prs', '2'],
            'Checking for open GitHub PRs... OK\n'
            'PR #2 checked out at local branch fix-10341\n'
        )
