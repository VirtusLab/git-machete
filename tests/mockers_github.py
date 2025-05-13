import json
import re
import ssl
from contextlib import AbstractContextManager, contextmanager
from http import HTTPStatus
from typing import Any, Callable, Dict, Iterator, List, Optional
from urllib.error import HTTPError
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse
from urllib.request import Request

from git_machete.github import GitHubToken
from tests.mockers_code_hosting import MockAPIResponse, MockHTTPError


def mock_pr_json(head: str, base: str, number: int,
                 repo_id: int = 1,
                 user: str = 'some_other_user',
                 html_url: str = 'www.github.com',
                 body: Optional[str] = '# Summary',
                 state: str = 'open',
                 draft: bool = False
                 ) -> Dict[str, Any]:
    return {
        'head': {'ref': head, 'repo': {'id': repo_id}},
        'user': {'login': user},
        'base': {'ref': base},
        'number': str(number),
        'html_url': html_url,
        'title': 'PR title',
        'body': body,
        'state': state,
        'draft': draft
    }


def mock_github_token_for_domain_none(_domain: str) -> None:
    return None


def mock_github_token_for_domain_fake(_domain: str) -> GitHubToken:
    return GitHubToken(value='ghp_dummy_token', provider='dummy_provider')


class MockGitHubAPIState:
    def __init__(self, repositories: Dict[int, Dict[str, Any]], *pulls: Dict[str, Any]) -> None:
        self.repositories: Dict[int, Dict[str, Any]] = repositories
        self.__pulls: List[Dict[str, Any]] = [dict(pull) for pull in pulls]

    @staticmethod
    def with_prs(*pulls: Dict[str, Any]) -> "MockGitHubAPIState":
        repositories = {
            1: {'owner': {'login': 'tester'}, 'name': 'repo_sandbox', 'clone_url': 'https://github.com/tester/repo_sandbox.git'},
            2: {'owner': {'login': 'example-org'}, 'name': 'example-repo', 'clone_url': 'https://github.com/example-org/example-repo.git'},
        }
        return MockGitHubAPIState(repositories, *pulls)

    def get_pull_by_number(self, pull_no: int) -> Optional[Dict[str, Any]]:
        for pull in self.__pulls:
            if pull['number'] == str(pull_no):
                return pull
        return None

    def get_open_pulls_by_head(self, head: str) -> List[Dict[str, Any]]:
        return [pull for pull in self.get_open_pulls() if pull['head']['ref'] == head]

    def get_open_pull_by_head_and_base(self, head: str, base: str) -> Optional[Dict[str, Any]]:
        for pull in self.get_open_pulls():
            pull_head: str = pull['head']['ref']
            pull_base: str = pull['base']['ref']
            if (head, base) == (pull_head, pull_base):
                return pull
        return None

    def get_open_pulls(self) -> List[Dict[str, Any]]:
        return [pull for pull in self.__pulls if pull['state'] == 'open']

    def add_pull(self, pull: Dict[str, Any]) -> None:
        pull_numbers = [int(item['number']) for item in self.__pulls]
        pull['number'] = str(max(pull_numbers or [0]) + 1)
        self.__pulls.append(pull)


# Not including [MockAPIResponse] type argument to maintain compatibility with Python <= 3.8
def mock_urlopen(github_api_state: MockGitHubAPIState,
                 _context: Optional[ssl.SSLContext] = None) -> Callable[[Request], AbstractContextManager]:  # type: ignore[type-arg]
    @contextmanager
    def inner(request: Request, **_kwargs: Any) -> Iterator[MockAPIResponse]:
        yield __mock_urlopen_impl(github_api_state, request)
    return inner


