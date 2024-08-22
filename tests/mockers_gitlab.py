import json
import re
import ssl
import urllib
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
        'title': 'Draft: MR title' if draft else 'MR title',
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
    def __init__(self, projects: Dict[int, Dict[str, Any]], *mrs: Dict[str, Any]) -> None:
        self.projects: Dict[int, Dict[str, Any]] = projects
        self.__mrs: List[Dict[str, Any]] = [dict(mr) for mr in mrs]

    @staticmethod
    def with_mrs(*mrs: Dict[str, Any]) -> "MockGitLabAPIState":
        projects = {
            1: {'id': 1, 'namespace': {'full_path': 'tester/tester/repo_sandbox'}, 'name': 'repo_sandbox',
                'http_url_to_repo': 'https://gitlab.com/tester/tester/repo_sandbox.git'},
            2: {'id': 2, 'namespace': {'full_path': 'example-org/example-repo'}, 'name': 'example-repo',
                'http_url_to_repo': 'https://gitlab.com/example-org/example-repo.git'},
            3: {'id': 3, 'namespace': {'full_path': 'example-org/example-repo-1'}, 'name': 'example-repo-1',
                'http_url_to_repo': 'https://gitlab.com/example-org/example-repo-1.git'},
            4: {'id': 4, 'namespace': {'full_path': 'example-org/example-repo-2'}, 'name': 'example-repo-2',
                'http_url_to_repo': 'https://gitlab.com/example-org/example-repo-2.git'},
        }
        return MockGitLabAPIState(projects, *mrs)

    def get_mr_by_number(self, mr_number: int) -> Optional[Dict[str, Any]]:
        for mr in self.__mrs:
            if mr['iid'] == str(mr_number):
                return mr
        return None

    def get_open_mrs_by_head(self, head: str) -> List[Dict[str, Any]]:
        return [mr for mr in self.get_open_mrs() if mr['source_branch'] == head]

    def get_open_mr_by_head_and_base(self, head: str, base: str) -> Optional[Dict[str, Any]]:
        for mr in self.get_open_mrs():
            mr_head: str = mr['source_branch']
            mr_base: str = mr['target_branch']
            if (head, base) == (mr_head, mr_base):
                return mr
        return None

    def get_open_mrs(self) -> List[Dict[str, Any]]:
        return [mr for mr in self.__mrs if mr['state'] == 'open']

    def add_mr(self, mr: Dict[str, Any]) -> None:
        mr_numbers = [int(item['iid']) for item in self.__mrs]
        mr['iid'] = str(max(mr_numbers or [0]) + 1)
        self.__mrs.append(mr)


# Not including [MockGitLabAPIResponse] type argument to maintain compatibility with Python <= 3.8
def mock_urlopen(gitlab_api_state: MockGitLabAPIState,
                 _context: Optional[ssl.SSLContext] = None) -> Callable[[Request], AbstractContextManager]:  # type: ignore[type-arg]
    @contextmanager
    def inner(request: Request, **_kwargs: Any) -> Iterator[MockAPIResponse]:
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
        elif url_path_matches('/projects/*'):
            repo_name = urllib.parse.unquote(url_segments[-1])
            for project in gitlab_api_state.projects.values():
                if project['namespace']['full_path'] == repo_name:
                    return MockAPIResponse(HTTPStatus.OK, project)
            raise error_404()
        elif url_path_matches('/projects/*/merge_requests'):
            head: Optional[str] = query_params.get('source_branch')
            if head:
                mrs = gitlab_api_state.get_open_mrs_by_head(head)
                # If no matching MRs are found, the real GitLab returns 200 OK with an empty JSON array - not 404.
                return MockAPIResponse(HTTPStatus.OK, mrs)
            else:
                mrs = gitlab_api_state.get_open_mrs()
                page_str = query_params.get('page')
                page = int(page_str) if page_str else 1
                per_page_str = query_params.get('per_page')
                per_page = int(per_page_str) if per_page_str else len(mrs)
                start = (page - 1) * per_page
                end = page * per_page
                if end < len(mrs):
                    headers = {'link': f'<{url_with_query_params(page=page + 1)}>; rel="next"'}
                elif page == 1:  # we're at the first page, and there are no more pages
                    headers = {}
                else:  # we're at the final page, and there were some pages before
                    headers = {'link': f'<{url_with_query_params(page=1)}>; rel="first"'}
                return MockAPIResponse(HTTPStatus.OK, response_data=mrs[start:end], headers=headers)
        elif url_path_matches('/projects/*/merge_requests/[0-9]+'):
            mr_number = int(url_segments[-1])
            mr = gitlab_api_state.get_mr_by_number(mr_number)
            if mr:
                return MockAPIResponse(HTTPStatus.OK, mr)
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
            return update_merge_request()
        else:
            raise error_404()

    def handle_post() -> "MockAPIResponse":
        assert not query_params
        if url_path_matches("/projects/*/merge_requests"):
            head = json_data['source_branch']
            base = json_data['target_branch']
            existing_mr = gitlab_api_state.get_open_mr_by_head_and_base(head, base)
            if existing_mr is not None:
                message = f"Another open merge request already exists for this source branch: !{existing_mr['iid']}"
                raise error_409({'message': [message]})
            return create_merge_request()
        else:
            raise error_404()

    def update_merge_request() -> "MockAPIResponse":
        mr_number = int(url_segments[-1])
        mr = gitlab_api_state.get_mr_by_number(mr_number)
        assert mr is not None
        fill_merge_request_from_json_data(mr)
        return MockAPIResponse(HTTPStatus.OK, mr)

    def create_merge_request() -> "MockAPIResponse":
        mr = {'author': {'username': 'some_other_user'},
              'web_url': 'www.gitlab.com',
              'description': '# Summary',
              'state': 'open',
              'source_branch': "<TO-BE-FILLED>",
              'source_project_id': 1,
              'target_branch': "<TO-BE-FILLED>"}
        fill_merge_request_from_json_data(mr)
        gitlab_api_state.add_mr(mr)
        return MockAPIResponse(HTTPStatus.CREATED, mr)

    def fill_merge_request_from_json_data(mr: Dict[str, Any]) -> None:
        for key in json_data.keys():
            mr[key] = json_data[key]
        mr['draft'] = mr['title'][:5] == 'Draft'

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
