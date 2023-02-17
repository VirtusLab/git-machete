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
from typing import Any, Dict, List, Optional

from git_machete import git_config_keys
from git_machete.exceptions import (MacheteException,
                                    UnprocessableEntityHTTPError)
from git_machete.git_operations import GitContext, LocalBranchShortName
from git_machete.utils import bold, debug, fmt, warn


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
        self.number = number
        self.user = user
        self.base = base
        self.head = head
        self.html_url = html_url
        self.state = state
        self.full_repository_name = full_repository_name
        self.repository_url = repository_url

    @classmethod
    def from_json(cls,
                  pr_json: Dict[str, Any]
                  ) -> "GitHubPullRequest":
        return cls(number=int(pr_json['number']),
                   user=pr_json['user']['login'],
                   base=pr_json['base']['ref'],
                   head=pr_json['head']['ref'],
                   html_url=pr_json['html_url'],
                   state=pr_json['state'],
                   full_repository_name=pr_json['head']['repo']['full_name'] if pr_json['head']['repo'] else None,
                   repository_url=pr_json['head']['repo']['html_url'] if pr_json['head']['repo'] else None)

    def __repr__(self) -> str:
        return f"PR #{self.number} by {self.user}: {self.head} -> {self.base}"


class RemoteAndOrganizationAndRepository:
    def __init__(self,
                 remote: Optional[str],
                 organization: Optional[str],
                 repository: Optional[str]
                 ) -> None:
        self.remote = remote
        self.organization = organization
        self.repository = repository

    @classmethod
    def from_config(cls,
                    git: GitContext
                    ) -> "RemoteAndOrganizationAndRepository":
        return cls(remote=git.get_config_attr_or_none(key=git_config_keys.GITHUB_REMOTE),
                   organization=git.get_config_attr_or_none(key=git_config_keys.GITHUB_ORGANIZATION),
                   repository=git.get_config_attr_or_none(key=git_config_keys.GITHUB_REPOSITORY))

    @classmethod
    def from_url(cls,
                 domain: str,
                 url: str,
                 remote: str
                 ) -> Optional["RemoteAndOrganizationAndRepository"]:
        for pattern in github_remote_url_patterns(domain):
            match = re.match(pattern, url)
            if match:
                org = match.group(1)
                repo = match.group(2)
                return cls(remote=remote,
                           organization=org,
                           repository=repo if repo[-4:] != '.git' else repo[:-4])
        return None


class GitHubToken:
    GITHUB_TOKEN_ENV_VAR = 'GITHUB_TOKEN'

    def __init__(self,
                 value: Optional[str],
                 provider: Optional[str]
                 ) -> None:
        self.__value: Optional[str] = value
        self.__provider: Optional[str] = provider
        debug("authenticating via " + self.provider)

    @property
    def value(self) -> Optional[str]:
        return self.__value

    @property
    def provider(self) -> Optional[str]:
        return self.__provider

    @classmethod
    def from_domain(cls, domain: str) -> Optional["GitHubToken"]:
        return (cls.__get_token_from_env() or
                cls.__get_token_from_file_in_home_directory(domain) or
                cls.__get_token_from_gh(domain) or
                cls.__get_token_from_hub(domain))

    @classmethod
    def __get_token_from_env(cls) -> Optional["GitHubToken"]:
        debug(f"1. Trying to authenticate via `{cls.GITHUB_TOKEN_ENV_VAR}` environment variable...")
        github_token = os.environ.get(cls.GITHUB_TOKEN_ENV_VAR)
        if github_token:
            cls(value=github_token,
                provider=f'`{cls.GITHUB_TOKEN_ENV_VAR}` environment variable')
        return None

    @classmethod
    def __get_token_from_file_in_home_directory(cls, domain: str) -> Optional["GitHubToken"]:
        debug("2. Trying to authenticate via `~/.github-token`...")
        required_file_name = '.github-token'
        provider = f'auth token for {domain} from `~/.github-token`'
        file_full_path = os.path.expanduser(f'~/{required_file_name}')

        if os.path.isfile(file_full_path):
            with open(file_full_path) as file:
                # ~/.github-token is a file with a structure similar to:
                #
                # ghp_mytoken_for_github_com
                # ghp_myothertoken_for_git_example_org git.example.org
                # ghp_yetanothertoken_for_git_example_com git.example.com

                for line in file.readlines():
                    if line.endswith(" " + domain):
                        token = line.split(" ")[0]
                        return cls(value=token, provider=provider)
                    elif domain == GitHubClient.DEFAULT_GITHUB_DOMAIN and " " not in line.rstrip():
                        return cls(value=line.rstrip(), provider=provider)
        return None

    @classmethod
    def __get_token_from_gh(cls, domain: str) -> Optional["GitHubToken"]:
        debug("3. Trying to authenticate via `gh` GitHub CLI...")
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
            return cls(value=match.group(1),
                       provider=f'auth token for {domain} from `hub` GitHub CLI')
        return None

    @classmethod
    def __get_token_from_hub(cls, domain: str) -> Optional["GitHubToken"]:
        debug("4. Trying to authenticate via `hub` GitHub CLI...")
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
                        result = re.sub(' *oauth_token:  *', '', line).rstrip().replace('"', '')
                        return cls(value=result,
                                   provider=f'auth token for {domain} from `hub` GitHub CLI')
        return None

    @classmethod
    def get_possible_providers(cls) -> str:
        return (f'\n\t1. `{cls.GITHUB_TOKEN_ENV_VAR}` environment variable.\n'
                '\t2. Content of the `~/.github-token` file.\n'
                '\t3. Current auth token from the `gh` GitHub CLI.\n'
                '\t4. Current auth token from the `hub` GitHub CLI.\n')


