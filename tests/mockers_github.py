import contextlib
import json
from http import HTTPStatus
from subprocess import CompletedProcess
from typing import (Any, Callable, Dict, Iterator, List, NamedTuple, Optional,
                    Union)
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from git_machete.github import GitHubToken, RemoteAndOrganizationAndRepository

mock_repository_info: Dict[str, str] = {'full_name': 'testing/checkout_prs',
                                        'html_url': 'https://github.com/tester/repo_sandbox.git'}


def mock_github_token_for_domain_none(domain: str) -> None:
    return None


def mock_github_token_for_domain_fake(domain: str) -> GitHubToken:
    return GitHubToken(value='dummy_token', provider='dummy_provider')


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
        return json.dumps(self.response_data).encode()

    def info(self) -> Dict[str, Any]:
        return {"link": None}


PRS_PER_PAGE = 3
NUMBER_OF_PAGES = 3


class PaginatedMockGitHubAPIResponse:

    def __init__(self, page_number: int) -> None:
        self.page_number = page_number
        self.pulls = [{
            'head': {'ref': f'feature_{i}', 'repo': {'full_name': 'testing/checkout_prs',
                                                     'html_url': 'https://github.com/tester/repo_sandbox.git'}},
            'user': {'login': 'some_other_user'},
            'base': {'ref': 'develop'},
            'number': f'{i}',
            'html_url': 'www.github.com',
            'state': 'open'
        } for i in range(NUMBER_OF_PAGES * PRS_PER_PAGE)]

    def read(self) -> bytes:
        start = (self.page_number - 1) * PRS_PER_PAGE
        end = self.page_number * PRS_PER_PAGE
        return json.dumps(self.pulls[start:end]).encode()

    def info(self) -> Dict[str, Any]:
        if self.page_number < NUMBER_OF_PAGES:
            link = f'<https://api.github.com/repositories/1300192/pulls?page={self.page_number + 1}>; rel="next"'
        else:
            link = ''
        return {"link": link}


def mock_paginated_request_returning_page_number(url: str, **kwargs: Any) -> int:
    parsed_query: Dict[str, List[str]] = parse_qs(urlparse(url).query)
    page = parsed_query.get("page")
    return int(page[0]) if page else 1


@contextlib.contextmanager
def mock_urlopen_paginated_response(page_number: int) -> Iterator[PaginatedMockGitHubAPIResponse]:
    yield PaginatedMockGitHubAPIResponse(page_number)


class MockGitHubAPIState:
    def __init__(self, pulls: List[Dict[str, Any]]) -> None:
        self.__pulls: List[Dict[str, Any]] = [dict(pull) for pull in pulls]

    def get_request_provider(self) -> "MockGitHubAPIRequestProvider":
        return MockGitHubAPIRequestProvider(self)

    def get_pull_by_number(self, pull_no: str) -> Optional[Dict[str, Any]]:
        for pull in self.__pulls:
            if pull['number'] == pull_no:
                return pull
        return None

    def get_pull_by_head(self, head: str) -> Optional[Dict[str, Any]]:
        for pull in self.__pulls:
            if pull['head']['ref'] == head:
                return pull
        return None

    def get_pull_by_head_and_base(self, head: str, base: str) -> Optional[Dict[str, Any]]:
        for pull in self.__pulls:
            pull_head: str = pull['head']['ref']
            pull_base: str = pull['base']['ref']
            if (head, base) == (pull_head, pull_base):
                return pull
        return None

    def get_open_pulls(self) -> List[Dict[str, Any]]:
        return [pull for pull in self.__pulls if pull['state'] == 'open']

    def add_pull(self, pull: Dict[str, Any]) -> None:
        pull_numbers = [int(item['number']) for item in self.__pulls]
        pull['number'] = str(max(pull_numbers) + 1)
        self.__pulls.append(pull)


class MockGitHubAPIRequestProvider:
    def __init__(self, github_api_state: MockGitHubAPIState) -> None:
        self.github_api_state: MockGitHubAPIState = github_api_state

    def __call__(self, url: str, headers: Dict[str, str] = {},
                 data: Union[str, bytes, None] = None, method: str = '') -> "MockGitHubAPIRequestProvider.Request":
        parsed_url = urlparse(url)
        url_segments = parsed_url.path.split('/')

        return MockGitHubAPIRequestProvider.Request(
            github_api_state=self.github_api_state,
            method=method,
            hostname=parsed_url.hostname,  # type: ignore[arg-type]
            url_segments=[('pulls' if s == 'issues' else s) for s in url_segments],
            query_params=parse_qs(parsed_url.query),
            headers=headers,
            json_data=data and json.loads(data))  # type: ignore[arg-type]

    class Request(NamedTuple):
        github_api_state: MockGitHubAPIState
        method: str
        hostname: str
        url_segments: List[str]
        query_params: Dict[str, List[str]]
        headers: Dict[str, str]
        json_data: Dict[str, Any]


