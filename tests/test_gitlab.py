import itertools
from contextlib import contextmanager
from typing import Iterator
from unittest.mock import mock_open

from pytest_mock import MockerFixture

from git_machete.code_hosting import OrganizationAndRepository
from git_machete.gitlab import GitLabClient, GitLabToken
from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success, launch_command,
                           mock__popen_cmd_with_fixed_results,
                           mock_input_returning_y, overridden_environment,
                           rewrite_branch_layout_file)
from tests.mockers_code_hosting import mock_from_url, mock_shutil_which
from tests.mockers_gitlab import (MockGitLabAPIState,
                                  mock_gitlab_token_for_domain_fake,
                                  mock_gitlab_token_for_domain_none,
                                  mock_mr_json, mock_urlopen)


class TestGitLab(BaseTest):

    def test_gitlab_client_constructor(self) -> None:
        # This is solely to make mypy check if the class correctly implements abstract methods from CodeHostingClient.
        GitLabClient(GitLabClient.spec(), "gitlab.com", "my-org", "my-repo")

    def test_gitlab_remote_patterns(self) -> None:
        organization = 'virtuslab'
        repository = 'repo_sandbox'
        urls = [f'https://tester@gitlab.com/{organization}/{repository}',
                f'https://gitlab.com/{organization}/{repository}',
                f'git@gitlab.com:{organization}/{repository}',
                f'ssh://git@gitlab.com/{organization}/{repository}']
        urls = urls + [url + '.git' for url in urls]

        for url in urls:
            org_and_repo = OrganizationAndRepository.from_url(domain=GitLabClient.DEFAULT_GITLAB_DOMAIN, url=url)
            assert org_and_repo is not None
            assert org_and_repo.organization == organization
            assert org_and_repo.repository == repository

    MR_COUNT_FOR_TEST_GITLAB_API_PAGINATION = 12

    @staticmethod
    def gitlab_api_state_for_test_gitlab_api_pagination() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(*[
            mock_mr_json(
                head=f'feature_{i:02d}', base='develop', number=i
            ) for i in range(TestGitLab.MR_COUNT_FOR_TEST_GITLAB_API_PAGINATION)])

    def test_gitlab_api_pagination(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabClient.MAX_PULLS_PER_PAGE_COUNT', 3)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.gitlab_api_state_for_test_gitlab_api_pagination()))

        (
            self.repo_sandbox.new_branch("develop")
            .commit("first commit")
            .push()
        )
        for i in range(self.MR_COUNT_FOR_TEST_GITLAB_API_PAGINATION):
            self.repo_sandbox.check_out('develop').new_branch(f'feature_{i:02d}').commit().push()
        self.repo_sandbox.check_out('develop')
        body: str = 'develop *\n' + '\n'.join([f'feature_{i:02d}' for i in range(self.MR_COUNT_FOR_TEST_GITLAB_API_PAGINATION)]) + '\n'
        rewrite_branch_layout_file(body)

        self.repo_sandbox.check_out('develop')
        for i in range(self.MR_COUNT_FOR_TEST_GITLAB_API_PAGINATION):
            self.repo_sandbox.delete_branch(f"feature_{i:02d}")
        body = 'develop *\n'
        rewrite_branch_layout_file(body)

        launch_command('gitlab', 'checkout-mrs', '--all')
        launch_command('discover', '--checked-out-since=1 day ago')
        expected_status_output = 'develop *\n' + '\n'.join([f'|\no-feature_{i:02d}  rebase=no push=no'
                                                            for i in range(self.MR_COUNT_FOR_TEST_GITLAB_API_PAGINATION)]) + '\n'
        assert_success(['status'], expected_status_output)

    def test_gitlab_enterprise_domain_unauthorized_without_token(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitLabAPIState.with_mrs()))

        self.repo_sandbox.set_git_config_key('http.sslVerify', 'false')
        self.repo_sandbox.set_git_config_key('machete.gitlab.domain', '403.example.org')

        expected_error_message = (
            "GitLab API returned 403 HTTP status with error message: Forbidden\n"
            "You might not have the required permissions for this project.\n"
            "Provide a GitLab API token with api access.\n"
            "Visit https://403.example.org/-/user_settings/personal_access_tokens to generate a new one.\n"
            "You can also use a different token provider - see git machete help gitlab for details.")
        assert_failure(['gitlab', 'checkout-mrs', '--all'], expected_error_message)

    def test_gitlab_enterprise_domain_unauthorized_with_token(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitLabAPIState.with_mrs()))

        self.repo_sandbox.set_git_config_key('machete.gitlab.domain', '403.example.org')

        expected_error_message = (
            "GitLab API returned 403 HTTP status with error message: Forbidden\n"
            "Make sure that the GitLab API token provided by dummy_provider is valid "
            "and allows for access to GET https://403.example.org/api/v4/user.\n"
            "You can also use a different token provider - see git machete help gitlab for details.")
        assert_failure(['gitlab', 'checkout-mrs', '--all'], expected_error_message)

    @staticmethod
    def gitlab_api_state_for_test_gitlab_enterprise_domain() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='snickers', base='develop', number=7, user='gitlab_user')
        )

    def test_gitlab_enterprise_domain(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.gitlab_api_state_for_test_gitlab_enterprise_domain()))

        gitlab_enterprise_domain = 'git.example.org'
        (
            self.repo_sandbox.new_branch("develop")
            .commit("first commit")
            .push()
            .new_branch("snickers")
            .commit("first commit")
            .push()
            .check_out("develop")
            .delete_branch("snickers")
            .set_git_config_key('machete.gitlab.domain', gitlab_enterprise_domain)
        )
        launch_command('gitlab', 'checkout-mrs', '--all')

    def test_gitlab_invalid_config(self) -> None:
        @contextmanager
        def git_config_key(key: str, value: str) -> Iterator[None]:
            self.repo_sandbox.set_git_config_key(key, value)
            yield
            self.repo_sandbox.unset_git_config_key(key)

        with git_config_key('machete.gitlab.namespace', "example-org"):
            assert_failure(
                ['gitlab', 'checkout-mrs', '--all'],
                "machete.gitlab.namespace git config key is present, but machete.gitlab.project is missing. "
                "Both keys must be present to take effect")

        with git_config_key('machete.gitlab.project', "example-repo"):
            assert_failure(
                ['gitlab', 'checkout-mrs', '--all'],
                "machete.gitlab.project git config key is present, but machete.gitlab.namespace is missing. "
                "Both keys must be present to take effect")

        with git_config_key('machete.gitlab.remote', "non-existent-remote"):
            assert_failure(
                ['gitlab', 'checkout-mrs', '--all'],
                "machete.gitlab.remote git config key points to non-existent-remote remote, but such remote does not exist")

        with git_config_key('machete.gitlab.namespace', "example-org"):
            with git_config_key('machete.gitlab.project', "example-repo"):
                assert_failure(
                    ['gitlab', 'checkout-mrs', '--all'],
                    'Both machete.gitlab.namespace and machete.gitlab.project git config keys are defined, '
                    'but no remote seems to correspond to example-org/example-repo (namespace/project) on GitLab.\n'
                    'Consider pointing to the remote via machete.gitlab.remote config key')

        self.repo_sandbox.add_remote("new-origin", "https://github.com/example-org/example-repo.git")  # not a valid GitLab repo URL
        with git_config_key('machete.gitlab.remote', "new-origin"):
            assert_failure(
                ['gitlab', 'checkout-mrs', '--all'],
                'machete.gitlab.remote git config key points to new-origin remote, '
                'but its URL https://github.com/example-org/example-repo.git does not correspond to a valid GitLab project')

    def test_gitlab_token_retrieval_order(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'os.path.isfile', lambda _file: False)
        self.patch_symbol(mocker, 'shutil.which', mock_shutil_which(None))
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.gitlab_api_state_for_test_gitlab_enterprise_domain()))

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

        expected_output = ["__get_token_from_env(cls=<class 'git_machete.gitlab.GitLabToken'>): "
                           "1. Trying to find token in `GITLAB_TOKEN` environment variable...",
                           "__get_token_from_file_in_home_directory(cls=<class 'git_machete.gitlab.GitLabToken'>, domain=gitlab.com): "
                           "2. Trying to find token in `~/.gitlab-token`...",
                           "__get_token_from_glab(cls=<class 'git_machete.gitlab.GitLabToken'>, domain=gitlab.com): "
                           "3. Trying to find token via `glab` GitLab CLI..."]

        assert list(itertools.dropwhile(
            lambda line: '__get_token_from_env' not in line,
            launch_command('gitlab', 'anno-mrs', '--debug').splitlines()
        ))[:3] == expected_output

    def test_gitlab_get_token_from_env_var(self) -> None:
        with overridden_environment(GITLAB_TOKEN='gitlab_token_from_env_var'):
            gitlab_token = GitLabToken.for_domain(domain="gitlab.com")

        assert gitlab_token is not None
        assert gitlab_token.provider == '`GITLAB_TOKEN` environment variable'
        assert gitlab_token.value == 'gitlab_token_from_env_var'

    # Note that tox doesn't pass env vars from its env to the processes by default,
    # so we don't need to mock away GITLAB_TOKEN in the following tests, even if it's present in the env.
    # This doesn't cover the case of running from outside tox (e.g. via IntelliJ),
    # so hiding GITLAB_TOKEN might eventually become necessary.

    def test_gitlab_get_token_from_file_in_home_directory(self, mocker: MockerFixture) -> None:
        gitlab_token_contents = ('glpat-mytoken_for_gitlab_com\n'
                                 'glpat-myothertoken_for_git_example_org git.example.org\n'
                                 'glpat-yetanothertoken_for_git_example_com git.example.com')
        self.patch_symbol(mocker, 'builtins.open', mock_open(read_data=gitlab_token_contents))
        self.patch_symbol(mocker, 'os.path.isfile', lambda _file: True)

        domain = GitLabClient.DEFAULT_GITLAB_DOMAIN
        gitlab_token = GitLabToken.for_domain(domain=domain)
        assert gitlab_token is not None
        assert gitlab_token.provider == f'auth token for {domain} from `~/.gitlab-token`'
        assert gitlab_token.value == 'glpat-mytoken_for_gitlab_com'

        # Line ends with \n
        domain = 'git.example.org'
        gitlab_token = GitLabToken.for_domain(domain=domain)
        assert gitlab_token is not None
        assert gitlab_token.provider == f'auth token for {domain} from `~/.gitlab-token`'
        assert gitlab_token.value == 'glpat-myothertoken_for_git_example_org'

        # Last line, doesn't end with \n
        domain = 'git.example.com'
        gitlab_token = GitLabToken.for_domain(domain=domain)
        assert gitlab_token is not None
        assert gitlab_token.provider == f'auth token for {domain} from `~/.gitlab-token`'
        assert gitlab_token.value == 'glpat-yetanothertoken_for_git_example_com'

        domain = 'git.example.net'
        gitlab_token = GitLabToken.for_domain(domain=domain)
        assert gitlab_token is None

    def test_gitlab_get_token_from_glab(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'os.path.isfile', lambda _file: False)
        self.patch_symbol(mocker, 'shutil.which', mock_shutil_which('/path/to/glab'))

        domain = 'git.example.com'

        fixed_popen_cmd_result = (1, "unknown error", "")
        self.patch_symbol(mocker, 'git_machete.utils._popen_cmd', mock__popen_cmd_with_fixed_results(fixed_popen_cmd_result))
        gitlab_token = GitLabToken.for_domain(domain=domain)
        assert gitlab_token is None

        fixed_popen_cmd_result = (0, "", """gitlab.com
                                          x gitlab.com: api call failed: GET https://gitlab.com/api/v4/user: 401 {message: 401 Unauthorized}
                                          ✓ Git operations for gitlab.com configured to use ssh protocol.
                                          ✓ API calls for gitlab.com are made over https protocol
                                          ✓ REST API Endpoint: https://gitlab.com/api/v4/
                                          ✓ GraphQL Endpoint: https://gitlab.com/api/graphql/
                                          x No token provided""")
        self.patch_symbol(mocker, 'git_machete.utils._popen_cmd', mock__popen_cmd_with_fixed_results(fixed_popen_cmd_result))
        gitlab_token = GitLabToken.for_domain(domain=domain)
        assert gitlab_token is None

        fixed_popen_cmd_result = (0, "", """gitlab.com
                                          ✓ Logged in to gitlab.com as Foo Bar (/Users/foo_bar/.config/gh/hosts.yml)
                                          ✓ Git operations for gitlab.com configured to use ssh protocol.
                                          ✓ API calls for gitlab.com are made over https protocol
                                          ✓ REST API Endpoint: https://gitlab.com/api/v4/
                                          ✓ GraphQL Endpoint: https://gitlab.com/api/graphql/
                                          ✓ Token: glpat-mytoken_for_gitlab_com_from_glab_cli""")
        self.patch_symbol(mocker, 'git_machete.utils._popen_cmd', mock__popen_cmd_with_fixed_results(fixed_popen_cmd_result))
        gitlab_token = GitLabToken.for_domain(domain=domain)
        assert gitlab_token is not None
        assert gitlab_token.provider == f'auth token for {domain} from `glab` GitLab CLI'
        assert gitlab_token.value == 'glpat-mytoken_for_gitlab_com_from_glab_cli'

    def test_gitlab_invalid_flag_combinations(self) -> None:
        assert_failure(["gitlab", "anno-mrs", "--draft"],
                       "--draft option is only valid with create-mr subcommand.")
        assert_failure(["gitlab", "anno-mrs", "--mine"],
                       "--mine option is only valid with checkout-mrs subcommand.")
        assert_failure(["gitlab", "retarget-mr", "123"],
                       "request_id option is only valid with checkout-mrs subcommand.")
        assert_failure(["gitlab", "checkout-mrs", "-b", "foo"],
                       "--branch option is only valid with retarget-mr subcommand.")
        assert_failure(["gitlab", "create-mr", "--ignore-if-missing"],
                       "--ignore-if-missing option is only valid with retarget-mr subcommand.")
        assert_failure(["gitlab", "checkout-mrs", "--all", "--mine"],
                       "checkout-mrs subcommand must take exactly one of the following options: --all, --by=..., --mine, mr-number(s)")
        assert_failure(["gitlab", "checkout-mrs", "--title=foo"],
                       "--title option is only valid with create-mr subcommand.")
        assert_failure(["gitlab", "restack-mr", "--with-urls"],
                       "--with-urls option is only valid with anno-mrs subcommand.")
        assert_failure(["gitlab", "restack-mr", "--yes"],
                       "--yes option is only valid with create-mr subcommand.")
