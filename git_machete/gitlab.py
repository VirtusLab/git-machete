import http
import json
import os
import re
import shutil
import urllib.error
import urllib.parse
# Deliberately NOT using much more convenient `requests` to avoid external dependencies in production code
import urllib.request
from typing import Any, Dict, List, NamedTuple, Optional

from git_machete.code_hosting import (CodeHostingClient,
                                      CodeHostingGitConfigKeys,
                                      CodeHostingSpec,
                                      OrganizationAndRepositoryAndGitUrl,
                                      PullRequest)
from git_machete.exceptions import MacheteException, UnexpectedMacheteException
from git_machete.git_operations import LocalBranchShortName
from git_machete.utils import compact_dict, debug, map_truthy_only, popen_cmd

GITLAB_TOKEN_ENV_VAR = 'GITLAB_TOKEN'


class GitLabToken(NamedTuple):
    value: str
    provider: str

    @classmethod
    def for_domain(cls, domain: str) -> Optional["GitLabToken"]:
        return (cls.__get_token_from_env() or
                cls.__get_token_from_file_in_home_directory(domain) or
                cls.__get_token_from_glab(domain))

    @classmethod
    def __get_token_from_env(cls) -> Optional["GitLabToken"]:
        debug(f"1. Trying to find token in `{GITLAB_TOKEN_ENV_VAR}` environment variable...")
        gitlab_token = os.environ.get(GITLAB_TOKEN_ENV_VAR)
        if gitlab_token:
            return cls(value=gitlab_token,
                       provider=f'`{GITLAB_TOKEN_ENV_VAR}` environment variable')
        return None

    @classmethod
    def __get_token_from_file_in_home_directory(cls, domain: str) -> Optional["GitLabToken"]:
        debug("2. Trying to find token in `~/.gitlab-token`...")
        required_file_name = '.gitlab-token'
        provider = f'auth token for {domain} from `~/.gitlab-token`'
        file_full_path = os.path.expanduser(f'~/{required_file_name}')

        if os.path.isfile(file_full_path):
            debug(f"  File `{file_full_path}` exists")
            with open(file_full_path) as file:
                # ~/.gitlab-token is a file with a structure similar to:
                #
                # glpat-mytoken_for_gitlab_com
                # glpat-myothertoken_for_git_example_org git.example.org
                # glpat-yetanothertoken_for_git_example_com git.example.com

                for line in file.readlines():
                    if line.rstrip().endswith(" " + domain):
                        token = line.split(" ")[0]
                        return cls(value=token, provider=provider)
                    elif domain == GitLabClient.DEFAULT_GITLAB_DOMAIN and " " not in line.rstrip():
                        return cls(value=line.rstrip(), provider=provider)
        return None

    @classmethod
    def __get_token_from_glab(cls, domain: str) -> Optional["GitLabToken"]:
        debug("3. Trying to find token via `glab` GitLab CLI...")
        # Abort without error if `glab` isn't available
        glab = shutil.which('glab')
        if not glab:
            return None

        glab_token_returncode, _, glab_token_stderr = \
            popen_cmd(glab, "auth", "status", "--hostname", domain, "--show-token", hide_debug_output=True)
        if glab_token_returncode != 0:
            return None

        # The stderr of `glab auth status --show-token` looks like:
        #
        # {domain}:
        #   ✓ Logged in to {domain} as {username} ({config_path})
        #   ✓ Git operations for {domain} configured to use {protocol} protocol.
        #   ✓ Token: <token>
        #
        # with non-zero exit code on failure.
        # As of glab version 1.36.0, this output goes to stderr.
        match = re.search(r"Token: ([\w-]+)", glab_token_stderr)
        if match:
            return cls(value=match.group(1), provider=f'auth token for {domain} from `glab` GitLab CLI')
        return None


