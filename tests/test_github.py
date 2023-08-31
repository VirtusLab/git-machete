import itertools
from contextlib import contextmanager
from textwrap import dedent
from typing import Iterator
from unittest.mock import mock_open

from pytest_mock import MockerFixture

from git_machete.github import (GitHubClient, GitHubToken,
                                OrganizationAndRepository)
from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success, launch_command,
                           mock__popen_cmd_with_fixed_results,
                           mock_input_returning_y, overridden_environment,
                           rewrite_branch_layout_file)
from tests.mockers_github import (MockGitHubAPIState, mock_from_url,
                                  mock_github_token_for_domain_fake,
                                  mock_github_token_for_domain_none,
                                  mock_repository_info, mock_shutil_which,
                                  mock_urlopen)


class TestGitHub(BaseTest):

    def test_github_remote_patterns(self) -> None:
        organization = 'virtuslab'
        repository = 'repo_sandbox'
        urls = [f'https://tester@github.com/{organization}/{repository}',
                f'https://github.com/{organization}/{repository}',
                f'git@github.com:{organization}/{repository}',
                f'ssh://git@github.com/{organization}/{repository}']
        urls = urls + [url + '.git' for url in urls]

        for url in urls:
            org_and_repo = OrganizationAndRepository.from_url(domain=GitHubClient.DEFAULT_GITHUB_DOMAIN, url=url)
            assert org_and_repo is not None
            assert org_and_repo.organization == organization
            assert org_and_repo.repository == repository

    PR_COUNT_FOR_TEST_GITHUB_API_PAGINATION = 12

    github_api_state_for_test_github_api_pagination = MockGitHubAPIState([{
        'head': {'ref': f'feature_{i:02d}', 'repo': {'full_name': 'tester/repo_sandbox',
                                                     'html_url': 'https://github.com/tester/repo_sandbox.git'}},
        'user': {'login': 'some_other_user'},
        'base': {'ref': 'develop'},
        'number': str(i),
        'html_url': 'www.github.com',
        'state': 'open'
    } for i in range(PR_COUNT_FOR_TEST_GITHUB_API_PAGINATION)])

    def test_github_api_pagination(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        self.patch_symbol(mocker, 'git_machete.github.GitHubClient.MAX_PULLS_PER_PAGE_COUNT', 3)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_github_api_pagination))

        (
            self.repo_sandbox.new_branch("develop")
            .commit("first commit")
            .push()
        )
        for i in range(self.PR_COUNT_FOR_TEST_GITHUB_API_PAGINATION):
            self.repo_sandbox.check_out('develop').new_branch(f'feature_{i:02d}').commit().push()
        self.repo_sandbox.check_out('develop')
        body: str = 'develop *\n' + '\n'.join([f'feature_{i:02d}' for i in range(self.PR_COUNT_FOR_TEST_GITHUB_API_PAGINATION)]) + '\n'
        rewrite_branch_layout_file(body)

        self.repo_sandbox.check_out('develop')
        for i in range(self.PR_COUNT_FOR_TEST_GITHUB_API_PAGINATION):
            self.repo_sandbox.delete_branch(f"feature_{i:02d}")
        body = 'develop *\n'
        rewrite_branch_layout_file(body)

        launch_command('github', 'checkout-prs', '--all')
        launch_command('discover', '--checked-out-since=1 day ago')
        expected_status_output = 'develop *\n' + '\n'.join([f'|\no-feature_{i:02d}  rebase=no push=no'
                                                            for i in range(self.PR_COUNT_FOR_TEST_GITHUB_API_PAGINATION)]) + '\n'
        assert_success(['status'], expected_status_output)

    def test_github_enterprise_domain_unauthorized_without_token(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitHubAPIState([])))

        self.repo_sandbox.set_git_config_key('machete.github.domain', '403.example.org')

        expected_error_message = (
            "GitHub API returned 403 HTTP status with error message: Forbidden\n"
            "You might not have the required permissions for this repository.\n"
            "Provide a GitHub API token with repo access.\n"
            "Visit https://403.example.org/settings/tokens to generate a new one.\n"
            "You can also use a different token provider, available providers can be found via git machete help github.")
        assert_failure(['github', 'checkout-prs', '--all'], expected_error_message)

    def test_github_enterprise_domain_unauthorized_with_token(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitHubAPIState([])))

        self.repo_sandbox.set_git_config_key('machete.github.domain', '403.example.org')

        expected_error_message = (
            "GitHub API returned 403 HTTP status with error message: Forbidden\n"
            "Make sure that the GitHub API token provided by the dummy_provider is valid "
            "and allows for access to GET https://403.example.org/api/v3/user.\n"
            "You can also use a different token provider, available providers can be found via git machete help github.")
        assert_failure(['github', 'checkout-prs', '--all'], expected_error_message)

    github_api_state_for_test_github_enterprise_domain = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'snickers', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '7',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ]
    )

    def test_github_enterprise_domain(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_github_enterprise_domain))

        github_enterprise_domain = 'git.example.org'
        (
            self.repo_sandbox.new_branch("develop")
            .commit("first commit")
            .push()
            .new_branch("snickers")
            .commit("first commit")
            .push()
            .check_out("develop")
            .delete_branch("snickers")
            .set_git_config_key('machete.github.domain', github_enterprise_domain)
        )
        launch_command('github', 'checkout-prs', '--all')

    def test_github_invalid_config(self) -> None:
        @contextmanager
        def git_config_key(key: str, value: str) -> Iterator[None]:
            self.repo_sandbox.set_git_config_key(key, value)
            yield
            self.repo_sandbox.unset_git_config_key(key)

        with git_config_key('machete.github.organization', "example-org"):
            assert_failure(
                ['github', 'checkout-prs', '--all'],
                "machete.github.organization git config key is present, but machete.github.repository is missing. "
                "Both keys must be present to take effect")

        with git_config_key('machete.github.repository', "example-repo"):
            assert_failure(
                ['github', 'checkout-prs', '--all'],
                "machete.github.repository git config key is present, but machete.github.organization is missing. "
                "Both keys must be present to take effect")

        with git_config_key('machete.github.remote', "non-existent-remote"):
            assert_failure(
                ['github', 'checkout-prs', '--all'],
                "machete.github.remote git config key points to non-existent-remote remote, but such remote does not exist")

        with git_config_key('machete.github.organization', "example-org"):
            with git_config_key('machete.github.repository', "example-repo"):
                assert_failure(
                    ['github', 'checkout-prs', '--all'],
                    'Both machete.github.organization and machete.github.repository git config keys are defined, '
                    'but no remote seems to correspond to example-org/example-repo (organization/repository) on GitHub.\n'
                    'Consider pointing to the remote via machete.github.remote config key')

        self.repo_sandbox.add_remote("new-origin", "https://gitlab.com/example-org/example-repo.git")  # not a valid GitHub repo URL
        with git_config_key('machete.github.remote', "new-origin"):
            assert_failure(
                ['github', 'checkout-prs', '--all'],
                'machete.github.remote git config key points to new-origin remote, '
                'but its URL https://gitlab.com/example-org/example-repo.git does not correspond to a valid GitHub repository')

    def test_github_token_retrieval_order(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'os.path.isfile', lambda _file: False)
        self.patch_symbol(mocker, 'shutil.which', mock_shutil_which(None))
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_github_enterprise_domain))

        (
            self.repo_sandbox.new_branch("develop")
                .commit("first commit")
                .push()
                .new_branch("snickers")
                .commit("first commit")
                .push()
                .check_out("develop")
                .delete_branch("snickers")
        )

        expected_output = ["__get_token_from_env(cls=<class 'git_machete.github.GitHubToken'>): "
                           "1. Trying to authenticate via `GITHUB_TOKEN` environment variable...",
                           "__get_token_from_file_in_home_directory(cls=<class 'git_machete.github.GitHubToken'>, domain=github.com): "
                           "2. Trying to authenticate via `~/.github-token`...",
                           "__get_token_from_gh(cls=<class 'git_machete.github.GitHubToken'>, domain=github.com): "
                           "3. Trying to authenticate via `gh` GitHub CLI...",
                           "__get_token_from_hub(cls=<class 'git_machete.github.GitHubToken'>, domain=github.com): "
                           "4. Trying to authenticate via `hub` GitHub CLI..."]

        assert list(itertools.dropwhile(
            lambda line: '__get_token_from_env' not in line,
            launch_command('github', 'anno-prs', '--debug').splitlines()
        ))[:4] == expected_output

    def test_github_get_token_from_env_var(self) -> None:
        with overridden_environment(GITHUB_TOKEN='github_token_from_env_var'):
            github_token = GitHubToken.for_domain(domain="github.com")

        assert github_token is not None
        assert github_token.provider == '`GITHUB_TOKEN` environment variable'
        assert github_token.value == 'github_token_from_env_var'

    # Note that tox doesn't pass env vars from its env to the processes by default,
    # so we don't need to mock away GITHUB_TOKEN in the following tests, even if it's present in the env.
    # This doesn't cover the case of running from outside tox (e.g. via IntelliJ),
    # so hiding GITHUB_TOKEN might eventually become necessary.

    def test_github_get_token_from_file_in_home_directory(self, mocker: MockerFixture) -> None:
        github_token_contents = ('ghp_mytoken_for_github_com\n'
                                 'ghp_myothertoken_for_git_example_org git.example.org\n'
                                 'ghp_yetanothertoken_for_git_example_com git.example.com')
        _mock_open = mock_open(read_data=github_token_contents)
        _mock_open.return_value.readlines.return_value = github_token_contents.split('\n')
        self.patch_symbol(mocker, 'builtins.open', _mock_open)
        self.patch_symbol(mocker, 'os.path.isfile', lambda _file: True)

        domain = GitHubClient.DEFAULT_GITHUB_DOMAIN
        github_token = GitHubToken.for_domain(domain=domain)
        assert github_token is not None
        assert github_token.provider == f'auth token for {domain} from `~/.github-token`'
        assert github_token.value == 'ghp_mytoken_for_github_com'

        domain = 'git.example.org'
        github_token = GitHubToken.for_domain(domain=domain)
        assert github_token is not None
        assert github_token.provider == f'auth token for {domain} from `~/.github-token`'
        assert github_token.value == 'ghp_myothertoken_for_git_example_org'

        domain = 'git.example.net'
        github_token = GitHubToken.for_domain(domain=domain)
        assert github_token is None

    def test_github_get_token_from_gh(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'os.path.isfile', lambda _file: False)
        self.patch_symbol(mocker, 'shutil.which', mock_shutil_which('/path/to/gh'))

        domain = 'git.example.com'

        fixed_popen_cmd_results = [(1, "unknown error", "")]
        self.patch_symbol(mocker, 'git_machete.utils._popen_cmd', mock__popen_cmd_with_fixed_results(*fixed_popen_cmd_results))
        github_token = GitHubToken.for_domain(domain=domain)
        assert github_token is None

        fixed_popen_cmd_results = [(0, "gh version 2.0.0 (2099-12-31)\nhttps://github.com/cli/cli/releases/tag/v2.0.0\n", ""),
                                   (0, "", "You are not logged into any GitHub hosts. Run gh auth login to authenticate.")]
        self.patch_symbol(mocker, 'git_machete.utils._popen_cmd', mock__popen_cmd_with_fixed_results(*fixed_popen_cmd_results))
        github_token = GitHubToken.for_domain(domain=domain)
        assert github_token is None

        fixed_popen_cmd_results = [(0, "gh version 2.16.0 (2099-12-31)\nhttps://github.com/cli/cli/releases/tag/v2.16.0\n", ""),
                                   (0, "", """github.com
                                                ✓ Logged in to git.example.com as Foo Bar (/Users/foo_bar/.config/gh/hosts.yml)
                                                ✓ Git operations for git.example.com configured to use ssh protocol.
                                                ✓ Token: ghp_mytoken_for_github_com_from_gh_cli
                                                ✓ Token scopes: gist, read:discussion, read:org, repo, workflow""")]
        self.patch_symbol(mocker, 'git_machete.utils._popen_cmd', mock__popen_cmd_with_fixed_results(*fixed_popen_cmd_results))
        github_token = GitHubToken.for_domain(domain=domain)
        assert github_token is not None
        assert github_token.provider == f'auth token for {domain} from `gh` GitHub CLI'
        assert github_token.value == 'ghp_mytoken_for_github_com_from_gh_cli'

        fixed_popen_cmd_results = [(0, "gh version 2.17.0 (2099-12-31)\nhttps://github.com/cli/cli/releases/tag/v2.17.0\n", ""),
                                   (0, "", "You are not logged into any GitHub hosts. Run gh auth login to authenticate.")]
        self.patch_symbol(mocker, 'git_machete.utils._popen_cmd', mock__popen_cmd_with_fixed_results(*fixed_popen_cmd_results))
        github_token = GitHubToken.for_domain(domain=domain)
        assert github_token is None

        fixed_popen_cmd_results = [(0, "gh version 2.17.0 (2099-12-31)\nhttps://github.com/cli/cli/releases/tag/v2.17.0\n", ""),
                                   (0, "ghp_mytoken_for_github_com_from_gh_cli", "")]
        self.patch_symbol(mocker, 'git_machete.utils._popen_cmd', mock__popen_cmd_with_fixed_results(*fixed_popen_cmd_results))
        github_token = GitHubToken.for_domain(domain=domain)
        assert github_token is not None
        assert github_token.provider == f'auth token for {domain} from `gh` GitHub CLI'
        assert github_token.value == 'ghp_mytoken_for_github_com_from_gh_cli'

    def test_github_get_token_from_hub(self, mocker: MockerFixture) -> None:
        domain0 = 'git.example.net'
        domain1 = GitHubClient.DEFAULT_GITHUB_DOMAIN
        domain2 = 'git.example.org'
        config_hub_contents = f'''        {domain1}:
        - user: username1
          oauth_token: ghp_mytoken_for_github_com
          protocol: protocol

        {domain2}:
        - user: username2
          oauth_token: ghp_myothertoken_for_git_example_org
          protocol: protocol
        '''

        # Let's pretend that `gh` is available, but fails for whatever reason.
        self.patch_symbol(mocker, 'shutil.which', mock_shutil_which('/path/to/gh'))
        self.patch_symbol(mocker, 'os.path.isfile', lambda file: '.github-token' not in file)
        self.patch_symbol(mocker, 'builtins.open', mock_open(read_data=dedent(config_hub_contents)))

        fixed_popen_cmd_results = [(0, "gh version 2.31.0 (2099-12-31)\nhttps://github.com/cli/cli/releases/tag/v2.31.0\n", ""),
                                   (1, "", "unknown error")]
        self.patch_symbol(mocker, 'git_machete.utils._popen_cmd', mock__popen_cmd_with_fixed_results(*fixed_popen_cmd_results))
        github_token = GitHubToken.for_domain(domain=domain0)
        assert github_token is None

        self.patch_symbol(mocker, 'git_machete.utils._popen_cmd', mock__popen_cmd_with_fixed_results(*fixed_popen_cmd_results))
        github_token = GitHubToken.for_domain(domain=domain1)
        assert github_token is not None
        assert github_token.provider == f'auth token for {domain1} from `hub` GitHub CLI'
        assert github_token.value == 'ghp_mytoken_for_github_com'

        fixed_popen_cmd_results = [(0, "gh version 2.16.0 (2099-12-31)\nhttps://github.com/cli/cli/releases/tag/v2.16.0\n", ""),
                                   (1, "", "unknown error")]
        self.patch_symbol(mocker, 'git_machete.utils._popen_cmd', mock__popen_cmd_with_fixed_results(*fixed_popen_cmd_results))
        github_token = GitHubToken.for_domain(domain=domain2)
        assert github_token is not None
        assert github_token.provider == f'auth token for {domain2} from `hub` GitHub CLI'
        assert github_token.value == 'ghp_myothertoken_for_git_example_org'

    def test_github_invalid_flag_combinations(self) -> None:
        assert_failure(["github", "anno-prs", "--draft"],
                       "--draft option is only valid with create-pr subcommand.")
        assert_failure(["github", "anno-prs", "--mine"],
                       "--mine option is only valid with checkout-prs subcommand.")
        assert_failure(["github", "retarget-pr", "123"],
                       "pr_no option is only valid with checkout-prs subcommand.")
        assert_failure(["github", "checkout-prs", "-b", "foo"],
                       "--branch option is only valid with retarget-pr subcommand.")
        assert_failure(["github", "create-pr", "--ignore-if-missing"],
                       "--ignore-if-missing option is only valid with retarget-pr subcommand.")
        assert_failure(["github", "checkout-prs", "--all", "--mine"],
                       "checkout-prs subcommand must take exactly one of the following options: --all, --by=..., --mine, pr-number(s)")
