import contextlib
import json
import re
from http import HTTPStatus
from subprocess import CompletedProcess
from tempfile import mkdtemp
from typing import Any, Callable, Dict, Iterator, List, Optional, Type, Union
from urllib.error import HTTPError
from urllib.parse import ParseResult, parse_qs, urlparse

from git_machete.github import GitHubToken, RemoteAndOrganizationAndRepository

mock_repository_info: Dict[str, str] = {'full_name': 'testing/checkout_prs',
                                        'html_url': 'https://github.com/tester/repo_sandbox.git'}


def mock_github_token_for_domain_none(domain: str) -> None:
    return None


def mock_github_token_for_domain_fake(domain: str) -> GitHubToken:
    return GitHubToken(value='dummy_token',
                       provider='dummy_provider')


def mock_from_url(domain: str, url: str, remote: str) -> "RemoteAndOrganizationAndRepository":
    return RemoteAndOrganizationAndRepository(remote, "example-org", "example-repo")


def mock_shutil_which(path: Optional[str]) -> Callable[[Any], Optional[str]]:
    return lambda cmd: path


def mock_subprocess_run(returncode: int, stdout: str = '', stderr: str = ''):  # type: ignore[no-untyped-def]
    return lambda *args, **kwargs: CompletedProcess(args, returncode, bytes(stdout, 'utf-8'), bytes(stderr, 'utf-8'))


class MockGitHubAPIResponse:
    def __init__(self, status_code: int, response_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> None:
        self.response_data = response_data
        self.status_code = status_code

    def read(self) -> bytes:
        raise NotImplementedError

    def info(self) -> Dict[str, Any]:
        raise NotImplementedError


class SimpleMockGitHubAPIResponse(MockGitHubAPIResponse):
    def __init__(self, status_code: int, response_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> None:
        super().__init__(status_code, response_data)

    def read(self) -> bytes:
        return json.dumps(self.response_data).encode()

    def info(self) -> Dict[str, Any]:
        return {"link": None}


PRS_PER_PAGE = 3
NUMBER_OF_PAGES = 3


class PaginatedMockGitHubAPIResponse(MockGitHubAPIResponse):

    # Note that this mock implementation currently only works if it's used by a single test only,
    # due to the reliance on a static class property.
    page_number: int = 1

    def __init__(self, status_code: int, response_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> None:
        super().__init__(status_code, response_data)

    def read(self) -> bytes:
        response_data = [
            {
                'head': {'ref': f'feature_{i}', 'repo': {'full_name': 'testing/checkout_prs',
                                                         'html_url': 'https://github.com/tester/repo_sandbox.git'}},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'develop'},
                'number': f'{i}',
                'html_url': 'www.github.com',
                'state': 'open'
            } for i in range((type(self).page_number - 1) * PRS_PER_PAGE, type(self).page_number * PRS_PER_PAGE)]
        return json.dumps(response_data).encode()

    def info(self) -> Dict[str, Any]:
        if type(self).page_number < NUMBER_OF_PAGES:
            link = f'<https://api.github.com/repositories/1300192/pulls?page={type(self).page_number + 1}>; rel="next"'
        else:
            link = ''
        type(self).page_number += 1
        return {"link": link}


class MockGitHubAPIState:
    def __init__(self, pulls: List[Dict[str, Any]], issues: Optional[List[Dict[str, Any]]] = None) -> None:
        self.pulls: List[Dict[str, Any]] = [dict(pull) for pull in pulls]
        self.user: Dict[str, str] = {'login': 'github_user', 'type': 'User', 'company': 'VirtusLab'}
        # login must be different from the one used in pull requests, otherwise pull request author will not be annotated
        self.issues: List[Dict[str, Any]] = list(issues) if issues else []

    def new_request(self, response_class: Type[MockGitHubAPIResponse] = SimpleMockGitHubAPIResponse) -> "MockGitHubAPIRequest":
        return MockGitHubAPIRequest(self, response_class)

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


class MockGitHubAPIRequest:
    def __init__(self, github_api_state: MockGitHubAPIState, response_class: Type[MockGitHubAPIResponse]) -> None:
        self.github_api_state: MockGitHubAPIState = github_api_state
        self.response_class: Type[MockGitHubAPIResponse] = response_class

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
                'user': {'login': 'some_other_user'},
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

    def make_response_object(self, status_code: int,
                             response_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> "MockGitHubAPIResponse":
        return self.response_class(status_code, response_data)

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


@contextlib.contextmanager
def mock_urlopen(obj: SimpleMockGitHubAPIResponse) -> Iterator[SimpleMockGitHubAPIResponse]:
    if obj.status_code == HTTPStatus.NOT_FOUND:
        raise HTTPError("http://example.org", 404, 'Not found', None, None)  # type: ignore[arg-type]
    elif obj.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
        raise MockHTTPError("http://example.org", 422, obj.response_data, None, None)  # type: ignore[arg-type]
    yield obj


@contextlib.contextmanager
def mock_urlopen_raising_403(obj: SimpleMockGitHubAPIResponse) -> Iterator[SimpleMockGitHubAPIResponse]:
    raise HTTPError("http://example.org", 403, 'Forbidden', None, None)  # type: ignore[arg-type]