class GitHubClient:
    DEFAULT_GITHUB_DOMAIN = "github.com"

    def __init__(self,
                 domain: str,
                 organization: str,
                 repository: str
                 ) -> None:
        self.__domain: str = domain
        self.__organization: str = organization
        self.__repository: str = repository
        self.__token: Optional[GitHubToken] = GitHubToken.from_domain(domain)

    @property
    def organization(self) -> str:
        return self.__organization

    @property
    def repository(self) -> str:
        return self.__repository

    def __fire_github_api_request(self,
                                  method: str,
                                  path: str,
                                  request_body: Optional[Dict[str, Any]] = None
                                  ) -> Any:
        headers: Dict[str, str] = {
            'Content-type': 'application/json',
            'User-Agent': 'git-machete',
            'Accept': 'application/vnd.github.v3+json'
        }
        if self.__token:
            headers['Authorization'] = 'Bearer ' + self.__token.value

        if self.__domain == self.DEFAULT_GITHUB_DOMAIN:
            url_prefix = 'https://api.' + self.__domain
        else:
            url_prefix = 'https://' + self.__domain + '/api/v3'

        url = url_prefix + path
        json_body: Optional[str] = json.dumps(request_body) if request_body else None
        http_request = urllib.request.Request(url, headers=headers, data=json_body.encode() if json_body else None, method=method.upper())
        debug(f'firing a {method} request to {url} with {"a" if self.__token else "no"} '
              f'bearer token and request body {json_body or "<none>"}')

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
                        return parsed_response_body + self.__fire_github_api_request(method, next_page_path, request_body)
                return parsed_response_body
        except urllib.error.HTTPError as err:
            if err.code == http.HTTPStatus.UNPROCESSABLE_ENTITY:
                error_response = json.loads(err.read().decode())
                error_reason: str = self.__extract_failure_info_from_422(error_response)
                raise UnprocessableEntityHTTPError(error_reason)
            elif err.code in (http.HTTPStatus.UNAUTHORIZED, http.HTTPStatus.FORBIDDEN):
                first_line = f'GitHub API returned `{err.code}` HTTP status with error message: `{err.reason}`\n'
                if self.__token:
                    raise MacheteException(first_line + 'Make sure that the GitHub API token '
                                                        f'provided by the {self.__token.provider} '
                                                        f'is valid and allows for access to `{method.upper()}` `{url_prefix}{path}`.\n'
                                                        'You can also use a different token provider, available providers can be found '
                                                        'when running `git machete help github`.')
                else:
                    raise MacheteException(
                        first_line + f'You might not have the required permissions for this repository.\n'
                                     f'Provide a GitHub API token with `repo` access via {self.__token.provider}.\n'
                                     f'Visit `https://{self.__domain}/settings/tokens` to generate a new one.\n'
                                     'You can also use a different token provider, available providers can be found '
                                     'when running `git machete help github`.')
            elif err.code == http.HTTPStatus.NOT_FOUND:
                raise MacheteException(
                    f'`{method} {url}` request ended up in 404 response from GitHub. A valid GitHub API token is required.\n'
                    f'Provide a GitHub API token with `repo` access via one of the: {GitHubToken.get_possible_providers()} '
                    f'Visit `https://{self.__domain}/settings/tokens` to generate a new one.')  # TODO (#164): make dedicated exception here
            elif err.code == http.HTTPStatus.TEMPORARY_REDIRECT:
                if err.headers['Location'] is not None:
                    if len(err.headers['Location'].split('/')) >= 5:
                        current_repo_and_org = self.get_repo_and_org_names_by_id(err.headers['Location'].split('/')[4])
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
                     f'New organization = {bold(current_repo_and_org.split("/")[0])}, '
                     f'new repository = {bold(current_repo_and_org.split("/")[1])}.\n'
                     'You can update your remote repository via: `git remote set-url <remote_name> <new_repository_url>`.',
                     end='')
                return self.__fire_github_api_request(method=method, path=new_path, request_body=request_body)
            else:
                first_line = fmt(f'GitHub API returned `{err.code}` HTTP status with error message: `{err.reason}`\n')
                raise MacheteException(first_line + "Please open an issue regarding this topic under link: "
                                                    "https://github.com/VirtusLab/git-machete/issues/new")
        except OSError as e:
            raise MacheteException(f'Could not connect to {url_prefix}: {e}')

    @staticmethod
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

    def create_pull_request(self,
                            head: str,
                            base: str,
                            title: str,
                            description: str,
                            draft: bool
                            ) -> GitHubPullRequest:
        request_body: Dict[str, Any] = {
            'head': head,
            'base': base,
            'title': title,
            'body': description,
            'draft': draft
        }
        pr = self.__fire_github_api_request(method='POST',
                                            path=f'/repos/{self.__organization}/{self.__repository}/pulls',
                                            request_body=request_body)
        return GitHubPullRequest.from_json(pr)

    def add_assignees_to_pull_request(self,
                                      number: int,
                                      assignees: List[str]
                                      ) -> None:
        request_body: Dict[str, List[str]] = {
            'assignees': assignees
        }
        # Adding assignees is only available via the Issues API, not PRs API.
        self.__fire_github_api_request(method='POST',
                                       path=f'/repos/{self.__organization}/{self.__repository}/issues/{number}/assignees',
                                       request_body=request_body)

    def add_reviewers_to_pull_request(self,
                                      number: int,
                                      reviewers: List[str]
                                      ) -> None:
        request_body: Dict[str, List[str]] = {
            'reviewers': reviewers
        }
        self.__fire_github_api_request(method='POST',
                                       path=f'/repos/{self.__organization}/{self.__repository}/pulls/{number}/requested_reviewers',
                                       request_body=request_body)

    def set_base_of_pull_request(self,
                                 number: int,
                                 base: LocalBranchShortName
                                 ) -> None:
        request_body: Dict[str, str] = {'base': base}
        self.__fire_github_api_request(method='PATCH',
                                       path=f'/repos/{self.__organization}/{self.__repository}/pulls/{number}',
                                       request_body=request_body)

    def set_milestone_of_pull_request(self,
                                      number: int,
                                      milestone: str
                                      ) -> None:
        request_body: Dict[str, str] = {'milestone': milestone}
        # Setting milestone is only available via the Issues API, not PRs API.
        self.__fire_github_api_request(method='PATCH',
                                       path=f'/repos/{self.__organization}/{self.__repository}/issues/{number}',
                                       request_body=request_body)

    def derive_pull_request_by_head(self,
                                    head: LocalBranchShortName
                                    ) -> Optional[GitHubPullRequest]:
        path = f'/repos/{self.__organization}/{self.__repository}/pulls?head={self.__organization}:{head}'
        prs = self.__fire_github_api_request(method='GET',
                                             path=path)
        if len(prs) >= 1:
            return GitHubPullRequest.from_json(prs[0])
        else:
            return None

    def derive_pull_requests(self) -> List[GitHubPullRequest]:
        # As of Dec 2022, GitHub API never returns more than 100 PRs, even if per_page>100.
        prs = self.__fire_github_api_request(method='GET',
                                             path=f'/repos/{self.__organization}/{self.__repository}/pulls?per_page=100')
        return list(map(GitHubPullRequest.from_json, prs))

    def derive_current_user_login(self) -> Optional[str]:
        if not self.__token:
            return None
        user = self.__fire_github_api_request(method='GET',
                                              path='/user')
        return str(user['login'])  # str() to satisfy mypy

    def get_pull_request_by_number_or_none(self,
                                           number: int
                                           ) -> Optional[GitHubPullRequest]:
        try:
            path = f'/repos/{self.__organization}/{self.__repository}/pulls/{number}'
            pr_json: Dict[str, Any] = self.__fire_github_api_request(method='GET',
                                                                     path=path)
            return GitHubPullRequest.from_json(pr_json)
        except MacheteException:
            return None

    def get_repo_and_org_names_by_id(self,
                                     repo_id: str
                                     ) -> str:
        repo = self.__fire_github_api_request(path='GET',
                                              method=f'/repositories/{repo_id}')
        return str(repo['full_name'])

    @staticmethod
    def checkout_pr_refs(git: GitContext,
                         remote: str,
                         pr_number: int,
                         branch: LocalBranchShortName
                         ) -> None:
        git.fetch_ref(remote, f'pull/{pr_number}/head:{branch}')
        git.checkout(branch)


def github_remote_url_patterns(domain: str) -> List[str]:
    # GitHub DOES NOT allow trailing `.git` suffix in the repository name (also applies to multiple repetitions e.g. `repo_name.git.git`)
    domain_regex = re.escape(domain)
    return [
        f"^https://.*@{domain_regex}/(.*)/(.*)$",
        f"^https://{domain_regex}/(.*)/(.*)$",
        f"^git@{domain_regex}:(.*)/(.*)$",
        f"^ssh://git@{domain_regex}/(.*)/(.*)$"
    ]


def is_github_remote_url(domain: str,
                         url: str
                         ) -> bool:
    return any((re.match(pattern, url) for pattern in github_remote_url_patterns(domain)))
