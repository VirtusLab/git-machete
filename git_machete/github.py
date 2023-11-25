import http
import json
import os
import re
import shutil
import urllib.error
# Deliberately NOT using much more convenient `requests` to avoid external dependencies in production code
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from .exceptions import MacheteException, UnprocessableEntityHTTPError
from .git_operations import GitContext, LocalBranchShortName
from .utils import bold, compact_dict, debug, fmt, popen_cmd, warn


class GitHubPullRequest(NamedTuple):
    number: int
    user: str
    base: str
    head: str
    html_url: str
    state: str
    description: Optional[str]
    full_repository_name: str
    repository_url: str

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
                   description=pr_json['body'],
                   full_repository_name=pr_json['head']['repo']['full_name'] if pr_json['head']['repo'] else None,
                   repository_url=pr_json['head']['repo']['html_url'] if pr_json['head']['repo'] else None)

    def __repr__(self) -> str:
        return f"PR #{self.number} by {self.user}: {self.head} -> {self.base}"


class OrganizationAndRepository(NamedTuple):
    organization: str
    repository: str

    @classmethod
    def from_url(cls, domain: str, url: str) -> Optional["OrganizationAndRepository"]:
        url = url if url.endswith('.git') else url + '.git'
        for pattern in github_remote_url_patterns(domain):
            match = re.match(pattern, url)
            if match:
                org = match.group(1)
                repo = match.group(2)
                return cls(organization=org, repository=repo if repo[-4:] != '.git' else repo[:-4])
        return None


class OrganizationAndRepositoryAndRemote(NamedTuple):
    organization: str
    repository: str
    remote: str


GITHUB_TOKEN_ENV_VAR = 'GITHUB_TOKEN'


class GitHubToken(NamedTuple):
    value: str
    provider: str

    @classmethod
    def for_domain(cls, domain: str) -> Optional["GitHubToken"]:
        return (cls.__get_token_from_env() or
                cls.__get_token_from_file_in_home_directory(domain) or
                cls.__get_token_from_gh(domain) or
                cls.__get_token_from_hub(domain))

    @classmethod
    def __get_token_from_env(cls) -> Optional["GitHubToken"]:
        debug(f"1. Trying to find token in `{GITHUB_TOKEN_ENV_VAR}` environment variable...")
        github_token = os.environ.get(GITHUB_TOKEN_ENV_VAR)
        if github_token:
            return cls(value=github_token,
                       provider=f'`{GITHUB_TOKEN_ENV_VAR}` environment variable')
        return None

    @classmethod
    def __get_token_from_file_in_home_directory(cls, domain: str) -> Optional["GitHubToken"]:
        debug("2. Trying to find token in `~/.github-token`...")
        required_file_name = '.github-token'
        provider = f'auth token for {domain} from `~/.github-token`'
        file_full_path = os.path.expanduser(f'~/{required_file_name}')

        if os.path.isfile(file_full_path):
            debug(f"  File `{file_full_path}` exists")
            with open(file_full_path) as file:
                # ~/.github-token is a file with a structure similar to:
                #
                # ghp_mytoken_for_github_com
                # ghp_myothertoken_for_git_example_org git.example.org
                # ghp_yetanothertoken_for_git_example_com git.example.com

                for line in file.readlines():
                    if line.rstrip().endswith(" " + domain):
                        token = line.split(" ")[0]
                        return cls(value=token, provider=provider)
                    elif domain == GitHubClient.DEFAULT_GITHUB_DOMAIN and " " not in line.rstrip():
                        return cls(value=line.rstrip(), provider=provider)
        return None

    @classmethod
    def __get_token_from_gh(cls, domain: str) -> Optional["GitHubToken"]:
        debug("3. Trying to find token via `gh` GitHub CLI...")
        # Abort without error if `gh` isn't available
        gh = shutil.which('gh')
        if not gh:
            return None

        gh_version_returncode, gh_version_stdout, _ = popen_cmd(gh, "--version")
        if gh_version_returncode != 0:
            return None

        # The stdout of `gh --version` looks like:
        #
        # gh version 2.18.0 (2022-10-18)
        # https://github.com/cli/cli/releases/tag/v2.18.0

        gh_version_match = re.search(r"gh version (\d+).(\d+).(\d+) ", gh_version_stdout)
        gh_version: Optional[Tuple[int, int, int]] = None
        if gh_version_match:  # pragma: no branch
            gh_version = int(gh_version_match.group(1)), int(gh_version_match.group(2)), int(gh_version_match.group(3))

        if gh_version and gh_version >= (2, 17, 0):
            gh_token_returncode, gh_token_stdout, _ = \
                popen_cmd(gh, "auth", "token", "--hostname", domain, hide_debug_output=True)
            if gh_token_returncode != 0:
                return None
            if gh_token_stdout:
                return cls(value=gh_token_stdout.strip(), provider=f'auth token for {domain} from `gh` GitHub CLI')
        else:
            gh_token_returncode, _, gh_token_stderr = \
                popen_cmd(gh, "auth", "status", "--hostname", domain, "--show-token", hide_debug_output=True)
            if gh_token_returncode != 0:
                return None

            # The stderr of `gh auth status --show-token` looks like:
            #
            # {domain}:
            #   ✓ Logged in to {domain} as {username} ({config_path})
            #   ✓ Git operations for {domain} configured to use {protocol} protocol.
            #   ✓ Token: <token>
            #
            # with non-zero exit code on failure.
            # Note that since v2.31.0 (https://github.com/cli/cli/pull/7540), this output goes to stdout instead.
            # Still, we're only handling here the versions < 2.17.0 that don't provide `gh auth token` yet.
            match = re.search(r"Token: (\w+)", gh_token_stderr)
            if match:
                return cls(value=match.group(1), provider=f'auth token for {domain} from `gh` GitHub CLI')
        return None

    @classmethod
    def __get_token_from_hub(cls, domain: str) -> Optional["GitHubToken"]:
        debug("4. Trying to find token via `hub` GitHub CLI...")
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
                        result = re.sub(' *oauth_token: +', '', line).rstrip().replace('"', '')
                        return cls(value=result,
                                   provider=f'auth token for {domain} from `hub` GitHub CLI')
        return None

    @classmethod
    def get_possible_providers(cls) -> str:
        return (f'\n\t1. `{GITHUB_TOKEN_ENV_VAR}` environment variable\n'
                '\t2. Content of the `~/.github-token` file\n'
                '\t3. Current auth token from the `gh` GitHub CLI\n'
                '\t4. Current auth token from the `hub` GitHub CLI\n')


