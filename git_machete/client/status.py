"""Status command: display branch tree and sync state."""

import io
import os
import sys
from enum import Enum, auto
from typing import Dict, List, NamedTuple, Optional, Tuple

from git_machete.annotation import Annotation
from git_machete.client.base import MacheteClient
from git_machete.client.state import ManagedBranchName
from git_machete.config import SquashMergeDetection
from git_machete.git import (BranchPair, FullCommitHash, GitLogEntry,
                             LocalBranchShortName, SyncToRemoteStatus)
from git_machete.utils import markup
from git_machete.utils._subproc import PopenResult
from git_machete.utils.cmd import popen_cmd
from git_machete.utils.debug_log import debug
from git_machete.utils.exceptions import MacheteException
from git_machete.utils.markup import escape_markup, print_fmt, warn
from git_machete.utils.paths import Path, strip_longest_common_path_prefix


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

    parent: Optional[ManagedBranchName]
    children: List[ManagedBranchName]
    sync_to_parent_status: SyncToParentStatus
    commits: List[Tuple[GitLogEntry, str]]
    sync_status: str
    hook_output: str
    annotation: Optional[Annotation]
    worktree_label: Optional[str]


class StatusData(NamedTuple):
    """All precomputed data needed to render status output (tree and optional warning)."""

    flags: StatusFlags
    # Keep the dict keyed on the broader `LocalBranchShortName` to spare every downstream helper from `ManagedBranchName`-narrowing dance
    # when indexing via a parent/sibling-of-ancestor (which mypy tracks as the broader type).
    branches: Dict[LocalBranchShortName, StatusBranch]
    branches_in_display_order: List[ManagedBranchName]
    roots: List[ManagedBranchName]
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

        edge_color_tag: Dict[SyncToParentStatus, str] = {
            SyncToParentStatus.IN_SYNC: "green",
            SyncToParentStatus.IN_SYNC_BUT_FORK_POINT_OFF: "yellow",
            SyncToParentStatus.OUT_OF_SYNC: "red",
            SyncToParentStatus.MERGED_TO_PARENT: "dim"
        }
        edge_junction_char: Dict[SyncToParentStatus, str] = {
            SyncToParentStatus.IN_SYNC: "o",
            SyncToParentStatus.IN_SYNC_BUT_FORK_POINT_OFF: "?",
            SyncToParentStatus.OUT_OF_SYNC: "x",
            SyncToParentStatus.MERGED_TO_PARENT: "m"
        }
        out = io.StringIO()
        space = data.flags.maybe_space_before_branch_name
        line_for_branch: Dict[LocalBranchShortName, int] = {}
        line_index = 0

        next_sibling_of_ancestor_by_branch: Dict[LocalBranchShortName, List[Optional[LocalBranchShortName]]] = {}

        def prefix_dfs(parent: LocalBranchShortName, accumulated_path: List[Optional[LocalBranchShortName]]) -> None:
            next_sibling_of_ancestor_by_branch[parent] = accumulated_path
            children = data.branches[parent].children
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
                    tag = edge_color_tag[data.branches[sibling].sync_to_parent_status]
                    out.write(f"<{tag}><vbar/> {space}</{tag}>")
            tag = edge_color_tag[data.branches[for_branch].sync_to_parent_status]
            out.write(f"<{tag}>{suffix}</{tag}>")

        for branch in data.branches_in_display_order:
            b = data.branches[branch]
            next_sibling_of_ancestor = next_sibling_of_ancestor_by_branch[branch]
            if b.parent is not None:
                write_line_prefix(branch, next_sibling_of_ancestor, "<vbar/>")
                out.write("\n")
                line_index += 1
                for commit, fp_suffix in b.commits:
                    write_line_prefix(branch, next_sibling_of_ancestor, "<vbar/>")
                    subj = escape_markup(commit.subject)
                    out.write(
                        f' {f"<dim>{commit.short_hash}</dim>  " if data.flags.opt_list_commits_with_hashes else ""}'
                        f'<dim>{subj}</dim>{fp_suffix}\n'
                    )
                    line_index += 1
                junc_char = edge_junction_char[b.sync_to_parent_status]
                next_sibling_of_branch: Optional[LocalBranchShortName] = next_sibling_of_ancestor[-1]
                if next_sibling_of_branch and data.branches[next_sibling_of_branch].sync_to_parent_status == b.sync_to_parent_status:
                    unicode_junc = "├─"
                else:
                    unicode_junc = "└─"
                junction = f"<ifansi>{unicode_junc}<else>{junc_char}-</ifansi>"
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
                if prefix:
                    current = f"<b><red>{prefix}</red></b><b><u>{branch}</u><ifansi><else> *</ifansi></b>"
                else:
                    current = f"<b><u>{branch}</u><ifansi><else> *</ifansi></b>"
            else:
                current = f"<b>{branch}</b>"

            anno = ''
            if b.annotation is not None and b.annotation.formatted_full_text:
                anno = '  ' + b.annotation.formatted_full_text

            worktree_part = ''
            if b.worktree_label is not None:
                worktree_part = f" <green>[{escape_markup(b.worktree_label)}]</green>"

            if selected_branch is not None and branch == selected_branch:
                current_part = f"<reverse>{current}</reverse>"
            else:
                current_part = current
            out.write(f"{current_part}{anno}{worktree_part}{b.sync_status}{b.hook_output}\n")
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
                f"yellow edge indicates that fork point for <b>{yellow_edge_branch}</b> "
                f"is probably incorrectly inferred,\nor that some extra branch should be between "
                f"<b>{data.branches[yellow_edge_branch].parent}</b> and <b>{yellow_edge_branch}</b>"
            )
        else:
            affected_branches = ", ".join(f"<b>{b}</b>" for b in branches_in_sync_but_fork_point_off)
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
                f"rebasing <b>{yellow_edge_branch}</b> onto its parent with `git machete update`,\n"
                f"or reattaching <b>{yellow_edge_branch}</b> under a different parent branch"
            )
        else:
            second_part = (
                "Consider using `git machete fork-point <branch> --override-to-parent` for each affected branch,\n"
                "rebasing each branch onto its parent with `git machete update`,\n"
                "or reattaching the affected branches under different parent branches"
            )
        return f"{first_part}.\n\n{second_part}."

    def _is_fork_point_inferred_by_parent_remote_counterpart(
            self,
            *,
            parent_branch: LocalBranchShortName,
            inferring_branches: List[BranchPair]) -> bool:
        # Suppresses the spurious yellow edge that appears when the parent branch is merely behind its remote counterpart
        # and the child branch was forked from the remote tip.
        # We only fire here for parents that have a remote counterpart at all (otherwise the "behind remote" situation cannot arise),
        # and only if `parent_branch` appears among the inferring branches -
        # either directly as `parent_remote`, or as the `local_branch` side of a `BranchPair(parent_branch, parent_branch)` entry
        # produced when the inferred commit survives on `parent_branch`'s own filtered reflog after the push.
        parent_remote = self._git.get_combined_counterpart_for_fetching_of_branch(parent_branch)
        if parent_remote is None:
            return False
        return any(p.local_branch == parent_branch for p in inferring_branches)

    def compute_status_data(self, *, flags: StatusFlags) -> StatusData:
        managed_branches: List[ManagedBranchName] = self._state.managed_branches  # already returns a copy

        sync_to_parent_status: Dict[LocalBranchShortName, SyncToParentStatus] = {}
        fork_point_hash_cached: Dict[LocalBranchShortName, Optional[FullCommitHash]] = {}
        fork_point_branches_cached: Dict[LocalBranchShortName, List[BranchPair]] = {}

        def fork_point_hash(for_branch: LocalBranchShortName) -> Optional[FullCommitHash]:
            if for_branch not in fork_point_hash_cached:
                try:
                    fork_point_hash_cached[for_branch], fork_point_branches_cached[for_branch] = \
                        self.fork_point_and_inferring_branch_pairs(for_branch, use_overrides=True)
                except MacheteException:
                    fork_point_hash_cached[for_branch], fork_point_branches_cached[for_branch] = None, []
            return fork_point_hash_cached[for_branch]

        for branch in managed_branches:
            parent_branch = self._state.get_parent(branch)
            if parent_branch is None:
                continue
            if self.is_merged_to(
                    branch=branch,
                    parent=parent_branch,
                    opt_squash_merge_detection=flags.opt_squash_merge_detection):
                sync_to_parent_status[branch] = SyncToParentStatus.MERGED_TO_PARENT
            elif not self._git.is_ancestor_or_equal(parent_branch.full_name(), branch.full_name()):
                sync_to_parent_status[branch] = SyncToParentStatus.OUT_OF_SYNC
            elif self._get_overridden_fork_point(branch):
                sync_to_parent_status[branch] = SyncToParentStatus.IN_SYNC
            else:
                fp = fork_point_hash(branch)
                # `fork_point_hash` only returns None when `fork_point_and_inferring_branch_pairs` raises
                # `MacheteException`, which in turn requires reflog inference to fail AND one of:
                # parent is missing, parent commit is unresolvable, or parent is not an ancestor of branch
                # with no common merge-base (unrelated histories). All of these are ruled out by reaching
                # this branch: parent exists (the early `continue` above) and parent is an ancestor of branch
                # (the preceding `elif` would have classified it as OUT_OF_SYNC otherwise).
                assert fp is not None
                if self._git.get_commit_hash_by_revision(parent_branch) == fp:
                    sync_to_parent_status[branch] = SyncToParentStatus.IN_SYNC
                elif self._is_fork_point_inferred_by_parent_remote_counterpart(
                        parent_branch=parent_branch,
                        inferring_branches=fork_point_branches_cached[branch]):
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
            for branch in managed_branches:
                if not self._state.has_parent(branch):
                    continue
                fork_point = fork_point_hash(branch)
                if not fork_point:
                    commits: List[Tuple[GitLogEntry, str]] = []
                elif sync_to_parent_status[branch] == SyncToParentStatus.MERGED_TO_PARENT:
                    commits = []
                elif sync_to_parent_status[branch] == SyncToParentStatus.OUT_OF_SYNC:
                    # For red edges the branch has diverged from its parent: there is no clean linear
                    # `parent..branch` range. List only the commits unique to the branch
                    # (`fork_point..branch`, exclusive). The fork point itself is not shown, so no
                    # `-> fork point` marker is needed.
                    raw_commits = self._git.get_commits_between(fork_point, branch.full_name())
                    commits = [(commit, '') for commit in raw_commits]
                else:
                    parent = self._state.get_parent(branch)
                    assert parent is not None
                    raw_commits = self._git.get_commits_between(parent.full_name(), branch.full_name())
                    is_fork_point_off = \
                        sync_to_parent_status[branch] == SyncToParentStatus.IN_SYNC_BUT_FORK_POINT_OFF
                    commits = []
                    for commit in raw_commits:
                        if commit.hash != fork_point:
                            fp_suffix = ''
                        else:
                            marker = '<red><rarrow/> fork point ???</red>' if is_fork_point_off else '<red><rarrow/> fork point</red>'
                            fp_branches_formatted = " and ".join(
                                sorted(f"<u>{lb_or_rb}</u>" for lb, lb_or_rb in fork_point_branches_cached[branch]))
                            if fp_branches_formatted:
                                # `???` already separates the marker from the prose; a colon would be redundant.
                                separator = '' if is_fork_point_off else ':'
                                commit_label = (
                                    "this commit" if flags.opt_list_commits_with_hashes
                                    else f"commit {commit.short_hash}"
                                )
                                fp_suffix = (
                                    f' {marker}{separator} {commit_label}'
                                    f' seems to be a part of the unique history of {fp_branches_formatted}'
                                )
                            else:
                                # Reaching the green-edge marker with no inferring branches
                                # means the fork point comes from an active override
                                # (a fallback-to-parent fork point equals the parent hash, so it never appears in `parent..branch`).
                                fp_suffix = f' {marker}: overridden'
                        commits.append((commit, fp_suffix))
                commits_by_branch[branch] = commits

        sync_status_by_branch: Dict[LocalBranchShortName, str] = {}
        hook_output_by_branch: Dict[LocalBranchShortName, str] = {}
        for branch in managed_branches:
            s, remote = self._git.get_combined_remote_sync_status(branch)
            sync_status_by_branch[branch] = {
                SyncToRemoteStatus.NO_REMOTES: "",
                SyncToRemoteStatus.UNTRACKED: "<orange> (untracked)</orange>",
                SyncToRemoteStatus.IN_SYNC_WITH_REMOTE: "",
                SyncToRemoteStatus.BEHIND_REMOTE: f"<red> (behind <b>{remote}</b>)</red>",
                SyncToRemoteStatus.AHEAD_OF_REMOTE: f"<red> (ahead of <b>{remote}</b>)</red>",
                SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE: f"<red> (diverged from & older than <b>{remote}</b>)</red>",
                SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE: f"<red> (diverged from <b>{remote}</b>)</red>",
            }[SyncToRemoteStatus(s)]

            hook_output = ""
            if hook_executable:
                debug(f"running machete-status-branch hook ({hook_path}) for branch {branch}")
                hook_env = dict(os.environ, ASCII_ONLY=str(not markup.use_ansi_escapes_in_stdout).lower())
                status_code, stdout, stderr = self._popen_hook(
                    hook_path, branch, cwd=self._git.get_current_worktree_root_dir(), env=hook_env)
                if status_code == 0 and not stdout.isspace():
                    hook_output = "  " + escape_markup(stdout.replace('\n', ' ').rstrip())
                else:
                    debug(f"machete-status-branch hook ({hook_path}) for branch {branch} "
                          f"returned {status_code}; stdout: '{stdout}'; stderr: '{stderr}'")
            hook_output_by_branch[branch] = hook_output

        worktree_label_by_branch = self._compute_worktree_label_by_branch()

        branches: Dict[LocalBranchShortName, StatusBranch] = {}
        for branch in managed_branches:
            branches[branch] = StatusBranch(
                parent=self._state.get_parent(branch),
                children=self.children_of(branch) or [],
                sync_to_parent_status=sync_to_parent_status.get(branch, SyncToParentStatus.IN_SYNC),
                commits=commits_by_branch.get(branch, []),
                sync_status=sync_status_by_branch[branch],
                hook_output=hook_output_by_branch[branch],
                annotation=self._state.get_annotation(branch),
                worktree_label=worktree_label_by_branch.get(branch),
            )

        return StatusData(
            flags=flags,
            branches=branches,
            branches_in_display_order=managed_branches,
            roots=self._state.roots,  # property returns a copy
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
            opt_squash_merge_detection: Optional[SquashMergeDetection]
    ) -> None:
        # CLI flag > `machete.squashMergeDetection` config key > built-in `SIMPLE` default - see `CommandLineOptions`.
        if opt_squash_merge_detection is None:
            opt_squash_merge_detection = self._config.squash_merge_detection()
        maybe_space_before_branch_name = ' ' if self._config.status_extra_space_before_branch_name() else ''
        flags = StatusFlags(
            maybe_space_before_branch_name=maybe_space_before_branch_name,
            opt_list_commits=opt_list_commits,
            opt_list_commits_with_hashes=opt_list_commits_with_hashes,
            opt_squash_merge_detection=opt_squash_merge_detection,
        )
        data = self.compute_status_data(flags=flags)
        format_out = self.format_status_output(data)
        print_fmt(format_out.result, newline=False)
        if warn_when_branch_in_sync_but_fork_point_off:
            warning_msg = self._status_warning_message(data)
            if warning_msg is not None:
                print("", file=sys.stderr)
                warn(warning_msg)

    def _compute_worktree_label_by_branch(self) -> Dict[LocalBranchShortName, str]:
        """For each managed branch checked out in a worktree, derive a short label naming that worktree
        (rendered in `status` after the annotation).

        The labeling is uniform: *every* branch checked out in any worktree is labeled when the feature
        fires, so users see one consistent piece of info per branch rather than guessing why some
        branches carry a label and others don't. Concretely:

        * branch in the current worktree (whether main or linked) -> the literal `<this worktree>` -
          self-explanatory so users encountering the label for the first time can interpret it without
          having to read any PSA in the status output,
        * branch in the main worktree, but the user is standing in a linked worktree -> `<main worktree>`,
        * branch in any other linked worktree -> that worktree's stripped-prefix label
          (`strip_longest_common_path_prefix` collapses sibling linked worktrees to plain basenames,
          so typical layouts like `~/worktrees/wt1`, `~/worktrees/wt2`, ... render as `wt1`, `wt2`, ...).

        The main worktree gets a literal `<main worktree>` label rather than participating in the prefix
        computation, because mixing it in could artificially lengthen every linked-worktree label
        (e.g. when the main worktree lives in the user's home dir but linked worktrees sit under `/tmp` -
        the only shared component would be `/`, leaving every label as a full absolute path).

        The whole feature is gated on at least one linked worktree existing: in a plain single-worktree
        repo we don't want a `[<this worktree>]` tag stuck on the current branch of every status output,
        since the user hasn't opted into the multi-worktree workflow and there's nothing to disambiguate.
        """
        branch_by_worktree_path = self._git.load_branch_by_worktree_root_dir()
        if not branch_by_worktree_path:
            return {}

        main_path = self._git.get_main_worktree_root_dir()
        current_path = self._git.get_current_worktree_root_dir()

        # `.keys()` covers detached-HEAD linked worktrees too - this is what makes the gate fire
        # in repos whose only linked worktree happens to be detached.
        linked_paths = sorted({p for p in branch_by_worktree_path.keys() if p != main_path})
        if not linked_paths:
            return {}

        stripped = strip_longest_common_path_prefix([str(p) for p in linked_paths])
        label_by_linked_path = dict(zip(linked_paths, stripped))

        # For the same-branch-in-multiple-worktrees foot-gun, multiple iterations write to
        # `labels[branch]` - the last write wins. Since porcelain emits main first and linked
        # after (and `load_branch_by_worktree_root_dir` preserves insertion order), the linked
        # entry overwrites the main one - so the branch's label points at the linked worktree,
        # which is the surprising one of the two locations and the more useful one to surface.
        labels: Dict[LocalBranchShortName, str] = {}
        for path, branch in branch_by_worktree_path.items():
            if branch is None:
                continue
            if path == current_path:
                labels[branch] = "<this worktree>"
            elif path == main_path:
                labels[branch] = "<main worktree>"
            else:
                labels[branch] = label_by_linked_path[path]
        return labels

    @staticmethod
    def _popen_hook(*args: str, cwd: Path, env: Dict[str, str]) -> PopenResult:
        if sys.platform == "win32":
            return popen_cmd("sh", *args, cwd=cwd, env=env)
        else:
            return popen_cmd(*args, cwd=cwd, env=env)
