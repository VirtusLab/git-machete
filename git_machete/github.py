# Deliberately NOT using much more convenient `requests` to avoid external dependencies
import http
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional
import urllib.request
import urllib.error

from git_machete.utils import debug, fmt
from git_machete.exceptions import MacheteException, UnprocessableEntityHTTPError
from git_machete.git_operations import GitContext, LocalBranchShortName

GITHUB_TOKEN_ENV_VAR = 'GITHUB_TOKEN'
# GitHub Enterprise deployments use alternate domains.
# The logic in this module will need to be expanded to detect
# and use alternate remote domains to provide enterprise support.
GITHUB_DOMAIN = "github.com"
GITHUB_REMOTE_PATTERNS = [
    r"^https://.*@github\.com/(.*)/(.*)\.git$",
    r"^https://github\.com/(.*)/(.*)\.git$",
    r"^git@github\.com:(.*)/(.*)\.git$",
    r"^ssh://git@github\.com/(.*)/(.*)\.git$"
]


class GitHubPullRequest(object):
    def __init__(self,
                 number: int,
                 user: str,
                 base: str,
                 head: str,
                 html_url: str,
                 state: str,
                 full_repository_name: str,
                 repository_url: str
                 ) -> None:
        self.number: int = number
        self.user: str = user
        self.base: str = base
        self.head: str = head
        self.html_url: str = html_url
        self.state: str = state
        self.full_repository_name: str = full_repository_name
        self.repository_url: str = repository_url

    def __repr__(self) -> str:
        return f"PR #{self.number} by {self.user}: {self.head} -> {self.base}"


class RemoteAndOrganizationAndRepository(NamedTuple):
    remote: str
    organization: str
    repository: str


def __parse_pr_json(pr_json: Any) -> GitHubPullRequest:
    return GitHubPullRequest(number=int(pr_json['number']),
                             user=pr_json['user']['login'],
                             base=pr_json['base']['ref'],
                             head=pr_json['head']['ref'],
                             html_url=pr_json['html_url'],
                             state=pr_json['state'],
                             full_repository_name=pr_json['head']['repo']['full_name'] if pr_json['head']['repo'] else None,
                             repository_url=pr_json['head']['repo']['html_url'] if pr_json['head']['repo'] else None)


class GithubTokenAndTokenProvider(NamedTuple):
    token: str
    token_provider: str


