import http
import json
import os
import re
import shutil
import subprocess
import urllib.error
# Deliberately NOT using much more convenient `requests` to avoid external dependencies in production code
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

from git_machete.exceptions import (MacheteException,
                                    UnprocessableEntityHTTPError)
from git_machete.git_operations import GitContext, LocalBranchShortName
from git_machete.utils import debug, fmt, warn

GITHUB_TOKEN_ENV_VAR = 'GITHUB_TOKEN'
DEFAULT_GITHUB_DOMAIN = "github.com"


def github_remote_url_patterns(domain: str) -> List[str]:
    # GitHub DOES NOT allow trailing `.git` suffix in the repository name (also applies to multiple repetitions e.g. `repo_name.git.git`)
    domain_regex = re.escape(domain)
    return [
        f"^https://.*@{domain_regex}/(.*)/(.*)$",
        f"^https://{domain_regex}/(.*)/(.*)$",
        f"^git@{domain_regex}:(.*)/(.*)$",
        f"^ssh://git@{domain_regex}/(.*)/(.*)$"
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


def __get_github_token_and_provider(domain: str) -> Optional[GithubTokenAndTokenProvider]:
    def get_token_from_gh() -> Optional[GithubTokenAndTokenProvider]:
        # Abort without error if `gh` isn't available
        gh = shutil.which('gh')
        if not gh:
            return None

        # There is also `gh auth token`, but it's only been added in gh v2.17.0, in Oct 2022.
        # Let's stick to the older `gh auth status --show-token` for compatibility.
        proc = subprocess.run(
            [gh, "auth", "status", "--hostname", domain, "--show-token"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if proc.returncode != 0:
            return None

        # `gh auth status --show-token` outputs to stderr in the form:
        #
        # {domain}:
        #   ✓ Logged in to {domain} as {username} ({config_path})
        #   ✓ Git operations for {domain} configured to use {protocol} protocol.
        #   ✓ Token: <token>
        #
        # with non-zero exit code on failure.
        stderr = proc.stderr.decode()
        match = re.search(r"Token: (\w+)", stderr)
        if match:
            return GithubTokenAndTokenProvider(token=match.group(1),
                                               token_provider=f'auth token for {domain} from `hub` GitHub CLI')
        return None

    def get_token_from_hub() -> Optional[GithubTokenAndTokenProvider]:
        home_path: str = str(Path.home())
        config_hub_path: str = os.path.join(home_path, ".config", "hub")
        if os.path.isfile(config_hub_path):
            with open(config_hub_path) as config_hub:
                # ~/.config/hub is a yaml file, with a structure similar to:
                #
                # {domain1}:
                # - user: {username1}
                #   oauth_token: *******************
                #   protocol: {protocol}
                #
                # {domain2}:
                # - user: {username2}
                #   oauth_token: *******************
                #   protocol: {protocol}
                found_host = False
                for line in config_hub.readlines():
                    if line.rstrip() == domain + ":":
                        found_host = True
                    elif found_host and line.lstrip().startswith("oauth_token:"):
                        result = re.sub(' *oauth_token: *', '', line).rstrip().replace('"', '')
                        return GithubTokenAndTokenProvider(token=result,
                                                           token_provider=f'auth token for {domain} from `hub` GitHub CLI')
        return None

    def get_token_from_env() -> Optional[GithubTokenAndTokenProvider]:
        github_token = os.environ.get(GITHUB_TOKEN_ENV_VAR)
        if github_token:
            return GithubTokenAndTokenProvider(token=github_token,
                                               token_provider=f'`{GITHUB_TOKEN_ENV_VAR}` environment variable')
        return None

    def get_token_from_file_in_home_directory() -> Optional[GithubTokenAndTokenProvider]:
        required_file_name = '.github-token'
        token_provider = f'auth token for {domain} from `~/.github-token`'
        file_full_path = os.path.expanduser(f'~/{required_file_name}')

        if os.path.isfile(file_full_path):
            with open(file_full_path) as file:
                for line in file.readlines():
                    if line.endswith(" " + domain):
                        token = line.split(" ")[0]
                        return GithubTokenAndTokenProvider(token=token, token_provider=token_provider)
                    elif domain == DEFAULT_GITHUB_DOMAIN and " " not in line.rstrip():
                        return GithubTokenAndTokenProvider(token=line.rstrip(), token_provider=token_provider)
        return None

    return (get_token_from_env() or
            get_token_from_file_in_home_directory() or
            get_token_from_gh() or
            get_token_from_hub())


def __get_github_token(domain: str) -> Optional[str]:
    github_token_and_provider = __get_github_token_and_provider(domain)
    return github_token_and_provider.token if github_token_and_provider else None


def __get_github_token_provider(domain: str) -> Optional[str]:
    github_token_and_provider = __get_github_token_and_provider(domain)
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


def __fire_github_api_request(domain: str, method: str, path: str,
                              token: Optional[str], request_body: Optional[Dict[str, Any]] = None) -> Any:
    headers: Dict[str, str] = {
        'Content-type': 'application/json',
        'User-Agent': 'git-machete',
        'Accept': 'application/vnd.github.v3+json'
    }
    if token:
        headers['Authorization'] = 'Bearer ' + token

    if domain == DEFAULT_GITHUB_DOMAIN:
        url_prefix = 'https://api.' + domain
    else:
        url_prefix = 'https://' + domain + '/api/v3'

    url = url_prefix + path
    json_body: Optional[str] = json.dumps(request_body) if request_body else None
    http_request = urllib.request.Request(url, headers=headers, data=json_body.encode() if json_body else None, method=method.upper())
    debug(f'firing a {method} request to {url} with {"a" if token else "no"} bearer token and request body {json_body or "<none>"}')

    try:
        with urllib.request.urlopen(http_request) as response:
            parsed_response_body: Any = json.loads(response.read().decode())
            # https://docs.github.com/en/rest/guides/using-pagination-in-the-rest-api?apiVersion=2022-11-28#using-link-headers
            link_header: str = response.info()["link"]
            if link_header:
                url_prefix_regex = re.escape(url_prefix)
                match = re.search(f'<{url_prefix_regex}(/[^>]+)>; rel="next"', link_header)
                if match:
                    next_page_path = match.group(1)
                    debug(f'there is more data to retrieve under {next_page_path}')
                    return parsed_response_body + __fire_github_api_request(domain, method, next_page_path, token, request_body)
            return parsed_response_body
    except urllib.error.HTTPError as err:
        if err.code == http.HTTPStatus.UNPROCESSABLE_ENTITY:
            error_response = json.loads(err.read().decode())
            error_reason: str = __extract_failure_info_from_422(error_response)
            raise UnprocessableEntityHTTPError(error_reason)
        elif err.code in (http.HTTPStatus.UNAUTHORIZED, http.HTTPStatus.FORBIDDEN):
            first_line = f'GitHub API returned `{err.code}` HTTP status with error message: `{err.reason}`\n'
            if token:
                raise MacheteException(first_line + 'Make sure that the GitHub API token '
                                                    f'provided by the {__get_github_token_provider(domain)} '
                                                    f'is valid and allows for access to `{method.upper()}` `{url_prefix}{path}`.\n'
                                                    'You can also use a different token provider, available providers can be found '
                                                    'when running `git machete help github`.')
            else:
                raise MacheteException(
                    first_line + f'You might not have the required permissions for this repository.\n'
                                 f'Provide a GitHub API token with `repo` access via {__get_github_token_provider(domain)}.\n'
                                 f'Visit `https://{domain}/settings/tokens` to generate a new one.\n'
                                 'You can also use a different token provider, available providers can be found '
                                 'when running `git machete help github`.')
        elif err.code == http.HTTPStatus.NOT_FOUND:
            raise MacheteException(
                f'`{method} {url}` request ended up in 404 response from GitHub. A valid GitHub API token is required.\n'
                f'Provide a GitHub API token with `repo` access via one of the: {get_github_token_possible_providers()} '
                f'Visit `https://{domain}/settings/tokens` to generate a new one.')  # TODO (#164): make dedicated exception here
        elif err.code == http.HTTPStatus.TEMPORARY_REDIRECT:
            if err.headers['Location'] is not None:
                if len(err.headers['Location'].split('/')) >= 5:
                    current_repo_and_org = get_repo_and_org_names_by_id(domain, err.headers['Location'].split('/')[4])
            else:
                first_line = fmt(f'GitHub API returned `{err.code}` HTTP status with error message: `{err.reason}`\n')
                raise MacheteException(
                    first_line + 'It looks like the organization or repository name got changed recently and is outdated.\n'
                    'Inferring current organization or repository... -> Cannot infer current organization or repository\n'
                    'Update your remote repository manually via: `git remote set-url <remote_name> <new_repository_url>`.')
            # err.headers is a case-insensitive dict of class Message with the `__getitem__` and `get` functions implemented in
            # https://github.com/python/cpython/blob/3.10/Lib/email/message.py
            pulls_or_issues_api_suffix = "/".join(path.split("/")[4:])
            new_path = f'/repos/{current_repo_and_org}/{pulls_or_issues_api_suffix}'
            # for example when creating a new PR, new_path='/repos/new_org_name/new_repo_name/pulls'
            warn(f'GitHub API returned `{err.code}` HTTP status with error message: `{err.reason}`. \n'
                 'It looks like the organization or repository name got changed recently and is outdated.\n'
                 'Inferring current organization or repository... '
                 f'New organization = `{current_repo_and_org.split("/")[0]}`, '
                 f'new repository = `{current_repo_and_org.split("/")[1]}`.\n'
                 'You can update your remote repository via: `git remote set-url <remote_name> <new_repository_url>`.',
                 end='')
            return __fire_github_api_request(domain=domain, method=method, path=new_path, token=token, request_body=request_body)
        else:
            first_line = fmt(f'GitHub API returned `{err.code}` HTTP status with error message: `{err.reason}`\n')
            raise MacheteException(
                first_line + "Please open an issue regarding this topic under link: https://github.com/VirtusLab/git-machete/issues/new")
    except OSError as e:
        raise MacheteException(f'Could not connect to {url_prefix}: {e}')


def create_pull_request(domain: str, org: str, repo: str,
                        head: str, base: str, title: str, description: str, draft: bool) -> GitHubPullRequest:
    token: Optional[str] = __get_github_token(domain)
    request_body: Dict[str, Any] = {
        'head': head,
        'base': base,
        'title': title,
        'body': description,
        'draft': draft
    }
    pr = __fire_github_api_request(domain, 'POST', f'/repos/{org}/{repo}/pulls', token, request_body)
    return __parse_pr_json(pr)


def add_assignees_to_pull_request(domain: str, org: str, repo: str, number: int, assignees: List[str]) -> None:
    token: Optional[str] = __get_github_token(domain)
    request_body: Dict[str, List[str]] = {
        'assignees': assignees
    }
    # Adding assignees is only available via the Issues API, not PRs API.
    __fire_github_api_request(domain, 'POST', f'/repos/{org}/{repo}/issues/{number}/assignees', token, request_body)


def add_reviewers_to_pull_request(domain: str, org: str, repo: str, number: int, reviewers: List[str]) -> None:
    token: Optional[str] = __get_github_token(domain)
    request_body: Dict[str, List[str]] = {
        'reviewers': reviewers
    }
    __fire_github_api_request(domain, 'POST', f'/repos/{org}/{repo}/pulls/{number}/requested_reviewers', token, request_body)


def set_base_of_pull_request(domain: str, org: str, repo: str, number: int, base: LocalBranchShortName) -> None:
    token: Optional[str] = __get_github_token(domain)
    request_body: Dict[str, str] = {'base': base}
    __fire_github_api_request(domain, 'PATCH', f'/repos/{org}/{repo}/pulls/{number}', token, request_body)


def set_milestone_of_pull_request(domain: str, org: str, repo: str, number: int, milestone: str) -> None:
    token: Optional[str] = __get_github_token(domain)
    request_body: Dict[str, str] = {'milestone': milestone}
    # Setting milestone is only available via the Issues API, not PRs API.
    __fire_github_api_request(domain, 'PATCH', f'/repos/{org}/{repo}/issues/{number}', token, request_body)


def derive_pull_request_by_head(domain: str, org: str, repo: str, head: LocalBranchShortName) -> Optional[GitHubPullRequest]:
    token: Optional[str] = __get_github_token(domain)
    prs = __fire_github_api_request(domain, 'GET', f'/repos/{org}/{repo}/pulls?head={org}:{head}', token)
    if len(prs) >= 1:
        return __parse_pr_json(prs[0])
    else:
        return None


def derive_pull_requests(domain: str, org: str, repo: str) -> List[GitHubPullRequest]:
    token: Optional[str] = __get_github_token(domain)
    # As of Dec 2022, GitHub API never returns more than 100 PRs, even if per_page>100.
    prs = __fire_github_api_request(domain, 'GET', f'/repos/{org}/{repo}/pulls?per_page=100', token)
    return list(map(__parse_pr_json, prs))


def derive_current_user_login(domain: str) -> Optional[str]:
    token: Optional[str] = __get_github_token(domain)
    if not token:
        return None
    user = __fire_github_api_request(domain, 'GET', '/user', token)
    return str(user['login'])  # str() to satisfy mypy


def is_github_remote_url(domain: str, url: str) -> bool:
    return any((re.match(pattern, url) for pattern in github_remote_url_patterns(domain)))


def get_parsed_github_remote_url(domain: str, url: str, remote: str) -> Optional[RemoteAndOrganizationAndRepository]:
    for pattern in github_remote_url_patterns(domain):
        match = re.match(pattern, url)
        if match:
            org = match.group(1)
            repo = match.group(2)
            return RemoteAndOrganizationAndRepository(remote=remote,
                                                      organization=org,
                                                      repository=repo if repo[-4:] != '.git' else repo[:-4])
    return None


def get_pull_request_by_number_or_none(domain: str, number: int, org: str, repo: str) -> Optional[GitHubPullRequest]:
    token: Optional[str] = __get_github_token(domain)
    try:
        pr_json: Dict[str, Any] = __fire_github_api_request(domain, 'GET', f'/repos/{org}/{repo}/pulls/{number}', token)
        return __parse_pr_json(pr_json)
    except MacheteException:
        return None


def checkout_pr_refs(git: GitContext, remote: str, pr_number: int, branch: LocalBranchShortName) -> None:
    git.fetch_ref(remote, f'pull/{pr_number}/head:{branch}')
    git.checkout(branch)


def get_repo_and_org_names_by_id(domain: str, repo_id: str) -> str:
    token: Optional[str] = __get_github_token(domain)
    repo = __fire_github_api_request(domain, 'GET', f'/repositories/{repo_id}', token)
    return str(repo['full_name'])


def get_github_token_possible_providers() -> str:
    return (f'\n\t1. `{GITHUB_TOKEN_ENV_VAR}` environment variable.\n'
            '\t2. Content of the `~/.github-token` file.\n'
            '\t3. Current auth token from the `gh` GitHub CLI.\n'
            '\t4. Current auth token from the `hub` GitHub CLI.\n')