class GitHubClient:
    DEFAULT_GITHUB_DOMAIN = "github.com"
    # As of Dec 2022, GitHub API never returns more than 100 PRs, even if per_page query param is above 100.
    MAX_PULLS_PER_PAGE_COUNT = 100

    def __init__(self, domain: str, organization: str, repository: str) -> None:
        self.__domain: str = domain
        self.__organization: str = organization
        self.__repository: str = repository
        self.__token: Optional[GitHubToken] = GitHubToken.for_domain(domain)

    @property
    def organization(self) -> str:
        return self.__organization

    @property
    def repository(self) -> str:
        return self.__repository

    def __fire_github_api_request(self, method: str, path: str, request_body: Optional[Dict[str, Any]] = None) -> Any:
        headers: Dict[str, str] = {
            'Content-type': 'application/json',
            'User-Agent': 'git-machete',
            'Accept': 'application/vnd.github.v3+json'
        }
        if self.__token:
            headers['Authorization'] = 'Bearer ' + self.__token.value

        if self.__domain == self.DEFAULT_GITHUB_DOMAIN:
            url_prefix = 'https://api.' + self.__domain
        elif path == '/graphql':
            url_prefix = 'https://' + self.__domain + '/api'
        else:
            url_prefix = 'https://' + self.__domain + '/api/v3'

        url = url_prefix + path
        json_body: Optional[str] = json.dumps(request_body) if request_body else None
        http_request = urllib.request.Request(url, headers=headers, data=json_body.encode() if json_body else None, method=method.upper())
        debug(f'firing a {method} request to {url} with {"a" if self.__token else "no"} '
              f'bearer token and request body {compact_dict(request_body) if request_body else "<none>"}')

        try:
            with urllib.request.urlopen(http_request) as response:
                parsed_response_body: Any = json.loads(response.read().decode())
                # https://docs.github.com/en/rest/guides/using-pagination-in-the-rest-api?apiVersion=2022-11-28#using-link-headers
                link_header: str = response.info()["link"]
                if link_header:
                    url_prefix_regex = re.escape(url_prefix)
                    match = re.search(f'<{url_prefix_regex}(/[^>]+)>; rel="next"', link_header)
                    if match:  # pragma: no branch; there should always be a match
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
                last_line = 'You can also use a different token provider, available providers can be found via `git machete help github`.'
                if self.__token:
                    raise MacheteException(
                        first_line + 'Make sure that the GitHub API token '
                                     f'provided by the {self.__token.provider} '
                                     f'is valid and allows for access to `{method.upper()}` `{url_prefix}{path}`.\n' + last_line)
                else:
                    raise MacheteException(
                        first_line + 'You might not have the required permissions for this repository.\n'
                                     'Provide a GitHub API token with `repo` access.\n'
                                     f'Visit `https://{self.__domain}/settings/tokens` to generate a new one.\n' + last_line)
            elif err.code == http.HTTPStatus.NOT_FOUND:
                # TODO (#164): make a dedicated exception here
                raise MacheteException(
                    f'`{method} {url}` request ended up in 404 response from GitHub. A valid GitHub API token is required.\n'
                    f'Provide a GitHub API token with `repo` access via one of the: {GitHubToken.get_possible_providers()} '
                    f'Visit `https://{self.__domain}/settings/tokens` to generate a new one.')
            # See https://stackoverflow.com/a/62385184 for why 307 for POST/PATCH isn't automatically followed by urllib,
            # unlike 307 for GET, or 301/302 for all HTTP methods.
            elif err.code == http.HTTPStatus.TEMPORARY_REDIRECT:
                # err.headers is a case-insensitive dict of class Message with the `__getitem__` and `get` functions implemented in
                # https://github.com/python/cpython/blob/3.10/Lib/email/message.py
                location = err.headers['Location']
                new_repo_and_org = None
                if location is not None:
                    # The URL returned in the `Location` header is of the form "https://api.github.com/repositories/453977473".
                    # It doesn't contain the info about the new org/repo name, which we'd like to display to the user in a warning.
                    match = re.search('/repositories/([0-9]+)/', location)
                    if match:  # pragma: no branch
                        new_repo_and_org = self.get_repo_and_org_names_by_id(match.group(1))
                else:  # pragma: no cover; unlikely to ever happen
                    first_line = fmt(f'GitHub API returned `{err.code}` HTTP status with error message: `{err.reason}`\n')
                    raise MacheteException(
                        first_line + 'It looks like the organization or repository name got changed recently and is outdated.\n'
                                     'Update your remote repository manually via: `git remote set-url <remote_name> <new_repository_url>`.')
                new_path = re.sub("https://[^/]+", "", location)
                result = self.__fire_github_api_request(method=method, path=new_path, request_body=request_body)
                if new_repo_and_org:  # pragma: no branch
                    warn(f'GitHub API returned `{err.code}` HTTP status with error message: `{err.reason}`.\n'
                         'It looks like the organization or repository name got changed recently and is outdated.\n'
                         f'New organization is {bold(new_repo_and_org.split("/")[0])} and '
                         f'new repository is {bold(new_repo_and_org.split("/")[1])}.\n'
                         'You can update your remote repository via: `git remote set-url <remote_name> <new_repository_url>`.')
                return result
            else:  # pragma: no cover
                first_line = fmt(f'GitHub API returned `{err.code}` HTTP status with error message: `{err.reason}`\n')
                raise MacheteException(first_line + "Please open an issue regarding this topic under link: "
                                                    "https://github.com/VirtusLab/git-machete/issues/new")
        except OSError as e:  # pragma: no cover
            raise MacheteException(f'Could not connect to {url_prefix}: {e}')

    def __fire_github_graphql_api_request(self, query: str) -> Any:
        return self.__fire_github_api_request(method='POST', path='/graphql', request_body={"query": query})

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
        else:
            return str(response)

    def create_pull_request(self, head: str, base: str, title: str, description: str, draft: bool) -> GitHubPullRequest:
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

    def add_assignees_to_pull_request(self, number: int, assignees: List[str]) -> None:
        request_body: Dict[str, List[str]] = {
            'assignees': assignees
        }
        # Adding assignees is only available via the Issues API, not PRs API.
        self.__fire_github_api_request(method='POST',
                                       path=f'/repos/{self.__organization}/{self.__repository}/issues/{number}/assignees',
                                       request_body=request_body)

    def add_reviewers_to_pull_request(self, number: int, reviewers: List[str]) -> None:
        request_body: Dict[str, List[str]] = {
            'reviewers': reviewers
        }
        self.__fire_github_api_request(method='POST',
                                       path=f'/repos/{self.__organization}/{self.__repository}/pulls/{number}/requested_reviewers',
                                       request_body=request_body)

    def set_base_of_pull_request(self, number: int, base: LocalBranchShortName) -> None:
        request_body: Dict[str, str] = {'base': base}
        self.__fire_github_api_request(method='PATCH',
                                       path=f'/repos/{self.__organization}/{self.__repository}/pulls/{number}',
                                       request_body=request_body)

    def set_description_of_pull_request(self, number: int, description: str) -> None:
        request_body: Dict[str, str] = {'body': description}
        self.__fire_github_api_request(method='PATCH',
                                       path=f'/repos/{self.__organization}/{self.__repository}/pulls/{number}',
                                       request_body=request_body)

    def set_milestone_of_pull_request(self, number: int, milestone: str) -> None:
        request_body: Dict[str, str] = {'milestone': milestone}
        # Setting milestone is only available via the Issues API, not PRs API.
        self.__fire_github_api_request(method='PATCH',
                                       path=f'/repos/{self.__organization}/{self.__repository}/issues/{number}',
                                       request_body=request_body)

    # As of September 2023, REST (v3) GitHub API does **not** allow for setting PR draft status,
    # only for creating a draft PR or retrieving draft status on an existing PR.
    # See https://docs.github.com/en/rest/pulls/pulls?apiVersion=2022-11-28#update-a-pull-request
    # and https://github.com/orgs/community/discussions/45174.
    # GraphQL (v4) API mutation needs to be used for that purpose.
    def set_draft_status_of_pull_request(self, number: int, target_draft_status: bool) -> bool:
        """Returns true if PR had a different draft status, and draft status has been toggled.
        Returns false if PR already had the desired draft status, and hence draft status has NOT been toggled."""

        # This query is required to get the GraphQL-specific id of the PR
        query = f"""query {{
            repository(owner: "{self.organization}", name: "{self.repository}") {{
                pullRequest(number: {number}) {{
                    id
                    isDraft
                }}
            }}
        }}"""
        response = self.__fire_github_graphql_api_request(query)
        debug(f"query response is {response}")
        is_draft = response["data"]["repository"]["pullRequest"]["isDraft"]
        if is_draft and target_draft_status is True:
            debug(f"PR #{number} is already a draft")
            return False
        if not is_draft and target_draft_status is False:
            # This case is not covered by tests since there's currently no scenario
            # in `git machete github restack-pr` that could reach here.
            debug(f"PR #{number} is already ready for review")
            return False

        # Ids are of the form "PR_kwDOB1DpPc5bDwiF"
        graphql_id = response["data"]["repository"]["pullRequest"]["id"]

        mutation = "convertPullRequestToDraft" if target_draft_status else "markPullRequestReadyForReview"
        query = f"""mutation {{
            {mutation}(input: {{pullRequestId: "{graphql_id}"}}) {{
                pullRequest {{
                    id
                    isDraft
                }}
            }}
        }}"""
        response = self.__fire_github_graphql_api_request(query)
        debug(f"mutation response is {response}")
        return True

    def get_open_pull_requests_by_head(self, head: LocalBranchShortName) -> List[GitHubPullRequest]:
        path = f'/repos/{self.__organization}/{self.__repository}/pulls?head={self.__organization}:{head}'
        prs = self.__fire_github_api_request(method='GET', path=path)
        return [GitHubPullRequest.from_json(pr) for pr in prs]

    def get_open_pull_requests(self) -> List[GitHubPullRequest]:
        path = f'/repos/{self.__organization}/{self.__repository}/pulls?per_page={self.MAX_PULLS_PER_PAGE_COUNT}'
        prs = self.__fire_github_api_request(method='GET', path=path)
        return list(map(GitHubPullRequest.from_json, prs))

    def get_current_user_login(self) -> Optional[str]:
        if not self.__token:
            return None
        user = self.__fire_github_api_request(method='GET', path='/user')
        return str(user['login'])  # str() to satisfy mypy

    def get_pull_request_by_number_or_none(self, number: int) -> Optional[GitHubPullRequest]:
        try:
            path = f'/repos/{self.__organization}/{self.__repository}/pulls/{number}'
            pr_json: Dict[str, Any] = self.__fire_github_api_request(method='GET', path=path)
            return GitHubPullRequest.from_json(pr_json)
        except MacheteException:
            return None

    def get_repo_and_org_names_by_id(self, repo_id: str) -> str:
        repo = self.__fire_github_api_request(method='GET', path=f'/repositories/{repo_id}')
        return str(repo['full_name'])

    @staticmethod
    def checkout_pr_refs(git: GitContext, remote: str, pr_number: int, branch: LocalBranchShortName) -> None:
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


def is_github_remote_url(domain: str, url: str) -> bool:
    url = url if url.endswith('.git') else url + '.git'
    return any((re.match(pattern, url) for pattern in github_remote_url_patterns(domain)))
