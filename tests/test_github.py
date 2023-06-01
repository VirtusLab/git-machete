from textwrap import dedent
from typing import Any
from unittest.mock import mock_open

from pytest_mock import MockerFixture

from git_machete.github import (GitHubClient, GitHubToken,
                                RemoteAndOrganizationAndRepository)
from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success, launch_command,
                           mock_input_returning, mock_input_returning_y,
                           mock_run_cmd_and_discard_output,
                           rewrite_definition_file)
from tests.mockers_github import (NUMBER_OF_PAGES, PRS_PER_PAGE,
                                  MockGitHubAPIState,
                                  PaginatedMockGitHubAPIResponse,
                                  mock_from_url,
                                  mock_github_token_for_domain_fake,
                                  mock_github_token_for_domain_none,
                                  mock_repository_info, mock_shutil_which,
                                  mock_subprocess_run, mock_urlopen,
                                  mock_urlopen_raising_403)


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
            remote_and_organization_and_repository = RemoteAndOrganizationAndRepository.from_url(
                domain=GitHubClient.DEFAULT_GITHUB_DOMAIN, url=url, remote='origin')
            assert remote_and_organization_and_repository is not None
            assert remote_and_organization_and_repository.organization == organization
            assert remote_and_organization_and_repository.repository == repository

    def test_github_api_pagination(self, mocker: MockerFixture, tmp_path: Any) -> None:
        mocker.patch('builtins.input', mock_input_returning_y)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        mocker.patch('git_machete.github.RemoteAndOrganizationAndRepository.from_url', mock_from_url)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('urllib.request.Request', MockGitHubAPIState([]).new_request(PaginatedMockGitHubAPIResponse))
        mocker.patch('urllib.request.urlopen', mock_urlopen)

        (
            self.repo_sandbox.new_branch("develop")
            .commit("first commit")
            .push()
        )
        for i in range(NUMBER_OF_PAGES * PRS_PER_PAGE):
            self.repo_sandbox.check_out('develop').new_branch(f'feature_{i}').commit().push()
        self.repo_sandbox.check_out('develop')
        body: str = 'develop *\n' + '\n'.join([f'feature_{i}'
                                               for i in range(NUMBER_OF_PAGES * PRS_PER_PAGE)]) + '\n'
        rewrite_definition_file(body)

        self.repo_sandbox.check_out('develop')
        for i in range(NUMBER_OF_PAGES * PRS_PER_PAGE):
            self.repo_sandbox.execute(f"git branch -D feature_{i}")
        body = 'develop *\n'
        rewrite_definition_file(body)

        launch_command('github', 'checkout-prs', '--all')
        launch_command('discover', '--checked-out-since=1 day ago')
        expected_status_output = 'develop *\n' + '\n'.join([f'|\no-feature_{i}  rebase=no push=no'
                                                            for i in range(NUMBER_OF_PAGES * PRS_PER_PAGE)]) + '\n'
        assert_success(['status'], expected_status_output)

    def test_github_enterprise_domain_fail(self, mocker: MockerFixture) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('builtins.input', mock_input_returning("1"))
        mocker.patch('git_machete.github.RemoteAndOrganizationAndRepository.from_url', mock_from_url)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        mocker.patch('urllib.request.urlopen', mock_urlopen_raising_403)

        github_enterprise_domain = 'git.example.org'
        self.repo_sandbox.set_git_config_key('machete.github.domain', github_enterprise_domain)

        expected_error_message = (
            "GitHub API returned 403 HTTP status with error message: Forbidden\n"
            "You might not have the required permissions for this repository.\n"
            "Provide a GitHub API token with repo access.\n"
            f"Visit https://{github_enterprise_domain}/settings/tokens to generate a new one.\n"
            "You can also use a different token provider, available providers can be found when running git machete help github.")
        assert_failure(['github', 'checkout-prs', '--all'], expected_error_message)

    git_api_state_for_test_github_enterprise_domain = MockGitHubAPIState(
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
        mocker.patch('builtins.input', mock_input_returning("1"))
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        mocker.patch('git_machete.github.RemoteAndOrganizationAndRepository.from_url', mock_from_url)
        mocker.patch('urllib.request.urlopen', mock_urlopen)
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_github_enterprise_domain.new_request())

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

    def test_github_token_retrieval_order(self, mocker: MockerFixture) -> None:
        mocker.patch('git_machete.github.GitHubToken._get_github_token_env_var', lambda: None)
        mocker.patch('git_machete.github.RemoteAndOrganizationAndRepository.from_url', mock_from_url)
        mocker.patch('os.path.isfile', lambda file: False)
        mocker.patch('shutil.which', mock_shutil_which(None))
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_github_enterprise_domain.new_request())
        mocker.patch('urllib.request.urlopen', mock_urlopen)

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

        assert launch_command('github', 'anno-prs', '--debug').splitlines()[8:12] == expected_output

    def test_get_token_from_env_var(self, mocker: MockerFixture) -> None:
        mocker.patch('git_machete.github.GitHubToken._get_github_token_env_var', lambda: 'github_token_from_env_var')

        github_token = GitHubToken.for_domain(domain=GitHubClient.DEFAULT_GITHUB_DOMAIN)
        assert github_token is not None
        assert github_token.provider == '`GITHUB_TOKEN` environment variable'
        assert github_token.value == 'github_token_from_env_var'

    def test_get_token_from_file_in_home_directory(self, mocker: MockerFixture) -> None:
        github_token_contents = ('ghp_mytoken_for_github_com\n'
                                 'ghp_myothertoken_for_git_example_org git.example.org\n'
                                 'ghp_yetanothertoken_for_git_example_com git.example.com')
        _mock_open = mock_open(read_data=github_token_contents)
        _mock_open.return_value.readlines.return_value = github_token_contents.split('\n')
        mocker.patch('builtins.open', _mock_open)
        mocker.patch('os.path.isfile', lambda file: True)

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

        domain = 'git.example.com'
        github_token = GitHubToken.for_domain(domain=domain)
        assert github_token is not None
        assert github_token.provider == f'auth token for {domain} from `~/.github-token`'
        assert github_token.value == 'ghp_yetanothertoken_for_git_example_com'

    def test_get_token_from_gh(self, mocker: MockerFixture) -> None:
        mocker.patch('os.path.isfile', lambda file: False)
        mocker.patch('git_machete.github.GitHubToken._get_github_token_env_var', lambda: None)
        mocker.patch('shutil.which', mock_shutil_which('/path/to/gh'))
        mocker.patch('subprocess.run', mock_subprocess_run(returncode=0, stdout='stdout', stderr='''
        github.com
            ✓ Logged in to github.com as Foo Bar (/Users/foo_bar/.config/gh/hosts.yml)
            ✓ Git operations for github.com configured to use ssh protocol.
            ✓ Token: ghp_mytoken_for_github_com_from_gh_cli
            ✓ Token scopes: gist, read:discussion, read:org, repo, workflow
        '''))

        domain = 'git.example.com'
        github_token = GitHubToken.for_domain(domain=domain)
        assert github_token is not None
        assert github_token.provider == f'auth token for {domain} from `gh` GitHub CLI'
        assert github_token.value == 'ghp_mytoken_for_github_com_from_gh_cli'

    def test_get_token_from_hub(self, mocker: MockerFixture) -> None:
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

        mocker.patch('builtins.open', mock_open(read_data=dedent(config_hub_contents)))
        mocker.patch('os.path.isfile', lambda file: '.github-token' not in file)
        mocker.patch('subprocess.run', mock_subprocess_run(returncode=1))

        github_token = GitHubToken.for_domain(domain=domain1)
        assert github_token is not None
        assert github_token.provider == f'auth token for {domain1} from `hub` GitHub CLI'
        assert github_token.value == 'ghp_mytoken_for_github_com'

        github_token = GitHubToken.for_domain(domain=domain2)
        assert github_token is not None
        assert github_token.provider == f'auth token for {domain2} from `hub` GitHub CLI'
        assert github_token.value == 'ghp_myothertoken_for_git_example_org'

    git_api_state_for_test_local_branch_name_different_than_tracking_branch_name = MockGitHubAPIState(
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

    def test_local_branch_name_different_than_tracking_branch_name(self, mocker: MockerFixture) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('urllib.request.Request',
                     self.git_api_state_for_test_local_branch_name_different_than_tracking_branch_name.new_request())
        mocker.patch('urllib.request.urlopen', mock_urlopen)

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
