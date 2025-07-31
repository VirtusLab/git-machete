import re
import ssl
from abc import ABCMeta, abstractmethod
from typing import Dict, List, NamedTuple, Optional

from git_machete.git_operations import GitContext, LocalBranchShortName
from git_machete.utils import bold


class PullRequest:
    def __init__(self, number: int, display_prefix: str, user: str, base: str, head: str, head_repo_id: int,
                 state: str, title: str, description: Optional[str], html_url: str):
        self.__number = number
        self.__display_prefix = display_prefix
        self.__user = user
        self.__base = base
        self.__head = head
        self.__head_repo_id = head_repo_id
        self.__state = state
        self.__title = title
        self.__description = description
        self.__html_url = html_url

    def copy(self) -> "PullRequest":
        return PullRequest(
            number=self.__number,
            display_prefix=self.__display_prefix,
            user=self.__user,
            base=self.__base,
            head=self.__head,
            head_repo_id=self.__head_repo_id,
            state=self.__state,
            title=self.__title,
            description=self.__description,
            html_url=self.__html_url
        )

    @property
    def number(self) -> int:
        return self.__number

    @property
    def display_prefix(self) -> str:
        return self.__display_prefix

    @property
    def user(self) -> str:
        return self.__user

    @property
    def base(self) -> str:
        return self.__base

    @base.setter
    def base(self, base: str) -> None:
        self.__base = base

    @property
    def head(self) -> str:
        return self.__head

    @property
    def head_repo_id(self) -> int:
        return self.__head_repo_id

    @property
    def state(self) -> str:
        return self.__state

    @property
    def title(self) -> str:
        return self.__title

    @property
    def description(self) -> Optional[str]:
        return self.__description

    @description.setter
    def description(self, description: str) -> None:
        self.__description = description

    @property
    def html_url(self) -> str:
        return self.__html_url

    def short_display_text(self, fmt: bool = True) -> str:
        return self.display_text(fmt).split(" ")[1]

    def display_text(self, fmt: bool = True) -> str:
        number = str(self.number)
        return f"{self.display_prefix}{bold(number) if fmt else number}"

    def __repr__(self) -> str:
        # repr is used in debug messages, let's turn off formatting
        return f"{self.display_text(fmt=False)} by {self.user}: {self.head} -> {self.base}"


class OrganizationAndRepository(NamedTuple):
    organization: str
    repository: str

    def __str__(self) -> str:
        return f"{self.organization}/{self.repository}"

    @classmethod
    def from_url(cls, domain: str, url: str) -> Optional["OrganizationAndRepository"]:
        url = url if url.endswith('.git') else url + '.git'
        for pattern in remote_url_patterns(domain):
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

    def extract_org_and_repo(self) -> OrganizationAndRepository:
        return OrganizationAndRepository(organization=self.organization, repository=self.repository)


class OrganizationAndRepositoryAndGitUrl(NamedTuple):
    organization: str
    repository: str
    git_url: str


def remote_url_patterns(domain: str) -> List[str]:
    # Neither GitHub not GitLab allows trailing `.git` suffix in the repository name (also applies to multiple repetitions e.g. `repo_name.git.git`)
    # Note that these regexes work for both GitLab and GitHub.
    # The difference is only that the organization (or rather, "namespace") in GitLab might contain multiple `/`-separated segments.
    domain_regex = re.escape(domain)
    org_repo_regex = "(.+)/([^/]+)"
    return [
        # (?:...) is a non-capturing group
        f"^https://(?:.+@)?{domain_regex}/{org_repo_regex}$",
        # A very rare way to express SSH URL
        f"^ssh://.+@{domain_regex}/{org_repo_regex}$",
        # The below is way more common for SSH; the user before `@` is typically called `git`, but doesn't need to be so
        f"^[^:/]+@{domain_regex}:{org_repo_regex}$",
    ]


def is_matching_remote_url(domain: str, url: str) -> bool:
    url = url if url.endswith('.git') else url + '.git'
    return any((re.match(pattern, url) for pattern in remote_url_patterns(domain)))


