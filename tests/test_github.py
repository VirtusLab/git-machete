import json
import os
import re
from http import HTTPStatus
from subprocess import CalledProcessError, CompletedProcess
from tempfile import mkdtemp
from textwrap import dedent
from typing import Any, Callable, ContextManager, Dict, List, Optional, Union
from unittest.mock import mock_open
from urllib.error import HTTPError
from urllib.parse import ParseResult, parse_qs, urlparse

import pytest

from git_machete.exceptions import MacheteException
from git_machete.git_operations import LocalBranchShortName
from git_machete.github import (GitHubClient, GitHubToken,
                                RemoteAndOrganizationAndRepository)
from git_machete.options import CommandLineOptions

from .base_test import BaseTest, GitRepositorySandbox, git
from .mockers import (assert_command, get_current_commit_hash, launch_command,
                      mock_ask_if, mock_exit_script, mock_run_cmd,
                      mock_should_perform_interactive_slide_out,
                      rewrite_definition_file)


class FakeCommandLineOptions(CommandLineOptions):
    def __init__(self) -> None:
        super().__init__()
        self.opt_no_interactive_rebase: bool = True
        self.opt_yes: bool = True


def mock_for_domain_none(domain: str) -> None:
    return None


def mock_for_domain_fake(domain: str) -> GitHubToken:
    return GitHubToken(value='dummy_token',
                       provider='dummy_provider')


def mock_github_remote_url_patterns(domain: str) -> List[str]:
    return ['(.*)/(.*)']


def mock_fetch_ref(cls: Any, remote: str, ref: str) -> None:
    branch: LocalBranchShortName = LocalBranchShortName.of(ref[ref.index(':') + 1:])
    git.create_branch(branch, get_current_commit_hash(), switch_head=True)


def mock_derive_current_user_login(domain: str) -> str:
    return "very_complex_user_token"


def mock_input(msg: str) -> str:
    print(msg)
    return '1'


def mock_is_file_true(file: Any) -> bool:
    return True


def mock_is_file_false(file: Any) -> bool:
    return False


def mock_is_file_not_github_token(file: Any) -> bool:
    if '.github-token' not in file:
        return True
    return False


def mock_os_environ_get_none(self: Any, key: str, default: Optional[str] = None) -> Any:
    if key == GitHubToken.GITHUB_TOKEN_ENV_VAR:
        return None
    try:
        return self[key]
    except KeyError:
        return default


def mock_os_environ_get_github_token(self: Any, key: str, default: Optional[str] = None) -> Any:
    if key == GitHubToken.GITHUB_TOKEN_ENV_VAR:
        return 'github_token_from_env_var'
    try:
        return self[key]
    except KeyError:
        return default


def mock_shutil_which_gh(path: Optional[str]) -> Callable[[Any], Optional[str]]:
    return lambda cmd: path


def mock_subprocess_run(returncode: int, stdout: str = '', stderr: str = ''):  # type: ignore[no-untyped-def]
    return lambda *args, **kwargs: CompletedProcess(args, returncode, bytes(stdout, 'utf-8'), bytes(stderr, 'utf-8'))


prs_per_page = 3
number_of_pages = 3


def mock_read(self: Any) -> bytes:
    response_data = [
        {
            'head': {'ref': f'feature_{i}', 'repo': {'full_name': 'testing/checkout_prs',
                                                     'html_url': 'https://github.com/tester/repo_sandbox.git'}},
            'user': {'login': 'github_user'},
            'base': {'ref': 'develop'},
            'number': f'{i}',
            'html_url': 'www.github.com',
            'state': 'open'
        } for i in range(mock_read.counter * prs_per_page, (mock_read.counter + 1) * prs_per_page)]  # type: ignore[attr-defined]

    mock_read.counter += 1  # type: ignore[attr-defined]
    return json.dumps(response_data).encode()


def mock_info(x: Any) -> Dict[str, Any]:
    if mock_info.counter < number_of_pages - 1:  # type: ignore[attr-defined]
        link = f'<https://api.github.com/repositories/1300192/pulls?page={mock_info.counter + 2}>; rel="next"'  # type: ignore[attr-defined]
    else:
        link = ''
    mock_info.counter += 1  # type: ignore[attr-defined]
    return {"link": link}


mock_info.counter = mock_read.counter = 0  # type: ignore[attr-defined]


class MockGitHubAPIState:
    def __init__(self, pulls: List[Dict[str, Any]], issues: Optional[List[Dict[str, Any]]] = None) -> None:
        self.pulls: List[Dict[str, Any]] = pulls
        self.user: Dict[str, str] = {'login': 'other_user', 'type': 'User', 'company': 'VirtusLab'}
        # login must be different from the one used in pull requests, otherwise pull request author will not be annotated
        self.issues: List[Dict[str, Any]] = issues or []

    def new_request(self) -> "MockGitHubAPIRequest":
        return MockGitHubAPIRequest(self)

    def get_issue(self, issue_no: str) -> Optional[Dict[str, Any]]:
        for issue in self.issues:
            if issue['number'] == issue_no:
                return issue
        return None

    def get_pull(self, pull_no: str) -> Optional[Dict[str, Any]]:
        for pull in self.pulls:
            if pull['number'] == pull_no:
                return pull
        return None


