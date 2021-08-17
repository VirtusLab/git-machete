#!/usr/bin/env python

# Deliberately NOT using much more convenient `requests` to avoid external dependencies
import http
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from git_machete.utils import fmt
from git_machete.exceptions import MacheteException, UnprocessableEntityHTTPError


GITHUB_TOKEN_ENV_VAR = 'GITHUB_TOKEN'

# GitHub Enterprise deployments use alternate domains.
# The logic in this module will need to be expanded to detect
# and use alternate remote domains to provide enterprise support.
GITHUB_DOMAIN = "github.com"
GITHUB_REMOTE_PATTERNS = [
    "^https://github\\.com/(.*)/(.*)\\.git$",
    "^git@github\\.com:(.*)/(.*)\\.git$",
]


class GitHubPullRequest(object):
    def __init__(self, number: int, user: str, base: str, head: str, html_url: str):
        self.number = number
        self.user = user
        self.base = base
        self.head = head
        self.html_url = html_url

    def __repr__(self) -> str:
        return f"PR #{self.number} by {self.user}: {self.head} -> {self.base}"


def __parse_pr_json(pr_json: Any) -> GitHubPullRequest:
    return GitHubPullRequest(int(pr_json['number']), pr_json['user']['login'], pr_json['base']['ref'], pr_json['head']['ref'], pr_json['html_url'])


def __token_from_gh() -> Optional[str]:

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
        return match.groups()[0]

    return None


def __token_from_hub() -> Optional[str]:
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
                return match.groups()[0]

    return None


def __token_from_env() -> Optional[str]:
    return os.environ.get(GITHUB_TOKEN_ENV_VAR)


def __github_token() -> Optional[str]:
    return __token_from_env() or __token_from_gh() or __token_from_hub()


def __fire_github_api_request(method: str, url: str, token: Optional[str], request_body: Optional[Dict[str, Any]] = None) -> Any:
    headers: Dict[str, str] = {
        'Content-type': 'application/json',
        'User-Agent': 'git-machete',
        'Accept': 'application/vnd.github.v3+json'
    }
    if token:
        headers['Authorization'] = 'Bearer ' + token

    host = 'https://api.' + GITHUB_DOMAIN
    http_request = Request(host + url, headers=headers, data=json.dumps(request_body).encode(), method=method.upper())

    try:
        with urlopen(http_request) as response:
            parsed_response_body: Any = json.loads(response.read().decode())
            return parsed_response_body
    except HTTPError as err:
        if err.code == http.HTTPStatus.UNPROCESSABLE_ENTITY:
            raise UnprocessableEntityHTTPError(err.reason)
        else:
            first_line = fmt(f'GitHub API returned {err.code} HTTP status with error message: `{err.reason}`\n')
            if token:
                raise MacheteException(first_line + fmt(f'Make sure that the token provided in `gh auth status` or `~/.config/hub` or <b>{GITHUB_TOKEN_ENV_VAR}</b> is valid and allows for access to `{method.upper()}` https://{host}{url}`.'))
            else:
                raise MacheteException(
                    first_line + fmt(f'This repository might be private. Provide a GitHub API token with `repo` access via `gh` or `hub` or <b>{GITHUB_TOKEN_ENV_VAR}</b> env var.\n'
                                     'Visit `https://github.com/settings/tokens` to generate a new one.'))
    except OSError as e:
        raise MacheteException(f'Could not connect to {host}: {e}')


def __check_pr_already_created(pull: GitHubPullRequest, pull_requests: List[GitHubPullRequest]) -> Optional[GitHubPullRequest]:
    for pr in pull_requests:
        if pull.base == pr.base and pull.head == pr.head:
            return pr
    return None


def create_pull_request(org: str, repo: str, head: str, base: str, title: str, description: str, draft: bool) -> GitHubPullRequest:
    token: Optional[str] = __github_token()
    request_body: Dict[str, Any] = {
        'head': head,
        'base': base,
        'title': title,
        'body': description,
        'draft': draft
    }
    prs: List[GitHubPullRequest] = derive_pull_requests(org, repo)
    to_load: GitHubPullRequest = GitHubPullRequest(1, 'user', base, head, '')
    pr_found: Optional[GitHubPullRequest] = __check_pr_already_created(to_load, prs)
    if not pr_found:
        pr = __fire_github_api_request('POST', f'/repos/{org}/{repo}/pulls', token, request_body)
        return __parse_pr_json(pr)
    else:
        raise MacheteException(f'Pull request for branch {head} is already created under link {pr_found.html_url}!\nPR details: {pr_found}')


def add_assignees_to_pull_request(org: str, repo: str, number: int, assignees: List[str]) -> None:
    token: Optional[str] = __github_token()
    request_body: Dict[str, List[str]] = {
        'assignees': assignees
    }
    # Adding assignees is only available via the Issues API, not PRs API.
    __fire_github_api_request('POST', f'/repos/{org}/{repo}/issues/{number}/assignees', token, request_body)


def add_reviewers_to_pull_request(org: str, repo: str, number: int, reviewers: List[str]) -> None:
    token: Optional[str] = __github_token()
    request_body: Dict[str, List[str]] = {
        'reviewers': reviewers
    }
    __fire_github_api_request('POST', f'/repos/{org}/{repo}/pulls/{number}/requested_reviewers', token, request_body)


def set_base_of_pull_request(org: str, repo: str, number: int, base: str) -> None:
    token: Optional[str] = __github_token()
    request_body: Dict[str, str] = {'base': base}
    __fire_github_api_request('PATCH', f'/repos/{org}/{repo}/pulls/{number}', token, request_body)


def set_milestone_of_pull_request(org: str, repo: str, number: int, milestone: str) -> None:
    token: Optional[str] = __github_token()
    request_body: Dict[str, str] = {'milestone': milestone}
    # Setting milestone is only available via the Issues API, not PRs API.
    __fire_github_api_request('PATCH', f'/repos/{org}/{repo}/issues/{number}', token, request_body)


def derive_pull_request_by_head(org: str, repo: str, head: str) -> Optional[GitHubPullRequest]:
    token: Optional[str] = __github_token()
    prs = __fire_github_api_request('GET', f'/repos/{org}/{repo}/pulls?head={org}:{head}', token)
    if len(prs) >= 1:
        return __parse_pr_json(prs[0])
    else:
        return None


def derive_pull_requests(org: str, repo: str) -> List[GitHubPullRequest]:
    token: Optional[str] = __github_token()
    prs = __fire_github_api_request('GET', f'/repos/{org}/{repo}/pulls', token)
    return list(map(__parse_pr_json, prs))


def derive_current_user_login() -> Optional[str]:
    token: Optional[str] = __github_token()
    if not token:
        return None
    user = __fire_github_api_request('GET', '/user', token)
    return str(user['login'])  # str() to satisfy mypy


def is_github_remote_url(url: str) -> bool:
    return any((re.match(pattern, url) for pattern in GITHUB_REMOTE_PATTERNS))


def parse_github_remote_url(url: str) -> Optional[Tuple[str, str]]:
    for pattern in GITHUB_REMOTE_PATTERNS:
        match = re.match(pattern, url)
        if match:
            return match.group(1), match.group(2)
    return None
