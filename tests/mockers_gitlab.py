import json
import re
from contextlib import AbstractContextManager, contextmanager
from http import HTTPStatus
from typing import Any, Callable, Dict, Iterator, List, Optional
from urllib.error import HTTPError
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse
from urllib.request import Request

from git_machete.gitlab import GitLabToken
from tests.mockers_code_hosting import MockAPIResponse, MockHTTPError

mock_user_ids = {
    "gitlab_user": 123456,
    "foo": 123,
    "bar": 456,
}


def mock_mr_json(head: str, base: str, number: int,
                 repo_id: int = 1,
                 user: str = 'some_other_user',
                 html_url: str = 'www.gitlab.com',
                 body: Optional[str] = '# Summary',
                 state: str = 'open',
                 draft: bool = False
                 ) -> Dict[str, Any]:
    return {
        'title': 'Draft: PR title' if draft else 'PR title',
        'source_branch': head,
        'source_project_id': repo_id,
        'target_branch': base,
        'author': {'username': user},
        'iid': str(number),
        'web_url': html_url,
        'description': body,
        'state': state,
        'draft': draft
    }


def mock_gitlab_token_for_domain_none(_domain: str) -> None:
    return None


def mock_gitlab_token_for_domain_fake(_domain: str) -> GitLabToken:
    return GitLabToken(value='glpat-dummy-token', provider='dummy_provider')


class MockGitLabAPIState:
    def __init__(self, projects: Dict[int, Dict[str, Any]], *pulls: Dict[str, Any]) -> None:
        self.projects: Dict[int, Dict[str, Any]] = projects
        self.__pulls: List[Dict[str, Any]] = [dict(pull) for pull in pulls]

    @staticmethod
    def with_mrs(*mrs: Dict[str, Any]) -> "MockGitLabAPIState":
        projects = {
            1: {'namespace': {'full_path': 'tester/tester'}, 'name': 'repo_sandbox',
                'http_url_to_repo': 'https://gitlab.com/tester/tester/repo_sandbox.git'},
            2: {'namespace': {'full_path': 'example-org'}, 'name': 'example-repo',
                'http_url_to_repo': 'https://github.com/example-org/example-repo.git'},
        }
        return MockGitLabAPIState(projects, *mrs)

    def get_pull_by_number(self, pull_no: int) -> Optional[Dict[str, Any]]:
        for pull in self.__pulls:
            if pull['iid'] == str(pull_no):
                return pull
        return None

    def get_open_pulls_by_head(self, head: str) -> List[Dict[str, Any]]:
        return [pull for pull in self.get_open_pulls() if pull['source_branch'] == head]

    def get_open_pull_by_head_and_base(self, head: str, base: str) -> Optional[Dict[str, Any]]:
        for pull in self.get_open_pulls():
            pull_head: str = pull['source_branch']
            pull_base: str = pull['target_branch']
            if (head, base) == (pull_head, pull_base):
                return pull
        return None

    def get_open_pulls(self) -> List[Dict[str, Any]]:
        return [pull for pull in self.__pulls if pull['state'] == 'open']

    def add_pull(self, pull: Dict[str, Any]) -> None:
        pull_numbers = [int(item['iid']) for item in self.__pulls]
        pull['iid'] = str(max(pull_numbers or [0]) + 1)
        self.__pulls.append(pull)


# Not including [MockGitLabAPIResponse] type argument to maintain compatibility with Python <= 3.8
def mock_urlopen(gitlab_api_state: MockGitLabAPIState) -> Callable[[Request], AbstractContextManager]:  # type: ignore[type-arg]
    @contextmanager
    def inner(request: Request) -> Iterator[MockAPIResponse]:
        yield __mock_urlopen_impl(gitlab_api_state, request)
    return inner