class MockGitHubAPIResponse:
    def __init__(self, status_code: int, response_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> None:
        self.response_data: Union[List[Dict[str, Any]], Dict[str, Any]] = response_data
        self.status_code: int = status_code

    def read(self) -> bytes:
        return json.dumps(self.response_data).encode()

    def info(self) -> Dict[str, Any]:
        return {"link": None}


class MockGitHubAPIRequest:
    def __init__(self, github_api_state: MockGitHubAPIState) -> None:
        self.github_api_state: MockGitHubAPIState = github_api_state

    def __call__(self, url: str, headers: Dict[str, str] = {}, data: Union[str, bytes, None] = None,
                 method: str = '') -> "MockGitHubAPIResponse":
        self.parsed_url: ParseResult = urlparse(url, allow_fragments=True)
        self.parsed_query: Dict[str, List[str]] = parse_qs(self.parsed_url.query)
        self.json_data: Union[str, bytes, None] = data
        self.headers: Dict[str, str] = headers
        return self.handle_method(method)

    def handle_method(self, method: str) -> "MockGitHubAPIResponse":
        if method == "GET":
            return self.handle_get()
        elif method == "PATCH":
            return self.handle_patch()
        elif method == "POST":
            return self.handle_post()
        else:
            return self.make_response_object(HTTPStatus.METHOD_NOT_ALLOWED, [])

    def handle_get(self) -> "MockGitHubAPIResponse":
        if 'pulls' in self.parsed_url.path:
            full_head_name: Optional[List[str]] = self.parsed_query.get('head')
            number: Optional[str] = self.find_number(self.parsed_url.path, 'pulls')
            if number:
                for pr in self.github_api_state.pulls:
                    if pr['number'] == number:
                        return self.make_response_object(HTTPStatus.OK, pr)
                return self.make_response_object(HTTPStatus.NOT_FOUND, [])
            elif full_head_name:
                head: str = full_head_name[0].split(':')[1]
                for pr in self.github_api_state.pulls:
                    if pr['head']['ref'] == head:
                        return self.make_response_object(HTTPStatus.OK, [pr])
                return self.make_response_object(HTTPStatus.NOT_FOUND, [])
            else:
                return self.make_response_object(HTTPStatus.OK, [pull for pull in self.github_api_state.pulls if pull['state'] == 'open'])
        elif self.parsed_url.path.endswith('user'):
            return self.make_response_object(HTTPStatus.OK, self.github_api_state.user)
        else:
            return self.make_response_object(HTTPStatus.NOT_FOUND, [])

    def handle_patch(self) -> "MockGitHubAPIResponse":
        if 'issues' in self.parsed_url.path:
            return self.update_issue()
        elif 'pulls' in self.parsed_url.path:
            return self.update_pull_request()
        else:
            return self.make_response_object(HTTPStatus.NOT_FOUND, [])

    def handle_post(self) -> "MockGitHubAPIResponse":
        assert not self.parsed_query
        if 'issues' in self.parsed_url.path:
            return self.update_issue()
        elif 'pulls' in self.parsed_url.path:
            return self.update_pull_request()
        else:
            return self.make_response_object(HTTPStatus.NOT_FOUND, [])

    def update_pull_request(self) -> "MockGitHubAPIResponse":
        pull_no = self.find_number(self.parsed_url.path, 'pulls')
        if not pull_no:
            if self.is_pull_created():
                head = json.loads(self.json_data)["head"]  # type: ignore[arg-type]
                return self.make_response_object(HTTPStatus.UNPROCESSABLE_ENTITY, {'message': 'Validation Failed', 'errors': [
                    {'message': f'A pull request already exists for test_repo:{head}.'}]})
            return self.create_pull_request()
        pull = self.github_api_state.get_pull(pull_no)
        assert pull is not None
        return self.fill_pull_request_data(json.loads(self.json_data), pull)  # type: ignore[arg-type]

    def create_pull_request(self) -> "MockGitHubAPIResponse":
        pull = {'number': self.get_next_free_number(self.github_api_state.pulls),
                'user': {'login': 'github_user'},
                'html_url': 'www.github.com',
                'state': 'open',
                'head': {'ref': "", 'repo': {'full_name': 'testing:checkout_prs', 'html_url': mkdtemp()}},
                'base': {'ref': ""}}
        return self.fill_pull_request_data(json.loads(self.json_data), pull)  # type: ignore[arg-type]

    def fill_pull_request_data(self, data: Dict[str, Any], pull: Dict[str, Any]) -> "MockGitHubAPIResponse":
        index = self.get_index_or_none(pull, self.github_api_state.issues)
        for key in data.keys():
            if key in ('base', 'head'):
                pull[key]['ref'] = json.loads(self.json_data)[key]  # type: ignore[arg-type]
            else:
                pull[key] = json.loads(self.json_data)[key]  # type: ignore[arg-type]
        if index:
            self.github_api_state.pulls[index] = pull
        else:
            self.github_api_state.pulls.append(pull)
        return self.make_response_object(HTTPStatus.CREATED, pull)

    def update_issue(self) -> "MockGitHubAPIResponse":
        issue_no = self.find_number(self.parsed_url.path, 'issues')
        if not issue_no:
            return self.create_issue()
        issue = self.github_api_state.get_issue(issue_no)
        assert issue is not None
        return self.fill_issue_data(json.loads(self.json_data), issue)  # type: ignore[arg-type]

    def create_issue(self) -> "MockGitHubAPIResponse":
        issue = {'number': self.get_next_free_number(self.github_api_state.issues)}
        return self.fill_issue_data(json.loads(self.json_data), issue)  # type: ignore[arg-type]

    def fill_issue_data(self, data: Dict[str, Any], issue: Dict[str, Any]) -> "MockGitHubAPIResponse":
        index = self.get_index_or_none(issue, self.github_api_state.issues)
        for key in data.keys():
            issue[key] = data[key]
        if index is not None:
            self.github_api_state.issues[index] = issue
        else:
            self.github_api_state.issues.append(issue)
        return self.make_response_object(HTTPStatus.CREATED, issue)

    def is_pull_created(self) -> bool:
        deserialized_json_data = json.loads(self.json_data)  # type: ignore[arg-type]
        head: str = deserialized_json_data['head']
        base: str = deserialized_json_data['base']
        for pull in self.github_api_state.pulls:
            pull_head: str = pull['head']['ref']
            pull_base: str = pull['base']['ref']
            if (head, base) == (pull_head, pull_base):
                return True
        return False

    @staticmethod
    def get_index_or_none(entity: Dict[str, Any], base: List[Dict[str, Any]]) -> Optional[int]:
        try:
            return base.index(entity)
        except ValueError:
            return None

    @staticmethod
    def make_response_object(status_code: int, response_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> "MockGitHubAPIResponse":
        return MockGitHubAPIResponse(status_code, response_data)

    @staticmethod
    def find_number(url: str, entity: str) -> Optional[str]:
        m = re.search(f'{entity}/(\\d+)', url)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def get_next_free_number(entities: List[Dict[str, Any]]) -> str:
        numbers = [int(item['number']) for item in entities]
        return str(max(numbers) + 1)


class MockHTTPError(HTTPError):
    from email.message import Message

    def __init__(self, url: str, code: int, msg: Any, hdrs: Message, fp: Any) -> None:
        super().__init__(url, code, msg, hdrs, fp)
        self.msg = msg

    def read(self, n: int = 1) -> bytes:  # noqa: F841
        return json.dumps(self.msg).encode()


class MockContextManager(ContextManager[MockGitHubAPIResponse]):
    def __init__(self, obj: MockGitHubAPIResponse) -> None:
        self.obj = obj

    def __enter__(self) -> MockGitHubAPIResponse:
        if self.obj.status_code == HTTPStatus.NOT_FOUND:
            raise HTTPError("http://example.org", 404, 'Not found', None, None)  # type: ignore[arg-type]
        elif self.obj.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise MockHTTPError("http://example.org", 422, self.obj.response_data, None, None)  # type: ignore[arg-type]
        return self.obj

    def __exit__(self, *args: Any) -> None:
        pass


class MockContextManagerRaise403(MockContextManager):
    def __init__(self, obj: MockGitHubAPIResponse) -> None:
        super().__init__(obj)

    def __enter__(self) -> MockGitHubAPIResponse:
        raise HTTPError("http://example.org", 403, 'Forbidden', None, None)  # type: ignore[arg-type]


class TestGitHub(BaseTest):
    mock_repository_info: Dict[str, str] = {'full_name': 'testing/checkout_prs',
                                            'html_url': 'https://github.com/tester/repo_sandbox.git'}

    git_api_state_for_test_retarget_pr = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'feature', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'root'}, 'number': '15',
                'html_url': 'www.github.com', 'state': 'open'
            },
            {
                'head': {'ref': 'feature_1', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'root'}, 'number': '20',
                'html_url': 'www.github.com', 'state': 'open'
            },
            {
                'head': {'ref': 'feature_2', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'root'}, 'number': '25',
                'html_url': 'www.github.com', 'state': 'open'
            },
            {
                'head': {'ref': 'feature_3', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'root'}, 'number': '35',
                'html_url': 'www.github.com', 'state': 'open'
            }
        ]
    )

    def test_github_retarget_pr(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_retarget_pr.new_request())
        mocker.patch('urllib.request.urlopen', MockContextManager)

        branchs_first_commit_msg = "First commit on branch."
        branchs_second_commit_msg = "Second commit on branch."
        (
            self.repo_sandbox.new_branch("root")
                .commit("First commit on root.")
                .new_branch("branch-1")
                .commit(branchs_first_commit_msg)
                .commit(branchs_second_commit_msg)
                .push()
                .new_branch('feature')
                .commit('introduce feature')
                .push()
                .check_out('feature')
                .add_remote('new_origin', 'https://github.com/user/repo.git')
        )
        body: str = \
            """
            root
                branch-1
                    feature
            """
        rewrite_definition_file(body)

        launch_command("anno", "-H")

        expected_status_output = """
        root (untracked)
        |
        o-branch-1
          |
          o-feature *  PR #15 (github_user) WRONG PR BASE or MACHETE PARENT? PR has root rebase=no push=no
        """
        assert_command(
            ['status'],
            expected_result=expected_status_output
        )

        assert_command(
            ['github', 'retarget-pr'],
            'The base branch of PR #15 has been switched to branch-1\n'
        )

        expected_status_output = """
        root (untracked)
        |
        o-branch-1
          |
          o-feature *  PR #15 rebase=no push=no
        """
        assert_command(
            ['status'],
            expected_result=expected_status_output
        )

        assert_command(
            ['github', 'retarget-pr'],
            'The base branch of PR #15 is already branch-1\n'
        )

    git_api_state_for_test_github_retarget_pr_explicit_branch = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'feature', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'root'}, 'number': '15',
                'html_url': 'www.github.com', 'state': 'open'
            }
        ]
    )

    def test_github_retarget_pr_explicit_branch(self, mocker: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_github_retarget_pr_explicit_branch.new_request())
        mocker.patch('urllib.request.urlopen', MockContextManager)

        branchs_first_commit_msg = "First commit on branch."
        branchs_second_commit_msg = "Second commit on branch."
        (
            self.repo_sandbox.new_branch("root")
                .commit("First commit on root.")
                .new_branch("branch-1")
                .commit(branchs_first_commit_msg)
                .commit(branchs_second_commit_msg)
                .push()
                .new_branch('feature')
                .commit('introduce feature')
                .push()
                .check_out('root')
                .new_branch('branch-without-pr')
                .commit('branch-without-pr')
                .push()
                .add_remote('new_origin', 'https://github.com/user/repo.git')
                .check_out('root')
        )

        body: str = \
            """
            root
                branch-1
                    feature
                branch-without-pr
            """
        rewrite_definition_file(body)
        launch_command("anno", "-H")

        expected_status_output = """
        root * (untracked)
        |
        o-branch-1
        | |
        | o-feature  PR #15 (github_user) WRONG PR BASE or MACHETE PARENT? PR has root rebase=no push=no
        |
        o-branch-without-pr
        """
        assert_command(
            ['status'],
            expected_result=expected_status_output
        )

        assert_command(
            ['github', 'retarget-pr', '--branch', 'feature'],
            'The base branch of PR #15 has been switched to branch-1\n'
        )

        expected_status_output = """
        root * (untracked)
        |
        o-branch-1
        | |
        | o-feature  PR #15 rebase=no push=no
        |
        o-branch-without-pr
        """
        assert_command(
            ['status'],
            expected_result=expected_status_output
        )

        expected_error_message = ('GET https://api.github.com/repos/user/repo/pulls?head=user:branch-without-pr request '
                                  'ended up in 404 response from GitHub. A valid GitHub API token is required.\n'
                                  'Provide a GitHub API token with repo access via one of the: \n'
                                  '\t1. GITHUB_TOKEN environment variable.\n'
                                  '\t2. Content of the ~/.github-token file.\n'
                                  '\t3. Current auth token from the gh GitHub CLI.\n'
                                  '\t4. Current auth token from the hub GitHub CLI.\n'
                                  ' Visit https://github.com/settings/tokens to generate a new one.')
        with pytest.raises(MacheteException) as e:
            launch_command("github", "retarget-pr", "--branch", "branch-without-pr")
        assert e.value.args[0] == expected_error_message, \
            'Verify that expected error message has appeared when there is no pull request associated with that branch name.'

        launch_command('github', 'retarget-pr', '--branch', 'branch-without-pr', '--ignore-if-missing')

    def test_github_retarget_pr_multiple_non_origin_remotes(self, mocker: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_retarget_pr.new_request())
        mocker.patch('urllib.request.urlopen', MockContextManager)

        branchs_first_commit_msg = "First commit on branch."
        branchs_second_commit_msg = "Second commit on branch."

        origin_1_remote_path = mkdtemp()
        origin_2_remote_path = mkdtemp()
        self.repo_sandbox.new_repo(origin_1_remote_path, switch_dir_to_new_repo=False)
        self.repo_sandbox.new_repo(origin_2_remote_path, switch_dir_to_new_repo=False)

        # branch feature present in each remote, no branch tracking data
        (
            self.repo_sandbox.remove_remote(remote='origin')
                .new_branch("root")
                .add_remote('origin_1', origin_1_remote_path)
                .add_remote('origin_2', origin_2_remote_path)
                .commit("First commit on root.")
                .push(remote='origin_1')
                .push(remote='origin_2')
                .new_branch("branch-1")
                .commit(branchs_first_commit_msg)
                .commit(branchs_second_commit_msg)
                .push(remote='origin_1')
                .push(remote='origin_2')
                .new_branch('feature')
                .commit('introduce feature')
                .push(remote='origin_1', set_upstream=False)
                .push(remote='origin_2', set_upstream=False)
        )

        body: str = \
            """
            root
                branch-1
                    feature
            """
        rewrite_definition_file(body)

        expected_error_message = (
            "Multiple non-origin remotes correspond to GitHub in this repository: origin_1, origin_2 -> aborting. \n"
            "You can also select the repository by providing some or all of git config keys: "
            "`machete.github.{domain,remote,organization,repository}`.\n"  # noqa: FS003
        )
        with pytest.raises(MacheteException) as e:
            launch_command("github", "retarget-pr")
        assert e.value.args[0] == expected_error_message, \
            'Verify that expected error message has appeared when given pull request to create is already created.'

        # branch feature_1 present in each remote, tracking data present
        (
            self.repo_sandbox.check_out('feature')
                .new_branch('feature_1')
                .commit('introduce feature 1')
                .push(remote='origin_1')
                .push(remote='origin_2')
        )

        body = \
            """
            root
                branch-1
                    feature
                        feature_1
            """
        rewrite_definition_file(body)

        assert_command(
            ['github', 'retarget-pr'],
            'The base branch of PR #20 has been switched to feature\n'
        )

        # branch feature_2 is not present in any of the remotes
        (
            self.repo_sandbox.check_out('feature')
                .new_branch('feature_2')
                .commit('introduce feature 2')
        )

        body = \
            """
            root
                branch-1
                    feature
                        feature_1
                        feature_2
            """
        rewrite_definition_file(body)

        with pytest.raises(MacheteException) as e:
            launch_command("github", "retarget-pr")
        assert e.value.args[0] == expected_error_message, \
            'Verify that expected error message has appeared when given pull request to create is already created.'

        # branch feature_2 present in only one remote: origin_1 and there is no tracking data available -> infer the remote
        (
            self.repo_sandbox.check_out('feature_2')
                .push(remote='origin_1', set_upstream=False)
        )

        assert_command(
            ['github', 'retarget-pr'],
            'The base branch of PR #25 has been switched to feature\n'
        )

        # branch feature_3 present in only one remote: origin_1 and has tracking data
        (
            self.repo_sandbox.check_out('feature_2')
                .new_branch('feature_3')
                .commit('introduce feature 3')
                .push(remote='origin_1')
        )

        body = \
            """
            root
                branch-1
                    feature
                        feature_1
                        feature_2
                            feature_3
            """
        rewrite_definition_file(body)

        assert_command(
            ['github', 'retarget-pr'],
            'The base branch of PR #35 has been switched to feature_2\n'
        )

    git_api_state_for_test_anno_prs = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'hotfix/add-trigger'},
                'number': '3',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'allow-ownership-link', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '7',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'call-ws', 'repo': mock_repository_info},
                'user': {'login': 'very_complex_user_token'},
                'base': {'ref': 'develop'},
                'number': '31',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ]
    )

    def test_github_anno_prs(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('git_machete.github.GitHubClient.derive_current_user_login', mock_derive_current_user_login)
        mocker.patch('urllib.request.urlopen', MockContextManager)
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_anno_prs.new_request())

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
                .commit_amend("HOTFIX Add the trigger (amended)")
                .new_branch("ignore-trailing")
                .commit("Ignore trailing data")
                .sleep(1)
                .commit_amend("Ignore trailing data (amended)")
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
        assert_command(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing *  PR #3 (github_user) rebase=no push=no (diverged from & older than origin)

            develop
            |
            x-allow-ownership-link  PR #7 (github_user) rebase=no (ahead of origin)
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
        assert_command(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing *  PR #3 (github_user) rebase=no push=no (diverged from & older than origin)

            develop
            |
            x-allow-ownership-link  PR #7 (github_user) rebase=no (ahead of origin)
            | |
            | x-build-chain  rebase=no push=no (untracked)
            |
            o-call-ws  PR #31 (ahead of origin)
              |
              x-drop-constraint (untracked)
            """,
        )

    git_api_state_for_test_create_pr = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'hotfix/add-trigger'},
                'number': '3',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ],
        issues=[
            {'number': '4'},
            {'number': '5'},
            {'number': '6'}
        ]
    )

    def test_github_create_pr(self, mocker: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)
        mocker.patch('git_machete.client.MacheteClient.ask_if', mock_ask_if)
        # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_create_pr`
        # due to `git fetch` executed by `create-pr` subcommand.
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
        mocker.patch('urllib.error.HTTPError', MockHTTPError)  # need to provide read() method, which does not actually reads error from url
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_create_pr.new_request())
        mocker.patch('urllib.request.urlopen', MockContextManager)

        (
            self.repo_sandbox.new_branch("root")
                .commit("initial commit")
                .new_branch("develop")
                .commit("first commit")
                .new_branch("allow-ownership-link")
                .commit("Enable ownership links")
                .push()
                .new_branch("build-chain")
                .commit("Build arbitrarily long chains of PRs")
                .check_out("allow-ownership-link")
                .commit("fixes")
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
                .commit_amend("HOTFIX Add the trigger (amended)")
                .new_branch("ignore-trailing")
                .commit("Ignore trailing data")
                .sleep(1)
                .commit_amend("Ignore trailing data (amended)")
                .push()
                .reset_to("ignore-trailing@{1}")  # noqa: FS003
                .delete_branch("root")
                .new_branch('chore/fields')
                .commit("remove outdated fields")
                .check_out("call-ws")
                .add_remote('new_origin', 'https://github.com/user/repo.git')
        )
        body: str = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing
                        chore/fields
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
            """
        rewrite_definition_file(body)

        launch_command("github", "create-pr")
        # ahead of origin state, push is advised and accepted
        assert_command(
            ['status'],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing (diverged from & older than origin)
                |
                o-chore/fields (untracked)

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws *  PR #4
              |
              x-drop-constraint (untracked)
            """,
        )
        self.repo_sandbox.check_out('chore/fields')
        #  untracked state (can only create pr when branch is pushed)
        launch_command("github", "create-pr", "--draft")
        assert_command(
            ['status'],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing (diverged from & older than origin)
                |
                o-chore/fields *  PR #5

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws  PR #4
              |
              x-drop-constraint (untracked)
            """,
        )

        (
            self.repo_sandbox.check_out('hotfix/add-trigger')
                .commit('trigger released')
                .commit('minor changes applied')
        )

        # diverged from and newer than origin
        launch_command("github", "create-pr")
        assert_command(
            ['status'],
            """
            master
            |
            o-hotfix/add-trigger *  PR #6
              |
              x-ignore-trailing (diverged from & older than origin)
                |
                o-chore/fields  PR #5

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws  PR #4
              |
              x-drop-constraint (untracked)
            """,
        )
        expected_error_message = "A pull request already exists for test_repo:hotfix/add-trigger."
        with pytest.raises(MacheteException) as e:
            launch_command("github", "create-pr")
        assert e.value.args[0] == expected_error_message, \
            'Verify that expected error message has appeared when given pull request to create is already created.'

        # check against head branch is ancestor or equal to base branch
        (
            self.repo_sandbox.check_out('develop')
                .new_branch('testing/endpoints')
                .push()
        )
        body = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing
                        chore/fields
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
                testing/endpoints
            """
        rewrite_definition_file(body)

        expected_error_message = "All commits in testing/endpoints branch are already included in develop branch.\n" \
                                 "Cannot create pull request."
        with pytest.raises(MacheteException) as e:
            launch_command("github", "create-pr")
        assert e.value.parameter == expected_error_message, \
            'Verify that expected error message has appeared when head branch is equal or ancestor of base branch.'

        self.repo_sandbox.check_out('develop')
        expected_error_message = "Branch develop does not have a parent branch (it is a root), " \
                                 "base branch for the PR cannot be established."
        with pytest.raises(MacheteException) as e:
            launch_command("github", "create-pr")
        assert e.value.parameter == expected_error_message, \
            'Verify that expected error message has appeared when creating PR from root branch.'

    git_api_state_for_test_create_pr_missing_base_branch_on_remote = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'chore/redundant_checks', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'restrict_access'},
                'number': '18',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ]
    )

    def test_github_create_pr_missing_base_branch_on_remote(self, mocker: Any) -> None:
        # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_create_pr`
        # due to `git fetch` executed by `create-pr` subcommand.
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_for_domain_none)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
        mocker.patch('git_machete.client.MacheteClient.ask_if', mock_ask_if)
        mocker.patch('urllib.request.urlopen', MockContextManager)
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_create_pr_missing_base_branch_on_remote.new_request())

        (
            self.repo_sandbox.new_branch("root")
                .commit("initial commit")
                .new_branch("develop")
                .commit("first commit on develop")
                .push()
                .new_branch("feature/api_handling")
                .commit("Introduce GET and POST methods on API")
                .new_branch("feature/api_exception_handling")
                .commit("catch exceptions coming from API")
                .push()
                .delete_branch("root")
        )
        body: str = \
            """
            develop
                feature/api_handling
                    feature/api_exception_handling
            """
        rewrite_definition_file(body)

        expected_msg = ("Fetching origin...\n"
                        "Warn: Base branch for this PR (feature/api_handling) is not found on remote, pushing...\n"
                        "Creating a PR from feature/api_exception_handling to feature/api_handling... OK, see www.github.com\n")
        assert_command(['github', 'create-pr'], expected_msg)
        assert_command(
            ['status'],
            """
            develop
            |
            o-feature/api_handling
              |
              o-feature/api_exception_handling *  PR #19
            """,
        )

    git_api_state_for_test_github_create_pr_with_multiple_non_origin_remotes = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'branch-1', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'root'}, 'number': '15',
                'html_url': 'www.github.com', 'state': 'open'
            }
        ],
        issues=[
            {'number': '16'},
            {'number': '17'},
            {'number': '18'},
            {'number': '19'},
            {'number': '20'},
        ]
    )

    def test_github_create_pr_with_multiple_non_origin_remotes(self, mocker: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)
        mocker.patch('git_machete.client.MacheteClient.ask_if', mock_ask_if)
        # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_create_pr`
        # due to `git fetch` executed by `create-pr` subcommand.
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_for_domain_none)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
        mocker.patch('urllib.error.HTTPError', MockHTTPError)  # need to provide read() method, which does not actually read error from url
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_github_create_pr_with_multiple_non_origin_remotes.new_request())
        mocker.patch('urllib.request.urlopen', MockContextManager)
        mocker.patch('builtins.input', mock_input)

        origin_1_remote_path = mkdtemp()
        origin_2_remote_path = mkdtemp()
        self.repo_sandbox.new_repo(origin_1_remote_path, "--bare", switch_dir_to_new_repo=False)
        self.repo_sandbox.new_repo(origin_2_remote_path, "--bare", switch_dir_to_new_repo=False)

        # branch feature present in each of the remotes, no branch tracking data, remote origin_1 picked manually via mock_input()
        (
            self.repo_sandbox.remove_remote(remote='origin')
                .new_branch("root")
                .add_remote('origin_1', origin_1_remote_path)
                .add_remote('origin_2', origin_2_remote_path)
                .commit("First commit on root.")
                .push(remote='origin_1')
                .push(remote='origin_2')
                .new_branch("branch-1")
                .commit('First commit on branch-1.')
                .push(remote='origin_1')
                .push(remote='origin_2')
                .new_branch('feature')
                .commit('introduce feature')
                .push(remote='origin_1', set_upstream=False)
                .push(remote='origin_2', set_upstream=False)
        )
        body: str = \
            """
            root
                branch-1
                    feature
            """
        rewrite_definition_file(body)

        expected_result = """
        Branch feature is untracked and there's no origin repository.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit creating pull request: 
        Branch feature is untracked, but its remote counterpart candidate origin_1/feature already exists and both branches point to the same commit.

          root
          |
          o-branch-1
            |
            o-feature *

        Fetching origin_1...
        Creating a PR from feature to branch-1... OK, see www.github.com
        """  # noqa: W291, E501
        assert_command(
            ['github', 'create-pr'],
            expected_result
        )
        # branch feature_1 present in each of the remotes, tracking data present
        (
            self.repo_sandbox.check_out('feature')
                .new_branch('feature_1')
                .commit('introduce feature 1')
                .push(remote='origin_1')
                .push(remote='origin_2')
        )

        expected_result = """
        Added branch feature_1 onto feature
        Fetching origin_2...
        Creating a PR from feature_1 to feature... OK, see www.github.com
        """
        assert_command(
            ['github', 'create-pr'],
            expected_result
        )

        # branch feature_2 not present in any of the remotes, remote origin_1 picked manually via mock_input()
        (
            self.repo_sandbox.check_out('feature')
                .new_branch('feature_2')
                .commit('introduce feature 2')
        )

        expected_result = """
        Added branch feature_2 onto feature
        Branch feature_2 is untracked and there's no origin repository.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit creating pull request: 

          root
          |
          o-branch-1
            |
            o-feature  PR #16
              |
              o-feature_1  PR #17
              |
              o-feature_2 *

        Fetching origin_1...
        Creating a PR from feature_2 to feature... OK, see www.github.com
        """  # noqa: W291
        assert_command(
            ['github', 'create-pr'],
            expected_result
        )

        # branch feature_2 present in only one remote: origin_1, no tracking data
        (
            self.repo_sandbox.check_out('feature_2')
                .new_branch('feature_3')
                .commit('introduce feature 3')
                .push(remote='origin_1', set_upstream=False)
        )

        expected_result = """
        Added branch feature_3 onto feature_2
        Fetching origin_1...
        Creating a PR from feature_3 to feature_2... OK, see www.github.com
        """  # noqa: E501
        assert_command(
            ['github', 'create-pr'],
            expected_result
        )

        # branch feature_3 present in only one remote: origin_2, tracking data present
        (
            self.repo_sandbox.check_out('feature_3')
                .new_branch('feature_4')
                .commit('introduce feature 4')
                .push(remote='origin_2')
        )

        expected_result = """
        Added branch feature_4 onto feature_3
        Fetching origin_2...
        Warn: Base branch for this PR (feature_3) is not found on remote, pushing...
        Creating a PR from feature_4 to feature_3... OK, see www.github.com
        """
        assert_command(
            ['github', 'create-pr'],
            expected_result
        )

        # branch feature_3 present in only one remote: origin_2 with tracking data, origin remote present - takes priority
        (
            self.repo_sandbox.add_remote('origin', self.repo_sandbox.remote_path)
                .check_out('feature_3')
                .new_branch('feature_5')
                .commit('introduce feature 5')
                .push(remote='origin_2')
        )

        expected_result = """
        Added branch feature_5 onto feature_3
        Fetching origin...
        Creating a PR from feature_5 to feature_3... OK, see www.github.com
        """
        assert_command(
            ['github', 'create-pr'],
            expected_result
        )

    git_api_state_for_test_checkout_prs = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'chore/redundant_checks', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
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
                'user': {'login': 'github_user'},
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
                'user': {'login': 'github_user'},
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
            {'head': {'ref': 'chore/comments', 'repo': mock_repository_info},
             'user': {'login': 'github_user'},
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
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '5',
                'html_url': 'www.github.com',
                'state': 'closed'
            }
        ]
    )

    def test_github_checkout_prs(self, mocker: Any, tmp_path: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)
        # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_checkout_prs`
        # due to `git fetch` executed by `checkout-prs` subcommand.
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        mocker.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_for_domain_none)
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_checkout_prs.new_request())
        mocker.patch('urllib.request.urlopen', MockContextManager)

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
        assert_command(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  PR #3 (github_user) rebase=no push=no
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
              |
              o-bugfix/feature  PR #6 (github_user) rebase=no push=no
                |
                o-allow-ownership-link  PR #12 (github_user) rebase=no push=no
                  |
                  o-restrict_access  PR #17 (github_user) rebase=no push=no
                    |
                    o-chore/redundant_checks *  PR #18 (github_user) rebase=no push=no
            """
        )
        # broken chain of pull requests (add new root)
        launch_command('github', 'checkout-prs', '24')
        assert_command(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  PR #3 (github_user) rebase=no push=no
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
              |
              o-bugfix/feature  PR #6 (github_user) rebase=no push=no
                |
                o-allow-ownership-link  PR #12 (github_user) rebase=no push=no
                  |
                  o-restrict_access  PR #17 (github_user) rebase=no push=no
                    |
                    o-chore/redundant_checks  PR #18 (github_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  PR #22 (github_user) rebase=no push=no
              |
              o-chore/comments *  PR #24 (github_user) rebase=no push=no
            """
        )

        # broken chain of pull requests (branches already added)
        launch_command('github', 'checkout-prs', '24')
        assert_command(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  PR #3 (github_user) rebase=no push=no
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
              |
              o-bugfix/feature  PR #6 (github_user) rebase=no push=no
                |
                o-allow-ownership-link  PR #12 (github_user) rebase=no push=no
                  |
                  o-restrict_access  PR #17 (github_user) rebase=no push=no
                    |
                    o-chore/redundant_checks  PR #18 (github_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  PR #22 (github_user) rebase=no push=no
              |
              o-chore/comments *  PR #24 (github_user) rebase=no push=no
            """
        )

        # all PRs
        launch_command('github', 'checkout-prs', '--all')
        assert_command(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  PR #3 (github_user) rebase=no push=no
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
            | |
            | o-bugfix/feature  PR #6 (github_user) rebase=no push=no
            |   |
            |   o-allow-ownership-link  PR #12 (github_user) rebase=no push=no
            |     |
            |     o-restrict_access  PR #17 (github_user) rebase=no push=no
            |       |
            |       o-chore/redundant_checks  PR #18 (github_user) rebase=no push=no
            |
            o-enhance/add_user  PR #19 (github_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  PR #22 (github_user) rebase=no push=no
              |
              o-chore/comments *  PR #24 (github_user) rebase=no push=no
            """
        )

        # check against wrong pr number
        remote_org_repo = RemoteAndOrganizationAndRepository.from_url(domain=GitHubClient.DEFAULT_GITHUB_DOMAIN,
                                                                      url=self.repo_sandbox.remote_path,
                                                                      remote='origin')
        assert remote_org_repo is not None
        expected_error_message = f"PR #100 is not found in repository {remote_org_repo.organization}/{remote_org_repo.repository}"
        with pytest.raises(MacheteException) as e:
            launch_command('github', 'checkout-prs', '100')
        assert e.value.parameter == expected_error_message, \
            'Verify that expected error message has appeared when given pull request to checkout does not exists.'

        with pytest.raises(MacheteException) as e:
            launch_command('github', 'checkout-prs', '19', '100')
        assert e.value.parameter == expected_error_message, \
            'Verify that expected error message has appeared when one of the given pull requests to checkout does not exists.'

        # check against user with no open pull requests
        expected_msg = ("Checking for open GitHub PRs... OK\n"
                        f"Warn: User tester has no open pull request in repository "
                        f"{remote_org_repo.organization}/{remote_org_repo.repository}\n")
        assert_command(['github', 'checkout-prs', '--by', 'tester'], expected_msg)

        # Check against closed pull request with head branch deleted from remote
        local_path = tmp_path
        self.repo_sandbox.new_repo(GitRepositorySandbox.second_remote_path)
        (self.repo_sandbox.new_repo(local_path)
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
        with pytest.raises(MacheteException) as e:
            launch_command('github', 'checkout-prs', '5')
        assert e.value.parameter == expected_error_message, \
            'Verify that expected error message has appeared when given pull request to checkout ' \
            'have already deleted branch from remote.'

        # Check against pr come from fork
        os.chdir(local_path)
        (self.repo_sandbox
         .new_branch('bugfix/remove-n-option')
         .commit('first commit')
         .push()
         )
        os.chdir(self.repo_sandbox.local_path)

        expected_msg = ("Checking for open GitHub PRs... OK\n"
                        "Warn: Pull request #5 is already closed.\n"
                        "Pull request #5 checked out at local branch bugfix/remove-n-option\n")

        assert_command(['github', 'checkout-prs', '5'], expected_msg)

        # Check against multiple PRs
        expected_msg = 'Checking for open GitHub PRs... OK\n'

        assert_command(['github', 'checkout-prs', '3', '12'], expected_msg)

    git_api_state_for_test_github_checkout_prs_fresh_repo = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'comments/add_docstrings', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'improve/refactor'},
                'number': '2',
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
                'head': {'ref': 'improve/refactor', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'chore/sync_to_docs'},
                'number': '1',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'sphinx_export',
                         'repo': {'full_name': 'testing/checkout_prs', 'html_url': GitRepositorySandbox.second_remote_path}},
                'user': {'login': 'github_user'},
                'base': {'ref': 'comments/add_docstrings'},
                'number': '23',
                'html_url': 'www.github.com',
                'state': 'closed'
            }
        ]
    )

    def test_github_checkout_prs_freshly_cloned(self, mocker: Any, tmp_path: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_checkout_prs_freshly_cloned`
        # due to `git fetch` executed by `checkout-prs` subcommand.
        mocker.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        mocker.patch('urllib.request.urlopen', MockContextManager)
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_github_checkout_prs_fresh_repo.new_request())

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
        self.repo_sandbox.new_repo(GitRepositorySandbox.second_remote_path)
        (
            self.repo_sandbox.new_repo(local_path)
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
        assert_command(
            ['github', 'checkout-prs', '2'],
            expected_msg
        )

        assert_command(
            ["status"],
            """
            master

            chore/sync_to_docs
            |
            o-improve/refactor  PR #1 (github_user) rebase=no push=no
              |
              o-comments/add_docstrings *  PR #2 (github_user) rebase=no push=no
            """
        )

        # Check against closed pull request
        self.repo_sandbox.execute('git branch -D sphinx_export')
        expected_msg = ("Checking for open GitHub PRs... OK\n"
                        "Warn: Pull request #23 is already closed.\n"
                        "Pull request #23 checked out at local branch sphinx_export\n")

        assert_command(
            ['github', 'checkout-prs', '23'],
            expected_msg
        )
        assert_command(
            ["status"],
            """
            master

            chore/sync_to_docs
            |
            o-improve/refactor  PR #1 (github_user) rebase=no push=no
              |
              o-comments/add_docstrings  PR #2 (github_user) rebase=no push=no
                |
                o-sphinx_export *
            """
        )

    git_api_state_for_test_github_checkout_prs_from_fork_with_deleted_repo = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'feature/allow_checkout', 'repo': None},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '2',
                'html_url': 'www.github.com',
                'state': 'closed'
            },
            {
                'head': {'ref': 'bugfix/allow_checkout', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '3',
                'html_url': 'www.github.com',
                'state': 'open'}
        ]
    )

    def test_github_checkout_prs_from_fork_with_deleted_repo(self, mocker: Any) -> None:
        mocker.patch('git_machete.git_operations.GitContext.fetch_ref', mock_fetch_ref)
        # need to mock fetch_ref due to underlying `git fetch pull/head` calls
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_checkout_prs_from_fork_with_deleted_repo`
        # due to `git fetch` executed by `checkout-prs` subcommand.
        mocker.patch('urllib.request.urlopen', MockContextManager)
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_github_checkout_prs_from_fork_with_deleted_repo.new_request())

        (
            self.repo_sandbox.new_branch("root")
            .commit('initial master commit')
            .push()
            .new_branch('develop')
            .commit('initial develop commit')
            .push()
        )
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
        assert_command(
            ['github', 'checkout-prs', '2'],
            expected_msg
        )

        assert 'feature/allow_checkout' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete github checkout prs' performs 'git checkout' to "
             "the head branch of given pull request."
             )

    git_api_state_for_test_github_checkout_prs_of_current_user_and_other_users = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'chore/redundant_checks', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'restrict_access'},
                'number': '18',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'restrict_access', 'repo': mock_repository_info},
                'user': {'login': 'very_complex_user_token'},
                'base': {'ref': 'allow-ownership-link'},
                'number': '17',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'allow-ownership-link', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'bugfix/feature'},
                'number': '12',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'bugfix/feature', 'repo': mock_repository_info},
                'user': {'login': 'very_complex_user_token'},
                'base': {'ref': 'enhance/feature'},
                'number': '6',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'enhance/add_user', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '19',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'testing/add_user', 'repo': mock_repository_info},
                'user': {'login': 'very_complex_user_token'},
                'base': {'ref': 'bugfix/add_user'},
                'number': '22',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {'head': {'ref': 'chore/comments', 'repo': mock_repository_info},
             'user': {'login': 'github_user'},
             'base': {'ref': 'testing/add_user'},
             'number': '24',
             'html_url': 'www.github.com',
             'state': 'open'
             },
            {
                'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info},
                'user': {'login': 'very_complex_user_token'},
                'base': {'ref': 'hotfix/add-trigger'},
                'number': '3',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'bugfix/remove-n-option',
                         'repo': {'full_name': 'testing/checkout_prs', 'html_url': GitRepositorySandbox.second_remote_path}},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '5',
                'html_url': 'www.github.com',
                'state': 'closed'
            }
        ]
    )

    def test_github_checkout_prs_of_current_user_and_other_users(self, mocker: Any, tmp_path: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)
        # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_checkout_prs`
        # due to `git fetch` executed by `checkout-prs` subcommand.
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        mocker.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_for_domain_none)
        mocker.patch('urllib.request.Request',
                     self.git_api_state_for_test_github_checkout_prs_of_current_user_and_other_users.new_request())
        mocker.patch('urllib.request.urlopen', MockContextManager)
        mocker.patch('git_machete.github.GitHubClient.derive_current_user_login', mock_derive_current_user_login)

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
        assert_command(
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
            |   o-allow-ownership-link  PR #12 (github_user) rebase=no push=no
            |     |
            |     o-restrict_access  PR #17
            |       |
            |       o-chore/redundant_checks  PR #18 (github_user) rebase=no push=no
            |
            o-enhance/add_user  PR #19 (github_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  PR #22
              |
              o-chore/comments  PR #24 (github_user) rebase=no push=no
            """
        )

        # test that `checkout-prs` doesn't overwrite annotation qualifiers but overwrites annotation text
        launch_command('anno', '-b=allow-ownership-link', 'branch_annotation rebase=no')
        launch_command('github', 'checkout-prs', '--all')
        assert_command(
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
            |   o-allow-ownership-link  PR #12 (github_user) rebase=no
            |     |
            |     o-restrict_access  PR #17
            |       |
            |       o-chore/redundant_checks  PR #18 (github_user) rebase=no push=no
            |
            o-enhance/add_user  PR #19 (github_user) rebase=no push=no

            bugfix/add_user
            |
            o-testing/add_user  PR #22
              |
              o-chore/comments  PR #24 (github_user) rebase=no push=no
            """
        )

    git_api_state_for_test_github_sync = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'snickers', 'repo': mock_repository_info},
                'user': {'login': 'other_user'},
                'base': {'ref': 'master'},
                'number': '7',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ]
    )

    def test_github_sync(self, mocker: Any) -> None:
        mocker.patch('git_machete.client.MacheteClient.should_perform_interactive_slide_out', mock_should_perform_interactive_slide_out)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)
        mocker.patch('git_machete.client.MacheteClient.ask_if', mock_ask_if)
        mocker.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_for_domain_fake)
        mocker.patch('urllib.request.urlopen', MockContextManager)
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_github_sync.new_request())

        (
            self.repo_sandbox
                .new_branch('master')
                .commit()
                .push()
                .new_branch('bar')
                .commit()
                .new_branch('bar2')
                .commit()
                .check_out("master")
                .new_branch('foo')
                .commit()
                .push()
                .new_branch('foo2')
                .commit()
                .check_out("master")
                .new_branch('moo')
                .commit()
                .new_branch('moo2')
                .commit()
                .check_out("master")
                .new_branch('snickers')
                .push()
        )
        body: str = \
            """
            master
                bar
                    bar2
                foo
                    foo2
                moo
                    moo2
                snickers
            """
        rewrite_definition_file(body)

        (
            self.repo_sandbox
                .check_out("master")
                .new_branch('mars')
                .commit()
                .check_out("master")
        )
        launch_command('github', 'sync')

        expected_status_output = (
            """
            master
            |
            o-bar (untracked)
            |
            o-foo
            |
            o-moo (untracked)
            |
            o-snickers *  PR #7
            """
        )
        assert_command(['status'], expected_status_output)

        with pytest.raises(CalledProcessError):
            self.repo_sandbox.check_out("mars")

    def test_github_remote_patterns(self) -> None:
        organization = 'virtuslab'
        repository = 'repo_sandbox'
        urls = [f'https://tester@github.com/{organization}/{repository}',
                f'https://github.com/{organization}/{repository}',
                f'git@github.com:{organization}/{repository}',
                f'ssh://git@github.com/{organization}/{repository}']
        urls = urls + [url + '.git' for url in urls]

        for url in urls:
            remote_and_organization_and_repository = RemoteAndOrganizationAndRepository.from_url(domain=GitHubClient.DEFAULT_GITHUB_DOMAIN,
                                                                                                 url=url,
                                                                                                 remote='origin')
            assert remote_and_organization_and_repository is not None
            assert remote_and_organization_and_repository.organization == organization
            assert remote_and_organization_and_repository.repository == repository

    def test_github_api_pagination(self, mocker: Any, tmp_path: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)
        # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_checkout_prs`
        # due to `git fetch` executed by `checkout-prs` subcommand.
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        mocker.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_for_domain_none)
        mocker.patch('urllib.request.urlopen', MockContextManager)
        mocker.patch('git_machete.github.GitHubClient.derive_current_user_login', mock_derive_current_user_login)
        mocker.patch('urllib.request.Request', MockGitHubAPIState([]).new_request())
        mocker.patch('tests.test_github.MockGitHubAPIResponse.info', mock_info)
        mocker.patch('tests.test_github.MockGitHubAPIResponse.read', mock_read)

        global prs_per_page
        (
            self.repo_sandbox.new_branch("develop")
            .commit("first commit")
            .push()
        )
        for i in range(number_of_pages * prs_per_page):
            self.repo_sandbox.check_out('develop').new_branch(f'feature_{i}').commit().push()
        self.repo_sandbox.check_out('develop')
        body: str = 'develop *\n' + '\n'.join([f'feature_{i}'
                                               for i in range(number_of_pages * prs_per_page)]) + '\n'
        rewrite_definition_file(body)

        self.repo_sandbox.check_out('develop')
        for i in range(number_of_pages * prs_per_page):
            self.repo_sandbox.execute(f"git branch -D feature_{i}")
        body = 'develop *\n'
        rewrite_definition_file(body)

        launch_command('github', 'checkout-prs', '--all')
        launch_command('discover', '--checked-out-since=1 day ago')
        expected_status_output = 'develop *\n' + '\n'.join([f'|\no-feature_{i}  rebase=no push=no'
                                                            for i in range(number_of_pages * prs_per_page)]) + '\n'
        assert_command(['status'], expected_status_output)

    def test_github_enterprise_domain_fail(self, mocker: Any) -> None:
        mocker.patch('git_machete.client.MacheteClient.should_perform_interactive_slide_out', mock_should_perform_interactive_slide_out)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)
        mocker.patch('git_machete.client.MacheteClient.ask_if', mock_ask_if)
        mocker.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_for_domain_none)
        mocker.patch('urllib.request.urlopen', MockContextManagerRaise403)
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)

        github_enterprise_domain = 'git.example.org'
        self.repo_sandbox.set_git_config_key('machete.github.domain', github_enterprise_domain)

        expected_error_message = (
            "GitHub API returned `403` HTTP status with error message: `Forbidden`\n"
            "You might not have the required permissions for this repository.\n"
            "Provide a GitHub API token with `repo` access.\n"
            f"Visit `https://{github_enterprise_domain}/settings/tokens` to generate a new one.\n"
            "You can also use a different token provider, available providers can be found when running `git machete help github`.")

        with pytest.raises(MacheteException) as e:
            launch_command('github', 'checkout-prs', '--all')
        assert e.value.args[0] == expected_error_message, 'Verify that expected error message has appeared.'

    git_api_state_for_test_github_enterprise_domain = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'snickers', 'repo': mock_repository_info},
                'user': {'login': 'other_user'},
                'base': {'ref': 'develop'},
                'number': '7',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ]
    )

    def test_github_enterprise_domain(self, mocker: Any) -> None:
        mocker.patch('git_machete.client.MacheteClient.should_perform_interactive_slide_out', mock_should_perform_interactive_slide_out)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)
        mocker.patch('git_machete.client.MacheteClient.ask_if', mock_ask_if)
        mocker.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_for_domain_fake)
        mocker.patch('urllib.request.urlopen', MockContextManager)
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_github_enterprise_domain.new_request())
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)

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

    def test_github_token_retrieval_order(self, mocker: Any) -> None:
        mocker.patch('os.path.isfile', mock_is_file_false)
        mocker.patch('shutil.which', mock_shutil_which_gh(None))
        mocker.patch('urllib.request.urlopen', MockContextManager)
        mocker.patch('git_machete.github.github_remote_url_patterns', mock_github_remote_url_patterns)
        mocker.patch('_collections_abc.Mapping.get', mock_os_environ_get_none)
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_github_enterprise_domain.new_request())

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

    def test_get_token_from_env_var(self, mocker: Any) -> None:
        mocker.patch('_collections_abc.Mapping.get', mock_os_environ_get_github_token)

        github_token = GitHubToken.for_domain(domain=GitHubClient.DEFAULT_GITHUB_DOMAIN)
        assert github_token is not None
        assert github_token.provider == '`GITHUB_TOKEN` environment variable'
        assert github_token.value == 'github_token_from_env_var'

    def test_get_token_from_file_in_home_directory(self, mocker: Any) -> None:
        github_token_contents = ('ghp_mytoken_for_github_com\n'
                                 'ghp_myothertoken_for_git_example_org git.example.org\n'
                                 'ghp_yetanothertoken_for_git_example_com git.example.com')
        _mock_open = mock_open(read_data=github_token_contents)
        _mock_open.return_value.readlines.return_value = github_token_contents.split('\n')
        mocker.patch('builtins.open', _mock_open)
        mocker.patch('os.path.isfile', mock_is_file_true)

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

    def test_get_token_from_gh(self, mocker: Any) -> None:
        mocker.patch('os.path.isfile', mock_is_file_false)
        mocker.patch('_collections_abc.Mapping.get', mock_os_environ_get_none)
        mocker.patch('shutil.which', mock_shutil_which_gh('/path/to/gh'))
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

    def test_get_token_from_hub(self, mocker: Any) -> None:
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
        mocker.patch('os.path.isfile', mock_is_file_not_github_token)
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
                'user': {'login': 'github_user'},
                'base': {'ref': 'root'}, 'number': '15',
                'html_url': 'www.github.com', 'state': 'open'
            },
            {
                'head': {'ref': 'feature_1', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'feature_repo'}, 'number': '20',
                'html_url': 'www.github.com', 'state': 'open'
            }
        ]
    )

    def test_local_branch_name_different_than_tracking_branch_name(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        mocker.patch('urllib.request.Request',
                     self.git_api_state_for_test_local_branch_name_different_than_tracking_branch_name.new_request())
        mocker.patch('urllib.request.urlopen', MockContextManager)

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
          o-feature_1 *  PR #20 (github_user) rebase=no push=no
        """
        assert_command(
            ['status'],
            expected_result=expected_status_output
        )
