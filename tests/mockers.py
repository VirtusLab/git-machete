import io
import json
import os
import re
import subprocess
import sys
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from http import HTTPStatus
from tempfile import mkdtemp
from typing import Any, Dict, Iterable, List, Optional, Union
from urllib.error import HTTPError
from urllib.parse import ParseResult, parse_qs, urlparse

from git_machete import cli, utils
from git_machete.git_operations import FullCommitHash
from git_machete.utils import dim
from tests.base_test import git, popen

"""
Usage: mockers.py

This module provides mocking classes and functions used to create pytest based tests.

Tips on when and why to use mocking functions:
1. `mock_run_cmd()`
    * used to mock `utils.run_cmd` in order to redirect command's stdout and stderr out of sys.stdout
    * used to hide git command outputs so it's easier to assert correctness of the `git machete` command output
    * used in tests of these git machete commands:
        `add`, `advance`, `clean`, `github`, `go`, `help`, 'show`, `slide-out`, `traverse`, `update`

2. `mock_run_cmd_and_forward_stdout()`
    * used to mock `utils.run_cmd` in order to capture command's stdout and stderr
    * used to capture git command outputs that would otherwise be lost, once the process that launched them finishes
    * used in tests of these git machete commands: `diff`, `log`, `slide-out`
"""


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


class MockContextManager:
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


def launch_command(*args: str) -> str:
    with io.StringIO() as out:
        with redirect_stdout(out):
            with redirect_stderr(out):
                utils.debug_mode = False
                utils.verbose_mode = False
                cli.launch(list(args))
                git.flush_caches()
        return out.getvalue()


def assert_command(cmds: Iterable[str], expected_result: str) -> None:
    if expected_result.startswith("\n"):
        # removeprefix is only available since Python 3.9
        expected_result = expected_result[1:]
    expected_result = textwrap.dedent(expected_result)
    actual_result = textwrap.dedent(launch_command(*cmds))
    assert actual_result == expected_result


def rewrite_definition_file(new_body: str, dedent: bool = True) -> None:
    if dedent:
        new_body = textwrap.dedent(new_body)
    definition_file_path = git.get_main_git_subpath("machete")
    with open(os.path.join(os.getcwd(), definition_file_path), 'w') as def_file:
        def_file.writelines(new_body)


def get_current_commit_hash() -> FullCommitHash:
    """Returns hash of the commit of the current branch head."""
    return get_commit_hash("HEAD")


def get_commit_hash(revision: str) -> FullCommitHash:
    """Returns hash of the commit pointed by the given revision."""
    return FullCommitHash.of(popen(f"git rev-parse {revision}"))


def mock_run_cmd(cmd: str, *args: str, **kwargs: Any) -> int:
    """Execute command in the new subprocess but redirect the stdout and stderr together to the PIPE's stdout"""
    completed_process: subprocess.CompletedProcess[bytes] = subprocess.run(
        [cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    exit_code: int = completed_process.returncode

    if exit_code != 0:
        print(dim(f"<exit code: {exit_code}>\n"), file=sys.stderr)
    return completed_process.returncode


def mock_run_cmd_and_forward_stdout(cmd: str, *args: str, **kwargs: Any) -> int:
    """Execute command in the new subprocess but capture together process's stdout and stderr and load it into sys.stdout via
    `print(completed_process.stdout.decode('utf-8'))`. This sys.stdout is later being redirected via the `redirect_stdout` in
    `launch_command()` and gets returned by this function. Below is shown the chain of function calls that presents this mechanism:
    1. `launch_command()` gets executed in the test case and evokes `cli.launch()`.
    2. `cli.launch()` executes `utils.run_cmd()` but `utils.run_cmd()` is being mocked by `mock_run_cmd_and_forward_stdout()`
    so the command's stdout and stderr is loaded into sys.stdout.
    3. After command execution we go back through `cli.launch()`(2) to `launch_command()`(1) which redirects just updated sys.stdout
    into variable and returns it.
    """
    completed_process: subprocess.CompletedProcess[bytes] = subprocess.run(
        [cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    print(completed_process.stdout.decode('utf-8'))
    exit_code: int = completed_process.returncode
    if exit_code != 0:
        print(dim(f"<exit code: {exit_code}>\n"), file=sys.stderr)
    return exit_code


def mock_ask_if(*args: str, **kwargs: Any) -> str:
    return 'y'


def mock_should_perform_interactive_slide_out(cmd: str) -> bool:
    return True


def mock_exit_script(status_code: int, error: Optional[BaseException] = None) -> None:
    if error:
        raise error
    else:
        sys.exit(status_code)


def mock_exit_script_no_exit(status_code: int, error: Optional[BaseException] = None) -> None:
    return