def __mock_urlopen_impl(gitlab_api_state: MockGitLabAPIState, request: Request) -> MockAPIResponse:
    parsed_url: ParseResult = urlparse(request.full_url)
    url_segments: List[str] = [s for s in parsed_url.path.split('/') if s]
    query_params: Dict[str, str] = {k: v[0] for k, v in parse_qs(parsed_url.query).items()}
    json_data: Dict[str, Any] = request.data and json.loads(request.data)  # type: ignore

    def handle_method() -> "MockAPIResponse":
        if request.method == "GET":
            return handle_get()
        elif request.method == "PUT":
            return handle_put()
        elif request.method == "POST":
            return handle_post()
        else:
            return MockAPIResponse(HTTPStatus.METHOD_NOT_ALLOWED, [])

    def url_path_matches(pattern: str) -> bool:
        regex = pattern.replace('*', '[^/]+')
        return re.match('^(/api/v4)?' + regex + '$', parsed_url.path) is not None

    def url_with_query_params(**new_params: Any) -> str:
        new_query_string: str = urlencode({**query_params, **new_params})
        return parsed_url._replace(query=new_query_string).geturl()

    def handle_get() -> "MockAPIResponse":
        if url_path_matches('/projects/[0-9]+'):
            repo_no = int(url_segments[-1])
            if repo_no in gitlab_api_state.projects:
                return MockAPIResponse(HTTPStatus.OK, gitlab_api_state.projects[repo_no])
            raise error_404()
        elif url_path_matches('/projects/*/merge_requests'):
            head: Optional[str] = query_params.get('source_branch')
            if head:
                prs = gitlab_api_state.get_open_pulls_by_head(head)
                # If no matching PRs are found, the real GitLab returns 200 OK with an empty JSON array - not 404.
                return MockAPIResponse(HTTPStatus.OK, prs)
            else:
                pulls = gitlab_api_state.get_open_pulls()
                page_str = query_params.get('page')
                page = int(page_str) if page_str else 1
                per_page_str = query_params.get('per_page')
                per_page = int(per_page_str) if per_page_str else len(pulls)
                start = (page - 1) * per_page
                end = page * per_page
                if end < len(pulls):
                    headers = {'link': f'<{url_with_query_params(page=page + 1)}>; rel="next"'}
                elif page == 1:  # we're at the first page, and there are no more pages
                    headers = {}
                else:  # we're at the final page, and there were some pages before
                    headers = {'link': f'<{url_with_query_params(page=1)}>; rel="first"'}
                return MockAPIResponse(HTTPStatus.OK, response_data=pulls[start:end], headers=headers)
        elif url_path_matches('/projects/*/merge_requests/[0-9]+'):
            pull_no = int(url_segments[-1])
            pull = gitlab_api_state.get_pull_by_number(pull_no)
            if pull:
                return MockAPIResponse(HTTPStatus.OK, pull)
            raise error_404()
        elif url_path_matches('/user'):
            return MockAPIResponse(HTTPStatus.OK, {'username': 'gitlab_user'})
        elif url_path_matches('/users'):
            username = query_params["username"]
            if username in mock_user_ids:
                result = [{'id': mock_user_ids[username]}]
            else:
                result = []
            return MockAPIResponse(HTTPStatus.OK, result)
        else:
            raise error_404()

    def handle_put() -> "MockAPIResponse":
        assert not query_params
        if url_path_matches("/projects/*/merge_requests/[0-9]+"):
            return update_pull_request()
        else:
            raise error_404()

    def handle_post() -> "MockAPIResponse":
        assert not query_params
        if url_path_matches("/projects/*/merge_requests"):
            head = json_data['source_branch']
            base = json_data['target_branch']
            existing_pr = gitlab_api_state.get_open_pull_by_head_and_base(head, base)
            if existing_pr is not None:
                message = f"Another open merge request already exists for this source branch: !{existing_pr['iid']}"
                raise error_409({'message': [message]})
            return create_pull_request()
        else:
            raise error_404()

    def update_pull_request() -> "MockAPIResponse":
        pull_no = int(url_segments[-1])
        pull = gitlab_api_state.get_pull_by_number(pull_no)
        assert pull is not None
        fill_pull_request_from_json_data(pull)
        return MockAPIResponse(HTTPStatus.OK, pull)

    def create_pull_request() -> "MockAPIResponse":
        pull = {'author': {'username': 'some_other_user'},
                'web_url': 'www.gitlab.com',
                'description': '# Summary',
                'state': 'open',
                'source_branch': "<TO-BE-FILLED>",
                'source_project_id': 1,
                'target_branch': "<TO-BE-FILLED>"}
        fill_pull_request_from_json_data(pull)
        gitlab_api_state.add_pull(pull)
        return MockAPIResponse(HTTPStatus.CREATED, pull)

    def fill_pull_request_from_json_data(pull: Dict[str, Any]) -> None:
        for key in json_data.keys():
            pull[key] = json_data[key]
        pull['draft'] = pull['title'][:5] == 'Draft'

    def error_404() -> HTTPError:
        return HTTPError(parsed_url.hostname, 404, 'Not found', None, None)  # type: ignore[arg-type]

    def error_405(response_data: Any) -> MockHTTPError:
        return MockHTTPError(parsed_url.hostname, 405, response_data, None, None)  # type: ignore[arg-type]

    def error_409(response_data: Any) -> MockHTTPError:
        return MockHTTPError(parsed_url.hostname, 409, response_data, None, None)  # type: ignore[arg-type]

    if parsed_url.hostname == "403.example.org":
        raise HTTPError("http://example.org", 403, 'Forbidden', None, None)  # type: ignore[arg-type]

    if request.method != "GET" and url_segments[2:4] == ["projects", "example-org%2Fold-example-repo"]:
        raise error_405({"message": "Non GET methods are not allowed for moved projects"})

    return handle_method()