def __mock_urlopen_impl(github_api_state: MockGitHubAPIState, request: Request) -> MockAPIResponse:
    parsed_url: ParseResult = urlparse(request.full_url)
    url_segments: List[str] = [s for s in parsed_url.path.split('/') if s]
    query_params: Dict[str, str] = {k: v[0] for k, v in parse_qs(parsed_url.query).items()}
    json_data: Dict[str, Any] = request.data and json.loads(request.data)  # type: ignore

    def handle_method() -> "MockAPIResponse":
        if request.method == "GET":
            return handle_get()
        elif request.method == "PATCH":
            return handle_patch()
        elif request.method == "POST":
            return handle_post()
        else:
            return MockAPIResponse(HTTPStatus.METHOD_NOT_ALLOWED, [])

    def url_path_matches(pattern: str) -> bool:
        regex = pattern.replace('*', '[^/]+')
        return re.match('^(/api/v3)?' + regex + '$', parsed_url.path) is not None

    def url_with_query_params(**new_params: Any) -> str:
        new_query_string: str = urlencode({**query_params, **new_params})
        return parsed_url._replace(query=new_query_string).geturl()

    def handle_get() -> "MockAPIResponse":
        if url_path_matches('/repositories/[0-9]+'):
            repo_no = int(url_segments[-1])
            if repo_no in github_api_state.repositories:
                return MockAPIResponse(HTTPStatus.OK, github_api_state.repositories[repo_no])
            raise error_404()
        elif url_path_matches('/repos/*/*/pulls'):
            full_head_name: Optional[str] = query_params.get('head')
            if full_head_name:
                head: str = full_head_name.split(':')[1]
                prs = github_api_state.get_open_pulls_by_head(head)
                # If no matching PRs are found, the real GitHub returns 200 OK with an empty JSON array - not 404.
                return MockAPIResponse(HTTPStatus.OK, prs)
            else:
                pulls = github_api_state.get_open_pulls()
                page_str = query_params.get('page')
                page = int(page_str) if page_str else 1
                per_page = int(query_params['per_page'])
                start = (page - 1) * per_page
                end = page * per_page
                if end < len(pulls):
                    headers = {'link': f'<{url_with_query_params(page=page + 1)}>; rel="next"'}
                elif page == 1:  # we're at the first page, and there are no more pages
                    headers = {}
                else:  # we're at the final page, and there were some pages before
                    headers = {'link': f'<{url_with_query_params(page=1)}>; rel="first"'}
                return MockAPIResponse(HTTPStatus.OK, response_data=pulls[start:end], headers=headers)
        elif url_path_matches('/repos/*/*/pulls/[0-9]+'):
            pull_no = int(url_segments[-1])
            pull = github_api_state.get_pull_by_number(pull_no)
            if pull:
                return MockAPIResponse(HTTPStatus.OK, pull)
            raise error_404()
        elif url_path_matches('/user'):
            token = request.get_header('Authorization', default='').replace('Bearer ', '')
            if token == 'ghp_dummy_token':
                return MockAPIResponse(HTTPStatus.OK, {'login': 'github_user', 'type': 'User'})
            else:
                raise Exception('Invalid token (did you forget mocking git_machete.github.GitHubToken.for_domain?): <REDACTED>')
        else:
            raise error_404()

    def handle_patch() -> "MockAPIResponse":
        assert not query_params
        if url_path_matches("/repos/*/*/(pulls|issues)/[0-9]+"):
            return update_pull_request()
        elif url_path_matches("/repositories/[0-9]+/(pulls|issues)/[0-9]+"):
            return update_pull_request()
        else:
            raise error_404()

    def handle_post() -> "MockAPIResponse":
        assert not query_params
        if url_path_matches("/repos/*/*/pulls"):
            head = json_data['head']
            base = json_data['base']
            if github_api_state.get_open_pull_by_head_and_base(head, base) is not None:
                raise error_422({'message': 'Validation Failed', 'errors': [
                    {'message': f'A pull request already exists for test_repo:{head}.'}]})
            return create_pull_request()
        elif url_path_matches("/repos/*/*/(pulls|issues)/[0-9]+/(assignees|requested_reviewers)"):
            pull_no = int(url_segments[-2])
            pull = github_api_state.get_pull_by_number(pull_no)
            assert pull is not None
            if "invalid-user" in list(json_data.values())[0]:
                raise error_422(
                    {"message": "Reviews may only be requested from collaborators. "
                                "One or more of the users or teams you specified is not a collaborator "
                                "of the example-org/example-repo repository."})
            else:
                fill_pull_request_from_json_data(pull)
                return MockAPIResponse(HTTPStatus.OK, pull)
        elif parsed_url.path in ("/api/graphql", "/graphql"):  # /api/graphql for Enterprise domains
            query_or_mutation = json_data['query']
            if 'query {' in query_or_mutation:
                match = re.search(r'pullRequest\(number: ([0-9]+)\)', query_or_mutation)
                assert match is not None
                pr_number = int(match.group(1))
                pr = github_api_state.get_pull_by_number(pr_number)
                assert pr is not None
                pr_is_draft: bool = pr.get("draft") is True
                return MockAPIResponse(HTTPStatus.OK, {
                    # Let's just use PR number as PR GraphQL id, for simplicity
                    'data': {'repository': {'pullRequest': {'id': str(pr_number), 'isDraft': pr_is_draft}}}
                })
            else:
                match = re.search(r'([a-zA-Z]+)\(input: \{pullRequestId: "([0-9]+)"}\)', query_or_mutation)
                assert match is not None
                target_draft_state = match.group(1) == "convertPullRequestToDraft"
                pr_number = int(match.group(2))
                pr = github_api_state.get_pull_by_number(pr_number)
                assert pr is not None
                pr['draft'] = target_draft_state
                return MockAPIResponse(HTTPStatus.OK, {
                    'data': {'repository': {'pullRequest': {'id': str(pr_number), 'isDraft': target_draft_state}}}
                })
        else:
            raise error_404()

    def update_pull_request() -> "MockAPIResponse":
        pull_no = int(url_segments[-1])
        pull = github_api_state.get_pull_by_number(pull_no)
        assert pull is not None
        fill_pull_request_from_json_data(pull)
        return MockAPIResponse(HTTPStatus.OK, pull)

    def create_pull_request() -> "MockAPIResponse":
        pull = {'user': {'login': 'some_other_user'},
                'html_url': 'www.github.com',
                'body': '# Summary',
                'state': 'open',
                'head': {'ref': "<TO-BE-FILLED>", 'repo': {'id': 1}},
                'base': {'ref': "<TO-BE-FILLED>"}}
        fill_pull_request_from_json_data(pull)
        github_api_state.add_pull(pull)
        return MockAPIResponse(HTTPStatus.CREATED, pull)

    def fill_pull_request_from_json_data(pull: Dict[str, Any]) -> None:
        for key in json_data.keys():
            value = json_data[key]
            if key in ('base', 'head'):
                pull[key]['ref'] = value
            else:
                pull[key] = value

    def redirect_307(location: str) -> HTTPError:
        return HTTPError(parsed_url.hostname, 307, 'Temporary redirect', {'Location': location}, None)  # type: ignore[arg-type]

    def error_404() -> HTTPError:
        return HTTPError(parsed_url.hostname, 404, 'Not found', None, None)  # type: ignore[arg-type]

    def error_422(response_data: Any) -> MockHTTPError:
        return MockHTTPError(parsed_url.hostname, 422, response_data, None, None)  # type: ignore[arg-type]

    if parsed_url.hostname == "403.example.org":
        raise HTTPError("http://example.org", 403, 'Forbidden', None, None)  # type: ignore[arg-type]

    if request.method != "GET" and url_segments[:3] == ["repos", "example-org", "old-example-repo"]:
        original_path = parsed_url.path
        new_path = original_path.replace("/repos/example-org/old-example-repo", "/repositories/2")
        location = parsed_url._replace(path=new_path).geturl()
        raise redirect_307(location)

    return handle_method()
