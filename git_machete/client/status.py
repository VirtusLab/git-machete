"""Status command: display branch tree and sync state."""

import io
import os
import sys
from enum import Enum, auto
from typing import Dict, List, NamedTuple, Optional, Tuple

from git_machete import utils
from git_machete.annotation import Annotation
from git_machete.config import SquashMergeDetection
from git_machete.exceptions import MacheteException
from git_machete.git_operations import (BranchPair, FullCommitHash,
                                        GitLogEntry, LocalBranchShortName,
                                        SyncToRemoteStatus)
from git_machete.utils import (PopenResult, bold, colored, debug, dim,
                               underline, warn)

from .base import MacheteClient


class SyncToParentStatus(Enum):
    IN_SYNC = auto()
    IN_SYNC_BUT_FORK_POINT_OFF = auto()
    OUT_OF_SYNC = auto()
    MERGED_TO_PARENT = auto()


class StatusFlags(NamedTuple):
    """Options and display flags for status output."""

    maybe_space_before_branch_name: str
    opt_list_commits: bool
    opt_list_commits_with_hashes: bool
    opt_squash_merge_detection: SquashMergeDetection


class StatusOngoingOperation(NamedTuple):
    """Which branch (if any) is checked out / rebased / bisected and which Git operations are in progress."""

    currently_bisected_branch: Optional[LocalBranchShortName]
    currently_rebased_branch: Optional[LocalBranchShortName]
    currently_checked_out_branch: Optional[LocalBranchShortName]
    is_am_in_progress: bool
    is_cherry_pick_in_progress: bool
    is_merge_in_progress: bool
    is_revert_in_progress: bool


class StatusBranch(NamedTuple):
    """Per-branch data for status output (tree structure, sync state, commits, annotations)."""

    up_branch: Optional[LocalBranchShortName]
    down_branches: List[LocalBranchShortName]
    sync_to_parent_status: SyncToParentStatus
    commits: List[Tuple[GitLogEntry, str]]
    sync_status: str
    hook_output: str
    annotation: Optional[Annotation]


class StatusData(NamedTuple):
    """All precomputed data needed to render status output (tree and optional warning)."""

    flags: StatusFlags
    branches: Dict[LocalBranchShortName, StatusBranch]
    branches_in_display_order: List[LocalBranchShortName]
    roots: List[LocalBranchShortName]
    ongoing_operation: StatusOngoingOperation


class StatusFormatOutput(NamedTuple):
    """Result of formatting status output. Returned by format_status_output."""

    result: str
    # Maps each branch to the 0-based index of the line in result (when split by newlines) where it appears.
    line_for_branch: Dict[LocalBranchShortName, int]