class CodeHostingGitConfigKeys(NamedTuple):
    domain: str
    organization: str
    repository: str
    remote: str
    annotate_with_urls: str
    force_description_from_commit_message: str
    pr_description_intro_style: str

    def for_locating_repo_message(self) -> str:
        return f"`{self.domain}`, `{self.organization}`, `{self.repository}`, `{self.remote}`"


class CodeHostingSpec(NamedTuple):
    base_branch_name: str
    client_class: type
    default_domain: str
    display_name: str
    git_machete_command: str
    head_branch_name: str
    organization_name: str
    pr_description_paths: List[List[str]]
    pr_full_name: str
    pr_intro_br_before_branches: bool
    pr_intro_explicit_title: bool
    pr_ordinal_char: str
    pr_short_name_article: str
    pr_short_name: str
    repository_name: str
    token_providers_message: str
    git_config_keys: CodeHostingGitConfigKeys

    def __str__(self) -> str:
        return f"CodeHostingSpec({self.display_name})"

    def create_client(self, domain: str, organization: str, repository: str) -> "CodeHostingClient":
        return self.client_class(domain=domain, organization=organization, repository=repository)  # type: ignore[no-any-return]


# flake8: noqa U100
# So that flake8 doesn't complain about unused params in abstract class.
class CodeHostingClient(metaclass=ABCMeta):  # pragma: no cover
    def __init__(self, domain: str, organization: str, repository: str) -> None:
        self.domain: str = domain
        self.organization: str = organization
        self.repository: str = repository
        self.ssl_context = self.__create_ssl_context()
        self.__org_repo_and_git_url_by_repo_id: Dict[int, Optional[OrganizationAndRepositoryAndGitUrl]] = {}

    @staticmethod
    def __create_ssl_context() -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        ssl_verify = GitContext().get_boolean_config_attr_or_none("http.sslVerify")
        if not ssl_verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def get_org_and_repo(self) -> OrganizationAndRepository:
        return OrganizationAndRepository(self.organization, self.repository)

    @abstractmethod
    def create_pull_request(self, head: str, head_org_repo: OrganizationAndRepository,
                            *, base: str, title: str, description: str, draft: bool) -> PullRequest:
        pass

    @abstractmethod
    def add_assignees_to_pull_request(self, number: int, assignees: List[str]) -> None:
        pass

    @abstractmethod
    def add_reviewers_to_pull_request(self, number: int, reviewers: List[str]) -> None:
        pass

    @abstractmethod
    def set_base_of_pull_request(self, number: int, base: LocalBranchShortName) -> None:
        pass

    @abstractmethod
    def set_description_of_pull_request(self, number: int, description: str) -> None:
        pass

    @abstractmethod
    def set_milestone_of_pull_request(self, number: int, milestone: str) -> None:
        pass

    @abstractmethod
    def set_draft_status_of_pull_request(self, number: int, *, target_draft_status: bool) -> bool:
        """Returns true if PR had a different draft status, and draft status has been toggled.
        Returns false if PR already had the desired draft status, and hence draft status has NOT been toggled."""

    @abstractmethod
    def get_open_pull_requests_by_head(self, head: LocalBranchShortName) -> List[PullRequest]:
        pass

    @abstractmethod
    def get_open_pull_requests(self) -> List[PullRequest]:
        pass

    @abstractmethod
    def get_current_user_login(self) -> Optional[str]:
        pass

    @abstractmethod
    def get_pull_request_by_number_or_none(self, number: int) -> Optional[PullRequest]:
        pass

    @abstractmethod
    def fetch_org_repo_and_git_url_by_repo_id_or_none(self, repo_id: int) -> Optional[OrganizationAndRepositoryAndGitUrl]:
        pass

    def get_org_repo_and_git_url_by_repo_id_or_none(self, repo_id: int) -> Optional[OrganizationAndRepositoryAndGitUrl]:
        if repo_id not in self.__org_repo_and_git_url_by_repo_id:
            self.__org_repo_and_git_url_by_repo_id[repo_id] = self.fetch_org_repo_and_git_url_by_repo_id_or_none(repo_id)
        return self.__org_repo_and_git_url_by_repo_id[repo_id]

    @abstractmethod
    def get_ref_name_for_pull_request(self, pr_number: int) -> str:
        pass