def __get_github_token_and_provider() -> Optional[GithubTokenAndTokenProvider]:
    def get_token_from_gh() -> Optional[GithubTokenAndTokenProvider]:
        # Abort without error if `gh` isn't available
        gh = shutil.which('gh')
        if not gh:
            return None

        # Run via subprocess.run as we're insensitive to return code.
        #
        # TODO (#137): `gh` can store auth token for public and enterprise domains,
        #  specify single domain for lookup.
        # This is *only* github.com until enterprise support is added.
        proc = subprocess.run(
            [gh, "auth", "status", "--hostname", GITHUB_DOMAIN, "--show-token"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # gh auth status outputs to stderr in the form:
        #
        # {domain}:
        #   ✓ Logged in to {domain} as {username} ({config_path})
        #   ✓ Git operations for {domain} configured to use {protocol} protocol.
        #   ✓ Token: *******************
        #
        # with non-zero exit code on failure
        result = proc.stderr.decode()

        match = re.search(r"Token: (\w+)", result)
        if match:
            return GithubTokenAndTokenProvider(token=match.groups()[0],
                                               token_provider='current auth token from the `gh` GitHub CLI')
        return None

    def get_token_from_hub() -> Optional[GithubTokenAndTokenProvider]:
        home_path: str = str(Path.home())
        config_hub_path: str = os.path.join(home_path, ".config", "hub")
        if os.path.isfile(config_hub_path):
            with open(config_hub_path) as config_hub:
                config_hub_content: str = config_hub.read()
                # ~/.config/hub is a yaml file, with a structure similar to:
                #
                # {domain}:
                # - user: {username}
                #   oauth_token: *******************
                #   protocol: {protocol}
                match = re.search(r"oauth_token: (\w+)", config_hub_content)
                if match:
                    return GithubTokenAndTokenProvider(token=match.groups()[0],
                                                       token_provider='current auth token from the `hub` GitHub CLI')
        return None

    def get_token_from_env() -> Optional[GithubTokenAndTokenProvider]:
        github_token = os.environ.get(GITHUB_TOKEN_ENV_VAR)
        if github_token:
            return GithubTokenAndTokenProvider(token=github_token,
                                               token_provider=f'`{GITHUB_TOKEN_ENV_VAR}` environment variable')
        return None

    def get_token_from_file_in_home_directory() -> Optional[GithubTokenAndTokenProvider]:
        required_file_name = '.github-token'
        file_full_path = os.path.expanduser(f'~/{required_file_name}')

        if os.path.isfile(file_full_path):
            with open(file_full_path) as file:
                return GithubTokenAndTokenProvider(token=file.read().strip(),
                                                   token_provider='content of the `~/.github-token` file')
        return None

    return (get_token_from_env() or
            get_token_from_file_in_home_directory() or
            get_token_from_gh() or
            get_token_from_hub())


def __get_github_token() -> Optional[str]:
    github_token_and_provider = __get_github_token_and_provider()
    return github_token_and_provider.token if github_token_and_provider else None


def __get_github_token_provider() -> Optional[str]:
    github_token_and_provider = __get_github_token_and_provider()
    return github_token_and_provider.token_provider if github_token_and_provider else None


def __extract_failure_info_from_422(response: Any) -> str:
    if response['message'] != 'Validation Failed':
        return str(response['message'])
    ret: List[str] = []
    if response.get('errors'):
        for error in response['errors']:
            if error.get('message'):
                ret.append(error['message'])
    if ret:
        return '\n'.join(ret)
    return str(response)


def __fire_github_api_request(method: str, path: str, token: Optional[str], request_body: Optional[Dict[str, Any]] = None) -> Any:
    headers: Dict[str, str] = {
        'Content-type': 'application/json',
        'User-Agent': 'git-machete',
        'Accept': 'application/vnd.github.v3+json'
    }
    if token:
        headers['Authorization'] = 'Bearer ' + token

    host = 'https://api.' + GITHUB_DOMAIN
    url = host + path
    json_body: Optional[str] = json.dumps(request_body) if request_body else None
    http_request = urllib.request.Request(url, headers=headers, data=json_body.encode() if json_body else None, method=method.upper())
    debug(f'firing a {method} request to {url} with {"a" if token else "no"} bearer token and request body {json_body or "<none>"}')

    try:
        with urllib.request.urlopen(http_request) as response:
            parsed_response_body: Any = json.loads(response.read().decode())
            return parsed_response_body
    except urllib.error.HTTPError as err:
        if err.code == http.HTTPStatus.UNPROCESSABLE_ENTITY:
            error_response = json.loads(err.read().decode())
            error_reason: str = __extract_failure_info_from_422(error_response)
            raise UnprocessableEntityHTTPError(error_reason)
        elif err.code in (http.HTTPStatus.UNAUTHORIZED, http.HTTPStatus.FORBIDDEN):
            first_line = f'GitHub API returned {err.code} HTTP status with error message: `{err.reason}`\n'
            if token:
                raise MacheteException(first_line + f'Make sure that the GitHub API token provided by the {__get_github_token_provider()} '
                                                    f'is valid and allows for access to `{method.upper()}` `https://{host}{path}`.\n'
                                                    'You can also use a different token provider, available providers can be found '
                                                    'when running `git machete help github`')
            else:
                raise MacheteException(
                    first_line + f'You might not have the required permissions for this repository.\n'
                                 f'Provide a GitHub API token with `repo` access via {__get_github_token_provider()}.\n'
                                 'Visit `https://github.com/settings/tokens` to generate a new one.\n'
                                 'You can also use a different token provider, available providers can be found '
                                 'when running `git machete help github`')
        elif err.code == http.HTTPStatus.NOT_FOUND:
            raise MacheteException(
                f'`{method} {url}` request ended up in 404 response from GitHub. A valid GitHub API token is required.\n'
                f'Provide a GitHub API token with `repo` access via one of the: {get_github_token_possible_providers()} '
                'Visit `https://github.com/settings/tokens` to generate a new one.')  # TODO (#164): make dedicated exception here
        else:
            first_line = fmt(f'GitHub API returned {err.code} HTTP status with error message: `{err.reason}`\n')
            raise MacheteException(
                first_line + "Please open an issue regarding this topic under link: https://github.com/VirtusLab/git-machete/issues/new")
    except OSError as e:
        raise MacheteException(f'Could not connect to {host}: {e}')


def create_pull_request(org: str, repo: str, head: str, base: str, title: str, description: str, draft: bool) -> GitHubPullRequest:
    token: Optional[str] = __get_github_token()
    request_body: Dict[str, Any] = {
        'head': head,
        'base': base,
        'title': title,
        'body': description,
        'draft': draft
    }
    pr = __fire_github_api_request('POST', f'/repos/{org}/{repo}/pulls', token, request_body)
    return __parse_pr_json(pr)


def add_assignees_to_pull_request(org: str, repo: str, number: int, assignees: List[str]) -> None:
    token: Optional[str] = __get_github_token()
    request_body: Dict[str, List[str]] = {
        'assignees': assignees
    }
    # Adding assignees is only available via the Issues API, not PRs API.
    __fire_github_api_request('POST', f'/repos/{org}/{repo}/issues/{number}/assignees', token, request_body)


def add_reviewers_to_pull_request(org: str, repo: str, number: int, reviewers: List[str]) -> None:
    token: Optional[str] = __get_github_token()
    request_body: Dict[str, List[str]] = {
        'reviewers': reviewers
    }
    __fire_github_api_request('POST', f'/repos/{org}/{repo}/pulls/{number}/requested_reviewers', token, request_body)


def set_base_of_pull_request(org: str, repo: str, number: int, base: LocalBranchShortName) -> None:
    token: Optional[str] = __get_github_token()
    request_body: Dict[str, str] = {'base': base}
    __fire_github_api_request('PATCH', f'/repos/{org}/{repo}/pulls/{number}', token, request_body)


def set_milestone_of_pull_request(org: str, repo: str, number: int, milestone: str) -> None:
    token: Optional[str] = __get_github_token()
    request_body: Dict[str, str] = {'milestone': milestone}
    # Setting milestone is only available via the Issues API, not PRs API.
    __fire_github_api_request('PATCH', f'/repos/{org}/{repo}/issues/{number}', token, request_body)


def derive_pull_request_by_head(org: str, repo: str, head: LocalBranchShortName) -> Optional[GitHubPullRequest]:
    token: Optional[str] = __get_github_token()
    prs = __fire_github_api_request('GET', f'/repos/{org}/{repo}/pulls?head={org}:{head}', token)
    if len(prs) >= 1:
        return __parse_pr_json(prs[0])
    else:
        return None


def derive_pull_requests(org: str, repo: str) -> List[GitHubPullRequest]:
    token: Optional[str] = __get_github_token()
    prs = __fire_github_api_request('GET', f'/repos/{org}/{repo}/pulls', token)
    return list(map(__parse_pr_json, prs))


def derive_current_user_login() -> Optional[str]:
    token: Optional[str] = __get_github_token()
    if not token:
        return None
    user = __fire_github_api_request('GET', '/user', token)
    return str(user['login'])  # str() to satisfy mypy


def is_github_remote_url(url: str) -> bool:
    return any((re.match(pattern, url) for pattern in GITHUB_REMOTE_PATTERNS))


def get_parsed_github_remote_url(url: str, remote: str) -> Optional[RemoteAndOrganizationAndRepository]:
    for pattern in GITHUB_REMOTE_PATTERNS:
        match = re.match(pattern, url)
        if match:
            return RemoteAndOrganizationAndRepository(remote=remote,
                                                      organization=match.group(1),
                                                      repository=match.group(2))
    return None


def get_pull_request_by_number_or_none(number: int, org: str, repo: str) -> Optional[GitHubPullRequest]:
    token: Optional[str] = __get_github_token()
    try:
        pr_json: Dict[str, Any] = __fire_github_api_request('GET', f'/repos/{org}/{repo}/pulls/{number}', token)
        return __parse_pr_json(pr_json)
    except MacheteException:
        return None


def checkout_pr_refs(git: GitContext, remote: str, pr_number: int, branch: LocalBranchShortName) -> None:
    git.fetch_ref(remote, f'pull/{pr_number}/head:{branch}')
    git.checkout(branch)


def get_github_token_possible_providers() -> str:
    return (f'\n\t1. `{GITHUB_TOKEN_ENV_VAR}` environment variable.\n'
            '\t2. Content of the `~/.github-token` file.\n'
            '\t3. Current auth token from the `gh` GitHub CLI.\n'
            '\t4. Current auth token from the `hub` GitHub CLI.\n')
