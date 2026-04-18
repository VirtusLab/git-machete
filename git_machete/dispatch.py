from typing import List, Optional

from git_machete import utils
from git_machete.client.advance import AdvanceMacheteClient
from git_machete.client.anno import AnnoMacheteClient
from git_machete.client.base import MacheteClient
from git_machete.client.diff import DiffMacheteClient
from git_machete.client.discover import DiscoverMacheteClient
from git_machete.client.fork_point import ForkPointMacheteClient
from git_machete.client.go_interactive import GoInteractiveMacheteClient
from git_machete.client.go_show import GoShowMacheteClient
from git_machete.client.log import LogMacheteClient
from git_machete.client.slide_out import SlideOutMacheteClient
from git_machete.client.squash import SquashMacheteClient
from git_machete.client.status import StatusMacheteClient
from git_machete.client.traverse import (TraverseMacheteClient,
                                         TraverseReturnTo, TraverseStartFrom)
from git_machete.client.update import UpdateMacheteClient
from git_machete.client.with_code_hosting import MacheteClientWithCodeHosting
from git_machete.code_hosting import CodeHostingSpec
from git_machete.config import MacheteConfig, SquashMergeDetection
from git_machete.git_operations import (AnyRevision, GitContext,
                                        LocalBranchShortName)
from git_machete.utils import MacheteException, green_ok, print_fmt, warn


def add(
        git: GitContext,
        *,
        branch: LocalBranchShortName,
        opt_onto: Optional[LocalBranchShortName],
        opt_as_first_child: bool,
        opt_as_root: bool,
        opt_yes: bool
) -> None:
    client = MacheteClient(git)
    client.read_branch_layout_file()
    client.add(
        branch=branch,
        opt_onto=opt_onto,
        opt_as_first_child=opt_as_first_child,
        opt_as_root=opt_as_root,
        opt_yes=opt_yes,
        verbose=True,
        switch_head_if_new_branch=True)


def advance(git: GitContext, *, opt_yes: bool) -> None:
    client = AdvanceMacheteClient(git)
    client.read_branch_layout_file()
    client.advance(opt_yes=opt_yes)


def anno(
        git: GitContext,
        *,
        branch: LocalBranchShortName,
        annotation_text: Optional[List[str]],
        opt_sync_github_prs: bool,
        opt_sync_gitlab_mrs: bool,
        spec: CodeHostingSpec
) -> None:
    client = AnnoMacheteClient(git, spec)
    client.read_branch_layout_file(verify_branches=False)
    if opt_sync_github_prs or opt_sync_gitlab_mrs:
        client.sync_annotations_to_prs(include_urls=False)
    else:
        client.expect_in_managed_branches(branch)
        if annotation_text is not None:
            client.annotate(branch, annotation_text)
        else:
            client.print_annotation(branch)


def clean(
        git: GitContext,
        *,
        opt_checkout_my_github_prs: bool,
        opt_yes: bool,
        spec: CodeHostingSpec
) -> None:
    client = MacheteClientWithCodeHosting(git, spec)
    client.read_branch_layout_file()
    if opt_checkout_my_github_prs:
        client.checkout_pull_requests(pr_numbers=[], mine=True)
    client.delete_unmanaged(opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=opt_yes)
    client.delete_untracked(opt_yes=opt_yes)


def delete_unmanaged(git: GitContext, *, opt_yes: bool) -> None:
    client = MacheteClient(git)
    client.read_branch_layout_file()
    client.delete_unmanaged(
        opt_squash_merge_detection=MacheteConfig(git).squash_merge_detection(),
        opt_yes=opt_yes)


def diff(
        git: GitContext,
        *,
        branch: Optional[LocalBranchShortName],
        opt_stat: bool,
        extra_args: List[str]
) -> None:
    client = DiffMacheteClient(git)
    client.read_branch_layout_file()
    client.display_diff(branch=branch, opt_stat=opt_stat, extra_git_diff_args=extra_args)


def discover(
        git: GitContext,
        *,
        opt_checked_out_since: Optional[str],
        opt_list_commits: bool,
        opt_roots: List[LocalBranchShortName],
        opt_yes: bool
) -> None:
    client = DiscoverMacheteClient(git)
    client.read_branch_layout_file()
    client.discover(
        opt_checked_out_since=opt_checked_out_since,
        opt_list_commits=opt_list_commits,
        opt_roots=opt_roots,
        opt_yes=opt_yes)


def edit(git: GitContext) -> None:
    client = MacheteClient(git)
    client.edit()


def file(git: GitContext) -> None:
    client = MacheteClient(git)
    print(utils.abspath_posix(client.branch_layout_file_path))