class GitLabClient(CodeHostingClient):
    DEFAULT_GITLAB_DOMAIN = "gitlab.com"
    MAX_PULLS_PER_PAGE_COUNT = 100

    def __init__(self, spec: CodeHostingSpec, domain: str, organization: str, repository: str) -> None:
        super().__init__(spec, domain, organization, repository)
        self.__token: Optional[GitLabToken] = GitLabToken.for_domain(domain)

    @classmethod
    def spec(cls) -> CodeHostingSpec:
        return CodeHostingSpec(
            base_branch_name='target',
            client_class=cls,
            default_domain=cls.DEFAULT_GITLAB_DOMAIN,
            display_name='GitLab',
            git_machete_command='gitlab',
            head_branch_name='source',
            organization_name='namespace',
            # https://docs.gitlab.com/ee/user/project/description_templates.html#create-a-merge-request-template
            # https://docs.gitlab.com/ee/user/project/description_templates.html#set-a-default-template-for-merge-requests-and-issues
            # Actual MR template resolution for GitLab has a complex hierarchy of templates, including
            # project-level, group-level and instance-level templates - and also the ability to "choose" a template.
            # To keep things simple, we'll only support the "Default.md" template for now.
            pr_description_path=['.gitlab', 'merge_request_templates', 'Default.md'],
            pr_full_name='merge request',
            pr_ordinal_char='!',
            pr_short_name='MR',
            repository_name='project',
            token_providers_message=(
                f'\n\t1. `{GITLAB_TOKEN_ENV_VAR}` environment variable\n'
                '\t2. Content of the `~/.gitlab-token` file\n'
                '\t3. Current auth token from the `glab` GitLab CLI\n'
            ),
            git_config_keys=CodeHostingGitConfigKeys(
                domain='machete.gitlab.domain',
                organization='machete.gitlab.namespace',
                repository='machete.gitlab.project',
                remote='machete.gitlab.remote',
                annotate_with_urls='machete.gitlab.annotateWithUrls',
                force_description_from_commit_message='machete.gitlab.forceDescriptionFromCommitMessage',
            )
        )

    def __get_merge_request_from_json(self, mr_json: Dict[str, Any]) -> PullRequest:
        return PullRequest(
            number=int(mr_json['iid']),
            display_prefix='MR !',
            user=mr_json['author']['username'],
            base=mr_json['target_branch'],
            head=mr_json['source_branch'],
            head_repo_id=int(mr_json['source_project_id']),
            html_url=mr_json['web_url'],
            state=mr_json['state'],
            description=mr_json['description'])

    def __fire_gitlab_api_request(self, method: str, path: str, request_body: Optional[Dict[str, Any]] = None) -> Any:
        headers: Dict[str, str] = {
            "Content-Type": "application/json"
        }
        if self.__token:
            headers['Authorization'] = 'Bearer ' + self.__token.value

        url_prefix = 'https://' + self.domain + '/api/v4'
        url = url_prefix + path
        json_body: Optional[str] = json.dumps(request_body) if request_body else None
        http_request = urllib.request.Request(url, headers=headers, data=json_body.encode() if json_body else None, method=method.upper())
        debug(f'firing a {method} request to {url} with {"a" if self.__token else "no"} '
              f'bearer token and request body {compact_dict(request_body) if request_body else "<none>"}')

        try:
            with urllib.request.urlopen(http_request) as response:
                parsed_response_body: Any = json.loads(response.read().decode())
                # https://docs.gitlab.com/ee/api/rest/#pagination-link-header
                link_header: str = response.info()["link"]
                if link_header:
                    url_prefix_regex = re.escape(url_prefix)
                    match = re.search(f'<{url_prefix_regex}(/[^>]+)>; rel="next"', link_header)
                    if match:
                        next_page_path = match.group(1)
                        debug(f'link header is present in the response, and there is more data to retrieve under {next_page_path}')
                        return parsed_response_body + self.__fire_gitlab_api_request(method, next_page_path, request_body)
                    else:
                        debug('link header is present in the response, but there is no more data to retrieve')
                return parsed_response_body
        except urllib.error.HTTPError as err:
            if err.code == http.HTTPStatus.CONFLICT:
                error_response = json.loads(err.read().decode())
                error_reason: str = self.__extract_failure_info_from_409(error_response)
                if 'Another open merge request already exists for this source branch:' in error_reason:
                    raise MacheteException(error_reason)
                else:
                    raise UnexpectedMacheteException(
                        f'GitLab API returned 409 (Conflict) HTTP status with error message: `{error_reason}`.')
            elif err.code in (http.HTTPStatus.UNAUTHORIZED, http.HTTPStatus.FORBIDDEN):
                first_line = f'GitLab API returned `{err.code}` HTTP status with error message: `{err.reason}`\n'
                last_line = 'You can also use a different token provider - see `git machete help gitlab` for details.'
                if self.__token:
                    raise MacheteException(
                        first_line + f'Make sure that the GitLab API token provided by {self.__token.provider} '
                        f'is valid and allows for access to `{method.upper()}` `{url_prefix}{path}`.\n' + last_line)
                else:
                    raise MacheteException(
                        first_line + 'You might not have the required permissions for this project.\n'
                                     'Provide a GitLab API token with `api` access.\n'
                                     f'Visit `https://{self.domain}/-/user_settings/personal_access_tokens` '
                                     'to generate a new one.\n' + last_line)
            elif err.code == http.HTTPStatus.NOT_FOUND:
                # TODO (#164): make a dedicated exception here
                raise MacheteException(
                    f'`{method} {url}` request ended up in 404 response from GitLab. A valid GitLab API token is required.\n'
                    f'Provide a GitLab API token with `api` access via one of the: {self._spec.token_providers_message} '
                    f'Visit `https://{self.domain}/-/user_settings/personal_access_tokens` to generate a new one.')
            elif err.code == http.HTTPStatus.METHOD_NOT_ALLOWED:
                error_response = json.loads(err.read().decode())
                if error_response.get("message") == "Non GET methods are not allowed for moved projects":
                    raise MacheteException(
                        f"Request `{method} {url}`\n"
                        f"ended up in `{error_response.get('message')}` response from GitLab.\n"
                        "Please report this error as a comment under `https://github.com/VirtusLab/git-machete/issues/1212`.\n"
                        "As a workaround for now, please check `git remote -v`.\n"
                        "Most likely you use an old URL of a repository that has been moved since.\n"
                        "Use `git remote set-url <remote> <URL>` to update the URL.")
                else:
                    UnexpectedMacheteException(
                        f'GitLab API returned 405 (Method Not Allowed) HTTP status with error message: `{err.reason}`.')
            elif err.code >= 500:
                raise MacheteException(f'GitLab API returned `{err.code}` '
                                       f'HTTP status with error message: `{err.reason}`.')  # pragma: no cover
            else:
                raise UnexpectedMacheteException(f'GitLab API returned `{err.code}` HTTP status with error message: `{err.reason}`.')
        except OSError as e:  # pragma: no cover
            raise MacheteException(f'Could not connect to {url_prefix}: {e}')

    def __fire_gitlab_api_project_request(self, method: str, path_suffix: str, request_body: Optional[Dict[str, Any]] = None) -> Any:
        project = urllib.parse.quote(f"{self.organization}/{self.repository}", safe='')  # `safe` empty, so that `/` is encoded as well
        path = f'/projects/{project}{path_suffix}'
        return self.__fire_gitlab_api_request(method=method, path=path, request_body=request_body)

    @staticmethod
    def __extract_failure_info_from_409(response: Any) -> str:
        message = response.get("message")
        if type(message) is list:
            return '\n'.join(message)
        elif message:
            return str(message)
        else:
            return str(response)

    def create_pull_request(self, head: str, base: str, title: str, description: str, draft: bool) -> PullRequest:
        request_body: Dict[str, Any] = {
            'source_branch': head,
            'target_branch': base,
            'title': ('Draft: ' if draft else '') + title,
            'description': description,
        }
        mr = self.__fire_gitlab_api_project_request(method='POST', path_suffix='/merge_requests', request_body=request_body)
        return self.__get_merge_request_from_json(mr)

    def __get_user_id_by_username(self, username: str) -> Optional[int]:
        result = self.__fire_gitlab_api_request(method='GET', path=f'/users?username={username}')
        if result:
            return int(result[0]["id"])
        else:
            return None

    def add_assignees_to_pull_request(self, number: int, assignees: List[str]) -> None:
        assignee_ids: List[int] = map_truthy_only(self.__get_user_id_by_username, assignees)
        request_body: Dict[str, List[int]] = {'assignee_ids': assignee_ids}
        self.__fire_gitlab_api_project_request(method='PUT', path_suffix=f'/merge_requests/{number}', request_body=request_body)

    def add_reviewers_to_pull_request(self, number: int, reviewers: List[str]) -> None:
        reviewer_ids: List[int] = map_truthy_only(self.__get_user_id_by_username, reviewers)
        request_body: Dict[str, List[int]] = {'reviewer_ids': reviewer_ids}
        self.__fire_gitlab_api_project_request(method='PUT', path_suffix=f'/merge_requests/{number}', request_body=request_body)

    def set_base_of_pull_request(self, number: int, base: LocalBranchShortName) -> None:
        request_body: Dict[str, str] = {'target_branch': base}
        self.__fire_gitlab_api_project_request(method='PUT', path_suffix=f'/merge_requests/{number}', request_body=request_body)

    def set_description_of_pull_request(self, number: int, description: str) -> None:
        request_body: Dict[str, str] = {'description': description}
        self.__fire_gitlab_api_project_request(method='PUT', path_suffix=f'/merge_requests/{number}', request_body=request_body)

    def set_milestone_of_pull_request(self, number: int, milestone: str) -> None:
        request_body: Dict[str, str] = {'milestone_id': milestone}
        self.__fire_gitlab_api_project_request(method='PUT', path_suffix=f'/merge_requests/{number}', request_body=request_body)

    def set_draft_status_of_pull_request(self, number: int, target_draft_status: bool) -> bool:
        mr = self.__fire_gitlab_api_project_request(method='GET', path_suffix=f'/merge_requests/{number}')
        is_draft = bool(mr["draft"])  # bool(...) to satisfy mypy
        if is_draft and target_draft_status is True:
            debug(f"MR !{number} is already a draft")
            return False
        if not is_draft and target_draft_status is False:
            # This case is not covered by tests since there's currently no scenario
            # in `git machete gitlab restack-mr` that could reach here.
            debug(f"MR !{number} is already ready for review")
            return False

        old_title = mr["title"]
        if target_draft_status is True:
            new_title = "Draft: " + old_title
        else:
            # Prefixes as per https://docs.gitlab.com/ee/user/project/merge_requests/drafts.html in March 2024
            new_title = re.sub(r'^(\[Draft]|Draft:|\(Draft\)) *', '', old_title)
        request_body: Dict[str, str] = {'title': new_title}
        self.__fire_gitlab_api_project_request(method='PUT', path_suffix=f'/merge_requests/{number}', request_body=request_body)
        return True

    def get_open_pull_requests_by_head(self, head: LocalBranchShortName) -> List[PullRequest]:
        mrs = self.__fire_gitlab_api_project_request(method='GET', path_suffix=f'/merge_requests?state=opened&source_branch={head}')
        return [self.__get_merge_request_from_json(mr) for mr in mrs]

    def get_open_pull_requests(self) -> List[PullRequest]:
        mrs = self.__fire_gitlab_api_project_request(method='GET',
                                                     path_suffix=f'/merge_requests?state=opened&per_page={self.MAX_PULLS_PER_PAGE_COUNT}')
        return [self.__get_merge_request_from_json(mr) for mr in mrs]

    def get_current_user_login(self) -> Optional[str]:
        if not self.__token:
            return None
        user = self.__fire_gitlab_api_request(method='GET', path='/user')
        return str(user['username'])  # str() to satisfy mypy

    def get_pull_request_by_number_or_none(self, number: int) -> Optional[PullRequest]:
        try:
            mr_json = self.__fire_gitlab_api_project_request(method='GET', path_suffix=f'/merge_requests/{number}')
            return self.__get_merge_request_from_json(mr_json)
        except MacheteException:
            return None

    def fetch_org_repo_and_git_url_by_repo_id_or_none(self, repo_id: int) -> Optional[OrganizationAndRepositoryAndGitUrl]:
        try:
            project = self.__fire_gitlab_api_request(method='GET', path=f'/projects/{repo_id}')
            return OrganizationAndRepositoryAndGitUrl(
                # `namespace`->`path` seems to be equal to `namespace`->`name` - only the last segment of the path
                organization=project['namespace']['full_path'],
                repository=project['name'],
                git_url=project['http_url_to_repo']
            )
        except MacheteException:
            return None

    def get_ref_name_for_pull_request(self, mr_number: int) -> str:
        # See `git ls-remote` for any GitLab remote.
        return f"merge-requests/{mr_number}/head"
