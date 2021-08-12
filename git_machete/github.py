#!/usr/bin/env python

import json
import os
import re
import shutil
import subprocess
# Deliberately NOT using much more convenient `requests` to avoid external dependencies
from http.client import HTTPResponse, HTTPSConnection
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from git_machete.cmd import MacheteException, fmt


class GitHubPullRequest(object):
    def __init__(self, number: int, user: str, base: str, head: str, html_url: str):
        self.number = number
        self.user = user
        self.base = base
        self.head = head
        self.html_url = html_url

    def __repr__(self) -> str:
        return f"PR #{self.number} by {self.user}: {self.head} -> {self.base}"


def parse_pr_json(pr_json: Any) -> GitHubPullRequest:
    return GitHubPullRequest(int(pr_json['number']), pr_json['user']['login'], pr_json['base']['ref'], pr_json['head']['ref'], pr_json['html_url'])


GITHUB_TOKEN_ENV_VAR = 'GITHUB_TOKEN'

# GitHub Enterprise deployments use alternate domains.
# The logic in this module will need to be expanded to detect
# and use alternate remote domains to provide enterprise support.
GITHUB_DOMAIN = "github.com"
GITHUB_REMOTE_PATTERNS = [
    "^https://github\\.com/(.*)/(.*)\\.git$",
    "^git@github\\.com:(.*)/(.*)\\.git$",
]


def _token_from_gh() -> Optional[str]:

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


def _token_from_hub() -> Optional[str]:
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


def _token_from_env() -> Optional[str]:
    return os.environ.get(GITHUB_TOKEN_ENV_VAR)


def github_token() -> Optional[str]:
    return _token_from_env() or _token_from_gh() or _token_from_hub()


def fire_github_api_get_request(method: str, url: str, token: Optional[str], request_body: Optional[Dict[str, Any]] = None) -> Any:
    headers: Dict[str, str] = {
        'Content-type': 'application/json',
        'User-Agent': 'git-machete',
        'Accept': 'application/vnd.github.v3+json'
    }
    if token:
        headers['Authorization'] = 'Bearer ' + token

    host = 'api.' + GITHUB_DOMAIN
    conn: HTTPSConnection = HTTPSConnection(host)

    try:
        conn.request(method, url, body=json.dumps(request_body), headers=headers)

        response: HTTPResponse = conn.getresponse()
        parsed_response_body: Any = json.loads(response.read().decode())

        if 200 <= response.status < 300:
            return parsed_response_body
        elif response.status == 422 and parsed_response_body.get("message") == "Validation Failed":
            raise MacheteException("Cannot create pull request on untracked branch. \nPlease push your changes before making pull request.")
        else:
            first_line = fmt(f'GitHub API returned {response.status} HTTP status with error message: `{parsed_response_body.get("message")}`\n')
            if token:
                raise MacheteException(
                    first_line + fmt(f'Make sure that the token provided in `gh auth status` or `~/.config/hub` or <b>{GITHUB_TOKEN_ENV_VAR}</b> is valid '
                                     f'and allows for access to `{method}` https://{host}{url}`.'))
            else:
                raise MacheteException(
                    first_line + fmt(f'This repository might be private. Provide a GitHub API token with `repo` access via `gh` or `hub` or <b>{GITHUB_TOKEN_ENV_VAR}</b> env var.\n'
                                     'Visit `https://github.com/settings/tokens` to generate a new one.'))
    except OSError as e:
        raise MacheteException(f'Could not connect to {host}: {e}')
    finally:
        conn.close()


def create_pull_request(org: str, repo: str, head: str, base: str, title: str, description: str, draft: bool) -> GitHubPullRequest:
    token: Optional[str] = github_token()
    request_body: Dict[str, Any] = {
        'head': head,
        'base': base,
        'title': title,
        'body': description,
        'draft': draft
    }
    prs: List[GitHubPullRequest] = derive_pull_requests(org, repo)
    to_load: GitHubPullRequest = GitHubPullRequest(1, 'user', base, head, '')
    if not is_pr_already_created(to_load, prs):
        pr = fire_github_api_get_request('POST', f'/repos/{org}/{repo}/pulls', token, request_body)
        return parse_pr_json(pr)
    else:
        raise MacheteException('Given Pull Request is already created!')


def is_pr_already_created(pull: GitHubPullRequest, pull_requests: List[GitHubPullRequest]) -> bool:
    if not pull_requests:
        return False
    for pr in pull_requests:
        if all((pull.base == pr.base, pull.head == pr.head)):
            return True
    return False


def add_assignees_to_pull_request(org: str, repo: str, number: int, assignees: List[str]) -> None:
    token: Optional[str] = github_token()
    request_body: Dict[str, List[str]] = {
        'assignees': assignees
    }
    # Adding assignees is only available via the Issues API, not PRs API.
    fire_github_api_get_request('POST', f'/repos/{org}/{repo}/issues/{number}/assignees', token, request_body)


def add_reviewers_to_pull_request(org: str, repo: str, number: int, reviewers: List[str]) -> None:
    token: Optional[str] = github_token()
    request_body: Dict[str, List[str]] = {
        'reviewers': reviewers
    }
    fire_github_api_get_request('POST', f'/repos/{org}/{repo}/pulls/{number}/requested_reviewers', token, request_body)


def set_base_of_pull_request(org: str, repo: str, number: int, base: str) -> None:
    token: Optional[str] = github_token()
    request_body: Dict[str, str] = {'base': base}
    fire_github_api_get_request('PATCH', f'/repos/{org}/{repo}/pulls/{number}', token, request_body)


def set_milestone_of_pull_request(org: str, repo: str, number: int, milestone: str) -> None:
    token: Optional[str] = github_token()
    request_body: Dict[str, str] = {'milestone': milestone}
    # Setting milestone is only available via the Issues API, not PRs API.
    fire_github_api_get_request('PATCH', f'/repos/{org}/{repo}/issues/{number}', token, request_body)


def derive_pull_request_by_head(org: str, repo: str, head: str) -> Optional[GitHubPullRequest]:
    token: Optional[str] = github_token()
    prs = fire_github_api_get_request('GET', f'/repos/{org}/{repo}/pulls?head={org}:{head}', token)
    if len(prs) >= 1:
        return parse_pr_json(prs[0])
    else:
        return None


def derive_pull_requests(org: str, repo: str) -> List[GitHubPullRequest]:
    token: Optional[str] = github_token()
    prs = fire_github_api_get_request('GET', f'/repos/{org}/{repo}/pulls', token)
    return list(map(parse_pr_json, prs))


def derive_current_user_login() -> Optional[str]:
    token: Optional[str] = github_token()
    if not token:
        return None
    user = fire_github_api_get_request('GET', '/user', token)
    return str(user['login'])  # str() to satisfy mypy


def is_github_remote_url(url: str) -> bool:
    return any((re.match(pattern, url) for pattern in GITHUB_REMOTE_PATTERNS))


def parse_github_remote_url(github_url: str) -> Tuple[str, str]:
    for pattern in GITHUB_REMOTE_PATTERNS:
        match = re.match(pattern, github_url)
        if match:
            return match.group(1), match.group(2)
    raise MacheteException(f'{github_url} is not a GitHub remote URL')