def fork_point(
        git: GitContext,
        *,
        branch: LocalBranchShortName,
        opt_inferred: bool = False,
        opt_override_to: Optional[str] = None,
        opt_override_to_inferred: bool = False,
        opt_override_to_parent: bool = False,
        opt_unset_override: bool = False
) -> None:
    client = ForkPointMacheteClient(git)
    client.read_branch_layout_file()
    upstream = client.up_branch_for(branch)
    client.expect_in_local_branches(branch)

    if opt_inferred:
        print(client.fork_point(branch=branch, use_overrides=False))
    elif opt_override_to:
        override_to = AnyRevision.of(opt_override_to)
        client.set_fork_point_override(branch, override_to)
        _warn_on_fork_point_deprecation(
            git, branch=branch, upstream=upstream,
            flag="--override-to=...",
            revision=override_to,
            revision_str="selected commit")
    elif opt_override_to_inferred:
        inferred = client.fork_point(branch=branch, use_overrides=False)
        client.set_fork_point_override(branch, inferred)
        _warn_on_fork_point_deprecation(
            git, branch=branch, upstream=upstream,
            flag="--override-to-inferred",
            revision=inferred,
            revision_str="inferred commit")
    elif opt_override_to_parent:
        if upstream:
            client.set_fork_point_override(branch, upstream)
        else:
            raise MacheteException(
                f"Branch <b>{branch}</b> does not have upstream (parent) branch")
    elif opt_unset_override:
        client.unset_fork_point_override(branch)
    else:
        print(client.fork_point(branch=branch, use_overrides=True))


def _warn_on_fork_point_deprecation(
        git: GitContext,
        *,
        branch: LocalBranchShortName,
        upstream: Optional[LocalBranchShortName],
        flag: str,
        revision: AnyRevision,
        revision_str: str
) -> None:
    if upstream:
        print()
        warn(
            f"`git machete fork-point {flag}` may lead to a confusing user experience and is deprecated.\n\n"
            f"If the commits between <b>{upstream}</b> (parent of <b>{branch}</b>) "
            f"and {revision_str} <b>{git.get_short_commit_hash_by_revision_or_none(revision) or ''}</b> "
            f"do NOT belong to <b>{branch}</b>, consider using:\n"
            f"    `git checkout {branch}`\n"
            f"    `git machete update --fork-point=\"{revision}\"`\n\n"
            "Otherwise, if you're okay with treating these commits "
            f"as a part of <b>{branch}</b>'s unique history, use instead:\n"
            f"    `git machete fork-point {branch} --override-to-parent`"
        )


def go(git: GitContext, *, direction: Optional[str]) -> None:
    git.expect_no_operation_in_progress()
    current_branch_or_none = git.get_current_branch_or_none()

    if direction is not None:
        client = GoShowMacheteClient(git)
        client.read_branch_layout_file()
        dest = client.parse_direction(
            direction, branch=current_branch_or_none,
            allow_current=False, pick_if_multiple=True)[0]
        if dest != current_branch_or_none:
            print_fmt(f"Checking out <b>{dest}</b>... ", newline=False)
            git.checkout(dest)
            print_fmt(green_ok())
    else:
        interactive_client = GoInteractiveMacheteClient(git)
        interactive_client.read_branch_layout_file()
        interactive_client.expect_at_least_one_managed_branch()
        selected_branch = interactive_client.go_interactive(current_branch=current_branch_or_none)
        if selected_branch is not None and selected_branch != current_branch_or_none:
            print()
            print_fmt(f"Checking out <b>{selected_branch}</b>... ", newline=False)
            git.checkout(selected_branch)
            print_fmt(green_ok())


def is_managed(git: GitContext, *, branch: Optional[LocalBranchShortName]) -> bool:
    client = MacheteClient(git)
    client.read_branch_layout_file()
    return branch is not None and branch in client.managed_branches


def list_branches(
        git: GitContext,
        *,
        category: str,
        branch: Optional[LocalBranchShortName]
) -> None:
    from git_machete.utils import UnexpectedMacheteException
    client = MacheteClient(git)
    client.read_branch_layout_file()
    res: List[LocalBranchShortName] = []
    if category == "addable":
        res = client.addable_branches
    elif category == "childless":
        res = client.childless_managed_branches
    elif category == "managed":
        res = client.managed_branches
    elif category == "slidable":
        res = client.slidable_branches
    elif category == "slidable-after":
        assert branch is not None
        client.expect_in_managed_branches(branch)
        res = client.get_slidable_after(branch)
    elif category == "unmanaged":
        res = client.unmanaged_branches
    elif category == "with-overridden-fork-point":
        res = client.branches_with_overridden_fork_point
    else:
        raise UnexpectedMacheteException(f"Invalid category: `{category}`")

    if res:
        print("\n".join(res))


