import itertools
import os
from enum import auto
from typing import Dict, Iterator, List, Optional, Set, Tuple

from git_machete import utils
from git_machete.annotation import Annotation, Qualifiers
from git_machete.client.base import (MacheteClient, ParsableEnum,
                                     SquashMergeDetection)
from git_machete.code_hosting import (CodeHostingClient, CodeHostingSpec,
                                      OrganizationAndRepository,
                                      OrganizationAndRepositoryAndRemote,
                                      PullRequest, is_matching_remote_url)
from git_machete.exceptions import MacheteException, UnexpectedMacheteException
from git_machete.git_operations import (GitContext, GitFormatPatterns,
                                        GitLogEntry, LocalBranchShortName,
                                        RemoteBranchShortName,
                                        SyncToRemoteStatus)
from git_machete.utils import (bold, debug, find_or_none, fmt,
                               get_pretty_choices, get_right_arrow, slurp_file,
                               warn)


class PRDescriptionIntroStyle(ParsableEnum):
    FULL = auto()
    FULL_NO_BRANCHES = auto()
    UP_ONLY = auto()
    UP_ONLY_NO_BRANCHES = auto()
    NONE = auto()


class MacheteClientWithCodeHosting(MacheteClient):
    def __init__(self, git: GitContext, spec: CodeHostingSpec):
        super().__init__(git)
        self.__code_hosting_spec: CodeHostingSpec = spec
        self.__code_hosting_client: Optional[CodeHostingClient] = None
        self.__all_open_prs: Optional[List[PullRequest]] = None

    @property
    def code_hosting_spec(self) -> CodeHostingSpec:
        return self.__code_hosting_spec

    @property
    def code_hosting_client(self) -> CodeHostingClient:
        if self.__code_hosting_client is None:
            raise UnexpectedMacheteException("Code hosting client has not been initialized, this is an unexpected state.")
        return self.__code_hosting_client

    @code_hosting_client.setter
    def code_hosting_client(self, value: CodeHostingClient) -> None:
        self.__code_hosting_client = value

    def _get_all_open_prs(self) -> List[PullRequest]:
        if self.__all_open_prs is None:
            spec = self.code_hosting_spec
            print(f'Checking for open {spec.display_name} {spec.pr_short_name}s... ', end='', flush=True)
            self.__all_open_prs = self.code_hosting_client.get_open_pull_requests()
            print(fmt('<green><b>OK</b></green>'))
        return self.__all_open_prs

    def _pull_request_annotation(self, pr: PullRequest, current_user: Optional[str], *, include_url: bool = False) -> str:
        anno = pr.display_text(fmt=False)
        if current_user != pr.user:
            anno += f" ({pr.user})"
        config_key = self.code_hosting_spec.git_config_keys.annotate_with_urls
        if include_url or self._git.get_boolean_config_attr(key=config_key, default_value=False):
            anno += f" {pr.html_url}"
        return anno

    def __sync_annotations_to_branch_layout_file(self, prs: List[PullRequest], current_user: Optional[str],
                                                 *, include_urls: bool, verbose: bool) -> None:
        spec = self.code_hosting_spec
        for pr in prs:
            if LocalBranchShortName.of(pr.head) in self.managed_branches:
                debug(f'{pr} corresponds to a managed branch')
                anno: str = self._pull_request_annotation(pr, current_user, include_url=include_urls)
                upstream: Optional[LocalBranchShortName] = self.up_branch_for(LocalBranchShortName.of(pr.head))
                if upstream is not None:
                    counterpart = self._git.get_combined_counterpart_for_fetching_of_branch(upstream)
                else:
                    counterpart = None
                upstream_tracking_branch = upstream if counterpart is None else '/'.join(counterpart.split('/')[1:])

                if pr.base != upstream_tracking_branch:
                    warn(f'branch {bold(pr.head)} has a different base in {pr.display_text()} ({bold(pr.base)}) '
                         f'than in machete file ({bold(upstream) if upstream else "<none, is a root>"})')
                    anno += (f" WRONG {spec.pr_short_name} {spec.base_branch_name.upper()} or MACHETE PARENT? "
                             f"{spec.pr_short_name} has {pr.base}")
                old_annotation_text = ''
                old_annotation_qualifiers = Qualifiers()
                if LocalBranchShortName.of(pr.head) in self._state.annotations:
                    old_annotation = self._state.annotations[LocalBranchShortName.of(pr.head)]
                    old_annotation_text = old_annotation.text_without_qualifiers
                    old_annotation_qualifiers = old_annotation.qualifiers

                if pr.user != current_user and old_annotation_qualifiers.is_default():
                    if verbose:
                        print(fmt(f'Annotating {bold(pr.head)} as `{anno} rebase=no push=no`'))
                    self._state.annotations[LocalBranchShortName.of(pr.head)] = Annotation(anno, Qualifiers(rebase=False, push=False))
                elif old_annotation_text != anno:
                    if verbose:
                        print(fmt(f'Annotating {bold(pr.head)} as `{anno}`'))
                    self._state.annotations[LocalBranchShortName.of(pr.head)] = Annotation(anno, old_annotation_qualifiers)
            else:
                debug(f'{pr} does NOT correspond to a managed branch')
        self.save_branch_layout_file()

    def __get_url_for_remote(self) -> Dict[str, str]:
        return {
            remote: url for remote, url in ((remote_, self._git.get_url_of_remote(remote_)) for remote_ in self._git.get_remotes()) if url
        }

    def __get_remote_name_for_org_and_repo(self, domain: str, org_and_repo: OrganizationAndRepository) -> Optional[str]:
        """
        Check if the given remote (as identified by `remote_url`) is already added to local git remotes,
        because it may happen that the local git remote's name is different from the name of organization on code hosting site.
        """
        for remote, url in self.__get_url_for_remote().items():
            if is_matching_remote_url(domain, url) and OrganizationAndRepository.from_url(domain, url) == org_and_repo:
                return remote
        return None

    def sync_before_creating_pull_request(self, *, opt_yes: bool) -> None:
        spec = self.code_hosting_spec
        self.expect_at_least_one_managed_branch()
        self._set_empty_line_status()

        current_branch = self._git.get_current_branch()
        if current_branch not in self.managed_branches:
            self.add(branch=current_branch,
                     opt_onto=None,
                     opt_as_first_child=False,
                     opt_as_root=False,
                     opt_yes=opt_yes,
                     verbose=True,
                     switch_head_if_new_branch=True)
            if current_branch not in self.managed_branches:
                subcommand = "create-" + spec.pr_short_name.lower()
                raise MacheteException(
                    f"Subcommand `{subcommand}` can NOT be executed on the branch"
                    " that is not managed by git machete (is not present in branch layout file).\n"
                    "To successfully execute this command "
                    "either add current branch to the file via commands `add`, "
                    "`discover` or `edit` or agree on adding the branch to the "
                    f"branch layout file during the execution of `{subcommand}` subcommand.")

        up_branch: Optional[LocalBranchShortName] = self.up_branch_for(current_branch)
        if not up_branch:
            raise MacheteException(
                f'Branch {bold(current_branch)} does not have a parent branch (it is a root), '
                f'{spec.base_branch_name} branch for the {spec.pr_short_name} cannot be established.')

        if self._git.is_ancestor_or_equal(current_branch.full_name(), up_branch.full_name()):
            raise MacheteException(
                f'All commits in {bold(current_branch)} branch are already included in {bold(up_branch)} branch.\n'
                f'Cannot create {spec.pr_full_name}.')

        s, remote = self._git.get_combined_remote_sync_status(current_branch)
        statuses_to_push = (
            SyncToRemoteStatus.UNTRACKED,
            SyncToRemoteStatus.AHEAD_OF_REMOTE,
            SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE)
        if s in statuses_to_push:
            if current_branch not in self.annotations or self.annotations[current_branch].qualifiers.push:
                if s == SyncToRemoteStatus.AHEAD_OF_REMOTE:
                    assert remote is not None
                    self._handle_ahead_state(
                        current_branch=current_branch,
                        remote=remote,
                        is_called_from_traverse=False,
                        opt_push_tracked=True,
                        opt_yes=opt_yes)
                elif s == SyncToRemoteStatus.UNTRACKED:
                    self._handle_untracked_state(
                        branch=current_branch,
                        is_called_from_traverse=False,
                        is_called_from_code_hosting=True,
                        opt_push_tracked=True,
                        opt_push_untracked=True,
                        opt_yes=opt_yes)
                elif s == SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                    assert remote is not None
                    self._handle_diverged_and_newer_state(
                        current_branch=current_branch,
                        remote=remote,
                        is_called_from_traverse=False,
                        opt_push_tracked=True,
                        opt_yes=opt_yes)
                else:
                    raise UnexpectedMacheteException(f"Invalid sync to remote status: `{s}`.")

                self._print_new_line(False)
                self.status(
                    warn_when_branch_in_sync_but_fork_point_off=True,
                    opt_list_commits=False,
                    opt_list_commits_with_hashes=False,
                    opt_squash_merge_detection=SquashMergeDetection.NONE)
                self._print_new_line(False)

        else:
            if s == SyncToRemoteStatus.BEHIND_REMOTE:
                warn(f"Branch {bold(current_branch)} is behind its remote counterpart. Consider using `git pull`.")
                self._print_new_line(False)
                ans = self.ask_if(f"Proceed with creating {spec.pr_full_name}?" + get_pretty_choices('y', 'Q'),
                                  f"Proceeding with {spec.pr_full_name} creation...", opt_yes=opt_yes)
            elif s == SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                warn(f"Branch {bold(current_branch)} is diverged from and older than its remote counterpart. "
                     "Consider using `git reset --keep`.")
                self._print_new_line(False)
                ans = self.ask_if(f"Proceed with creating {spec.pr_full_name}?" + get_pretty_choices('y', 'Q'),
                                  f"Proceeding with {spec.pr_full_name} creation...", opt_yes=opt_yes)
            elif s == SyncToRemoteStatus.NO_REMOTES:
                raise MacheteException(
                    f"Could not create {spec.pr_full_name} - there are no remote repositories!")
            else:
                ans = 'y'  # only IN SYNC status is left

            if ans in ('y', 'yes'):
                return
            raise MacheteException(f'Interrupted creating {spec.pr_full_name}.')

    def sync_annotations_to_prs(self, *, include_urls: bool) -> None:
        self._init_code_hosting_client()
        current_user: Optional[str] = self.code_hosting_client.get_current_user_login()
        debug(f'Current {self.code_hosting_spec.display_name} user is ' + (bold(current_user or '<none>')))
        all_open_prs = self._get_all_open_prs()
        self.__sync_annotations_to_branch_layout_file(all_open_prs, current_user, include_urls=include_urls, verbose=True)

    def create_pull_request(
            self,
            *,
            head: LocalBranchShortName,
            opt_draft: bool,
            opt_title: Optional[str],
            opt_update_related_descriptions: bool,
            opt_yes: bool
    ) -> None:
        # first make sure that head branch is synced with remote
        base: Optional[LocalBranchShortName] = self.up_branch_for(LocalBranchShortName.of(head))
        spec = self.code_hosting_spec
        if not base:
            raise UnexpectedMacheteException(f'Could not determine {spec.base_branch_name} branch for {spec.pr_short_name}. '
                                             f'Branch {bold(head)} is a root branch.')

        domain = self.__derive_code_hosting_domain()
        head_org_repo_remote = self.__derive_org_repo_and_remote(domain=domain, branch_used_for_tracking_data=head)
        base_org_repo_remote = self.__derive_org_repo_and_remote(domain=domain, branch_used_for_tracking_data=base)
        debug(f"head_org_repo_remote={head_org_repo_remote}, base_org_repo_remote={base_org_repo_remote}")

        base_org_repo = base_org_repo_remote.extract_org_and_repo()
        head_org_repo = head_org_repo_remote.extract_org_and_repo()
        if base_org_repo != head_org_repo:
            arrow = get_right_arrow()
            warn(f"{spec.base_branch_name.capitalize()} branch <b>{base}</b> lives in <b>{base_org_repo}</b> {spec.repository_name},\n"
                 f"while {spec.head_branch_name} branch <b>{head}</b> lives in <b>{head_org_repo}</b> {spec.repository_name}.\n"
                 f"git-machete will now attempt to create {spec.pr_short_name_article} {spec.pr_short_name} in <b>{base_org_repo}</b>.\n"
                 "\n"
                 f"Note that due to the limitations of {spec.display_name}'s {spec.pr_short_name} model, "
                 f"it is <b>not</b> possible to cleanly create stacked {spec.pr_short_name}s from forks.\n"
                 f"For example, in a hypothetical chain <b>some-other-branch</b> {arrow} <b>{head}</b> {arrow} <b>{base}</b>, "
                 f"{spec.pr_short_name_article} {spec.pr_short_name} from <b>some-other-branch</b> to <b>{head}</b>\n"
                 f"could <b>not</b> be created in <b>{base_org_repo}</b>, "
                 f"since its {spec.head_branch_name} branch <b>{head}</b> lives in <b>{head_org_repo}</b>.\n"
                 f"Generally, {spec.pr_short_name}s need to be created "
                 f"in whatever {spec.repository_name} the {spec.base_branch_name} branch lives.\n")

        base_remote_branch = RemoteBranchShortName(f"{base_org_repo_remote.remote}/{base}")
        remote_base_branch_exists_locally = base_remote_branch in self._git.get_remote_branches()
        print(f"Checking if {spec.base_branch_name} branch {bold(base)} "
              f"exists in {bold(base_org_repo_remote.remote)} remote... ", end='', flush=True)
        base_branch_found_on_remote = self._git.does_remote_branch_exist(base_org_repo_remote.remote, base)
        print(fmt('<green><b>YES</b></green>' if base_branch_found_on_remote else '<red><b>NO</b></red>'))
        if not base_branch_found_on_remote and remote_base_branch_exists_locally:
            self._git.delete_remote_branch(base_remote_branch)

        if not base_branch_found_on_remote:
            self._handle_untracked_branch(
                branch=base,
                new_remote=base_org_repo_remote.remote,
                is_called_from_traverse=False,
                is_called_from_code_hosting=True,
                opt_push_tracked=False,
                opt_push_untracked=True,
                opt_yes=opt_yes)

        self.code_hosting_client = spec.create_client(domain=domain, organization=base_org_repo_remote.organization,
                                                      repository=base_org_repo_remote.repository)
        current_user: Optional[str] = self.code_hosting_client.get_current_user_login()
        debug(f'organization is {base_org_repo_remote.organization}, repository is {base_org_repo_remote.repository}')
        debug(f'current {spec.display_name} user is ' + (current_user or '<none>'))

        fork_point = self.fork_point(head, use_overrides=True)
        commits: List[GitLogEntry] = self._git.get_commits_between(fork_point, head)

        pr_title_file_path = self._git.get_main_git_subpath('info', 'title')
        is_pr_title_file = os.path.isfile(pr_title_file_path)
        if opt_title:
            title = opt_title
        elif is_pr_title_file:
            title = slurp_file(pr_title_file_path)
        else:
            # git-machete can still see an empty range of unique commits (e.g. in case of yellow edge)
            # even though code hosting may see a non-empty range.
            # Let's use branch name as a fallback for PR title in such case.
            title = commits[0].subject if commits else head

        force_description_from_commit_message = self._git.get_boolean_config_attr(
            key=spec.git_config_keys.force_description_from_commit_message, default_value=False)
        if force_description_from_commit_message:
            description = self._git.get_commit_data(commits[0].hash, GitFormatPatterns.MESSAGE_BODY) if commits else ''
        else:
            machete_description_path = self._git.get_main_git_subpath('info', 'description')
            if os.path.isfile(machete_description_path):
                description = slurp_file(machete_description_path)
            else:
                code_hosting_description_paths = [os.path.join(self._git.get_root_dir(), *path) for path in spec.pr_description_paths]
                existing = find_or_none(os.path.isfile, code_hosting_description_paths)
                if existing:
                    description = slurp_file(existing)
                else:
                    description = self._git.get_commit_data(commits[0].hash, GitFormatPatterns.MESSAGE_BODY) if commits else ''

        ok_str = '<green><b>OK</b></green>'
        print(f'Creating a {"draft " if opt_draft else ""}{spec.pr_short_name} from {bold(head)} to {bold(base)}... ', end='', flush=True)

        pr: PullRequest = self.code_hosting_client.create_pull_request(
            head=head, head_org_repo=head_org_repo, base=base,
            title=title, description=description, draft=opt_draft)
        print(fmt(f'{ok_str}, see `{pr.html_url}`'))

        style = self.__get_pr_description_into_style_from_config()
        # If base branch has NOT originally been found on the remote,
        # we can be sure that a longer chain of PRs above the newly-created PR does NOT exist.
        # So in the default UP_ONLY mode, we can skip generating the intro completely.
        if base_branch_found_on_remote or style in (PRDescriptionIntroStyle.FULL, PRDescriptionIntroStyle.FULL_NO_BRANCHES):
            # As the description may include the reference to this PR itself (in case of a chain of >=2 PRs),
            # let's update the PR description after it's already created (so that we know the current PR's number).
            new_description = self._get_updated_pull_request_description(pr)
            if new_description.strip() != description.strip():
                print(f'Updating description of {pr.display_text()} to include '
                      f'the chain of {spec.pr_short_name}s... ', end='', flush=True)
                self.code_hosting_client.set_description_of_pull_request(pr.number, new_description)
                print(fmt(ok_str))

        milestone_path: str = self._git.get_main_git_subpath('info', 'milestone')
        if os.path.isfile(milestone_path):
            milestone = slurp_file(milestone_path).strip()
        else:
            milestone = None
        if milestone:
            print(f'Setting milestone of {pr.display_text()} to {bold(milestone)}... ', end='', flush=True)
            self.code_hosting_client.set_milestone_of_pull_request(pr.number, milestone=milestone)
            print(fmt(ok_str))

        if current_user:
            print(f'Adding {bold(current_user)} as assignee to {pr.display_text()}... ', end='', flush=True)
            self.code_hosting_client.add_assignees_to_pull_request(pr.number, [current_user])
            print(fmt(ok_str))

        reviewers_path = self._git.get_main_git_subpath('info', 'reviewers')
        if os.path.isfile(reviewers_path):
            reviewers = utils.get_non_empty_lines(slurp_file(reviewers_path))
        else:
            reviewers = []
        if reviewers:
            print(f'Adding {", ".join(bold(reviewer) for reviewer in reviewers)} '
                  f'as reviewer{"s" if len(reviewers) > 1 else ""} to {pr.display_text()}... ',
                  end='', flush=True)
            self.code_hosting_client.add_reviewers_to_pull_request(pr.number, reviewers)
            print(fmt(ok_str))

        self._state.annotations[head] = Annotation(self._pull_request_annotation(pr, current_user), qualifiers=Qualifiers())
        self.save_branch_layout_file()

        if opt_update_related_descriptions:
            print(f"Updating descriptions of other {spec.pr_short_name}s...")
            self.update_pull_request_descriptions(related=True)

    def restack_pull_request(self, *, opt_update_related_descriptions: bool) -> None:
        spec = self.code_hosting_spec
        head = self._git.get_current_branch()
        _, org_repo_remote = self._init_code_hosting_client(branch_used_for_tracking_data=head)

        pr: Optional[PullRequest] = self.__get_sole_pull_request_for_head(head, ignore_if_missing=False)
        assert pr is not None

        self._git.fetch_remote(org_repo_remote.remote)

        self._set_empty_line_status()
        current_branch = self._git.get_current_branch()
        s, remote = self._git.get_combined_remote_sync_status(current_branch)
        statuses_to_push = (
            SyncToRemoteStatus.UNTRACKED,
            SyncToRemoteStatus.AHEAD_OF_REMOTE,
            SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE)
        if s in statuses_to_push:
            if current_branch in self.annotations and not self.annotations[current_branch].qualifiers.push:
                subcommand = "retarget-" + spec.pr_short_name.lower()
                raise MacheteException(
                    f'Branch <b>{current_branch}</b> is marked as `push=no`; aborting the restack.\n'
                    f'Did you want to just use `git machete {spec.git_machete_command} {subcommand}`?\n')

            converted_to_draft = self.code_hosting_client.set_draft_status_of_pull_request(pr.number, target_draft_status=True)
            if converted_to_draft:
                print(f'{pr.display_text()} has been temporarily marked as draft')

            # Note that retarget should happen BEFORE push, see issue #1222
            self.retarget_pull_request(head, opt_ignore_if_missing=False,
                                       opt_update_related_descriptions=opt_update_related_descriptions)

            if s == SyncToRemoteStatus.AHEAD_OF_REMOTE:
                assert remote is not None
                self._handle_ahead_state(
                    current_branch=current_branch,
                    remote=remote,
                    is_called_from_traverse=False,
                    opt_push_tracked=True,
                    opt_yes=True)
            elif s == SyncToRemoteStatus.UNTRACKED:
                self._handle_untracked_state(
                    branch=current_branch,
                    is_called_from_traverse=False,
                    is_called_from_code_hosting=True,
                    opt_push_tracked=True,
                    opt_push_untracked=True,
                    opt_yes=True)
            elif s == SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                assert remote is not None
                self._handle_diverged_and_newer_state(
                    current_branch=current_branch,
                    remote=remote,
                    is_called_from_traverse=False,
                    opt_push_tracked=True,
                    opt_yes=True)
            else:
                raise UnexpectedMacheteException(f"Invalid sync to remote status: {s}.")

            self._print_new_line(False)
            self.status(
                warn_when_branch_in_sync_but_fork_point_off=True,
                opt_list_commits=False,
                opt_list_commits_with_hashes=False,
                opt_squash_merge_detection=SquashMergeDetection.NONE)
            self._print_new_line(False)

            if converted_to_draft:
                self.code_hosting_client.set_draft_status_of_pull_request(pr.number, target_draft_status=False)
                print(f'{pr.display_text()} has been marked as ready for review again')

        else:
            if s == SyncToRemoteStatus.BEHIND_REMOTE:
                warn(f"Branch {bold(current_branch)} is behind its remote counterpart. Consider using `git pull`.\n")
            elif s == SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                warn(f"Branch {bold(current_branch)} is diverged from and older than its remote counterpart. "
                     "Consider using `git reset --keep`.\n")
            elif s == SyncToRemoteStatus.IN_SYNC_WITH_REMOTE:
                pass
            else:  # case handled elsewhere
                raise UnexpectedMacheteException(f"Could not retarget {spec.pr_full_name}: invalid sync-to-remote status `{s}`.")

            self.retarget_pull_request(head, opt_ignore_if_missing=False,
                                       opt_update_related_descriptions=opt_update_related_descriptions)

    def _get_updated_pull_request_description(self, pr: PullRequest) -> str:
        def skip_leading_empty(strs: List[str]) -> List[str]:
            return list(itertools.dropwhile(lambda line: line.strip() == '', strs))

        original_trailing_newlines = ''.join(itertools.takewhile(lambda c: c == '\n', reversed(pr.description or '')))
        lines = pr.description.strip().splitlines() if pr.description else []
        style = self.__get_pr_description_into_style_from_config()
        text_to_prepend = self.__generate_pr_description_intro(pr, style)
        lines_to_prepend = text_to_prepend.splitlines() if text_to_prepend else []
        if self.START_GIT_MACHETE_GENERATED_COMMENT in lines and self.END_GIT_MACHETE_GENERATED_COMMENT in lines:
            start_index = lines.index(self.START_GIT_MACHETE_GENERATED_COMMENT)
            end_index = lines.index(self.END_GIT_MACHETE_GENERATED_COMMENT)
            lines = lines[:start_index] + lines_to_prepend + lines[end_index + 1:]
            lines = skip_leading_empty(lines)
        else:
            # For compatibility with pre-v3.23.0 format; only affects GitHub
            if lines and '# Based on PR #' in lines[0]:
                lines = lines[1:]
            lines = lines_to_prepend + ([''] if lines_to_prepend else []) + skip_leading_empty(lines)
        return '\n'.join(lines) + original_trailing_newlines

    def retarget_pull_request(self, head: LocalBranchShortName, *,
                              opt_ignore_if_missing: bool, opt_update_related_descriptions: bool) -> None:
        spec = self.code_hosting_spec
        if self.__code_hosting_client is None:
            self._init_code_hosting_client(branch_used_for_tracking_data=head)

        pr: Optional[PullRequest] = self.__get_sole_pull_request_for_head(
            head, ignore_if_missing=opt_ignore_if_missing)
        if pr is None:
            return

        new_base: Optional[LocalBranchShortName] = self.up_branch_for(LocalBranchShortName.of(head))
        if not new_base:
            raise MacheteException(
                f'Branch {bold(head)} does not have a parent branch (it is a root) '
                f'even though there is an open {pr.display_text()} to {bold(pr.base)}.\n'
                'Consider modifying the branch layout file (`git machete edit`)'
                f' so that {bold(head)} is a child of {bold(pr.base)}.')

        pr_with_original_base = pr.copy()
        if pr.base != new_base:
            self.code_hosting_client.set_base_of_pull_request(pr.number, base=new_base)
            print(f'{spec.base_branch_name.capitalize()} branch of {pr.display_text()} has been switched to {bold(new_base)}')
            pr.base = new_base
        else:
            print(f'{spec.base_branch_name.capitalize()} branch of {pr.display_text()} is already {bold(new_base)}')

        new_description = self._get_updated_pull_request_description(pr)
        if pr.description != new_description:
            self.code_hosting_client.set_description_of_pull_request(pr.number, description=new_description)
            print(f'Description of {pr.display_text()} has been updated')

        current_user: Optional[str] = self.code_hosting_client.get_current_user_login()
        anno = self._state.annotations.get(head)
        qualifiers = anno.qualifiers if anno else Qualifiers()
        self._state.annotations[head] = Annotation(self._pull_request_annotation(pr, current_user), qualifiers)
        self.save_branch_layout_file()

        if opt_update_related_descriptions:
            print(f"Updating descriptions of other {spec.pr_short_name}s...")
            applicable_prs: List[PullRequest] = self._get_applicable_pull_requests(related_to=pr_with_original_base) \
                + self._get_applicable_pull_requests(related_to=pr)
            applicable_prs = [pr_ for pr_ in applicable_prs if pr_.number != pr.number]

            for pr in applicable_prs:
                new_description = self._get_updated_pull_request_description(pr)
                if (pr.description or '').rstrip() != new_description.rstrip():
                    self.code_hosting_client.set_description_of_pull_request(pr.number, description=new_description)
                    pr.description = new_description
                    print(fmt(f'Description of {pr.display_text()} (<b>{pr.head} {get_right_arrow()} {pr.base}</b>) has been updated'))

    def __derive_code_hosting_domain(self) -> str:
        spec = self.code_hosting_spec
        return self._git.get_config_attr_or_none(key=spec.git_config_keys.domain) or spec.default_domain

    def __derive_org_repo_and_remote(
            self,
            domain: str,
            branch_used_for_tracking_data: Optional[LocalBranchShortName] = None
    ) -> OrganizationAndRepositoryAndRemote:
        spec = self.code_hosting_spec
        remote_config_key = spec.git_config_keys.remote
        organization_config_key = spec.git_config_keys.organization
        repository_config_key = spec.git_config_keys.repository

        remote_from_config = self._git.get_config_attr_or_none(key=remote_config_key)
        org_from_config = self._git.get_config_attr_or_none(key=organization_config_key)
        repo_from_config = self._git.get_config_attr_or_none(key=repository_config_key)

        url_for_remote: Dict[str, str] = self.__get_url_for_remote()
        if not url_for_remote:
            raise MacheteException('No remotes defined for this repository (see `git remote`)')

        if org_from_config and not repo_from_config:
            raise MacheteException(f'`{organization_config_key}` git config key is present, '
                                   f'but `{repository_config_key}` is missing. Both keys must be present to take effect')

        if not org_from_config and repo_from_config:
            raise MacheteException(f'`{repository_config_key}` git config key is present, '
                                   f'but `{organization_config_key}` is missing. Both keys must be present to take effect')

        if remote_from_config:
            if remote_from_config not in url_for_remote:
                raise MacheteException(f'`{remote_config_key}` git config key points to `{remote_from_config}` remote, '
                                       'but such remote does not exist')

        if remote_from_config and org_from_config and repo_from_config:
            return OrganizationAndRepositoryAndRemote(org_from_config, repo_from_config, remote_from_config)

        if remote_from_config:
            url = url_for_remote[remote_from_config]
            org_and_repo = OrganizationAndRepository.from_url(domain, url)
            if not org_and_repo:
                raise MacheteException(f'`{remote_config_key}` git config key points to `{remote_from_config}` remote, '
                                       f'but its URL `{url}` does not correspond to a valid {spec.display_name} {spec.repository_name}')
            return OrganizationAndRepositoryAndRemote(org_and_repo.organization, org_and_repo.repository, remote_from_config)

        if org_from_config and repo_from_config:
            for remote, url in self.__get_url_for_remote().items():
                if is_matching_remote_url(domain, url) and \
                        OrganizationAndRepository.from_url(domain, url) == \
                        OrganizationAndRepository(org_from_config, repo_from_config):
                    return OrganizationAndRepositoryAndRemote(org_from_config, repo_from_config, remote)
            raise MacheteException(
                f'Both `{organization_config_key}` and `{repository_config_key}` git config keys are defined, '
                f'but no remote seems to correspond to `{org_from_config}/{repo_from_config}` '
                f'({spec.organization_name}/{spec.repository_name}) on {spec.display_name}.\n'
                f'Consider pointing to the remote via `{remote_config_key}` config key')

        remote_and_organization_and_repository_from_urls: Dict[str, OrganizationAndRepositoryAndRemote] = {
            remote: OrganizationAndRepositoryAndRemote(oar.organization, oar.repository, remote) for remote, oar in (
                (remote, OrganizationAndRepository.from_url(domain, url)) for remote, url in url_for_remote.items()
            ) if oar
        }
        debug(f"remote_and_organization_and_repository_from_urls = {remote_and_organization_and_repository_from_urls}")

        if not remote_and_organization_and_repository_from_urls:
            raise MacheteException(
                'Remotes are defined for this repository, but none of them '
                f'seems to correspond to {spec.display_name} (see `git remote -v` for details).\n'
                f'It is possible that you are using a custom {spec.display_name} URL.\n'
                f'If that is the case, you can provide {spec.repository_name} information explicitly '
                f'via some or all of git config keys: \n'
                f'{spec.git_config_keys.for_locating_repo_message()}\n')

        if len(remote_and_organization_and_repository_from_urls) == 1:
            return remote_and_organization_and_repository_from_urls[list(remote_and_organization_and_repository_from_urls.keys())[0]]

        if len(remote_and_organization_and_repository_from_urls) > 1 and branch_used_for_tracking_data is not None:
            remote_for_fetching_of_branch = self._git.get_combined_remote_for_fetching_of_branch(
                branch=branch_used_for_tracking_data,
                remotes=list(remote_and_organization_and_repository_from_urls.keys()))
            if remote_for_fetching_of_branch is not None:
                return remote_and_organization_and_repository_from_urls[remote_for_fetching_of_branch]

        if 'origin' in remote_and_organization_and_repository_from_urls:
            return remote_and_organization_and_repository_from_urls['origin']

        raise MacheteException(
            f'Multiple non-origin remotes correspond to {spec.display_name} in this repository: '
            f'{", ".join(remote_and_organization_and_repository_from_urls.keys())} -> aborting. \n'
            f'You can select the {spec.repository_name} by providing some or all of git config keys:\n'
            f'{spec.git_config_keys.for_locating_repo_message()}\n')

    def _init_code_hosting_client(self,
                                  branch_used_for_tracking_data: Optional[LocalBranchShortName] = None
                                  ) -> Tuple[str, OrganizationAndRepositoryAndRemote]:
        if self.__code_hosting_client is not None:
            raise UnexpectedMacheteException("Code hosting client has already been initialized.")
        domain = self.__derive_code_hosting_domain()
        org_repo_remote = self.__derive_org_repo_and_remote(
            domain=domain, branch_used_for_tracking_data=branch_used_for_tracking_data)
        self.code_hosting_client = self.code_hosting_spec.create_client(
            domain=domain, organization=org_repo_remote.organization, repository=org_repo_remote.repository)
        return domain, org_repo_remote

    START_GIT_MACHETE_GENERATED_COMMENT = '<!-- start git-machete generated -->'
    END_GIT_MACHETE_GENERATED_COMMENT = '<!-- end git-machete generated -->'

    def __get_sole_pull_request_for_head(
            self,
            head: LocalBranchShortName,
            *,
            ignore_if_missing: bool
    ) -> Optional[PullRequest]:
        prs: List[PullRequest] = self.code_hosting_client.get_open_pull_requests_by_head(head)
        spec = self.code_hosting_spec
        org_and_repo = self.code_hosting_client.get_org_and_repo()
        if not prs:
            if ignore_if_missing:
                warn(f"no {spec.pr_short_name}s in <b>{org_and_repo}</b> "
                     f"have <b>{head}</b> as its {spec.head_branch_name} branch")
                return None
            else:
                raise MacheteException(f"No {spec.pr_short_name}s in <b>{org_and_repo}</b> "
                                       f"have <b>{head}</b> as its {spec.head_branch_name} branch")
        if len(prs) > 1:
            raise MacheteException(f"Multiple {spec.pr_short_name}s in <b>{org_and_repo}</b> "
                                   f"have <b>{head}</b> as its {spec.head_branch_name} branch: " +
                                   ", ".join(_pr.short_display_text() for _pr in prs))
        pr = prs[0]
        debug(f'found {pr}')
        return pr

    def __get_pr_description_into_style_from_config(self) -> PRDescriptionIntroStyle:
        config_key = self.code_hosting_spec.git_config_keys.pr_description_intro_style
        return PRDescriptionIntroStyle.from_string(
            value=self._git.get_config_attr(key=config_key, default_value="up-only"),
            from_where=f"`{config_key}` git config key"
        )

    def __generate_pr_description_intro(self, pr: PullRequest, style: PRDescriptionIntroStyle) -> str:
        if style == PRDescriptionIntroStyle.NONE:
            return ''

        if self.__all_open_prs is not None:
            prs_for_base_branch = list(filter(lambda _pr: _pr.head == pr.base, self.__all_open_prs))
        else:
            # For determining the PR chain, we need to fetch all PRs from the repo.
            # We could just fetch them straight away... but this list can be quite long for commercial monorepos,
            # esp. given that GitHub and GitLab limit the single page to 100 PRs/MRs (so multiple HTTP requests may be needed).
            # As a slight optimization, in the default UP_ONLY style,
            # let's fetch the full PR list only if the current PR has a base PR at all.
            prs_for_base_branch = self.code_hosting_client.get_open_pull_requests_by_head(LocalBranchShortName(pr.base))
        if style in (PRDescriptionIntroStyle.UP_ONLY, PRDescriptionIntroStyle.UP_ONLY_NO_BRANCHES) and len(prs_for_base_branch) == 0:
            return ''
        spec = self.code_hosting_spec
        pr_short_name = spec.pr_short_name
        br_before_branches = ' <br>' if spec.pr_intro_br_before_branches else ''

        pr_up_path = list(reversed(self.__get_upwards_path_including_pr(pr)))
        if style in (PRDescriptionIntroStyle.FULL, PRDescriptionIntroStyle.FULL_NO_BRANCHES):
            pr_down_tree = self.__get_downwards_tree_excluding_pr(pr)
        else:
            pr_down_tree = []
        if len(pr_up_path) == 1 and pr_down_tree == []:
            return ''

        prepend = f'{self.START_GIT_MACHETE_GENERATED_COMMENT}\n\n'
        # In FULL mode, we're likely to generate a non-empty intro even when there are NO upstream PRs above
        if len(prs_for_base_branch) >= 1:
            prepend += f'# Based on {prs_for_base_branch[0].display_text(fmt=False)}\n\n'

        if pr_down_tree and len(pr_up_path) > 1:
            prepend += f'## Chain of upstream {pr_short_name}s & tree of downstream {pr_short_name}s'
        elif pr_down_tree:
            prepend += f'## Tree of downstream {pr_short_name}s'
        else:
            prepend += f'## Chain of upstream {pr_short_name}s'
        current_date = utils.get_current_date()
        prepend += f' as of {current_date}\n\n'

        def pr_entry(_pr: PullRequest, _depth: int) -> str:
            result = '  ' * _depth
            display_text = _pr.display_text(fmt=False)
            explicit_title = f' _{_pr.title}_' if spec.pr_intro_explicit_title else ''
            if style in (PRDescriptionIntroStyle.UP_ONLY, PRDescriptionIntroStyle.FULL):
                if _pr.number == pr.number:
                    result += f'* **{display_text}{explicit_title} (THIS ONE)**:{br_before_branches}\n'
                else:
                    result += f'* {display_text}{explicit_title}:{br_before_branches}\n'
                result += '  ' * _depth
                result += f'  `{_pr.base}` ← `{_pr.head}`\n\n'
            else:
                if _pr.number == pr.number:
                    result += f'* **{display_text}{explicit_title} (THIS ONE)**\n\n'
                else:
                    result += f'* {display_text}{explicit_title}\n\n'
            return result

        base_depth = 0
        for up_pr in pr_up_path:
            prepend += pr_entry(up_pr, base_depth)
            base_depth += 1
        for (down_pr, depth) in pr_down_tree:
            prepend += pr_entry(down_pr, base_depth + depth)
        prepend += f'{self.END_GIT_MACHETE_GENERATED_COMMENT}\n'
        return prepend

    def update_pull_request_descriptions(
        self, *,
            all: bool = False,
            by: Optional[str] = None,
            mine: bool = False,
            related: bool = False
    ) -> None:
        spec = self.code_hosting_spec
        if self.__code_hosting_client is None:
            self._init_code_hosting_client()

        current_user: Optional[str] = self.code_hosting_client.get_current_user_login()
        if not current_user and mine:
            msg = (f"Could not determine current user name, please check that the {spec.display_name} API token provided by one of the: "
                   f"{spec.token_providers_message}is valid.")
            raise MacheteException(msg)

        if related:
            head = self._git.get_current_branch()
            related_to = self.__get_sole_pull_request_for_head(head, ignore_if_missing=False)
        else:
            related_to = None
        applicable_prs: List[PullRequest] = self._get_applicable_pull_requests(
            all=all, by=current_user if mine else by, related_to=related_to)
        debug("applicable PRs: " + ", ".join(pr.display_text() for pr in applicable_prs))

        for pr in applicable_prs:
            new_description = self._get_updated_pull_request_description(pr)
            if pr.description != new_description:
                self.code_hosting_client.set_description_of_pull_request(pr.number, description=new_description)
                pr.description = new_description
                print(fmt(f'Description of {pr.display_text()} (<b>{pr.head} {get_right_arrow()} {pr.base}</b>) has been updated'))

    def checkout_pull_requests(
        self,
            pr_numbers: Optional[List[int]],
            *,
            all: bool = False,
            by: Optional[str] = None,
            mine: bool = False,
            fail_on_missing_current_user_for_my_open_prs: bool = False
    ) -> None:
        spec = self.code_hosting_spec
        domain, org_repo_remote = self._init_code_hosting_client()

        current_user: Optional[str] = self.code_hosting_client.get_current_user_login()
        if not current_user and mine:
            msg = (f"Could not determine current user name, please check that the {spec.display_name} API token provided by one of the: "
                   f"{spec.token_providers_message}is valid.")
            if fail_on_missing_current_user_for_my_open_prs:
                raise MacheteException(msg)
            else:
                warn(msg)
                return
        if mine:
            by = current_user

        applicable_prs: List[PullRequest] = self._get_applicable_pull_requests(
            pr_numbers=pr_numbers, all=all, by=by)

        debug(f'organization is {org_repo_remote.organization}, repository is {org_repo_remote.repository}')
        self._git.fetch_remote(org_repo_remote.remote)

        prs_to_annotate = set(applicable_prs)
        for pr in sorted(applicable_prs, key=lambda x: x.number):
            head_org_repo_and_git_url = self.code_hosting_client.get_org_repo_and_git_url_by_repo_id_or_none(pr.head_repo_id)
            if head_org_repo_and_git_url:
                head_org = head_org_repo_and_git_url.organization  # explicit access to attributes to satisfy vulture
                head_repo = head_org_repo_and_git_url.repository
                head_repo_git_url = head_org_repo_and_git_url.git_url
                head_org_and_repo = OrganizationAndRepository(head_org, head_repo)
                if '/'.join([org_repo_remote.remote, pr.head]) not in self._git.get_remote_branches():
                    remote_already_added: Optional[str] = self.__get_remote_name_for_org_and_repo(domain, head_org_and_repo)
                    if remote_already_added:
                        remote_to_fetch = remote_already_added
                    else:
                        remote_to_fetch = head_org
                        if remote_to_fetch not in self._git.get_remotes():
                            self._git.add_remote(remote_to_fetch, head_repo_git_url)
                    if org_repo_remote.remote != remote_to_fetch:
                        self._git.fetch_remote(remote_to_fetch)
                    if '/'.join([remote_to_fetch, pr.head]) not in self._git.get_remote_branches():
                        raise MacheteException(
                            f"Could not check out {pr.display_text()} "
                            f"because branch {bold(pr.head)} is already deleted from {bold(remote_to_fetch)}.")
            else:
                warn(f'{pr.display_text()} comes from fork and its {spec.repository_name} is already deleted. '
                     f'No remote tracking data will be set up for {bold(pr.head)} branch.')
                refspec = f'{self.code_hosting_client.get_ref_name_for_pull_request(pr.number)}:{pr.head}'
                self._git.fetch_refspec(org_repo_remote.remote, refspec)
                self._git.checkout(LocalBranchShortName.of(pr.head))
            if pr.state in ('closed', 'merged'):
                warn(f'{pr.display_text()} is already closed.')
            debug(f'found {pr}')

            pr_path: List[PullRequest] = self.__get_upwards_path_including_pr(pr)
            prs_to_annotate.update(pr_path)
            reversed_pr_path: List[PullRequest] = pr_path[::-1]  # need to add from root downwards
            if reversed_pr_path[0].base not in self.managed_branches:
                self.add(
                    branch=LocalBranchShortName.of(reversed_pr_path[0].base),
                    opt_as_first_child=False,
                    opt_as_root=True,
                    opt_onto=None,
                    opt_yes=True,
                    verbose=False,
                    switch_head_if_new_branch=False)
            for pr_on_path in reversed_pr_path:
                if pr_on_path.head not in self.managed_branches:
                    self.add(
                        branch=LocalBranchShortName.of(pr_on_path.head),
                        opt_onto=LocalBranchShortName.of(pr_on_path.base),
                        opt_as_first_child=False,
                        opt_as_root=False,
                        opt_yes=True,
                        verbose=False,
                        switch_head_if_new_branch=False)
                    print(fmt(f"{pr_on_path.display_text()} checked out at local branch {bold(pr_on_path.head)}"))

        debug(f'Current {spec.display_name} user is ' + (current_user or '<none>'))
        self.__sync_annotations_to_branch_layout_file(list(prs_to_annotate), current_user=current_user, include_urls=False, verbose=False)
        if len(applicable_prs) == 1:
            self._git.checkout(LocalBranchShortName.of(applicable_prs[0].head))

    def __get_downwards_tree_excluding_pr(self, original_pr: PullRequest) -> List[Tuple[PullRequest, int]]:
        """Returns pairs of (PR, depth below the given PR)"""

        visited_head_branches: Set[str] = set([])

        def reverse_pr_dfs(pr: PullRequest, depth: int) -> Iterator[Tuple[PullRequest, int]]:
            visited_head_branches.add(pr.head)
            down_prs = filter(lambda x: x.base == pr.head, self._get_all_open_prs())
            for down_pr in sorted(down_prs, key=lambda x: x.number):
                if down_pr.head not in visited_head_branches:
                    yield (down_pr, depth + 1)
                    yield from reverse_pr_dfs(down_pr, depth + 1)

        return list(reverse_pr_dfs(original_pr, 0))

    def __get_upwards_path_including_pr(self, original_pr: PullRequest) -> List[PullRequest]:
        visited_head_branches: List[str] = [original_pr.head]
        path: List[PullRequest] = [original_pr]
        pr_base: Optional[str] = original_pr.base
        while pr_base:
            # The chain needs to stop at main/master branches
            # to avoid false-positive cycles when there's a PR from main in fork to main in the original repo.
            # See https://github.com/VirtusLab/git-machete/issues/1276
            if pr_base in ('main', 'master'):
                return path
            if pr_base in visited_head_branches:
                spec = self.code_hosting_spec
                raise MacheteException(f"There is a cycle between {spec.display_name} {spec.pr_short_name}s: " +
                                       " -> ".join(visited_head_branches + [pr_base]))
            visited_head_branches += [pr_base]
            pr = utils.find_or_none(lambda x: x.head == pr_base, self._get_all_open_prs())
            path = (path + [pr]) if pr else path
            pr_base = pr.base if pr else None
        return path

    def _get_applicable_pull_requests(
            self,
            *,
            pr_numbers: Optional[List[int]] = None,
            all: bool = False,
            by: Optional[str] = None,
            related_to: Optional[PullRequest] = None
    ) -> List[PullRequest]:
        result: List[PullRequest] = []
        spec = self.code_hosting_spec
        all_open_prs = self._get_all_open_prs()
        repo_pretty = f"{spec.repository_name} {bold(self.code_hosting_client.organization)}/{bold(self.code_hosting_client.repository)}"
        if pr_numbers:
            for pr_number in pr_numbers:
                pr: Optional[PullRequest] = utils.find_or_none(lambda x: x.number == pr_number, all_open_prs)
                if pr:
                    result.append(pr)
                else:
                    pr = self.code_hosting_client.get_pull_request_by_number_or_none(pr_number)
                    if pr:
                        result.append(pr)
                    else:

                        raise MacheteException(
                            f"{spec.pr_short_name} {spec.pr_ordinal_char}{bold(str(pr_number))} is not found in {repo_pretty}")
            return result
        if all:
            if not all_open_prs:
                warn(f"Currently there are no {spec.pr_full_name}s opened in {repo_pretty}")
                return []
            return all_open_prs
        elif by:
            result = [pr for pr in all_open_prs if pr.user == by]
            if not result:
                warn(f"User {bold(by)} has no open {spec.pr_full_name} in {repo_pretty}")
                return []
            return result
        elif related_to:
            style = self.__get_pr_description_into_style_from_config()
            if style in (PRDescriptionIntroStyle.FULL, PRDescriptionIntroStyle.FULL_NO_BRANCHES):
                result = list(reversed(self.__get_upwards_path_including_pr(related_to)))
            else:
                result = [related_to]
            result += [pr_ for pr_, _ in self.__get_downwards_tree_excluding_pr(related_to)]
            return result

        raise UnexpectedMacheteException("All params passed to __get_applicable_pull_requests are empty.")
