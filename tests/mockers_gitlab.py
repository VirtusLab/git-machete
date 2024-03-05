import json
import re
from collections import defaultdict
from contextlib import AbstractContextManager, contextmanager
from http import HTTPStatus
from typing import Any, Callable, Dict, Iterator, List, Optional, Union
from urllib.error import HTTPError
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse
from urllib.request import Request

from git_machete.code_hosting import OrganizationAndRepository
from git_machete.gitlab import GitLabToken


def mock_mr_json(head: str, base: str, number: int,
                 repo_id: int = 1,
                 user: str = 'some_other_user',
                 html_url: str = 'www.gitlab.com',
                 body: Optional[str] = '# Summary',
                 state: str = 'open',
                 draft: bool = False
                 ) -> Dict[str, Any]:
    return {
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


def mock_gitlab_token_for_domain_fake(_domain: str) -> GitLabToken:
    return GitLabToken(value='glpat-dummy-token', provider='dummy_provider')


def mock_from_url(domain: str, url: str) -> "OrganizationAndRepository":  # noqa: U100
    return OrganizationAndRepository("example-org", "example-repo")


def mock_shutil_which(path: Optional[str]) -> Callable[[Any], Optional[str]]:
    return lambda _cmd: path


class MockGitLabAPIResponse:
    def __init__(self,
                 status_code: int,
                 response_data: Union[List[Dict[str, Any]], Dict[str, Any]],
                 headers: Dict[str, Any] = {}) -> None:
        self.status_code = status_code
        self.response_data = response_data
        self.headers = headers

    def read(self) -> bytes:
        return json.dumps(self.response_data).encode()

    def info(self) -> Dict[str, Any]:
        return defaultdict(lambda: "", self.headers)


class MockGitLabAPIState:
    def __init__(self, *pulls: Dict[str, Any]) -> None:
        self.__pulls: List[Dict[str, Any]] = [dict(pull) for pull in pulls]

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


class MockHTTPError(HTTPError):
    from email.message import Message

    def __init__(self, url: str, code: int, msg: Any, hdrs: Message, fp: Any) -> None:
        super().__init__(url, code, msg, hdrs, fp)
        self.msg = msg

    def read(self, _n: int = 1) -> bytes:  # noqa: F841
        return json.dumps(self.msg).encode()


# Not including [MockGitLabAPIResponse] type argument to maintain compatibility with Python <= 3.8
def mock_urlopen(gitlab_api_state: MockGitLabAPIState) -> Callable[[Request], AbstractContextManager]:  # type: ignore[type-arg]
    @contextmanager
    def inner(request: Request) -> Iterator[MockGitLabAPIResponse]:
        yield __mock_urlopen_impl(gitlab_api_state, request)
    return inner


def __mock_urlopen_impl(gitlab_api_state: MockGitLabAPIState, request: Request) -> MockGitLabAPIResponse:
    parsed_url: ParseResult = urlparse(request.full_url)
    url_segments: List[str] = [s for s in parsed_url.path.split('/') if s]
    query_params: Dict[str, str] = {k: v[0] for k, v in parse_qs(parsed_url.query).items()}
    json_data: Dict[str, Any] = request.data and json.loads(request.data)  # type: ignore

    def handle_method() -> "MockGitLabAPIResponse":
        if request.method == "GET":
            return handle_get()
        elif request.method == "PATCH":
            return handle_patch()
        elif request.method == "POST":
            return handle_post()
        else:
            return MockGitLabAPIResponse(HTTPStatus.METHOD_NOT_ALLOWED, [])

    def url_path_matches(pattern: str) -> bool:
        regex = pattern.replace('*', '[^/]+')
        return re.match('^(/api/v4)?' + regex + '$', parsed_url.path) is not None

    def url_with_query_params(**new_params: Any) -> str:
        new_query_string: str = urlencode({**query_params, **new_params})
        return parsed_url._replace(query=new_query_string).geturl()

    def handle_get() -> "MockGitLabAPIResponse":
        if url_path_matches('/projects/*/merge_requests'):
            full_head_name: Optional[str] = query_params.get('head')
            if full_head_name:
                head: str = full_head_name.split(':')[1]
                prs = gitlab_api_state.get_open_pulls_by_head(head)
                # If no matching PRs are found, the real GitLab returns 200 OK with an empty JSON array - not 404.
                return MockGitLabAPIResponse(HTTPStatus.OK, prs)
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
                return MockGitLabAPIResponse(HTTPStatus.OK, response_data=pulls[start:end], headers=headers)
        elif url_path_matches('/repos/*/*/pulls/[0-9]+'):
            pull_no = int(url_segments[-1])
            pull = gitlab_api_state.get_pull_by_number(pull_no)
            if pull:
                return MockGitLabAPIResponse(HTTPStatus.OK, pull)
            raise error_404()
        elif url_path_matches('/user'):
            return MockGitLabAPIResponse(HTTPStatus.OK, {'username': 'gitlab_user'})
        else:
            raise error_404()

    def handle_patch() -> "MockGitLabAPIResponse":
        assert not query_params
        if url_path_matches("/repos/*/*/(pulls|issues)/[0-9]+"):
            return update_pull_request()
        elif url_path_matches("/repositories/[0-9]+/(pulls|issues)/[0-9]+"):
            return update_pull_request()
        else:
            raise error_404()

    def handle_post() -> "MockGitLabAPIResponse":
        assert not query_params
        if url_path_matches("/repos/*/*/pulls"):
            head = json_data['head']
            base = json_data['base']
            if gitlab_api_state.get_open_pull_by_head_and_base(head, base) is not None:
                raise error_422({'message': 'Validation Failed', 'errors': [
                    {'message': f'A pull request already exists for test_repo:{head}.'}]})
            return create_pull_request()
        elif url_path_matches("/repos/*/*/(pulls|issues)/[0-9]+/(assignees|requested_reviewers)"):
            pull_no = int(url_segments[-2])
            pull = gitlab_api_state.get_pull_by_number(pull_no)
            assert pull is not None
            if "invalid-user" in list(json_data.values())[0]:
                raise error_422(
                    {"message": "Reviews may only be requested from collaborators. "
                                "One or more of the users or teams you specified is not a collaborator "
                                "of the example-org/example-repo repository."})
            else:
                fill_pull_request_from_json_data(pull)
                return MockGitLabAPIResponse(HTTPStatus.OK, pull)
        elif parsed_url.path in ("/api/graphql", "/graphql"):  # /api/graphql for Enterprise domains
            query_or_mutation = json_data['query']
            if 'query {' in query_or_mutation:
                match = re.search(r'pullRequest\(number: ([0-9]+)\)', query_or_mutation)
                assert match is not None
                pr_number = int(match.group(1))
                pr = gitlab_api_state.get_pull_by_number(pr_number)
                assert pr is not None
                pr_is_draft: bool = pr.get("draft") is True
                return MockGitLabAPIResponse(HTTPStatus.OK, {
                    # Let's just use PR number as PR GraphQL id, for simplicity
                    'data': {'repository': {'pullRequest': {'id': str(pr_number), 'isDraft': pr_is_draft}}}
                })
            else:
                match = re.search(r'([a-zA-Z]+)\(input: \{pullRequestId: "([0-9]+)"}\)', query_or_mutation)
                assert match is not None
                target_draft_state = match.group(1) == "convertPullRequestToDraft"
                pr_number = int(match.group(2))
                pr = gitlab_api_state.get_pull_by_number(pr_number)
                assert pr is not None
                pr['draft'] = target_draft_state
                return MockGitLabAPIResponse(HTTPStatus.OK, {
                    'data': {'repository': {'pullRequest': {'id': str(pr_number), 'isDraft': target_draft_state}}}
                })
        else:
            raise error_404()

    def update_pull_request() -> "MockGitLabAPIResponse":
        pull_no = int(url_segments[-1])
        pull = gitlab_api_state.get_pull_by_number(pull_no)
        assert pull is not None
        fill_pull_request_from_json_data(pull)
        return MockGitLabAPIResponse(HTTPStatus.OK, pull)

    def create_pull_request() -> "MockGitLabAPIResponse":
        pull = {'user': {'login': 'some_other_user'},
                'html_url': 'www.gitlab.com',
                'body': '# Summary',
                'state': 'open',
                'head': {'ref': "", 'repo': {'full_name': 'testing:checkout_prs', 'html_url': 'https:/example.org/pull/1234'}},
                'base': {'ref': ""}}
        fill_pull_request_from_json_data(pull)
        gitlab_api_state.add_pull(pull)
        return MockGitLabAPIResponse(HTTPStatus.CREATED, pull)

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
        new_path = original_path.replace("/repos/example-org/old-example-repo", "/repositories/123456789")
        location = parsed_url._replace(path=new_path).geturl()
        raise redirect_307(location)

    return handle_method()