def log(
        git: GitContext,
        *,
        branch: LocalBranchShortName,
        extra_args: List[str]
) -> None:
    client = LogMacheteClient(git)
    client.read_branch_layout_file()
    client.display_log(branch, extra_git_log_args=extra_args)


def reapply(
        git: GitContext,
        *,
        opt_fork_point: Optional[AnyRevision],
        opt_no_interactive_rebase: bool
) -> None:
    client = MacheteClient(git)
    client.read_branch_layout_file()
    current_branch = git.get_current_branch()
    if opt_fork_point is not None:
        client.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
            fork_point=opt_fork_point, branch=current_branch)

    resolved_fork_point = opt_fork_point or client.fork_point(branch=current_branch, use_overrides=True)
    client.rebase(
        onto=resolved_fork_point,
        from_exclusive=resolved_fork_point,
        branch=current_branch,
        opt_no_interactive_rebase=opt_no_interactive_rebase)


def show(
        git: GitContext,
        *,
        direction: str,
        branch: LocalBranchShortName
) -> None:
    client = GoShowMacheteClient(git)
    client.read_branch_layout_file(verify_branches=False)
    print('\n'.join(client.parse_direction(direction, branch=branch, allow_current=True, pick_if_multiple=False)))


def slide_out(
        git: GitContext,
        *,
        branches: List[LocalBranchShortName],
        opt_delete: bool,
        opt_down_fork_point: Optional[AnyRevision],
        opt_merge: bool,
        opt_no_edit_merge: bool,
        opt_no_interactive_rebase: bool,
        opt_no_rebase: bool,
        opt_removed_from_remote: bool
) -> None:
    client = SlideOutMacheteClient(git)
    client.read_branch_layout_file()
    if opt_removed_from_remote:
        client.slide_out_removed_from_remote(opt_delete=opt_delete)
    else:
        client.slide_out(
            branches_to_slide_out=branches,
            opt_delete=opt_delete,
            opt_down_fork_point=opt_down_fork_point,
            opt_merge=opt_merge,
            opt_no_edit_merge=opt_no_edit_merge,
            opt_no_interactive_rebase=opt_no_interactive_rebase,
            opt_no_rebase=opt_no_rebase)


def squash(git: GitContext, *, opt_fork_point: Optional[AnyRevision]) -> None:
    client = SquashMacheteClient(git)
    client.read_branch_layout_file()
    current_branch = git.get_current_branch()
    if opt_fork_point is not None:
        client.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
            fork_point=opt_fork_point, branch=current_branch)

    resolved_fork_point = opt_fork_point or client.fork_point_or_none(branch=current_branch, use_overrides=True)
    if resolved_fork_point is None:
        raise MacheteException(
            f"git-machete cannot determine the range of commits unique to branch <b>{current_branch}</b>.\n"
            f"Use `git machete squash --fork-point=...` to select the commit "
            f"after which the commits of <b>{current_branch}</b> start.\n"
            "For example, if you want to squash 3 latest commits, use `git machete squash --fork-point=HEAD~3`."
        )
    client.squash(current_branch=current_branch, opt_fork_point=resolved_fork_point)


def status(
        git: GitContext,
        *,
        opt_list_commits: bool,
        opt_list_commits_with_hashes: bool,
        opt_squash_merge_detection: SquashMergeDetection
) -> None:
    client = StatusMacheteClient(git)
    client.read_branch_layout_file(interactively_slide_out_invalid_branches=utils.is_stdout_a_tty())
    client.expect_at_least_one_managed_branch()
    client.status(
        warn_when_branch_in_sync_but_fork_point_off=True,
        opt_list_commits=opt_list_commits,
        opt_list_commits_with_hashes=opt_list_commits_with_hashes,
        opt_squash_merge_detection=opt_squash_merge_detection)


def traverse(
        git: GitContext,
        *,
        opt_fetch: bool,
        opt_list_commits: bool,
        opt_merge: bool,
        opt_no_edit_merge: bool,
        opt_no_interactive_rebase: bool,
        opt_push_tracked: bool,
        opt_push_untracked: bool,
        opt_return_to: str,
        opt_squash_merge_detection: SquashMergeDetection,
        opt_start_from: str,
        opt_stop_after: Optional[LocalBranchShortName],
        opt_sync_github_prs: bool,
        opt_sync_gitlab_mrs: bool,
        opt_yes: bool,
        spec: CodeHostingSpec
) -> None:
    resolved_return_to = TraverseReturnTo.from_string(opt_return_to, "`--return-to` flag")
    resolved_start_from = TraverseStartFrom.from_string_or_branch(opt_start_from, git)

    client = TraverseMacheteClient(git, spec)
    client.read_branch_layout_file(interactively_slide_out_invalid_branches=utils.is_stdout_a_tty())
    client.traverse(
        opt_fetch=opt_fetch,
        opt_list_commits=opt_list_commits,
        opt_merge=opt_merge,
        opt_no_edit_merge=opt_no_edit_merge,
        opt_no_interactive_rebase=opt_no_interactive_rebase,
        opt_push_tracked=opt_push_tracked,
        opt_push_untracked=opt_push_untracked,
        opt_return_to=resolved_return_to,
        opt_squash_merge_detection=opt_squash_merge_detection,
        opt_start_from=resolved_start_from,
        opt_stop_after=opt_stop_after,
        opt_sync_github_prs=opt_sync_github_prs,
        opt_sync_gitlab_mrs=opt_sync_gitlab_mrs,
        opt_yes=opt_yes)


