import os
from tempfile import mkdtemp

from pytest_mock import MockerFixture

from git_machete.github import GitHubClient, OrganizationAndRepository
from tests.base_test import BaseTest, GitRepositorySandbox
from tests.mockers import (assert_failure, assert_success, launch_command,
                           rewrite_branch_layout_file)
from tests.mockers_github import (MockGitHubAPIState, mock_from_url,
                                  mock_github_token_for_domain_fake,
                                  mock_github_token_for_domain_none,
                                  mock_pr_json, mock_repository_info,
                                  mock_urlopen)


class TestGitHubCheckoutPRs(BaseTest):
    github_api_state_for_test_checkout_prs = MockGitHubAPIState(
        mock_pr_json(head='chore/redundant_checks', base='restrict_access', number=18),
        mock_pr_json(head='restrict_access', base='allow-ownership-link', number=17),
        mock_pr_json(head='allow-ownership-link', base='bugfix/feature', number=12),
        mock_pr_json(head='bugfix/feature', base='enhance/feature', number=6),
        mock_pr_json(head='enhance/add_user', base='develop', number=19),
        mock_pr_json(head='testing/add_user', base='bugfix/add_user', number=22),
        mock_pr_json(head='chore/comments', base='testing/add_user', number=24),
        mock_pr_json(head='ignore-trailing', base='hotfix/add-trigger', number=3),
        mock_pr_json(head='bugfix/remove-n-option', base='develop', number=5, state='closed',
                     repo={'full_name': 'tester/repo_sandbox', 'html_url': GitRepositorySandbox.second_remote_path})
    )

    def test_github_checkout_prs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_checkout_prs))

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
            self.repo_sandbox.delete_branch(branch)

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

        # check against wrong PR number
        org_repo = OrganizationAndRepository.from_url(
            domain=GitHubClient.DEFAULT_GITHUB_DOMAIN,
            url=self.repo_sandbox.remote_path)

        assert org_repo is not None
        expected_error_message = f"PR #100 is not found in repository {org_repo.organization}/{org_repo.repository}"
        assert_failure(['github', 'checkout-prs', '100'], expected_error_message)

        assert_failure(['github', 'checkout-prs', '19', '100'], expected_error_message)

        expected_msg = "Checking for open GitHub PRs... OK\n"
        assert_success(['github', 'checkout-prs', '--by', 'some_other_user'], expected_msg)

        # Check against closed pull request with head branch deleted from remote
        other_local_path = mkdtemp()
        self.repo_sandbox.new_repo(GitRepositorySandbox.second_remote_path, bare=True)
        (
            self.repo_sandbox
            .new_repo(other_local_path, bare=False)
            .add_remote("origin", GitRepositorySandbox.second_remote_path)
            .set_git_config_key("user.email", "tester@test.com")
            .set_git_config_key("user.name", "Tester Test")
            .new_branch('main')
            .commit('initial commit')
            .push()
        )

        expected_error_message = "Could not check out PR #5 because its head branch bugfix/remove-n-option " \
                                 "is already deleted from tester."
        assert_failure(['github', 'checkout-prs', '5'], expected_error_message)

        # Check against PR coming from fork
        (
            self.repo_sandbox
            .new_branch('bugfix/remove-n-option')
            .commit('first commit')
            .push()
            .chdir(self.repo_sandbox.local_path)
        )

        expected_msg = ("Checking for open GitHub PRs... OK\n"
                        "Warn: Pull request #5 is already closed.\n"
                        "Pull request #5 checked out at local branch bugfix/remove-n-option\n")
        assert_success(['github', 'checkout-prs', '5'], expected_msg)

        # Check against multiple PRs
        expected_msg = 'Checking for open GitHub PRs... OK\n'
        assert_success(['github', 'checkout-prs', '3', '12'], expected_msg)

    github_api_state_for_test_github_checkout_prs_fresh_repo = MockGitHubAPIState(
        mock_pr_json(head='comments/add_docstrings', base='improve/refactor', number=2),
        mock_pr_json(head='restrict_access', base='allow-ownership-link', number=17),
        mock_pr_json(head='improve/refactor', base='chore/sync_to_docs', number=1),
        mock_pr_json(head='sphinx_export', base='comments/add_docstrings', number=23, state='closed',
                     repo={'full_name': 'tester/repo_sandbox', 'html_url': GitRepositorySandbox.second_remote_path})
    )

    def test_github_checkout_prs_freshly_cloned(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_github_checkout_prs_fresh_repo))

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
            self.repo_sandbox.delete_branch(branch)
        local_path = mkdtemp()
        self.repo_sandbox\
            .chdir(local_path)\
            .execute(f'git clone {self.repo_sandbox.remote_path}')\
            .chdir(os.path.join(local_path, os.listdir()[0]))

        for branch in ('develop', 'chore/sync_to_docs', 'improve/refactor', 'comments/add_docstrings'):
            self.repo_sandbox.delete_remote_branch(f"origin/{branch}")

        self.repo_sandbox.new_repo(GitRepositorySandbox.second_remote_path, bare=True)
        (
            self.repo_sandbox.new_repo(local_path, bare=False)
            .add_remote("origin", GitRepositorySandbox.second_remote_path)
            .set_git_config_key("user.email", "tester@test.com")
            .set_git_config_key("user.name", "Tester Test")
            .new_branch('feature')
            .commit('initial commit')
            .push()
        )
        os.chdir(self.repo_sandbox.local_path)
        rewrite_branch_layout_file("master")
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
        self.repo_sandbox.delete_branch('sphinx_export')
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
        mock_pr_json(head='feature/allow_checkout', base='develop', number=2, repo=None, state='closed'),
        mock_pr_json(head='bugfix/allow_checkout', base='develop', number=3)
    )

    def test_github_checkout_prs_from_fork_with_deleted_repo(self, mocker: MockerFixture) -> None:
        # need to mock fetch_ref due to underlying `git fetch pull/head` calls
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen',
                          mock_urlopen(self.github_api_state_for_test_github_checkout_prs_from_fork_with_deleted_repo))

        (
            self.repo_sandbox.new_branch("root")
            .commit('initial master commit')
            .push()
            .new_branch('develop')
            .commit('initial develop commit')
            .push()
        )

        self.repo_sandbox \
            .chdir(self.repo_sandbox.remote_path)\
            .execute("git branch pull/2/head develop")\
            .chdir(self.repo_sandbox.local_path)

        body: str = \
            """
            root
            develop
            """
        rewrite_branch_layout_file(body)
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
        mock_pr_json(head='chore/redundant_checks', base='restrict_access', number=18),
        mock_pr_json(head='restrict_access', base='allow-ownership-link', number=17, user='github_user'),
        mock_pr_json(head='allow-ownership-link', base='bugfix/feature', number=12),
        mock_pr_json(head='bugfix/feature', base='enhance/feature', number=6, user='github_user'),
        mock_pr_json(head='enhance/add_user', base='develop', number=19),
        mock_pr_json(head='testing/add_user', base='bugfix/add_user', number=22, user='github_user'),
        mock_pr_json(head='chore/comments', base='testing/add_user', number=24),
        mock_pr_json(head='ignore-trailing', base='hotfix/add-trigger', number=3, user='github_user'),
        mock_pr_json(head='bugfix/remove-n-option', base='develop', number=5, state='closed',
                     repo={'full_name': 'tester/repo_sandbox', 'html_url': GitRepositorySandbox.second_remote_path})
    )

    def test_github_checkout_prs_of_current_user_and_other_users(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen',
                          mock_urlopen(self.github_api_state_for_test_github_checkout_prs_of_current_user_and_other_users))

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
            self.repo_sandbox.delete_branch(branch)

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
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitHubAPIState()))

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
            \t1. GITHUB_TOKEN environment variable
            \t2. Content of the ~/.github-token file
            \t3. Current auth token from the gh GitHub CLI
            \t4. Current auth token from the hub GitHub CLI
            is valid."""
        )

        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        assert_success(
            ["github", "checkout-prs", "--mine"],
            """
            Checking for open GitHub PRs... OK
            Warn: Current user github_user has no open pull request in repository example-org/example-repo
            """
        )

    github_api_state_for_test_github_checkout_prs_single_pr = MockGitHubAPIState(
        mock_pr_json(head='develop', base='master', number=18)
    )

    def test_github_checkout_prs_remote_already_added(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.git_operations.GitContext.fetch_remote', lambda _self, _remote: None)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(
            self.github_api_state_for_test_github_checkout_prs_single_pr))
        (
            self.repo_sandbox
            .remove_remote("origin")
            .add_remote("origin-1", mock_repository_info["html_url"])
        )
        assert_failure(
            ["github", "checkout-prs", "--all"],
            "Could not check out PR #18 because its head branch develop is already deleted from origin-1."
        )

        (
            self.repo_sandbox
            .remove_remote("origin-1")
            .add_remote("tester", 'https://github.com/tester/lolxd.git')
        )
        assert_failure(
            ["github", "checkout-prs", "--all"],
            "Could not check out PR #18 because its head branch develop is already deleted from tester."
        )

    def test_github_checkout_prs_org_and_repo_from_config(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.git_operations.GitContext.fetch_remote', lambda _self, _remote: None)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(
            self.github_api_state_for_test_github_checkout_prs_single_pr))

        (
            self.repo_sandbox
            .new_branch("master").commit()
            .new_branch("develop").commit().push()
        )

        self.repo_sandbox.set_remote_url("origin", "https://github.com/example-org/example-repo.git")
        self.repo_sandbox.set_git_config_key('machete.github.organization', "example-org")
        self.repo_sandbox.set_git_config_key('machete.github.repository', "example-repo")
        assert_success(
            ['github', 'checkout-prs', '--all'],
            'Checking for open GitHub PRs... OK\n'
            'Pull request #18 checked out at local branch develop\n'
        )

    def test_github_checkout_prs_remote_from_config(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.git_operations.GitContext.fetch_remote', lambda _self, _remote: None)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(
            self.github_api_state_for_test_github_checkout_prs_single_pr))

        (
            self.repo_sandbox
            .new_branch("master").commit()
            .new_branch("develop").commit().push()
        )

        self.repo_sandbox.set_remote_url("origin", "https://github.com/example-org/example-repo.git")
        self.repo_sandbox.set_git_config_key('machete.github.remote', "origin")
        assert_success(
            ['github', 'checkout-prs', '--all'],
            'Checking for open GitHub PRs... OK\n'
            'Pull request #18 checked out at local branch develop\n'
        )
