import io
import json
import os
import random
import re
import string
import subprocess
import sys
import textwrap
import time
from contextlib import redirect_stderr, redirect_stdout
from http import HTTPStatus
from tempfile import mkdtemp
from typing import Any, Dict, Iterable, List, Optional, Union
from urllib.error import HTTPError
from urllib.parse import ParseResult, parse_qs, urlparse

from git_machete import cli
from git_machete.git_operations import FullCommitHash, GitContext
from git_machete.utils import dim

git: GitContext = GitContext()


def popen(command: str) -> str:
    with os.popen(command) as process:
        return process.read().strip()


def get_current_commit_hash() -> FullCommitHash:
    """Returns hash of a commit of the current branch head."""
    return FullCommitHash.of(popen("git rev-parse HEAD"))


def mock_run_cmd(cmd: str, *args: str, **kwargs: Any) -> int:
    completed_process: subprocess.CompletedProcess[bytes] = subprocess.run(
        [cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    exit_code: int = completed_process.returncode

    if exit_code != 0:
        print(dim(f"<exit code: {exit_code}>\n"), file=sys.stderr)
    return completed_process.returncode


class GitRepositorySandbox:
    second_remote_path = mkdtemp()

    def __init__(self) -> None:
        self.remote_path = mkdtemp()
        self.local_path = mkdtemp()

    def execute(self, command: str) -> "GitRepositorySandbox":
        subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
        return self

    def new_repo(self, *args: str) -> "GitRepositorySandbox":
        os.chdir(args[0])
        opts = args[1:]
        self.execute(f"git init {' '.join(opts)}")
        return self

    def new_branch(self, branch_name: str) -> "GitRepositorySandbox":
        self.execute(f"git checkout -b {branch_name}")
        return self

    def new_root_branch(self, branch_name: str) -> "GitRepositorySandbox":
        self.execute(f"git checkout --orphan {branch_name}")
        return self

    def check_out(self, branch: str) -> "GitRepositorySandbox":
        self.execute(f"git checkout {branch}")
        return self

    def commit(self, message: str = "Some commit message.") -> "GitRepositorySandbox":
        f = "%s.txt" % "".join(random.choice(string.ascii_letters) for _ in range(20))
        self.execute(f"touch {f}")
        self.execute(f"git add {f}")
        self.execute(f'git commit -m "{message}"')
        return self

    def add_file_with_content_and_commit(self, file_name: str = 'file_name.txt', file_content: str = 'Some file content', message: str = "Some commit message.") -> "GitRepositorySandbox":
        self.execute(f"echo {file_content} > {file_name}")
        self.execute(f"git add {file_name}")
        self.execute(f'git commit -m "{message}"')
        return self

    def commit_amend(self, message: str) -> "GitRepositorySandbox":
        self.execute(f'git commit --amend -m "{message}"')
        return self

    def push(self) -> "GitRepositorySandbox":
        branch = popen("git symbolic-ref -q --short HEAD")
        self.execute(f"git push -u origin {branch}")
        return self

    def sleep(self, seconds: int) -> "GitRepositorySandbox":
        time.sleep(seconds)
        return self

    def reset_to(self, revision: str) -> "GitRepositorySandbox":
        self.execute(f'git reset --keep "{revision}"')
        return self

    def delete_branch(self, branch: str) -> "GitRepositorySandbox":
        self.execute(f'git branch -d "{branch}"')
        return self

    def add_remote(self, remote: str, url: str) -> "GitRepositorySandbox":
        self.execute(f'git remote add {remote} {url}')
        return self

    def remove_remote(self, remote: str) -> "GitRepositorySandbox":
        self.execute(f'git remote remove {remote}')
        return self

    def add_git_config_key(self, key: str, value: str) -> "GitRepositorySandbox":
        self.execute(f'git config {key} {value}')
        return self


class MockGitHubAPIState:
    def __init__(self, pulls: List[Dict[str, Any]], issues: List[Dict[str, Any]] = None) -> None:
        self.pulls: List[Dict[str, Any]] = pulls
        self.user: Dict[str, str] = {'login': 'other_user', 'type': 'User', 'company': 'VirtusLab'}  # login must be different from the one used in pull requests, otherwise pull request author will not be annotated
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


class MockGitHubAPIRequest:
    def __init__(self, github_api_state: MockGitHubAPIState) -> None:
        self.github_api_state: MockGitHubAPIState = github_api_state

    def __call__(self, url: str, headers: Dict[str, str] = None, data: Union[str, bytes, None] = None, method: str = '') -> "MockGitHubAPIResponse":
        self.parsed_url: ParseResult = urlparse(url, allow_fragments=True)
        self.parsed_query: Dict[str, List[str]] = parse_qs(self.parsed_url.query)
        self.json_data: Union[str, bytes] = data
        self.return_data: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
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
        pull_no: str = self.find_number(self.parsed_url.path, 'pulls')
        if not pull_no:
            if self.is_pull_created():
                return self.make_response_object(HTTPStatus.UNPROCESSABLE_ENTITY, {'message': 'Validation Failed', 'errors': [
                    {'message': f'A pull request already exists for test_repo:{json.loads(self.json_data)["head"]}.'}]})
            return self.create_pull_request()
        pull: Dict[str, Any] = self.github_api_state.get_pull(pull_no)
        return self.fill_pull_request_data(json.loads(self.json_data), pull)

    def create_pull_request(self) -> "MockGitHubAPIResponse":
        pull = {'number': self.get_next_free_number(self.github_api_state.pulls),
                'user': {'login': 'github_user'},
                'html_url': 'www.github.com',
                'state': 'open',
                'head': {'ref': "", 'repo': {'full_name': 'testing:checkout_prs', 'html_url': mkdtemp()}},
                'base': {'ref': ""}}
        return self.fill_pull_request_data(json.loads(self.json_data), pull)

    def fill_pull_request_data(self, data: Dict[str, Any], pull: Dict[str, Any]) -> "MockGitHubAPIResponse":
        index = self.get_index_or_none(pull, self.github_api_state.issues)
        for key in data.keys():
            if key in ('base', 'head'):
                pull[key]['ref'] = json.loads(self.json_data)[key]
            else:
                pull[key] = json.loads(self.json_data)[key]
        if index:
            self.github_api_state.pulls[index] = pull
        else:
            self.github_api_state.pulls.append(pull)
        return self.make_response_object(HTTPStatus.CREATED, pull)

    def update_issue(self) -> "MockGitHubAPIResponse":
        issue_no: str = self.find_number(self.parsed_url.path, 'issues')
        if not issue_no:
            return self.create_issue()
        issue: Dict[str, Any] = self.github_api_state.get_issue(issue_no)
        return self.fill_issue_data(json.loads(self.json_data), issue)

    def create_issue(self) -> "MockGitHubAPIResponse":
        issue = {'number': self.get_next_free_number(self.github_api_state.issues)}
        return self.fill_issue_data(json.loads(self.json_data), issue)

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
        deserialized_json_data = json.loads(self.json_data)
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

    def read(self, n: int = 1) -> bytes:
        return json.dumps(self.msg).encode()


class MockContextManager:
    def __init__(self, obj: MockGitHubAPIResponse) -> None:
        self.obj = obj

    def __enter__(self) -> MockGitHubAPIResponse:
        if self.obj.status_code == HTTPStatus.NOT_FOUND:
            raise HTTPError(None, 404, 'Not found', None, None)
        elif self.obj.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise MockHTTPError(None, 422, self.obj.response_data, None, None)
        return self.obj

    def __exit__(self, *args: Any) -> None:
        pass


def adapt(s: str) -> str:
    return textwrap.indent(textwrap.dedent(re.sub(r"\|\n", "| \n", s[1:])), "  ")


def launch_command(*args: str) -> str:
    with io.StringIO() as out:
        with redirect_stdout(out):
            with redirect_stderr(out):
                cli.launch(list(args))
                git.flush_caches()
        return out.getvalue()


def assert_command(cmds: Iterable[str], expected_result: str, strip_indentation: bool = True) -> None:
    assert launch_command(*cmds) == (adapt(expected_result) if strip_indentation else expected_result)


def rewrite_definition_file(new_body: str) -> None:
    definition_file_path = git.get_main_git_subpath("machete")
    with open(os.path.join(os.getcwd(), definition_file_path), 'w') as def_file:
        def_file.writelines(new_body)


def mock_run_cmd_and_forward_stdout(cmd: str, *args: str, **kwargs: Any) -> int:
    completed_process: subprocess.CompletedProcess[bytes] = subprocess.run(
        [cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, ** kwargs)
    print(completed_process.stdout.decode('utf-8'))
    exit_code: int = completed_process.returncode
    if exit_code != 0:
        print(dim(f"<exit code: {exit_code}>\n"), file=sys.stderr)
    return exit_code


def mock_ask_if(*args: str, **kwargs: Any) -> str:
    return 'y'


def mock_should_perform_interactive_slide_out(cmd: str) -> bool:
    return True


def mock_exit_script(status_code: Optional[int] = None, error: Optional[BaseException] = None) -> None:
    if error:
        raise error
    else:
        sys.exit(status_code)