def update(
        git: GitContext,
        *,
        opt_merge: bool,
        opt_no_edit_merge: bool,
        opt_no_interactive_rebase: bool,
        opt_fork_point: Optional[AnyRevision]
) -> None:
    client = UpdateMacheteClient(git)
    client.read_branch_layout_file()
    if opt_fork_point is not None:
        client.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
            fork_point=opt_fork_point, branch=git.get_current_branch())
    client.update(
        opt_merge=opt_merge,
        opt_no_edit_merge=opt_no_edit_merge,
        opt_no_interactive_rebase=opt_no_interactive_rebase,
        opt_fork_point=opt_fork_point)


# Code hosting (github/gitlab) subcommands

def code_hosting_anno_prs(
        git: GitContext,
        spec: CodeHostingSpec,
        *,
        include_urls: bool
) -> None:
    client = MacheteClientWithCodeHosting(git, spec)
    client.read_branch_layout_file()
    client.sync_annotations_to_prs(include_urls=include_urls)


def code_hosting_checkout_prs(
        git: GitContext,
        spec: CodeHostingSpec,
        *,
        pr_numbers: List[int],
        opt_all: bool,
        opt_mine: bool,
        opt_by: Optional[str]
) -> None:
    client = MacheteClientWithCodeHosting(git, spec)
    client.read_branch_layout_file()
    client.checkout_pull_requests(
        pr_numbers=pr_numbers,
        all=opt_all,
        mine=opt_mine,
        by=opt_by,
        fail_on_missing_current_user_for_my_open_prs=True)


def code_hosting_create_pr(
        git: GitContext,
        spec: CodeHostingSpec,
        *,
        opt_base: Optional[LocalBranchShortName],
        opt_draft: bool,
        opt_title: Optional[str],
        opt_update_related_descriptions: bool,
        opt_yes: bool
) -> None:
    current_branch = git.get_current_branch()
    client = MacheteClientWithCodeHosting(git, spec)
    client.read_branch_layout_file()
    client.sync_before_creating_pull_request(opt_yes=opt_yes)
    client.create_pull_request(
        head=current_branch,
        opt_base=opt_base,
        opt_draft=opt_draft,
        opt_title=opt_title,
        opt_update_related_descriptions=opt_update_related_descriptions,
        opt_yes=opt_yes)


def code_hosting_restack_pr(
        git: GitContext,
        spec: CodeHostingSpec,
        *,
        opt_update_related_descriptions: bool
) -> None:
    client = MacheteClientWithCodeHosting(git, spec)
    client.read_branch_layout_file()
    client.restack_pull_request(opt_update_related_descriptions=opt_update_related_descriptions)


def code_hosting_retarget_pr(
        git: GitContext,
        spec: CodeHostingSpec,
        *,
        branch: LocalBranchShortName,
        opt_ignore_if_missing: bool,
        opt_update_related_descriptions: bool
) -> None:
    client = MacheteClientWithCodeHosting(git, spec)
    client.read_branch_layout_file()
    client.expect_in_managed_branches(branch)
    client.retarget_pull_request(
        head=branch,
        opt_ignore_if_missing=opt_ignore_if_missing,
        opt_update_related_descriptions=opt_update_related_descriptions)


def code_hosting_sync(
        git: GitContext,
        spec: CodeHostingSpec,
        *,
        opt_yes: bool
) -> None:
    client = MacheteClientWithCodeHosting(git, spec)
    client.read_branch_layout_file()
    client.checkout_pull_requests(pr_numbers=[], mine=True)
    client.delete_unmanaged(opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=False)
    client.delete_untracked(opt_yes=opt_yes)


def code_hosting_update_pr_descriptions(
        git: GitContext,
        spec: CodeHostingSpec,
        *,
        opt_all: bool,
        opt_by: Optional[str],
        opt_mine: bool,
        opt_related: bool
) -> None:
    client = MacheteClientWithCodeHosting(git, spec)
    client.read_branch_layout_file()
    client.update_pull_request_descriptions(
        all=opt_all, by=opt_by, mine=opt_mine, related=opt_related)