class MockHTTPError(HTTPError):
    from email.message import Message

    def __init__(self, url: str, code: int, msg: Any, hdrs: Message, fp: Any) -> None:
        super().__init__(url, code, msg, hdrs, fp)
        self.msg = msg

    def read(self, n: int = 1) -> bytes:  # noqa: F841
        return json.dumps(self.msg).encode()


@contextlib.contextmanager
def mock_urlopen(request: MockGitHubAPIRequestProvider.Request) -> Iterator[MockGitHubAPIResponse]:

    def handle_method() -> "MockGitHubAPIResponse":
        if request.method == "GET":
            return handle_get()
        elif request.method == "PATCH":
            return handle_patch()
        elif request.method == "POST":
            return handle_post()
        else:
            return make_response_object(HTTPStatus.METHOD_NOT_ALLOWED, [])

    def handle_get() -> "MockGitHubAPIResponse":
        if 'pulls' == request.url_segments[-1]:
            full_head_name: Optional[List[str]] = request.query_params.get('head')
            if full_head_name:
                head: str = full_head_name[0].split(':')[1]
                pr = request.github_api_state.get_pull_by_head(head)
                if pr:
                    return make_response_object(HTTPStatus.OK, [pr])
                raise error_404()
            else:
                return make_response_object(HTTPStatus.OK, request.github_api_state.get_open_pulls())
        elif 'pulls' in request.url_segments:
            number = request.url_segments[-1]
            pr = request.github_api_state.get_pull_by_number(number)
            if pr:
                return make_response_object(HTTPStatus.OK, pr)
            raise error_404()
        elif request.url_segments[-1] == 'user':
            return make_response_object(HTTPStatus.OK, {'login': 'github_user', 'type': 'User', 'company': 'VirtusLab'})
        else:
            raise error_404()

    def handle_patch() -> "MockGitHubAPIResponse":
        assert not request.query_params
        if 'pulls' in request.url_segments:
            return update_pull_request()
        else:
            raise error_404()

    def handle_post() -> "MockGitHubAPIResponse":
        assert not request.query_params
        if request.url_segments[-1] == 'pulls':
            head = request.json_data['head']
            base = request.json_data['base']
            if request.github_api_state.get_pull_by_head_and_base(head, base) is not None:
                raise error_422({'message': 'Validation Failed', 'errors': [
                    {'message': f'A pull request already exists for test_repo:{head}.'}]})
            return create_pull_request()
        elif 'pulls' in request.url_segments:
            pull_no = request.url_segments[-2]  # e.g. /repos/example-org/example-repo/pulls/5/requested_reviewers
            pull = request.github_api_state.get_pull_by_number(pull_no)
            assert pull is not None
            fill_pull_request_from_json_data(pull)
            return make_response_object(HTTPStatus.OK, pull)
        else:
            raise error_404()

    def update_pull_request() -> "MockGitHubAPIResponse":
        pull_no = request.url_segments[-1]
        pull = request.github_api_state.get_pull_by_number(pull_no)
        assert pull is not None
        fill_pull_request_from_json_data(pull)
        return make_response_object(HTTPStatus.OK, pull)

    def create_pull_request() -> "MockGitHubAPIResponse":
        pull = {'user': {'login': 'some_other_user'},
                'html_url': 'www.github.com',
                'state': 'open',
                'head': {'ref': "", 'repo': {'full_name': 'testing:checkout_prs', 'html_url': 'https:/example.org/pull/1234'}},
                'base': {'ref': ""}}
        fill_pull_request_from_json_data(pull)
        request.github_api_state.add_pull(pull)
        return make_response_object(HTTPStatus.CREATED, pull)

    def fill_pull_request_from_json_data(pull: Dict[str, Any]) -> None:
        for key in request.json_data.keys():
            value = request.json_data[key]
            if key in ('base', 'head'):
                pull[key]['ref'] = value
            else:
                pull[key] = value

    def make_response_object(status_code: int,
                             response_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> "MockGitHubAPIResponse":
        return MockGitHubAPIResponse(status_code, response_data)

    def error_404() -> HTTPError:
        return HTTPError(request.hostname, 404, 'Not found', None, None)  # type: ignore[arg-type]

    def error_422(response_data: Any) -> MockHTTPError:
        return MockHTTPError(request.hostname, 422, response_data, None, None)  # type: ignore[arg-type]

    if request.hostname == "403.example.org":
        raise HTTPError("http://example.org", 403, 'Forbidden', None, None)  # type: ignore[arg-type]

    yield handle_method()
