#!/usr/bin/env python

import json
import os
import re
# Deliberately NOT using much more convenient `requests` to avoid external dependencies
from http.client import HTTPResponse, HTTPSConnection
from typing import Dict, List, Optional, Any, Tuple

from git_machete.cmd import MacheteException, fmt


class GitHubPullRequest(object):
    def __init__(self, number: int, user: str, base: str, head: str):
        self.number = number
        self.user = user
        self.base = base
        self.head = head

    def __repr__(self) -> str:
        return f"PR #{self.number} by {self.user}: {self.head} -> {self.base}"


GITHUB_TOKEN_ENV_VAR = 'GITHUB_TOKEN'


def github_token() -> Optional[str]:
    return os.environ.get(GITHUB_TOKEN_ENV_VAR)


def fire_github_api_get_request(url: str, token: Optional[str]) -> Any:
    headers: Dict[str, str] = {
        'Content-type': 'application/json',
        'User-Agent': 'git-machete'
    }
    if token:
        headers['Authorization'] = 'Bearer ' + token

    host = 'api.github.com'
    conn: HTTPSConnection = HTTPSConnection(host)

    try:
        conn.request('GET', url, body=None, headers=headers)

        response: HTTPResponse = conn.getresponse()
        body: Any = json.loads(response.read().decode())

        if 200 <= response.status < 300:
            return body
        else:
            first_line = fmt(f'GitHub API returned {response.status} HTTP status with error message: `{body.get("message")}`.\n')
            if token:
                raise MacheteException(
                    first_line + fmt(f'Make sure that the token provided in <b>{GITHUB_TOKEN_ENV_VAR}</b> env var is valid '
                                     f'and allows for access to `GET https://{host}{url}`.'))
            else:
                raise MacheteException(
                    first_line + fmt(f'This repository might be private. Provide a GitHub API token with `repo` access in <b>{GITHUB_TOKEN_ENV_VAR}</b> env var.\n'
                                     'Visit `https://github.com/settings/tokens` to generate a new one.'))
    except OSError as e:
        raise MacheteException(f'Could not connect to {host}: {e}')
    finally:
        conn.close()


def derive_pull_requests(org: str, repo: str) -> List[GitHubPullRequest]:

    token: Optional[str] = github_token()
    prs = fire_github_api_get_request(f'/repos/{org}/{repo}/pulls', token)
    return [GitHubPullRequest(int(pr['number']), pr['user']['login'], pr['base']['ref'], pr['head']['ref']) for pr in prs]


def derive_current_user_login() -> Optional[str]:
    token: Optional[str] = github_token()
    if not token:
        return None
    user = fire_github_api_get_request('/user', token)
    return str(user['login'])  # str() to satisfy mypy


GITHUB_REMOTE_PATTERNS = [
    '^https://github\\.com/(.*)/(.*)\\.git$',
    '^git@github\\.com:(.*)/(.*)\\.git$'
]


def is_github_remote_url(url: str) -> bool:

    return any((re.match(pattern, url) for pattern in GITHUB_REMOTE_PATTERNS))


def parse_github_remote_url(url: str) -> Optional[Tuple[str, str]]:

    for pattern in GITHUB_REMOTE_PATTERNS:
        match = re.match(pattern, url)
        if match:
            return match.group(1), match.group(2)
    return None
