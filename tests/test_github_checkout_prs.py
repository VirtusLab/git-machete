import os
from typing import Any

from pytest_mock import MockerFixture

from git_machete.github import GitHubClient, RemoteAndOrganizationAndRepository
from tests.base_test import BaseTest, GitRepositorySandbox
from tests.mockers import (assert_failure, assert_success, launch_command,
                           mock_run_cmd_and_discard_output,
                           rewrite_definition_file)
from tests.mockers_github import (MockGitHubAPIState, mock_from_url,
                                  mock_github_token_for_domain_fake,
                                  mock_github_token_for_domain_none,
                                  mock_repository_info, mock_urlopen)


class TestGitHubCheckoutPRs(BaseTest):
    github_api_state_for_test_checkout_prs = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'chore/redundant_checks', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'restrict_access'},
                'number': '18',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'restrict_access', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'allow-ownership-link'},
                'number': '17',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'allow-ownership-link', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'bugfix/feature'},
                'number': '12',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'bugfix/feature', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'enhance/feature'},
                'number': '6',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'enhance/add_user', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'develop'},
                'number': '19',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'testing/add_user', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'bugfix/add_user'},
                'number': '22',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {'head': {'ref': 'chore/comments', 'repo': mock_repository_info},
             'user': {'login': 'some_other_user'},
             'base': {'ref': 'testing/add_user'},
             'number': '24',
             'html_url': 'www.github.com',
             'state': 'open'
             },
            {
                'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'hotfix/add-trigger'},
                'number': '3',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'bugfix/remove-n-option',
                         'repo': {'full_name': 'testing/checkout_prs', 'html_url': GitRepositorySandbox.second_remote_path}},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'develop'},
                'number': '5',
                'html_url': 'www.github.com',
                'state': 'closed'
            }
        ]
    )

    def test_github_checkout_prs(self, mocker: MockerFixture, tmp_path: Any) -> None:
        mocker.patch('git_machete.github.RemoteAndOrganizationAndRepository.from_url', mock_from_url)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        mocker.patch('urllib.request.Request', self.github_api_state_for_test_checkout_prs.get_request_provider())
        mocker.patch('urllib.request.urlopen', mock_urlopen)

        (
            self.repo_sandbox.new_branch("root")
            .commit("initial commit")
            .new_branch("develop")
            .commit("first commit")
            .push()
            .new_branch("enhance/feature")
            .commit("introduce feature")
            .push()
            .new_branch("bugfix/feature")
            .commit("bugs removed")
            .push()
            .new_branch("allow-ownership-link")
            .commit("fixes")
            .push()
            .new_branch('restrict_access')
            .commit('authorized users only')
            .push()
            .new_branch("chore/redundant_checks")
            .commit('remove some checks')
            .push()
            .check_out("root")
            .new_branch("master")
            .commit("Master commit")
            .push()
            .new_branch("hotfix/add-trigger")
            .commit("HOTFIX Add the trigger")
            .push()
            .new_branch("ignore-trailing")
            .commit("Ignore trailing data")
            .push()
            .delete_branch("root")
            .new_branch('chore/fields')
            .commit("remove outdated fields")
            .push()
            .check_out('develop')
            .new_branch('enhance/add_user')
            .commit('allow externals to add users')
            .push()
            .new_branch('bugfix/add_user')
            .commit('first round of fixes')
            .push()
            .new_branch('testing/add_user')
            .commit('add test set for add_user feature')
            .push()
            .new_branch('chore/comments')
            .commit('code maintenance')
            .push()
            .check_out('master')
        )
        for branch in ('chore/redundant_checks', 'restrict_access', 'allow-ownership-link', 'bugfix/feature', 'enhance/add_user',
                       'testing/add_user', 'chore/comments', 'bugfix/add_user'):
            self.repo_sandbox.execute(f"git branch -D {branch}")

        body: str = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing
                        chore/fields
            develop
                enhance/feature
                    bugfix/feature
                        allow-ownership-link
                            restrict_access
                                chore/redundant_checks
            """
        rewrite_definition_file(body)

        # not broken chain of pull requests (root found in dependency tree)
        launch_command('github', 'checkout-prs', '18')
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
              o-ignore-trailing  PR #3 (some_other_user) rebase=no push=no
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
              o-ignore-trailing  PR #3 (some_other_user) rebase=no push=no
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

        # check against wrong pr number
        remote_org_repo = RemoteAndOrganizationAndRepository.from_url(domain=GitHubClient.DEFAULT_GITHUB_DOMAIN,
                                                                      url=self.repo_sandbox.remote_path,
                                                                      remote='origin')
        assert remote_org_repo is not None
        expected_error_message = f"PR #100 is not found in repository {remote_org_repo.organization}/{remote_org_repo.repository}"
        assert_failure(['github', 'checkout-prs', '100'], expected_error_message)

        assert_failure(['github', 'checkout-prs', '19', '100'], expected_error_message)

        # check against user with no open pull requests
        expected_msg = ("Checking for open GitHub PRs... OK\n"
                        f"Warn: User tester has no open pull request in repository "
                        f"{remote_org_repo.organization}/{remote_org_repo.repository}\n")
        assert_success(['github', 'checkout-prs', '--by', 'tester'], expected_msg)

        # Check against closed pull request with head branch deleted from remote
        local_path = tmp_path
        self.repo_sandbox.new_repo(GitRepositorySandbox.second_remote_path, bare=True)
        (self.repo_sandbox.new_repo(local_path, bare=False)
         .execute(f"git remote add origin {GitRepositorySandbox.second_remote_path}")
         .execute('git config user.email "tester@test.com"')
         .execute('git config user.name "Tester Test"')
         .new_branch('main')
         .commit('initial commit')
         .push()
         )
        os.chdir(self.repo_sandbox.local_path)

        expected_error_message = "Could not check out PR #5 because its head branch bugfix/remove-n-option " \
                                 "is already deleted from testing."
        assert_failure(['github', 'checkout-prs', '5'], expected_error_message)

        # Check against pr come from fork
        os.chdir(local_path)
        (self.repo_sandbox
         .new_branch('bugfix/remove-n-option')
         .commit('first commit')
         .push())
        os.chdir(self.repo_sandbox.local_path)

        expected_msg = ("Checking for open GitHub PRs... OK\n"
                        "Warn: Pull request #5 is already closed.\n"
                        "Pull request #5 checked out at local branch bugfix/remove-n-option\n")
        assert_success(['github', 'checkout-prs', '5'], expected_msg)

        # Check against multiple PRs
        expected_msg = 'Checking for open GitHub PRs... OK\n'
        assert_success(['github', 'checkout-prs', '3', '12'], expected_msg)

    github_api_state_for_test_github_checkout_prs_fresh_repo = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'comments/add_docstrings', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'improve/refactor'},
                'number': '2',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'restrict_access', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'allow-ownership-link'},
                'number': '17',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'improve/refactor', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'chore/sync_to_docs'},
                'number': '1',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'sphinx_export',
                         'repo': {'full_name': 'testing/checkout_prs', 'html_url': GitRepositorySandbox.second_remote_path}},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'comments/add_docstrings'},
                'number': '23',
                'html_url': 'www.github.com',
                'state': 'closed'
            }
        ]
    )

    def test_github_checkout_prs_freshly_cloned(self, mocker: MockerFixture, tmp_path: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('git_machete.github.RemoteAndOrganizationAndRepository.from_url', mock_from_url)
        mocker.patch('urllib.request.urlopen', mock_urlopen)
        mocker.patch('urllib.request.Request', self.github_api_state_for_test_github_checkout_prs_fresh_repo.get_request_provider())

        (
            self.repo_sandbox.new_branch("root")
            .commit("initial commit")
            .new_branch("develop")
            .commit("first commit")
            .push()
            .new_branch("chore/sync_to_docs")
            .commit("synchronize docs")
            .push()
            .new_branch("improve/refactor")
            .commit("refactor code")
            .push()
            .new_branch("comments/add_docstrings")
            .commit("docstring added")
            .push()
            .new_branch("sphinx_export")
            .commit("export docs to html")
            .push()
            .check_out("root")
            .new_branch("master")
            .commit("Master commit")
            .push()
            .delete_branch("root")
            .push()
        )
        for branch in ('develop', 'chore/sync_to_docs', 'improve/refactor', 'comments/add_docstrings'):
            self.repo_sandbox.execute(f"git branch -D {branch}")
        local_path = tmp_path
        os.chdir(local_path)
        self.repo_sandbox.execute(f'git clone {self.repo_sandbox.remote_path}')
        os.chdir(os.path.join(local_path, os.listdir()[0]))

        for branch in ('develop', 'chore/sync_to_docs', 'improve/refactor', 'comments/add_docstrings'):
            self.repo_sandbox.execute(f"git branch -D -r origin/{branch}")

        local_path = tmp_path
        self.repo_sandbox.new_repo(GitRepositorySandbox.second_remote_path, bare=True)
        (
            self.repo_sandbox.new_repo(local_path, bare=False)
            .execute(f"git remote add origin {GitRepositorySandbox.second_remote_path}")
            .execute('git config user.email "tester@test.com"')
            .execute('git config user.name "Tester Test"')
            .new_branch('feature')
            .commit('initial commit')
            .push()
        )
        os.chdir(self.repo_sandbox.local_path)
        rewrite_definition_file("master")
        expected_msg = ("Checking for open GitHub PRs... OK\n"
                        "Pull request #2 checked out at local branch comments/add_docstrings\n")
        assert_success(
            ['github', 'checkout-prs', '2'],
            expected_msg
        )

        assert_success(
            ["status"],
            """
            master

            chore/sync_to_docs
            |
            o-improve/refactor  PR #1 (some_other_user) rebase=no push=no
              |
              o-comments/add_docstrings *  PR #2 (some_other_user) rebase=no push=no
            """
        )

        # Check against closed pull request
        self.repo_sandbox.execute('git branch -D sphinx_export')
        expected_msg = ("Checking for open GitHub PRs... OK\n"
                        "Warn: Pull request #23 is already closed.\n"
                        "Pull request #23 checked out at local branch sphinx_export\n")

        assert_success(
            ['github', 'checkout-prs', '23'],
            expected_msg
        )
        assert_success(
            ["status"],
            """
            master

            chore/sync_to_docs
            |
            o-improve/refactor  PR #1 (some_other_user) rebase=no push=no
              |
              o-comments/add_docstrings  PR #2 (some_other_user) rebase=no push=no
                |
                o-sphinx_export *
            """
        )

    github_api_state_for_test_github_checkout_prs_from_fork_with_deleted_repo = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'feature/allow_checkout', 'repo': None},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'develop'},
                'number': '2',
                'html_url': 'www.github.com',
                'state': 'closed'
            },
            {
                'head': {'ref': 'bugfix/allow_checkout', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'develop'},
                'number': '3',
                'html_url': 'www.github.com',
                'state': 'open'}
        ]
    )

    def test_github_checkout_prs_from_fork_with_deleted_repo(self, mocker: MockerFixture) -> None:
        # need to mock fetch_ref due to underlying `git fetch pull/head` calls
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('git_machete.github.RemoteAndOrganizationAndRepository.from_url', mock_from_url)
        mocker.patch('urllib.request.urlopen', mock_urlopen)
        mocker.patch('urllib.request.Request',
                     self.github_api_state_for_test_github_checkout_prs_from_fork_with_deleted_repo.get_request_provider())

        (
            self.repo_sandbox.new_branch("root")
            .commit('initial master commit')
            .push()
            .new_branch('develop')
            .commit('initial develop commit')
            .push()
        )

        os.chdir(self.repo_sandbox.remote_path)
        self.repo_sandbox.execute("git branch pull/2/head develop")
        os.chdir(self.repo_sandbox.local_path)

        body: str = \
            """
            root
            develop
            """
        rewrite_definition_file(body)
        expected_msg = ("Checking for open GitHub PRs... OK\n"
                        "Warn: Pull request #2 comes from fork and its repository is already deleted. "
                        "No remote tracking data will be set up for feature/allow_checkout branch.\n"
                        "Warn: Pull request #2 is already closed.\n"
                        "Pull request #2 checked out at local branch feature/allow_checkout\n")
        assert_success(
            ['github', 'checkout-prs', '2'],
            expected_msg
        )

        assert 'feature/allow_checkout' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete github checkout prs' performs 'git checkout' to "
             "the head branch of given pull request."
             )

    github_api_state_for_test_github_checkout_prs_of_current_user_and_other_users = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'chore/redundant_checks', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'restrict_access'},
                'number': '18',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'restrict_access', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'allow-ownership-link'},
                'number': '17',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'allow-ownership-link', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'bugfix/feature'},
                'number': '12',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'bugfix/feature', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'enhance/feature'},
                'number': '6',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'enhance/add_user', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'develop'},
                'number': '19',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'testing/add_user', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'bugfix/add_user'},
                'number': '22',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'chore/comments', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'testing/add_user'},
                'number': '24',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'hotfix/add-trigger'},
                'number': '3',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'bugfix/remove-n-option',
                         'repo': {'full_name': 'testing/checkout_prs', 'html_url': GitRepositorySandbox.second_remote_path}},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'develop'},
                'number': '5',
                'html_url': 'www.github.com',
                'state': 'closed'
            }
        ]
    )

    def test_github_checkout_prs_of_current_user_and_other_users(self, mocker: MockerFixture, tmp_path: Any) -> None:
        mocker.patch('git_machete.github.RemoteAndOrganizationAndRepository.from_url', mock_from_url)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        mocker.patch('urllib.request.Request',
                     self.github_api_state_for_test_github_checkout_prs_of_current_user_and_other_users.get_request_provider())
        mocker.patch('urllib.request.urlopen', mock_urlopen)

        (
            self.repo_sandbox.new_branch("root")
            .commit("initial commit")
            .new_branch("develop")
            .commit("first commit")
            .push()
            .new_branch("enhance/feature")
            .commit("introduce feature")
            .push()
            .new_branch("bugfix/feature")
            .commit("bugs removed")
            .push()
            .new_branch("allow-ownership-link")
            .commit("fixes")
            .push()
            .new_branch('restrict_access')
            .commit('authorized users only')
            .push()
            .new_branch("chore/redundant_checks")
            .commit('remove some checks')
            .push()
            .check_out("root")
            .new_branch("master")
            .commit("Master commit")
            .push()
            .new_branch("hotfix/add-trigger")
            .commit("HOTFIX Add the trigger")
            .push()
            .new_branch("ignore-trailing")
            .commit("Ignore trailing data")
            .push()
            .delete_branch("root")
            .new_branch('chore/fields')
            .commit("remove outdated fields")
            .push()
            .check_out('develop')
            .new_branch('enhance/add_user')
            .commit('allow externals to add users')
            .push()
            .new_branch('bugfix/add_user')
            .commit('first round of fixes')
            .push()
            .new_branch('testing/add_user')
            .commit('add test set for add_user feature')
            .push()
            .new_branch('chore/comments')
            .commit('code maintenance')
            .push()
            .check_out('master')
        )
        for branch in ('chore/redundant_checks', 'restrict_access', 'allow-ownership-link', 'bugfix/feature', 'enhance/add_user',
                       'testing/add_user', 'chore/comments', 'bugfix/add_user'):
            self.repo_sandbox.execute(f"git branch -D {branch}")

        body: str = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing
                        chore/fields
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
        rewrite_definition_file(body)

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