class StatusMacheteClient(MacheteClient):
    """Client for the status command. Exposes status() and can be used as a mixin for other clients."""

    @staticmethod
    def format_status_output(
        data: StatusData,
        *,
        selected_branch: Optional[LocalBranchShortName] = None,
    ) -> StatusFormatOutput:
        """Pure function: given StatusData, returns StatusFormatOutput (result string and line_for_branch).
        When selected_branch is set, that branch's name (not annotation/sync status) is wrapped in reverse video.
        line_for_branch maps each branch to the 0-based line index in result where it appears."""

        # These maps need to be defined in a local scope to avoid for mocking the color palette more easily.
        sync_to_parent_status_to_edge_color_map: Dict[SyncToParentStatus, str] = {
            SyncToParentStatus.IN_SYNC: utils.AE.GREEN,
            SyncToParentStatus.IN_SYNC_BUT_FORK_POINT_OFF: utils.AE.YELLOW,
            SyncToParentStatus.OUT_OF_SYNC: utils.AE.RED,
            SyncToParentStatus.MERGED_TO_PARENT: utils.AE.DIM
        }
        sync_to_parent_status_to_junction_ascii_only_map: Dict[SyncToParentStatus, str] = {
            SyncToParentStatus.IN_SYNC: "o-",
            SyncToParentStatus.IN_SYNC_BUT_FORK_POINT_OFF: "?-",
            SyncToParentStatus.OUT_OF_SYNC: "x-",
            SyncToParentStatus.MERGED_TO_PARENT: "m-"
        }
        out = io.StringIO()
        space = data.flags.maybe_space_before_branch_name
        line_for_branch: Dict[LocalBranchShortName, int] = {}
        line_index = 0

        next_sibling_of_ancestor_by_branch: Dict[LocalBranchShortName, List[Optional[LocalBranchShortName]]] = {}

        def prefix_dfs(parent: LocalBranchShortName, accumulated_path: List[Optional[LocalBranchShortName]]) -> None:
            next_sibling_of_ancestor_by_branch[parent] = accumulated_path
            children = data.branches[parent].down_branches
            if children:
                shifted_children: List[Optional[LocalBranchShortName]] = children[1:]  # type: ignore[assignment]
                for (v, nv) in zip(children, shifted_children + [None]):
                    prefix_dfs(v, accumulated_path + [nv])

        for root in data.roots:
            prefix_dfs(root, accumulated_path=[])

        def write_line_prefix(
            for_branch: LocalBranchShortName,
            next_sibling_of_ancestor: List[Optional[LocalBranchShortName]],
            suffix: str,
        ) -> None:

            out.write("  " + space)
            for sibling in next_sibling_of_ancestor[:-1]:
                if not sibling:
                    out.write("  " + space)
                else:
                    out.write(colored(
                        f"{utils.get_vertical_bar()} " + space,
                        sync_to_parent_status_to_edge_color_map[data.branches[sibling].sync_to_parent_status]))
            out.write(colored(suffix, sync_to_parent_status_to_edge_color_map[data.branches[for_branch].sync_to_parent_status]))

        for branch in data.branches_in_display_order:
            b = data.branches[branch]
            next_sibling_of_ancestor = next_sibling_of_ancestor_by_branch[branch]
            if b.up_branch is not None:
                write_line_prefix(branch, next_sibling_of_ancestor, f"{utils.get_vertical_bar()}\n")
                line_index += 1
                for commit, fp_suffix in b.commits:
                    write_line_prefix(branch, next_sibling_of_ancestor, utils.get_vertical_bar())
                    out.write(
                        f' {f"{dim(commit.short_hash)}  " if data.flags.opt_list_commits_with_hashes else ""}'
                        f'{dim(commit.subject)}{fp_suffix}\n'
                    )
                    line_index += 1
                if utils.ascii_only:
                    junction = sync_to_parent_status_to_junction_ascii_only_map[b.sync_to_parent_status]
                else:
                    next_sibling_of_branch: Optional[LocalBranchShortName] = next_sibling_of_ancestor[-1]
                    if next_sibling_of_branch and data.branches[next_sibling_of_branch].sync_to_parent_status == b.sync_to_parent_status:
                        junction = "├─"
                    else:
                        junction = "└─"
                write_line_prefix(branch, next_sibling_of_ancestor, junction + space)
            else:
                if branch != data.roots[0]:
                    out.write("\n")
                    line_index += 1
                out.write("  " + space)

            line_for_branch[branch] = line_index
            op = data.ongoing_operation
            if branch in (op.currently_checked_out_branch, op.currently_rebased_branch, op.currently_bisected_branch):
                if branch == op.currently_rebased_branch:
                    prefix = "REBASING "
                elif branch == op.currently_bisected_branch:
                    prefix = "BISECTING "
                elif op.is_am_in_progress:
                    prefix = "GIT AM IN PROGRESS "
                elif op.is_cherry_pick_in_progress:
                    prefix = "CHERRY-PICKING "
                elif op.is_merge_in_progress:
                    prefix = "MERGING "
                elif op.is_revert_in_progress:
                    prefix = "REVERTING "
                else:
                    prefix = ""
                current = f"{bold(colored(prefix, utils.AE.RED))}{bold(underline(branch, star_if_ascii_only=True))}"
            else:
                current = bold(branch)

            anno = ''
            if b.annotation is not None and b.annotation.formatted_full_text:
                anno = '  ' + b.annotation.formatted_full_text

            if selected_branch is not None and branch == selected_branch:
                current_part = f"{utils.AE.REVERSE_VIDEO}{current}{utils.AE.ENDC}"
            else:
                current_part = current
            out.write(f"{current_part}{anno}{b.sync_status}{b.hook_output}\n")
            line_index += 1

        return StatusFormatOutput(result=out.getvalue(), line_for_branch=line_for_branch)

    @staticmethod
    def _status_warning_message(data: StatusData) -> Optional[str]:
        """Derives the optional warning message for yellow edges (in-sync but fork point off)."""
        branches_in_sync_but_fork_point_off = [
            b for b in data.branches_in_display_order
            if data.branches[b].sync_to_parent_status == SyncToParentStatus.IN_SYNC_BUT_FORK_POINT_OFF
        ]
        if not branches_in_sync_but_fork_point_off:
            return None
        yellow_edge_branch = branches_in_sync_but_fork_point_off[0]
        if len(branches_in_sync_but_fork_point_off) == 1:
            first_part = (
                f"yellow edge indicates that fork point for {bold(yellow_edge_branch)} "
                f"is probably incorrectly inferred,\nor that some extra branch should be between "
                f"{bold(str(data.branches[yellow_edge_branch].up_branch))} and {bold(yellow_edge_branch)}"
            )
        else:
            affected_branches = ", ".join(map(bold, branches_in_sync_but_fork_point_off))
            first_part = (
                f"yellow edges indicate that fork points for {affected_branches} are probably incorrectly inferred,\n"
                "or that some extra branch should be added between each of these branches and its parent"
            )
        if not data.flags.opt_list_commits:
            second_part = (
                "Run `git machete status --list-commits` or "
                "`git machete status --list-commits-with-hashes` to see more details"
            )
        elif len(branches_in_sync_but_fork_point_off) == 1:
            second_part = (
                f"Consider using `git machete fork-point {yellow_edge_branch} --override-to-parent`,\n"
                f"rebasing {bold(yellow_edge_branch)} onto its parent with `git machete update`,\n"
                f"or reattaching {bold(yellow_edge_branch)} under a different parent branch"
            )
        else:
            second_part = (
                "Consider using `git machete fork-point <branch> --override-to-parent` for each affected branch,\n"
                "rebasing each branch onto its parent with `git machete update`,\n"
                "or reattaching the affected branches under different parent branches"
            )
        return f"{first_part}.\n\n{second_part}."

    def compute_status_data(self, *, flags: StatusFlags) -> StatusData:
        managed_branches: List[LocalBranchShortName] = list(self._state.managed_branches)

        sync_to_parent_status: Dict[LocalBranchShortName, SyncToParentStatus] = {}
        fork_point_hash_cached: Dict[LocalBranchShortName, Optional[FullCommitHash]] = {}
        fork_point_branches_cached: Dict[LocalBranchShortName, List[BranchPair]] = {}

        def fork_point_hash(for_branch: LocalBranchShortName) -> Optional[FullCommitHash]:
            if for_branch not in fork_point_hash_cached:
                try:
                    fork_point_hash_cached[for_branch], fork_point_branches_cached[for_branch] = \
                        self.fork_point_and_containing_branch_pairs(for_branch, use_overrides=True)
                except MacheteException:
                    fork_point_hash_cached[for_branch], fork_point_branches_cached[for_branch] = None, []
            return fork_point_hash_cached[for_branch]

        for branch in self._state.up_branch_for:
            parent_branch = self._state.up_branch_for[branch]
            assert parent_branch is not None
            if self.is_merged_to(
                    branch=branch,
                    upstream=parent_branch,
                    opt_squash_merge_detection=flags.opt_squash_merge_detection):
                sync_to_parent_status[branch] = SyncToParentStatus.MERGED_TO_PARENT
            elif not self._git.is_ancestor_or_equal(parent_branch.full_name(), branch.full_name()):
                sync_to_parent_status[branch] = SyncToParentStatus.OUT_OF_SYNC
            elif self._get_overridden_fork_point(branch) or \
                    self._git.get_commit_hash_by_revision(parent_branch) == fork_point_hash(branch):
                sync_to_parent_status[branch] = SyncToParentStatus.IN_SYNC
            else:
                sync_to_parent_status[branch] = SyncToParentStatus.IN_SYNC_BUT_FORK_POINT_OFF

        currently_bisected_branch = self._git.get_currently_bisected_branch_or_none()
        currently_rebased_branch = self._git.get_currently_rebased_branch_or_none()
        currently_checked_out_branch = self._git.get_currently_checked_out_branch_or_none()

        hook_path = self._git.get_hook_path("machete-status-branch")
        hook_executable = self._git.check_hook_executable(hook_path)

        commits_by_branch: Dict[LocalBranchShortName, List[Tuple[GitLogEntry, str]]] = {}
        if flags.opt_list_commits:
            for branch in self._state.up_branch_for:
                fork_point = fork_point_hash(branch)
                if not fork_point:
                    commits: List[Tuple[GitLogEntry, str]] = []
                elif sync_to_parent_status[branch] == SyncToParentStatus.MERGED_TO_PARENT:
                    commits = []
                elif sync_to_parent_status[branch] == SyncToParentStatus.IN_SYNC_BUT_FORK_POINT_OFF:
                    upstream = self._state.up_branch_for[branch]
                    assert upstream is not None
                    raw_commits = self._git.get_commits_between(upstream.full_name(), branch.full_name())
                    commits = []
                    for commit in raw_commits:
                        if commit.hash == fork_point:
                            fp_branches_formatted = " and ".join(
                                sorted(underline(lb_or_rb) for lb, lb_or_rb in fork_point_branches_cached[branch]))
                            right_arrow = colored(utils.get_right_arrow(), utils.AE.RED)
                            fork_point_str = colored("fork point ???", utils.AE.RED)
                            fp_suffix = (
                                f' {right_arrow} {fork_point_str} ' +
                                ("this commit" if flags.opt_list_commits_with_hashes else f"commit {commit.short_hash}") +
                                f' seems to be a part of the unique history of {fp_branches_formatted}'
                            )
                        else:
                            fp_suffix = ''
                        commits.append((commit, fp_suffix))
                else:
                    raw_commits = self._git.get_commits_between(fork_point, branch.full_name())
                    commits = [(commit, '') for commit in raw_commits]
                commits_by_branch[branch] = commits

        sync_status_by_branch: Dict[LocalBranchShortName, str] = {}
        hook_output_by_branch: Dict[LocalBranchShortName, str] = {}
        for branch in self._state.managed_branches:
            s, remote = self._git.get_combined_remote_sync_status(branch)
            sync_status_by_branch[branch] = {
                SyncToRemoteStatus.NO_REMOTES: "",
                SyncToRemoteStatus.UNTRACKED: colored(" (untracked)", utils.AE.ORANGE),
                SyncToRemoteStatus.IN_SYNC_WITH_REMOTE: "",
                SyncToRemoteStatus.BEHIND_REMOTE: colored(f" (behind {bold(remote)})", utils.AE.RED),  # type: ignore[arg-type]
                SyncToRemoteStatus.AHEAD_OF_REMOTE: colored(f" (ahead of {bold(remote)})", utils.AE.RED),  # type: ignore[arg-type]
                SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE: colored(
                    f" (diverged from & older than {bold(remote)})", utils.AE.RED),  # type: ignore[arg-type]
                SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE: colored(
                    f" (diverged from {bold(remote)})", utils.AE.RED),  # type: ignore[arg-type]
            }[SyncToRemoteStatus(s)]

            hook_output = ""
            if hook_executable:
                debug(f"running machete-status-branch hook ({hook_path}) for branch {branch}")
                hook_env = dict(os.environ, ASCII_ONLY=str(utils.ascii_only).lower())
                status_code, stdout, stderr = self._popen_hook(
                    hook_path, branch, cwd=self._git.get_current_worktree_root_dir(), env=hook_env)
                if status_code == 0 and not stdout.isspace():
                    hook_output = "  " + stdout.replace('\n', ' ').rstrip()
                else:
                    debug(f"machete-status-branch hook ({hook_path}) for branch {branch} "
                          f"returned {status_code}; stdout: '{stdout}'; stderr: '{stderr}'")
            hook_output_by_branch[branch] = hook_output

        branches: Dict[LocalBranchShortName, StatusBranch] = {}
        for branch in managed_branches:
            branches[branch] = StatusBranch(
                up_branch=self._state.up_branch_for.get(branch),
                down_branches=self.down_branches_for(branch) or [],
                sync_to_parent_status=sync_to_parent_status.get(branch, SyncToParentStatus.IN_SYNC),
                commits=commits_by_branch.get(branch, []),
                sync_status=sync_status_by_branch[branch],
                hook_output=hook_output_by_branch[branch],
                annotation=self._state.annotations.get(branch),
            )

        return StatusData(
            flags=flags,
            branches=branches,
            branches_in_display_order=managed_branches,
            roots=self._state.roots,
            ongoing_operation=StatusOngoingOperation(
                currently_bisected_branch=currently_bisected_branch,
                currently_rebased_branch=currently_rebased_branch,
                currently_checked_out_branch=currently_checked_out_branch,
                is_am_in_progress=self._git.is_am_in_progress(),
                is_cherry_pick_in_progress=self._git.is_cherry_pick_in_progress(),
                is_merge_in_progress=self._git.is_merge_in_progress(),
                is_revert_in_progress=self._git.is_revert_in_progress(),
            ),
        )

    def status(
            self,
            *,
            warn_when_branch_in_sync_but_fork_point_off: bool,
            opt_list_commits: bool,
            opt_list_commits_with_hashes: bool,
            opt_squash_merge_detection: SquashMergeDetection
    ) -> None:
        maybe_space_before_branch_name = ' ' if self._config.status_extra_space_before_branch_name() else ''
        flags = StatusFlags(
            maybe_space_before_branch_name=maybe_space_before_branch_name,
            opt_list_commits=opt_list_commits,
            opt_list_commits_with_hashes=opt_list_commits_with_hashes,
            opt_squash_merge_detection=opt_squash_merge_detection,
        )
        data = self.compute_status_data(flags=flags)
        format_out = self.format_status_output(data)
        sys.stdout.write(format_out.result)
        if warn_when_branch_in_sync_but_fork_point_off:
            warning_msg = self._status_warning_message(data)
            if warning_msg is not None:
                print("", file=sys.stderr)
                warn(warning_msg)

    @staticmethod
    def _popen_hook(*args: str, cwd: str, env: Dict[str, str]) -> PopenResult:
        if sys.platform == "win32":
            return utils.popen_cmd("sh", *args, cwd=cwd, env=env)
        else:
            return utils.popen_cmd(*args, cwd=cwd, env=env)
