import io
import itertools
import os
import re
import shlex
import shutil
import sys
import textwrap
from collections import OrderedDict
from enum import Enum, auto
from typing import (Callable, Dict, Iterator, List, Optional, Tuple, Type,
                    TypeVar)

from git_machete import git_config_keys, utils
from git_machete.annotation import Annotation
from git_machete.constants import (INITIAL_COMMIT_COUNT_FOR_LOG,
                                   TOTAL_COMMIT_COUNT_FOR_LOG)
from git_machete.exceptions import (InteractionStopped, MacheteException,
                                    UnexpectedMacheteException)
from git_machete.git_operations import (HEAD, AnyBranchName, AnyRevision,
                                        BranchPair, ForkPointOverrideData,
                                        FullCommitHash, GitContext,
                                        GitLogEntry, LocalBranchShortName,
                                        RemoteBranchShortName,
                                        SyncToRemoteStatus)
from git_machete.utils import (AnsiEscapeCodes, PopenResult, bold, colored,
                               debug, dim, excluding, flat_map, fmt,
                               get_pretty_choices, get_second, tupled,
                               underline, warn)


class SyncToParentStatus(Enum):
    IN_SYNC = auto()
    IN_SYNC_BUT_FORK_POINT_OFF = auto()
    OUT_OF_SYNC = auto()
    MERGED_TO_PARENT = auto()


sync_to_parent_status_to_edge_color_map: Dict[SyncToParentStatus, str] = {
    SyncToParentStatus.IN_SYNC: AnsiEscapeCodes.GREEN,
    SyncToParentStatus.IN_SYNC_BUT_FORK_POINT_OFF: AnsiEscapeCodes.YELLOW,
    SyncToParentStatus.OUT_OF_SYNC: AnsiEscapeCodes.RED,
    SyncToParentStatus.MERGED_TO_PARENT: AnsiEscapeCodes.DIM
}

sync_to_parent_status_to_junction_ascii_only_map: Dict[SyncToParentStatus, str] = {
    SyncToParentStatus.IN_SYNC: "o-",
    SyncToParentStatus.IN_SYNC_BUT_FORK_POINT_OFF: "?-",
    SyncToParentStatus.OUT_OF_SYNC: "x-",
    SyncToParentStatus.MERGED_TO_PARENT: "m-"
}

E = TypeVar('E', bound='Enum')


class ParsableEnum(Enum):
    @classmethod
    def from_string(cls: Type[E], value: str, from_where: Optional[str]) -> E:
        try:
            return cls[value.upper().replace("-", "_")]
        except KeyError:
            valid_values = ', '.join('`' + e.name.lower().replace("_", "-") + '`' for e in cls)
            prefix = f"Invalid value for {from_where}" if from_where else "Invalid value"
            printed_value = value or '<empty>'
            raise MacheteException(f"{prefix}: `{printed_value}`. Valid values are {valid_values}")


class PickRoot(Enum):
    FIRST = auto()
    LAST = auto()


class SquashMergeDetection(ParsableEnum):
    NONE = auto()
    SIMPLE = auto()
    EXACT = auto()


class TraverseReturnTo(ParsableEnum):
    HERE = auto()
    NEAREST_REMAINING = auto()
    STAY = auto()  # noqa: F841


class TraverseStartFrom(ParsableEnum):
    HERE = auto()
    ROOT = auto()
    FIRST_ROOT = auto()


class MacheteState:
    def __init__(self) -> None:
        self.managed_branches: List[LocalBranchShortName] = []
        self.roots: List[LocalBranchShortName] = []
        self.up_branch_for: Dict[LocalBranchShortName, LocalBranchShortName] = {}
        self.down_branches_for: Dict[LocalBranchShortName, List[LocalBranchShortName]] = {}
        self.annotations: Dict[LocalBranchShortName, Annotation] = {}


class MacheteClient:

    def __init__(self, git: GitContext) -> None:
        self._git: GitContext = git
        git.owner = self

        self._branch_layout_file_path: str = self.__get_git_machete_branch_layout_file_path()
        if not os.path.exists(self._branch_layout_file_path):
            # We're opening in "append" and not "write" mode to avoid a race condition:
            # if other process writes to the file between we check the
            # result of `os.path.exists` and call `open`,
            # then open(..., "w") would result in us clearing up the file
            # contents, while open(..., "a") has no effect.
            with open(self._branch_layout_file_path, "a"):
                pass
        elif os.path.isdir(self._branch_layout_file_path):
            # Extremely unlikely case, basically checking if anybody
            # tampered with the repository.
            raise MacheteException(
                f"{self._branch_layout_file_path} is a directory "
                "rather than a regular file, aborting")

        self.__init_state()

    def __get_git_machete_branch_layout_file_path(self) -> str:
        use_top_level_machete_file = self._git.get_boolean_config_attr(key=git_config_keys.WORKTREE_USE_TOP_LEVEL_MACHETE_FILE,
                                                                       default_value=True)
        machete_file_directory = self._git.get_main_git_dir() if use_top_level_machete_file else self._git.get_worktree_git_dir()
        return os.path.join(machete_file_directory, 'machete')

    def __init_state(self) -> None:
        self._state = MacheteState()
        self.__indent: Optional[str] = None
        self.__empty_line_status: Optional[bool] = None
        self.__branch_pairs_by_hash_in_reflog: Optional[Dict[FullCommitHash, List[BranchPair]]] = None

    @property
    def branch_layout_file_path(self) -> str:
        return self._branch_layout_file_path

    @property
    def managed_branches(self) -> List[LocalBranchShortName]:
        return self._state.managed_branches

    @property
    def addable_branches(self) -> List[LocalBranchShortName]:
        def strip_remote_name(remote_branch: RemoteBranchShortName) -> LocalBranchShortName:
            return LocalBranchShortName.of(re.sub("^[^/]+/", "", remote_branch))

        remote_counterparts_of_local_branches = utils.map_truthy_only(
            self._git.get_combined_counterpart_for_fetching_of_branch,
            self._git.get_local_branches())
        qualifying_remote_branches: List[RemoteBranchShortName] = \
            excluding(self._git.get_remote_branches(), remote_counterparts_of_local_branches)
        return excluding(self._git.get_local_branches(), self.managed_branches) + [
            strip_remote_name(branch) for branch in qualifying_remote_branches]

    @property
    def unmanaged_branches(self) -> List[LocalBranchShortName]:
        return excluding(self._git.get_local_branches(), self.managed_branches)

    @property
    def childless_managed_branches(self) -> List[LocalBranchShortName]:
        parent_branches = [parent_branch for parent_branch, child_branches in self._state.down_branches_for.items() if child_branches]
        return excluding(self.managed_branches, parent_branches)

    @property
    def branches_with_overridden_fork_point(self) -> List[LocalBranchShortName]:
        return [branch for branch in self._git.get_local_branches() if self.has_any_fork_point_override_config(branch)]

    @property
    def annotations(self) -> Dict[LocalBranchShortName, Annotation]:
        return self._state.annotations

    def up_branch_for(self, branch: LocalBranchShortName) -> Optional[LocalBranchShortName]:
        return self._state.up_branch_for.get(branch)

    def down_branches_for(self, branch: LocalBranchShortName) -> Optional[List[LocalBranchShortName]]:
        return self._state.down_branches_for.get(branch)

    def expect_in_managed_branches(self, branch: LocalBranchShortName) -> None:
        if branch not in self.managed_branches:
            raise MacheteException(
                f"Branch {bold(branch)} not found in the tree of branch dependencies.\n"
                f"Use `git machete add {branch}` or `git machete edit`.")

    def expect_in_local_branches(self, branch: LocalBranchShortName) -> None:
        if branch not in self._git.get_local_branches():
            raise MacheteException(f"{bold(branch)} is not a local branch")

    def expect_at_least_one_managed_branch(self) -> None:
        if not self._state.roots:
            self.__raise_no_branches_error()

    def __raise_no_branches_error(self) -> None:
        raise MacheteException(
            textwrap.dedent(f"""
                No branches listed in {self._branch_layout_file_path}. Consider one of:
                * `git machete discover`
                * `git machete edit` or edit {self._branch_layout_file_path} manually
                * `git machete github checkout-prs --mine`
                * `git machete gitlab checkout-mrs --mine`"""[1:]))

    def read_branch_layout_file(self, *, interactively_slide_out_invalid_branches: bool = False, verify_branches: bool = True) -> None:
        with open(self._branch_layout_file_path) as file:
            lines: List[str] = [line.rstrip() for line in file.readlines()]

        at_depth = {}
        last_depth = -1
        hint = "Edit the branch layout file manually with `git machete edit`"

        invalid_branches: List[LocalBranchShortName] = []
        for index, line in enumerate(lines):
            if line == "":
                continue
            prefix = "".join(itertools.takewhile(str.isspace, line))
            if prefix and not self.__indent:
                self.__indent = prefix

            branch_and_maybe_annotation: List[LocalBranchShortName] = [LocalBranchShortName.of(entry) for entry in
                                                                       line.strip().split(" ", 1)]
            branch = branch_and_maybe_annotation[0]
            if len(branch_and_maybe_annotation) > 1:
                self._state.annotations[branch] = Annotation.parse(branch_and_maybe_annotation[1])
            if branch in self.managed_branches:
                raise MacheteException(
                    f"{self._branch_layout_file_path}, line {index + 1}: branch "
                    f"{bold(branch)} re-appears in the branch layout. {hint}")
            if verify_branches and branch not in self._git.get_local_branches():
                invalid_branches += [branch]
            self._state.managed_branches += [branch]

            if prefix:
                assert self.__indent is not None
                depth: int = len(prefix) // len(self.__indent)
                if prefix != self.__indent * depth:
                    mapping: Dict[str, str] = {" ": "<SPACE>", "\t": "<TAB>"}
                    prefix_expanded: str = "".join(mapping[c] for c in prefix)
                    indent_expanded: str = "".join(mapping[c] for c in self.__indent)
                    raise MacheteException(
                        f"{self._branch_layout_file_path}, line {index + 1}: "
                        f"invalid indent {bold(prefix_expanded)}, expected a multiply"
                        f" of {bold(indent_expanded)}. {hint}")
            else:
                depth = 0

            if depth > last_depth + 1:
                raise MacheteException(
                    f"{self._branch_layout_file_path}, line {index + 1}: too much "
                    f"indent (level {depth}, expected at most {last_depth + 1}) "
                    f"for the branch {bold(branch)}. {hint}")
            last_depth = depth

            at_depth[depth] = branch
            if depth:
                p = at_depth[depth - 1]
                self._state.up_branch_for[branch] = p
                if p in self._state.down_branches_for:
                    self._state.down_branches_for[p] += [branch]
                else:
                    self._state.down_branches_for[p] = [branch]
            else:
                self._state.roots += [branch]

        if not invalid_branches:
            return

        if interactively_slide_out_invalid_branches:
            if len(invalid_branches) == 1:
                ans: str = self.ask_if(
                    f"Skipping {bold(invalid_branches[0])} " +
                    "which is not a local branch (perhaps it has been deleted?).\n" +
                    "Slide it out from the branch layout file?" +
                    get_pretty_choices("y", "e[dit]", "N"), msg_if_opt_yes=None, opt_yes=False)
            else:
                ans = self.ask_if(
                    f"Skipping {', '.join(bold(branch) for branch in invalid_branches)}"
                    " which are not local branches (perhaps they have been deleted?).\n"
                    "Slide them out from the branch layout file?" + get_pretty_choices("y", "e[dit]", "N"),
                    msg_if_opt_yes=None, opt_yes=False)
        else:
            if len(invalid_branches) == 1:
                what = f"invalid branch {bold(invalid_branches[0])}"
            else:
                what = f"invalid branches {', '.join(bold(branch) for branch in invalid_branches)}"
            print(f"Warning: sliding {what} out of the branch layout file", file=sys.stderr)
            ans = 'y'

        def recursive_slide_out_invalid_branches(branch_: LocalBranchShortName) -> List[LocalBranchShortName]:
            new_down_branches = flat_map(
                recursive_slide_out_invalid_branches, self.down_branches_for(branch_) or [])
            if branch_ in invalid_branches:
                if branch_ in self._state.down_branches_for:
                    del self._state.down_branches_for[branch_]
                if branch_ in self._state.annotations:
                    del self._state.annotations[branch_]
                if branch_ in self._state.up_branch_for:
                    for down_branch in new_down_branches:
                        self._state.up_branch_for[down_branch] = self._state.up_branch_for[branch_]
                    del self._state.up_branch_for[branch_]
                else:
                    for down_branch in new_down_branches:
                        del self._state.up_branch_for[down_branch]
                return new_down_branches
            else:
                self._state.down_branches_for[branch_] = new_down_branches
                return [branch_]

        self._state.roots = flat_map(recursive_slide_out_invalid_branches, self._state.roots)
        self._state.managed_branches = excluding(self.managed_branches, invalid_branches)
        if ans in ('y', 'yes'):
            self.save_branch_layout_file()
        elif ans in ('e', 'edit'):
            self.edit()
            self.__init_state()
            self.read_branch_layout_file(verify_branches=verify_branches)

    def render_branch_layout_file(self, indent: str) -> List[str]:
        def render_dfs(branch: LocalBranchShortName, depth: int) -> List[str]:
            annotation = (" " + self.annotations[branch].unformatted_full_text) if branch in self.annotations else ""
            res: List[str] = [depth * indent + branch + annotation]
            for down_branch in self.down_branches_for(branch) or []:
                res += render_dfs(down_branch, depth + 1)
            return res

        result: List[str] = []
        for root in self._state.roots:
            result += render_dfs(root, depth=0)
        return result

    def back_up_branch_layout_file(self) -> None:
        shutil.copyfile(self._branch_layout_file_path, self._branch_layout_file_path + "~")

    def save_branch_layout_file(self) -> None:
        with open(self._branch_layout_file_path, "w") as file:
            file.write("\n".join(self.render_branch_layout_file(indent=self.__indent or "  ")) + "\n")

    def add(self,
            *,
            branch: LocalBranchShortName,
            opt_onto: Optional[LocalBranchShortName],
            opt_as_first_child: bool,
            opt_as_root: bool,
            opt_yes: bool,
            verbose: bool,
            switch_head_if_new_branch: bool
            ) -> None:
        if branch in self.managed_branches:
            raise MacheteException(f"Branch {bold(branch)} already exists in the tree of branch dependencies")

        if opt_onto:
            self.expect_in_managed_branches(opt_onto)

        if branch not in self._git.get_local_branches():
            remote_branch: Optional[RemoteBranchShortName] = self._git.get_sole_remote_branch(branch)
            if remote_branch:
                common_line = (
                    f"A local branch {bold(branch)} does not exist, but a remote "
                    f"branch {bold(remote_branch)} exists.\n")
                msg = common_line + f"Check out {bold(branch)} locally?" + get_pretty_choices('y', 'N')
                opt_yes_msg = common_line + f"Checking out {bold(branch)} locally..."
                if self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes, verbose=verbose) in ('y', 'yes'):
                    self._git.create_branch(branch, remote_branch.full_name(), switch_head=switch_head_if_new_branch)
                else:
                    return
                # Not dealing with `onto` here. If it hasn't been explicitly
                # specified via `--onto`, we'll try to infer it now.
            else:
                out_of = LocalBranchShortName.of(opt_onto).full_name() if opt_onto else HEAD
                out_of_str = bold(opt_onto) if opt_onto else "the current HEAD"
                msg = (f"A local branch {bold(branch)} does not exist. Create out "
                       f"of {out_of_str}?" + get_pretty_choices('y', 'N'))
                opt_yes_msg = (f"A local branch {bold(branch)} does not exist. "
                               f"Creating out of {out_of_str}")
                if self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes, verbose=verbose) in ('y', 'yes'):
                    # If `--onto` hasn't been explicitly specified, let's try to
                    # assess if the current branch would be a good `onto`.
                    if not opt_onto:
                        current_branch = self._git.get_current_branch_or_none()
                        if self._state.roots:
                            if current_branch and current_branch in self.managed_branches:
                                opt_onto = current_branch
                        else:
                            if current_branch:
                                # In this case (empty .git/machete, creating a new branch with `git machete add`)
                                # it's usually pretty obvious that the current branch needs to be added as root first.
                                # Let's skip interactive questions so as not to confuse new users.
                                self._state.roots = [current_branch]
                                self._state.managed_branches = [current_branch]
                                # This section of code is only ever executed in verbose mode, but let's leave the `if` for consistency
                                if verbose:  # pragma: no branch
                                    print(fmt(f"Added branch {bold(current_branch)} as a new root"))
                                opt_onto = current_branch
                    self._git.create_branch(branch, out_of, switch_head=switch_head_if_new_branch)
                else:
                    return

        if opt_as_root or not self._state.roots:
            self._state.roots += [branch]
            if verbose:
                print(fmt(f"Added branch {bold(branch)} as a new root"))
        else:
            if not opt_onto:
                upstream = self._infer_upstream(
                    branch,
                    condition=lambda x: x in self.managed_branches,
                    reject_reason_message="this candidate is not a managed branch")
                if not upstream:
                    raise MacheteException(
                        f"Could not automatically infer upstream (parent) branch for {bold(branch)}.\n"
                        "You can either:\n"
                        "1) specify the desired upstream branch with `--onto` or\n"
                        f"2) pass `--as-root` to attach {bold(branch)} as a new root or\n"
                        "3) edit the branch layout file manually with `git machete edit`")
                else:
                    msg = (f"Add {bold(branch)} onto the inferred upstream (parent) "
                           f"branch {bold(upstream)}?" + get_pretty_choices('y', 'N'))
                    opt_yes_msg = (f"Adding {bold(branch)} onto the inferred upstream"
                                   f" (parent) branch {bold(upstream)}")
                    if self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes, verbose=verbose) in ('y', 'yes'):
                        opt_onto = upstream
                    else:
                        return

            self._state.up_branch_for[branch] = opt_onto

            existing_down_branches = self._state.down_branches_for[opt_onto] if opt_onto in self._state.down_branches_for else []
            if opt_as_first_child:
                down_branches = [branch] + existing_down_branches
            else:
                down_branches = existing_down_branches + [branch]
            self._state.down_branches_for[opt_onto] = down_branches
            if verbose:
                print(fmt(f"Added branch {bold(branch)} onto {bold(opt_onto)}"))

        self._state.managed_branches += [branch]
        self.save_branch_layout_file()

    def _set_empty_line_status(self) -> None:
        self.__empty_line_status = True

    def _print_new_line(self, new_status: bool) -> None:  # noqa: KW
        if not self.__empty_line_status:
            print("")
        self.__empty_line_status = new_status

    def status(
            self,
            *,
            warn_when_branch_in_sync_but_fork_point_off: bool,
            opt_list_commits: bool,
            opt_list_commits_with_hashes: bool,
            opt_squash_merge_detection: SquashMergeDetection
    ) -> None:
        next_sibling_of_ancestor_by_branch: OrderedDict[LocalBranchShortName, List[Optional[LocalBranchShortName]]] = OrderedDict()

        def prefix_dfs(parent: LocalBranchShortName, accumulated_path_: List[Optional[LocalBranchShortName]]) -> None:
            next_sibling_of_ancestor_by_branch[parent] = accumulated_path_
            children = self.down_branches_for(parent)
            if children:
                shifted_children: List[Optional[LocalBranchShortName]] = children[1:]  # type: ignore[assignment]
                for (v, nv) in zip(children, shifted_children + [None]):
                    prefix_dfs(v, accumulated_path_ + [nv])

        for root in self._state.roots:
            prefix_dfs(root, accumulated_path_=[])

        out = io.StringIO()
        sync_to_parent_status: Dict[LocalBranchShortName, SyncToParentStatus] = {}
        fork_point_hash_cached: Dict[LocalBranchShortName, Optional[FullCommitHash]] = {}  # TODO (#110): default dict with None
        fork_point_branches_cached: Dict[LocalBranchShortName, List[BranchPair]] = {}

        def fork_point_hash(branch_: LocalBranchShortName) -> Optional[FullCommitHash]:
            if branch not in fork_point_hash_cached:
                try:
                    # We're always using fork point overrides, even when status
                    # is launched from discover().
                    fork_point_hash_cached[branch_], fork_point_branches_cached[branch_] = \
                        self.__fork_point_and_containing_branch_pairs(branch_, use_overrides=True)
                except MacheteException:
                    fork_point_hash_cached[branch_], fork_point_branches_cached[branch_] = None, []
            return fork_point_hash_cached[branch_]

        # Edge colors need to be precomputed
        # in order to render the leading parts of lines properly.
        branch: LocalBranchShortName
        for branch in self._state.up_branch_for:
            parent_branch = self._state.up_branch_for[branch]
            assert parent_branch is not None
            if self.is_merged_to(
                    branch=branch,
                    upstream=parent_branch,
                    opt_squash_merge_detection=opt_squash_merge_detection):
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

        maybe_space_before_branch_name = ' ' if self._git.get_boolean_config_attr(git_config_keys.STATUS_EXTRA_SPACE_BEFORE_BRANCH_NAME,
                                                                                  default_value=False) else ''

        def print_line_prefix(branch_: LocalBranchShortName, suffix: str) -> None:
            out.write("  " + maybe_space_before_branch_name)
            for sibling in next_sibling_of_ancestor[:-1]:
                if not sibling:
                    out.write("  " + maybe_space_before_branch_name)
                else:
                    out.write(colored(f"{utils.get_vertical_bar()} " + maybe_space_before_branch_name,
                                      sync_to_parent_status_to_edge_color_map[sync_to_parent_status[sibling]]))
            out.write(colored(suffix, sync_to_parent_status_to_edge_color_map[sync_to_parent_status[branch_]]))

        next_sibling_of_ancestor: List[Optional[LocalBranchShortName]]
        for branch, next_sibling_of_ancestor in next_sibling_of_ancestor_by_branch.items():
            if branch in self._state.up_branch_for:
                print_line_prefix(branch, f"{utils.get_vertical_bar()}\n")
                if opt_list_commits:
                    fork_point = fork_point_hash(branch)
                    if not fork_point:
                        # Rare case, but can happen e.g. due to reflog expiry.
                        commits: List[GitLogEntry] = []
                    elif sync_to_parent_status[branch] == SyncToParentStatus.MERGED_TO_PARENT:
                        commits = []
                    elif sync_to_parent_status[branch] == SyncToParentStatus.IN_SYNC_BUT_FORK_POINT_OFF:
                        upstream = self._state.up_branch_for[branch]
                        assert upstream is not None
                        commits = self._git.get_commits_between(upstream.full_name(), branch.full_name())
                    else:  # (SyncToParentStatus.OutOfSync, SyncToParentStatus.InSync):
                        commits = self._git.get_commits_between(fork_point, branch.full_name())

                    for commit in commits:
                        if commit.hash == fork_point:
                            # fork_point_branches_cached will already be there thanks to
                            # the above call to 'fork_point_hash'.
                            fp_branches_formatted: str = " and ".join(
                                sorted(underline(lb_or_rb) for lb, lb_or_rb in fork_point_branches_cached[branch]))
                            right_arrow = colored(utils.get_right_arrow(), AnsiEscapeCodes.RED)
                            fork_point_str = colored("fork point ???", AnsiEscapeCodes.RED)
                            fp_suffix: str = f' {right_arrow} {fork_point_str} ' + \
                                ("this commit" if opt_list_commits_with_hashes else f"commit {commit.short_hash}") + \
                                f' seems to be a part of the unique history of {fp_branches_formatted}'
                        else:
                            fp_suffix = ''
                        print_line_prefix(branch, utils.get_vertical_bar())
                        out.write(f' {f"{dim(commit.short_hash)}  " if opt_list_commits_with_hashes else ""}'
                                  f'{dim(commit.subject)}{fp_suffix}\n')

                junction: str
                if utils.ascii_only:
                    junction = sync_to_parent_status_to_junction_ascii_only_map[sync_to_parent_status[branch]]
                else:
                    next_sibling_of_branch: Optional[LocalBranchShortName] = next_sibling_of_ancestor[-1]
                    if next_sibling_of_branch and sync_to_parent_status[next_sibling_of_branch] == sync_to_parent_status[branch]:
                        junction = "├─"
                    else:
                        # The three-legged turnstile looks pretty bad when the upward and rightward leg
                        # have a different color than the downward leg.
                        # It's better to use a two-legged elbow
                        # in case `sync_to_parent_status[next_sibling_of_branch] != sync_to_parent_status[branch]`,
                        # at the expense of a little gap to the elbow/turnstile below.
                        junction = "└─"
                print_line_prefix(branch, junction + maybe_space_before_branch_name)
            else:
                if branch != self._state.roots[0]:
                    out.write("\n")
                out.write("  " + maybe_space_before_branch_name)

            if branch in (currently_checked_out_branch, currently_rebased_branch, currently_bisected_branch):
                # i.e. if branch is the current branch (checked out or being rebased or being bisected)
                if branch == currently_rebased_branch:
                    prefix = "REBASING "
                elif branch == currently_bisected_branch:
                    prefix = "BISECTING "
                elif self._git.is_am_in_progress():
                    prefix = "GIT AM IN PROGRESS "
                elif self._git.is_cherry_pick_in_progress():
                    prefix = "CHERRY-PICKING "
                elif self._git.is_merge_in_progress():
                    prefix = "MERGING "
                elif self._git.is_revert_in_progress():
                    prefix = "REVERTING "
                else:
                    prefix = ""
                current = f"{bold(colored(prefix, AnsiEscapeCodes.RED))}{bold(underline(branch, star_if_ascii_only=True))}"
            else:
                current = bold(branch)

            anno: str = ''
            if branch in self._state.annotations and self._state.annotations[branch].formatted_full_text:
                anno = '  ' + self._state.annotations[branch].formatted_full_text

            s, remote = self._git.get_combined_remote_sync_status(branch)
            sync_status = {
                SyncToRemoteStatus.NO_REMOTES: "",
                SyncToRemoteStatus.UNTRACKED:
                    colored(" (untracked)", AnsiEscapeCodes.ORANGE),
                SyncToRemoteStatus.IN_SYNC_WITH_REMOTE: "",
                SyncToRemoteStatus.BEHIND_REMOTE:
                    colored(f" (behind {bold(remote)})", AnsiEscapeCodes.RED),  # type: ignore [arg-type]
                SyncToRemoteStatus.AHEAD_OF_REMOTE:
                    colored(f" (ahead of {bold(remote)})", AnsiEscapeCodes.RED),  # type: ignore [arg-type]
                SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                    colored(f" (diverged from & older than {bold(remote)})", AnsiEscapeCodes.RED),  # type: ignore [arg-type]
                SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                    colored(f" (diverged from {bold(remote)})", AnsiEscapeCodes.RED)  # type: ignore [arg-type]
            }[SyncToRemoteStatus(s)]

            hook_output = ""
            if hook_executable:
                debug(f"running machete-status-branch hook ({hook_path}) for branch {branch}")
                hook_env = dict(os.environ, ASCII_ONLY=str(utils.ascii_only).lower())
                status_code, stdout, stderr = self.__popen_hook(hook_path, branch, cwd=self._git.get_root_dir(), env=hook_env)

                if status_code == 0:
                    if not stdout.isspace():
                        # Replace all newlines with spaces, in case the hook prints out more than one line
                        hook_output = "  " + stdout.replace('\n', ' ').rstrip()
                else:
                    debug(f"machete-status-branch hook ({hook_path}) for branch {branch} "
                          f"returned {status_code}; stdout: '{stdout}'; stderr: '{stderr}'")

            out.write(current + anno + sync_status + hook_output + "\n")

        sys.stdout.write(out.getvalue())
        out.close()

        branches_in_sync_but_fork_point_off = [k for k, v in sync_to_parent_status.items() if v ==
                                               SyncToParentStatus.IN_SYNC_BUT_FORK_POINT_OFF]
        if branches_in_sync_but_fork_point_off and warn_when_branch_in_sync_but_fork_point_off:
            yellow_edge_branch: LocalBranchShortName = branches_in_sync_but_fork_point_off[0]
            if len(branches_in_sync_but_fork_point_off) == 1:
                first_part = (f"yellow edge indicates that fork point for {bold(str(yellow_edge_branch))} "
                              f"is probably incorrectly inferred,\nor that some extra branch should be between "
                              f"{bold(str(self._state.up_branch_for[yellow_edge_branch]))} and {bold(str(yellow_edge_branch))}")
            else:
                affected_branches = ", ".join(map(bold, branches_in_sync_but_fork_point_off))
                first_part = f"yellow edges indicate that fork points for {affected_branches} are probably incorrectly inferred,\n" \
                    "or that some extra branch should be added between each of these branches and its parent"

            if not opt_list_commits:
                second_part = "Run `git machete status --list-commits` or " \
                              "`git machete status --list-commits-with-hashes` to see more details"
            elif len(branches_in_sync_but_fork_point_off) == 1:
                second_part = "Consider using `git machete fork-point " \
                              f"--override-to=<revision>|--override-to-inferred|--override-to-parent {bold(yellow_edge_branch)}`,\n" \
                              f"or reattaching {bold(yellow_edge_branch)} under a different parent branch"
            else:
                second_part = "Consider using `git machete fork-point " \
                              "--override-to=<revision>|--override-to-inferred|--override-to-parent <branch>` for each affected branch,\n" \
                              "or reattaching the affected branches under different parent branches"

            print("", file=sys.stderr)
            warn(f"{first_part}.\n\n{second_part}.")

    @staticmethod
    def __popen_hook(*args: str, cwd: str, env: Dict[str, str]) -> PopenResult:
        if sys.platform == "win32":
            # This is a poor-man's solution to the problem of Windows **not** recognizing Unix-style shebangs :/
            return utils.popen_cmd("sh", *args, cwd=cwd, env=env)
        else:
            return utils.popen_cmd(*args, cwd=cwd, env=env)

    def __run_hook(self, *args: str, cwd: str) -> int:
        self._git.flush_caches()
        if sys.platform == "win32":
            return utils.run_cmd("sh", *args, cwd=cwd)
        else:
            return utils.run_cmd(*args, cwd=cwd)

    def rebase(
            self, *,
            onto: AnyRevision,
            from_exclusive: AnyRevision,
            branch: LocalBranchShortName,
            opt_no_interactive_rebase: bool
    ) -> None:
        self._git.expect_no_operation_in_progress()

        anno = self.annotations.get(branch)
        if anno and not anno.qualifiers.rebase:
            raise MacheteException(f"Branch {bold(branch)} is annotated with `rebase=no` qualifier, aborting.\n"
                                   f"Remove the qualifier using `git machete anno` or edit branch layout file directly.")
        # Let's use `OPTS` suffix for consistency with git's built-in env var `GIT_DIFF_OPTS`
        extra_rebase_opts = os.environ.get('GIT_MACHETE_REBASE_OPTS', '').split()

        hook_path = self._git.get_hook_path("machete-pre-rebase")
        if self._git.check_hook_executable(hook_path):
            debug(f"running machete-pre-rebase hook ({hook_path})")
            exit_code = self.__run_hook(hook_path, onto, from_exclusive, branch, cwd=self._git.get_root_dir())
            if exit_code == 0:
                self._git.rebase(
                    onto, from_exclusive, branch,
                    opt_no_interactive_rebase=opt_no_interactive_rebase,
                    extra_rebase_opts=extra_rebase_opts)
            else:
                raise MacheteException(
                    f"The machete-pre-rebase hook refused to rebase. Error code: {exit_code}")
        else:
            self._git.rebase(
                onto, from_exclusive, branch,
                opt_no_interactive_rebase=opt_no_interactive_rebase,
                extra_rebase_opts=extra_rebase_opts)

    def delete_unmanaged(self, *, opt_squash_merge_detection: SquashMergeDetection, opt_yes: bool) -> None:
        print('Checking for unmanaged branches...')
        branches_to_delete = sorted(excluding(self._git.get_local_branches(), self.managed_branches))
        self._delete_branches(branches_to_delete=branches_to_delete,
                              opt_squash_merge_detection=opt_squash_merge_detection, opt_yes=opt_yes)

    def _delete_branches(
        self,
        branches_to_delete: List[LocalBranchShortName],
        *,
        opt_squash_merge_detection: SquashMergeDetection,
        opt_yes: bool
    ) -> None:
        current_branch = self._git.get_current_branch_or_none()
        if current_branch and current_branch in branches_to_delete:
            branches_to_delete = excluding(branches_to_delete, [current_branch])
            print(f"Skipping current branch {bold(current_branch)}")
        if not branches_to_delete:
            print("No branches to delete")
            return

        if opt_yes:
            for branch in branches_to_delete:
                print(f"Deleting branch {bold(branch)}...")
                self._git.delete_branch(branch, force=True)
        else:
            for branch in branches_to_delete:
                if self.is_merged_to(branch=branch, upstream=AnyBranchName('HEAD'), opt_squash_merge_detection=opt_squash_merge_detection):
                    remote_branch = self._git.get_strict_counterpart_for_fetching_of_branch(branch)
                    if remote_branch:
                        is_merged_to_remote = self.is_merged_to(
                            branch=branch,
                            upstream=remote_branch,
                            opt_squash_merge_detection=opt_squash_merge_detection)
                    else:
                        is_merged_to_remote = True
                    if is_merged_to_remote:
                        msg_core_suffix = ''
                    else:
                        msg_core_suffix = f', but not merged to {bold(str(remote_branch))}'
                    msg_core = f"{bold(branch)} (merged to HEAD{msg_core_suffix})"
                else:
                    msg_core = f"{bold(branch)} (unmerged to HEAD)"
                msg = f"Delete branch {msg_core}?" + get_pretty_choices('y', 'N', 'q')
                ans = self.ask_if(msg, msg_if_opt_yes=None, opt_yes=False)
                if ans in ('y', 'yes'):
                    self._git.delete_branch(branch, force=True)
                elif ans in ('q', 'quit'):
                    return

    def edit(self) -> int:
        default_editor_with_args: List[str] = self.__get_editor_with_args()
        if not default_editor_with_args:
            raise MacheteException(
                f"Cannot determine editor. Set `GIT_MACHETE_EDITOR` environment "
                f"variable or edit {self._branch_layout_file_path} directly.")

        command = default_editor_with_args[0]
        args = default_editor_with_args[1:] + [self._branch_layout_file_path]
        return utils.run_cmd(command, *args)

    def __get_editor_with_args(self) -> List[str]:
        # Based on the git's own algorithm for identifying the editor.
        # '$GIT_MACHETE_EDITOR', 'editor' (to please Debian-based systems) and 'nano' have been added.
        git_machete_editor_var = "GIT_MACHETE_EDITOR"
        proposed_editor_funs: List[Tuple[str, Callable[[], Optional[str]]]] = [
            ("$" + git_machete_editor_var, lambda: os.environ.get(git_machete_editor_var)),
            ("$GIT_EDITOR", lambda: os.environ.get("GIT_EDITOR")),
            ("git config core.editor", lambda: self._git.get_config_attr_or_none("core.editor")),
            ("$VISUAL", lambda: os.environ.get("VISUAL")),
            ("$EDITOR", lambda: os.environ.get("EDITOR")),
            ("editor", lambda: "editor"),
            ("nano", lambda: "nano"),
            ("vi", lambda: "vi"),
        ]

        for name, fun in proposed_editor_funs:
            editor = fun()
            if not editor:
                debug(f"'{name}' is undefined")
            else:
                editor_parsed = shlex.split(editor)
                if not editor_parsed:
                    debug(f"'{name}' shlexes into an empty list")
                    continue
                editor_command = editor_parsed[0]
                editor_repr = "'" + name + "'" + ((' (' + editor + ')') if editor_command != name else '')

                if not utils.find_executable(editor_command):
                    debug(f"'{editor_command}' executable ('{name}') not found")
                    if name == "$" + git_machete_editor_var:
                        # In this specific case, when GIT_MACHETE_EDITOR is defined but doesn't point to a valid executable,
                        # it's more reasonable/less confusing to raise an error and exit without opening anything.
                        raise MacheteException(f"<b>{editor_repr}</b> is not available")
                else:
                    debug(f"'{editor_command}' executable ('{name}') found")
                    if name != "$" + git_machete_editor_var and \
                            self._git.get_config_attr_or_none('advice.macheteEditorSelection') != 'false':
                        sample_alternative = 'nano' if editor_command.startswith('vi') else 'vi'
                        print(fmt(f"Opening <b>{editor_repr}</b>.\n",
                                  f"To override this choice, use <b>{git_machete_editor_var}</b> env var, e.g. `export "
                                  f"{git_machete_editor_var}={sample_alternative}`.\n\n",
                                  "See `git machete help edit` and `git machete edit --debug` for more details.\n\n"
                                  "Use `git config --global advice.macheteEditorSelection false` to suppress this message."),
                              file=sys.stderr)
                    return editor_parsed

        # This case is extremely unlikely on a modern Unix-like system.
        return []

    def __fork_point_and_containing_branch_pairs(
        self,
        branch: LocalBranchShortName,
        *,
        use_overrides: bool
    ) -> Tuple[FullCommitHash, List[BranchPair]]:
        upstream = self.up_branch_for(branch)
        upstream_hash = self._git.get_commit_hash_by_revision(upstream) if upstream else None

        if use_overrides:
            overridden_fork_point = self._get_overridden_fork_point(branch)
            if overridden_fork_point:
                if upstream and upstream_hash and \
                        self._git.is_ancestor_or_equal(upstream.full_name(), branch.full_name()) and \
                        not self._git.is_ancestor_or_equal(upstream.full_name(), overridden_fork_point):
                    # We need to handle the case when branch is a descendant of upstream,
                    # but the fork point of branch is overridden to a commit that is NOT a descendant of upstream.
                    # In this case it's more reasonable to assume that upstream (and not overridden_fork_point) is the fork point.
                    debug(
                        f"{branch} is descendant of its upstream {upstream}, but overridden fork point commit {overridden_fork_point} "
                        f"is NOT a descendant of {upstream}; falling back to {upstream} as fork point")
                    return upstream_hash, []
                elif upstream and \
                        self._git.is_ancestor_or_equal(overridden_fork_point, upstream.full_name()):
                    common_ancestor = self._git.get_merge_base(upstream.full_name(), branch.full_name())
                    # We are sure that a common ancestor exists - `overridden_fork_point` is an ancestor of both `branch` and `upstream`.
                    assert common_ancestor is not None
                    return common_ancestor, []
                else:
                    debug(f"fork point of {branch} is overridden to {overridden_fork_point}; skipping inference")
                    return overridden_fork_point, []

        try:
            computed_fork_point, containing_branch_pairs = next(self.__match_log_to_filtered_reflogs(branch))
        except StopIteration:
            if upstream and upstream_hash:
                if self._git.is_ancestor_or_equal(upstream.full_name(), branch.full_name()):
                    debug(
                        f"cannot find fork point, but {branch} is a descendant of its upstream {upstream}; "
                        f"falling back to {upstream} as fork point")
                    return upstream_hash, []
                else:
                    common_ancestor_hash = self._git.get_merge_base(upstream.full_name(), branch.full_name())
                    if common_ancestor_hash:
                        debug(
                            f"cannot find fork point, and {branch} is NOT a descendant of its upstream {upstream}; "
                            f"falling back to common ancestor of {branch} and {upstream} (commit {common_ancestor_hash}) as fork point")
                        return common_ancestor_hash, []
            raise MacheteException(f"Fork point not found for branch <b>{branch}</b>; "
                                   f"use `git machete fork-point {branch} --override-to...`")
        else:
            debug(f"commit {computed_fork_point} is the most recent point in history of {branch} to occur on "
                  "filtered reflog of any other branch or its remote counterpart "
                  f"(specifically: {' and '.join(map(utils.get_second, containing_branch_pairs))})")

            if upstream and upstream_hash and \
                    self._git.is_ancestor_or_equal(upstream.full_name(), branch.full_name()) and \
                    not self._git.is_ancestor_or_equal(upstream.full_name(), computed_fork_point):
                # That happens very rarely in practice (typically current head
                # of any branch, including upstream, should occur on the reflog
                # of this branch, thus is_ancestor(upstream, branch) should imply
                # is_ancestor(upstream, FP(branch)), but it's still possible in
                # case reflog of upstream is incomplete for whatever reason.
                debug(
                    f"{upstream} is an ancestor of {branch}, "
                    f"but the inferred fork point commit {computed_fork_point} is NOT a descendant of {upstream}; "
                    f"falling back to {upstream} as fork point")
                return upstream_hash, []
            elif upstream and \
                    not self._git.is_ancestor_or_equal(upstream.full_name(), branch.full_name()) and \
                    self._git.is_ancestor_or_equal(computed_fork_point, upstream.full_name()):

                # We are sure that a common ancestor exists - `computed_fork_point` is an ancestor of both `branch` and `upstream`.
                common_ancestor_hash = self._git.get_merge_base(upstream.full_name(), branch.full_name())
                assert common_ancestor_hash is not None
                debug(
                    f"{upstream} is NOT an ancestor of {branch}, "
                    f"but the inferred fork point commit {computed_fork_point} is an ancestor of {upstream}; "
                    f"falling back to the common ancestor of {branch} and {upstream} (commit {common_ancestor_hash}) as fork point")
                return common_ancestor_hash, []
            else:
                improved_fork_point = computed_fork_point
                improved_containing_branch_pairs = containing_branch_pairs
                for candidate_branch, original_matched_branch in containing_branch_pairs:
                    merge_base = self._git.get_merge_base(original_matched_branch, branch)
                    debug(f"improving fork point {improved_fork_point} "
                          f"by checking for merge_base({original_matched_branch}, {branch}) = {merge_base}")
                    if merge_base:
                        if self._git.is_ancestor(improved_fork_point, merge_base):
                            debug(f"improving fork point {improved_fork_point} to {merge_base}")
                            improved_fork_point = merge_base
                            improved_containing_branch_pairs = [BranchPair(candidate_branch, original_matched_branch)]
                debug(f"effective fork point of {branch} is {improved_fork_point}")
                return improved_fork_point, improved_containing_branch_pairs

    def fork_point(self, branch: LocalBranchShortName, *, use_overrides: bool) -> FullCommitHash:
        hash, containing_branch_pairs = self.__fork_point_and_containing_branch_pairs(branch, use_overrides=use_overrides)
        return FullCommitHash.of(hash)

    def fork_point_or_none(self, branch: LocalBranchShortName, *, use_overrides: bool) -> Optional[FullCommitHash]:
        try:
            return self.fork_point(branch, use_overrides=use_overrides)
        except MacheteException:
            return None

    def get_or_pick_down_branch_for(self, branch: LocalBranchShortName, *, pick_if_multiple: bool) -> List[LocalBranchShortName]:
        self.expect_in_managed_branches(branch)
        dbs = self.down_branches_for(branch)
        if not dbs:
            raise MacheteException(f"Branch {bold(branch)} has no downstream branch")
        elif len(dbs) == 1:
            return [dbs[0]]
        elif pick_if_multiple:
            return [self.pick(dbs, "downstream branch")]
        else:
            return dbs

    def first_branch_for(self, branch: LocalBranchShortName) -> LocalBranchShortName:
        root = self.root_branch_for(branch, if_unmanaged=PickRoot.FIRST)
        root_dbs = self.down_branches_for(root)
        return root_dbs[0] if root_dbs else root

    def last_branch_for(self, branch: LocalBranchShortName) -> LocalBranchShortName:
        destination = self.root_branch_for(branch, if_unmanaged=PickRoot.LAST)
        while self.down_branches_for(destination):
            destination = self._state.down_branches_for[destination][-1]
        return destination

    def next_branch_for(self, branch: LocalBranchShortName) -> LocalBranchShortName:
        self.expect_in_managed_branches(branch)
        index: int = self.managed_branches.index(branch) + 1
        if index == len(self.managed_branches):
            raise MacheteException(f"Branch {bold(branch)} has no successor")
        return self.managed_branches[index]

    def prev_branch_for(self, branch: LocalBranchShortName) -> LocalBranchShortName:
        self.expect_in_managed_branches(branch)
        index: int = self.managed_branches.index(branch) - 1
        if index == -1:
            raise MacheteException(f"Branch {bold(branch)} has no predecessor")
        return self.managed_branches[index]

    def root_branch_for(self, branch: LocalBranchShortName, if_unmanaged: PickRoot) -> LocalBranchShortName:
        if branch not in self.managed_branches:
            if self._state.roots:
                if if_unmanaged == PickRoot.FIRST:
                    warn(
                        f"{bold(branch)} is not a managed branch, assuming "
                        f"{self._state.roots[0]} (the first root) instead as root")
                    return self._state.roots[0]
                else:  # if_unmanaged == PickRoot.LAST
                    warn(
                        f"{bold(branch)} is not a managed branch, assuming "
                        f"{self._state.roots[-1]} (the last root) instead as root")
                    return self._state.roots[-1]
            else:
                self.__raise_no_branches_error()
        upstream = self.up_branch_for(branch)
        while upstream:
            branch = upstream
            upstream = self.up_branch_for(branch)
        return branch

    def get_or_infer_up_branch_for(self,
                                   branch: LocalBranchShortName,
                                   prompt_if_inferred_msg: Optional[str],
                                   prompt_if_inferred_yes_opt_msg: Optional[str]) -> LocalBranchShortName:
        if branch in self.managed_branches:
            upstream = self.up_branch_for(branch)
            if upstream:
                return upstream
            else:
                raise MacheteException(f"Branch {bold(branch)} has no upstream branch")
        else:
            upstream = self._infer_upstream(branch)
            if upstream:
                if prompt_if_inferred_msg and prompt_if_inferred_yes_opt_msg:
                    if self.ask_if(
                            prompt_if_inferred_msg % (branch, upstream),
                            prompt_if_inferred_yes_opt_msg % (branch, upstream),
                            opt_yes=False
                    ) in ('y', 'yes'):
                        return upstream
                    raise MacheteException("Aborting.")
                else:
                    warn(
                        f"branch {bold(branch)} not found in the tree of branch "
                        f"dependencies; the upstream has been inferred to {bold(upstream)}")
                    return upstream
            else:
                raise MacheteException(
                    f"Branch {bold(branch)} not found in the tree of branch "
                    f"dependencies and its upstream could not be inferred")

    @property
    def slidable_branches(self) -> List[LocalBranchShortName]:
        return [branch for branch in self.managed_branches if branch in self._state.up_branch_for]

    def get_slidable_after(self, branch: LocalBranchShortName) -> List[LocalBranchShortName]:
        if branch in self._state.up_branch_for:
            dbs = self.down_branches_for(branch)
            if dbs and len(dbs) == 1:
                return dbs
        return []

    def _is_merged_to_upstream(
            self, branch: LocalBranchShortName, *, opt_squash_merge_detection: SquashMergeDetection) -> bool:
        upstream = self.up_branch_for(branch)
        if not upstream:
            return False
        return self.is_merged_to(branch=branch, upstream=upstream, opt_squash_merge_detection=opt_squash_merge_detection)

    def _run_post_slide_out_hook(
        self,
        *,
        new_upstream: LocalBranchShortName,
        slid_out_branch: LocalBranchShortName,
        new_downstreams: List[LocalBranchShortName]
    ) -> None:
        hook_path = self._git.get_hook_path("machete-post-slide-out")
        if self._git.check_hook_executable(hook_path):
            debug(f"running machete-post-slide-out hook ({hook_path})")
            new_downstreams_strings: List[str] = [str(db) for db in new_downstreams]
            exit_code = self.__run_hook(hook_path, new_upstream, slid_out_branch, *new_downstreams_strings,
                                        cwd=self._git.get_root_dir())
            if exit_code != 0:
                raise MacheteException(f"The machete-post-slide-out hook exited with {exit_code}, aborting.")

    def filtered_reflog(self, branch: AnyBranchName) -> List[FullCommitHash]:
        def is_excluded_reflog_subject(hash_: str, gs_: str) -> bool:
            is_excluded = (gs_.startswith("branch: Created from") or
                           gs_ == f"branch: Reset to {branch}" or
                           gs_ == "branch: Reset to HEAD" or
                           gs_.startswith("reset: moving to ") or
                           gs_.startswith("fetch . ") or
                           # The rare case of a no-op rebase, the exact wording
                           # likely depends on git version
                           gs_ == f"rebase finished: {branch.full_name()} onto {hash_}" or
                           gs_ == f"rebase -i (finish): {branch.full_name()} onto {hash_}" or
                           # For remote branches, let's NOT include the pushes,
                           # as a branch can be pushed directly after being created,
                           # which might lead to fork point being inferred too *late* in the history
                           gs_ == "update by push")
            if is_excluded:
                debug("skipping reflog entry")
            return is_excluded

        branch_reflog = self._git.get_reflog(branch.full_name())
        if not branch_reflog:
            return []

        earliest_hash, earliest_gs = branch_reflog[-1]  # Note that the reflog is returned from latest to earliest entries.
        hashes_to_exclude = set()
        if earliest_gs.startswith("branch: Created from"):
            debug(f"skipping any reflog entry with the hash equal to the hash of the earliest (branch creation) entry: {earliest_hash}")
            hashes_to_exclude.add(earliest_hash)

        result = [hash for (hash, gs) in branch_reflog if
                  hash not in hashes_to_exclude and not is_excluded_reflog_subject(hash, gs)]
        reflog = (", ".join(result) or "<empty>")
        debug("computed filtered reflog (= reflog without branch creation "
              f"and branch reset events irrelevant for fork point/upstream inference): {reflog}")
        return result

    def __match_log_to_filtered_reflogs(self, branch: LocalBranchShortName) -> Iterator[Tuple[FullCommitHash, List[BranchPair]]]:

        if self.__branch_pairs_by_hash_in_reflog is None:
            def generate_entries() -> Iterator[Tuple[FullCommitHash, BranchPair]]:
                for lb in self._git.get_local_branches():
                    lb_hashes = set()
                    for hash_ in self.filtered_reflog(lb):
                        lb_hashes.add(hash_)
                        yield FullCommitHash.of(hash_), BranchPair(lb, lb)
                    remote_branch = self._git.get_combined_counterpart_for_fetching_of_branch(lb)
                    if remote_branch:
                        for hash_ in self.filtered_reflog(remote_branch):
                            if hash_ not in lb_hashes:
                                yield FullCommitHash.of(hash_), BranchPair(lb, remote_branch)

            self.__branch_pairs_by_hash_in_reflog = {}
            for hash, branch_pair in generate_entries():
                if hash in self.__branch_pairs_by_hash_in_reflog:
                    # The practice shows that it's rather unlikely for a given
                    # commit to appear on filtered reflogs of two unrelated branches
                    # ("unrelated" as in, not a local branch and its remote counterpart)
                    # but we need to handle this case anyway.
                    self.__branch_pairs_by_hash_in_reflog[hash] += [branch_pair]
                else:
                    self.__branch_pairs_by_hash_in_reflog[hash] = [branch_pair]

            def log_result() -> Iterator[str]:
                branch_pairs_: List[BranchPair]
                hash_: FullCommitHash
                assert self.__branch_pairs_by_hash_in_reflog is not None
                for hash_, branch_pairs_ in self.__branch_pairs_by_hash_in_reflog.items():
                    def branch_pair_to_str(lb: str, lb_or_rb: str) -> str:
                        return lb if lb == lb_or_rb else f"{lb_or_rb} (remote counterpart of {lb})"

                    joined_branch_pairs = ", ".join(map(tupled(branch_pair_to_str), branch_pairs_))
                    yield dim(f"{hash_} => {joined_branch_pairs}")

            branches = "\n".join(log_result())
            debug(f"branches containing the given hash in their filtered reflog: \n{branches}\n")

        branch_full_hash = self._git.get_commit_hash_by_revision(branch)
        if not branch_full_hash:
            return

        for hash in self._git.spoonfeed_log_hashes(branch_full_hash,
                                                   initial_count=INITIAL_COMMIT_COUNT_FOR_LOG,
                                                   total_count=TOTAL_COMMIT_COUNT_FOR_LOG):
            if hash in self.__branch_pairs_by_hash_in_reflog:
                # The entries must be sorted by lb_or_rb to make sure the
                # upstream inference is deterministic (and does not depend on the
                # order in which `generate_entries` iterated through the local branches).
                branch_pairs: List[BranchPair] = self.__branch_pairs_by_hash_in_reflog[hash]

                def lb_is_not_b(lb: str, _lb_or_rb: str) -> bool:
                    return lb != branch

                containing_branch_pairs = sorted(filter(tupled(lb_is_not_b), branch_pairs), key=get_second)
                if containing_branch_pairs:
                    debug(f"commit {hash} found in filtered reflog of {' and '.join(map(get_second, branch_pairs))}")
                    yield hash, containing_branch_pairs
                else:
                    debug(f"commit {hash} found only in filtered reflog of {' and '.join(map(get_second, branch_pairs))}; ignoring")
            else:
                debug(f"commit {hash} not found in any filtered reflog")

    def _infer_upstream(self,
                        branch: LocalBranchShortName,
                        condition: Callable[[LocalBranchShortName], bool] = lambda upstream: True,
                        *,
                        reject_reason_message: str = ""
                        ) -> Optional[LocalBranchShortName]:
        for hash, containing_branch_pairs in self.__match_log_to_filtered_reflogs(branch):
            debug(f"commit {hash} found in filtered reflog of {' and '.join(map(get_second, containing_branch_pairs))}")

            for candidate, original_matched_branch in containing_branch_pairs:
                if candidate != original_matched_branch:
                    debug(f"upstream candidate is {candidate}, which is the local counterpart of {original_matched_branch}")

                if condition(candidate):
                    debug(f"upstream candidate {candidate} accepted")
                    return candidate
                else:
                    debug(f"upstream candidate {candidate} rejected ({reject_reason_message})")
        return None

    def remote_enabled_for_traverse_fetch(self, remote: str) -> bool:
        return self._git.get_boolean_config_attr(git_config_keys.traverse_remote_fetch(remote), default_value=True)

    # Also includes config that is invalid (corresponding to a non-existent/GCed commit etc.).
    def has_any_fork_point_override_config(self, branch: LocalBranchShortName) -> bool:
        return (self._git.get_config_attr_or_none(git_config_keys.override_fork_point_to(branch)) or
                # Note that we still include the now-deprecated `whileDescendantOf` key for this purpose.
                self._git.get_config_attr_or_none(git_config_keys.override_fork_point_while_descendant_of(branch))) is not None

    def __get_fork_point_override_data(self, branch: LocalBranchShortName) -> Optional[ForkPointOverrideData]:
        # Note that here we ignore the now-deprecated `whileDescendantOf`.
        to_key = git_config_keys.override_fork_point_to(branch)
        to_value = self._git.get_config_attr_or_none(to_key)
        if to_value and FullCommitHash.is_valid(value=to_value):
            return ForkPointOverrideData(FullCommitHash.of(to_value))
        else:
            return None

    def _get_overridden_fork_point(self, branch: LocalBranchShortName) -> Optional[FullCommitHash]:
        override_data = self.__get_fork_point_override_data(branch)
        if not override_data:
            return None

        to = override_data.to_hash
        # Checks if the override still applies to wherever the given branch currently points.
        if not self._git.is_ancestor_or_equal(to.full_name(), branch.full_name()):
            warn(fmt(
                f"since branch {bold(branch)} is no longer a descendant of commit {bold(to)}, ",
                "the fork point override to this commit no longer applies.\n",
                f"Consider running:\n  `git machete fork-point --unset-override {branch}`\n"))
            return None
        debug(f"since branch {branch} is descendant of {to}, fork point of {branch} is overridden to {to}")
        return to

    def __pick_remote(
            self,
            *,
            branch: LocalBranchShortName,
            is_called_from_traverse: bool,
            is_called_from_code_hosting: bool,
            opt_push_untracked: bool,
            opt_push_tracked: bool,
            opt_yes: bool
    ) -> None:
        rems = self._git.get_remotes()
        print("\n".join(f"[{index + 1}] {rem}" for index, rem in enumerate(rems)))
        if is_called_from_traverse:
            msg = f"Select number 1..{len(rems)} to specify the destination remote " \
                "repository, or 'n' to skip this branch, or " \
                "'q' to quit the traverse: "
        else:
            msg = f"Select number 1..{len(rems)} to specify the destination remote " \
                "repository, or 'q' to quit the operation: "

        ans = input(msg).lower()
        if ans in ('q', 'quit'):
            raise InteractionStopped
        try:
            index = int(ans) - 1
            if index not in range(len(rems)):
                raise MacheteException(f"Invalid index: {index + 1}")
            self._handle_untracked_branch(
                new_remote=rems[index],
                branch=branch,
                is_called_from_traverse=is_called_from_traverse,
                is_called_from_code_hosting=is_called_from_code_hosting,
                opt_push_untracked=opt_push_untracked,
                opt_push_tracked=opt_push_tracked,
                opt_yes=opt_yes)
        except ValueError:
            if is_called_from_code_hosting:
                raise MacheteException('Could not establish remote repository, operation interrupted.')

    def _handle_untracked_branch(
            self,
            *,
            new_remote: str,
            branch: LocalBranchShortName,
            is_called_from_traverse: bool,
            is_called_from_code_hosting: bool,
            opt_push_untracked: bool,
            opt_push_tracked: bool,
            opt_yes: bool
    ) -> None:
        remotes: List[str] = self._git.get_remotes()
        can_pick_other_remote = len(remotes) > 1 and is_called_from_traverse
        other_remote_choice = "o[ther-remote]" if can_pick_other_remote else ""
        remote_branch = RemoteBranchShortName.of(f"{new_remote}/{branch}")
        if not self._git.get_commit_hash_by_revision(remote_branch):
            choices = get_pretty_choices(
                *('y', 'N', 'q', 'yq', other_remote_choice) if is_called_from_traverse else ('y', 'Q'))
            ask_message = f"Push untracked branch {bold(branch)} to {bold(new_remote)}?" + choices
            ask_opt_yes_message = f"Pushing untracked branch {bold(branch)} to {bold(new_remote)}..."
            ans = self.ask_if(
                ask_message,
                ask_opt_yes_message,
                opt_yes=opt_yes,
                override_answer=None if opt_push_untracked else "N")
            if is_called_from_traverse:
                if ans in ('y', 'yes', 'yq'):
                    self._git.push(new_remote, branch)
                    if ans == 'yq':
                        raise InteractionStopped
                elif can_pick_other_remote and ans in ('o', 'other'):
                    self.__pick_remote(
                        branch=branch,
                        is_called_from_traverse=is_called_from_traverse,
                        is_called_from_code_hosting=is_called_from_code_hosting,
                        opt_push_untracked=opt_push_untracked,
                        opt_push_tracked=opt_push_tracked,
                        opt_yes=opt_yes)
                elif ans in ('q', 'quit'):
                    raise InteractionStopped
                return
            else:
                if ans in ('y', 'yes'):
                    self._git.push(new_remote, branch)
                else:
                    raise InteractionStopped
                return

        relation = self._git.get_relation_to_remote_counterpart(branch, remote_branch)

        message: str = {
            SyncToRemoteStatus.IN_SYNC_WITH_REMOTE:
                f"Branch {bold(branch)} is untracked, but its remote counterpart candidate {bold(remote_branch)} "
                f"already exists and both branches point to the same commit.",
            SyncToRemoteStatus.BEHIND_REMOTE:
                f"Branch {bold(branch)} is untracked, but its remote counterpart candidate {bold(remote_branch)} "
                f"already exists and is ahead of {bold(branch)}.",
            SyncToRemoteStatus.AHEAD_OF_REMOTE:
                f"Branch {bold(branch)} is untracked, but its remote counterpart candidate {bold(remote_branch)} "
                f"already exists and is behind {bold(branch)}.",
            SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                f"Branch {bold(branch)} is untracked, it diverged from its remote counterpart candidate {bold(remote_branch)}, "
                f"and has {bold('older')} commits than {bold(remote_branch)}.",
            SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                f"Branch {bold(branch)} is untracked, it diverged from its remote counterpart candidate {bold(remote_branch)}, "
                f"and has {bold('newer')} commits than {bold(remote_branch)}."
        }[SyncToRemoteStatus(relation)]

        ask_message, ask_opt_yes_message = {
            SyncToRemoteStatus.IN_SYNC_WITH_REMOTE: (
                f"Set the remote of {bold(branch)} to {bold(new_remote)} without pushing or pulling?" +
                get_pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Setting the remote of {bold(branch)} to {bold(new_remote)}..."
            ),
            SyncToRemoteStatus.BEHIND_REMOTE: (
                f"Pull {bold(branch)} (fast-forward only) from {bold(new_remote)}?" + get_pretty_choices('y', 'N', 'q', 'yq',
                                                                                                         other_remote_choice),
                f"Pulling {bold(branch)} (fast-forward only) from {bold(new_remote)}..."
            ),
            SyncToRemoteStatus.AHEAD_OF_REMOTE: (
                f"Push branch {bold(branch)} to {bold(new_remote)}?" + get_pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Pushing branch {bold(branch)} to {bold(new_remote)}..."
            ),
            SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE: (
                f"Reset branch {bold(branch)} to the commit pointed by {bold(remote_branch)}?" + get_pretty_choices('y', 'N', 'q', 'yq',
                                                                                                                    other_remote_choice),
                f"Resetting branch {bold(branch)} to the commit pointed by {bold(remote_branch)}..."
            ),
            SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE: (
                f"Push branch {bold(branch)} with force-with-lease to {bold(new_remote)}?" + get_pretty_choices('y', 'N', 'q', 'yq',
                                                                                                                other_remote_choice),
                f"Pushing branch {bold(branch)} with force-with-lease to {bold(new_remote)}..."
            )
        }[SyncToRemoteStatus(relation)]

        override_answer: Optional[str] = {
            SyncToRemoteStatus.IN_SYNC_WITH_REMOTE: None,
            SyncToRemoteStatus.BEHIND_REMOTE: None,
            SyncToRemoteStatus.AHEAD_OF_REMOTE: None if opt_push_tracked else "N",
            SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE: None,
            SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE: None if opt_push_tracked else "N",
        }[SyncToRemoteStatus(relation)]

        yes_action: Callable[[], None] = {
            SyncToRemoteStatus.IN_SYNC_WITH_REMOTE: lambda: self._git.set_upstream_to(remote_branch),
            SyncToRemoteStatus.BEHIND_REMOTE: lambda: self._git.pull_ff_only(new_remote, remote_branch),
            SyncToRemoteStatus.AHEAD_OF_REMOTE: lambda: self._git.push(new_remote, branch),
            SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE: lambda: self._git.reset_keep(remote_branch),
            SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE: lambda: self._git.push(
                new_remote, branch, force_with_lease=True)
        }[SyncToRemoteStatus(relation)]

        print(message)
        ans = self.ask_if(ask_message, ask_opt_yes_message, override_answer=override_answer, opt_yes=opt_yes)
        if ans in ('y', 'yes', 'yq'):
            yes_action()
            if ans == 'yq':
                raise InteractionStopped
        elif ans in ('q', 'quit'):
            raise InteractionStopped

    def is_merged_to(
            self,
            *,
            branch: AnyBranchName,
            upstream: AnyBranchName,
            opt_squash_merge_detection: SquashMergeDetection
    ) -> bool:
        if self._git.is_ancestor_or_equal(branch.full_name(), upstream.full_name()):
            # If branch is ancestor of or equal to the upstream, we need to distinguish between the
            # case of branch being "recently" created from the upstream and the case of
            # branch being fast-forward-merged to the upstream.
            # The applied heuristics is to check if the filtered reflog of the branch
            # (reflog stripped of trivial events like branch creation, reset etc.)
            # is non-empty.
            return bool(self.filtered_reflog(branch))
        elif opt_squash_merge_detection == SquashMergeDetection.NONE:
            return False
        elif opt_squash_merge_detection == SquashMergeDetection.SIMPLE:
            # In the default mode.
            # If a commit with an identical tree state to branch is reachable from upstream,
            # then branch may have been squashed or rebase-merged into upstream.
            return self._git.is_equivalent_tree_reachable(equivalent_to=branch, reachable_from=upstream)
        elif opt_squash_merge_detection == SquashMergeDetection.EXACT:
            # Let's try another way, a little more complex but takes into account the possibility
            # that there were other commits between the common ancestor of the two branches and the squashed merge.
            return self._git.is_equivalent_tree_reachable(equivalent_to=branch, reachable_from=upstream) or \
                self._git.is_equivalent_patch_reachable(equivalent_to=branch, reachable_from=upstream)
        else:  # pragma: no cover
            raise UnexpectedMacheteException(f"Invalid squash merged detection mode: {opt_squash_merge_detection}.")

    @staticmethod
    def ask_if(
            msg: str,
            msg_if_opt_yes: Optional[str],
            *,
            opt_yes: bool,
            override_answer: Optional[str] = None,
            apply_fmt: bool = True,
            verbose: bool = True
    ) -> str:
        if override_answer:
            return override_answer
        if opt_yes and msg_if_opt_yes:
            if verbose:
                print(fmt(msg_if_opt_yes) if apply_fmt else msg_if_opt_yes)
            return 'y'
        try:
            ans: str = input(fmt(msg) if apply_fmt else msg).lower().strip()
        except InterruptedError:
            sys.exit(1)
        return ans

    @staticmethod
    def pick(choices: List[LocalBranchShortName], name: str, *, apply_fmt: bool = True) -> LocalBranchShortName:
        xs: str = "".join(f"[{index + 1}] {x}\n" for index, x in enumerate(choices))
        msg: str = xs + f"Specify {name} or hit <return> to skip: "
        try:
            ans: str = input(fmt(msg) if apply_fmt else msg)
            if not ans:
                sys.exit(0)
            index: int = int(ans) - 1
        except ValueError:
            sys.exit(1)
        if index not in range(len(choices)):
            raise MacheteException(f"Invalid index: {index + 1}")
        return choices[index]

    def flush_caches(self) -> None:
        self.__branch_pairs_by_hash_in_reflog = None

    def check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
            self, *, fork_point: AnyRevision, branch: AnyBranchName) -> None:
        if not self._git.is_ancestor_or_equal(
                earlier_revision=fork_point.full_name(),
                later_revision=branch.full_name()):
            raise MacheteException(
                f"Fork point {bold(fork_point)} is not ancestor of or the tip "
                f"of the {bold(branch)} branch.")

    def _handle_diverged_and_newer_state(
            self,
            *,
            current_branch: LocalBranchShortName,
            remote: str,
            is_called_from_traverse: bool = True,
            opt_push_tracked: bool,
            opt_yes: bool
    ) -> None:
        self._print_new_line(False)
        remote_branch = self._git.get_combined_counterpart_for_fetching_of_branch(current_branch)
        assert remote_branch is not None
        choices = get_pretty_choices(*('y', 'N', 'q', 'yq') if is_called_from_traverse else ('y', 'N', 'q'))
        ans = self.ask_if(
            f"Branch {bold(current_branch)} diverged from (and has newer commits than) its remote counterpart {bold(remote_branch)}.\n"
            f"Push {bold(current_branch)} with force-with-lease to {bold(remote)}?" + choices,
            f"Branch {bold(current_branch)} diverged from (and has newer commits than) its remote counterpart {bold(remote_branch)}.\n"
            f"Pushing {bold(current_branch)} with force-with-lease to {bold(remote)}...",
            override_answer=None if opt_push_tracked else "N", opt_yes=opt_yes)
        if ans in ('y', 'yes', 'yq'):
            self._git.push(remote, current_branch, force_with_lease=True)
            if ans == 'yq':
                raise InteractionStopped
        elif ans in ('q', 'quit'):
            raise InteractionStopped

    def _handle_untracked_state(
            self,
            *,
            branch: LocalBranchShortName,
            is_called_from_traverse: bool,
            is_called_from_code_hosting: bool,
            opt_push_tracked: bool,
            opt_push_untracked: bool,
            opt_yes: bool
    ) -> None:
        remotes: List[str] = self._git.get_remotes()
        self._print_new_line(False)
        if len(remotes) == 1:
            self._handle_untracked_branch(
                new_remote=remotes[0],
                branch=branch,
                is_called_from_traverse=is_called_from_traverse,
                is_called_from_code_hosting=is_called_from_code_hosting,
                opt_push_untracked=opt_push_untracked,
                opt_push_tracked=opt_push_tracked,
                opt_yes=opt_yes)
        elif "origin" in remotes:
            self._handle_untracked_branch(
                new_remote="origin",
                branch=branch,
                is_called_from_traverse=is_called_from_traverse,
                is_called_from_code_hosting=is_called_from_code_hosting,
                opt_push_untracked=opt_push_untracked,
                opt_push_tracked=opt_push_tracked,
                opt_yes=opt_yes)
        else:
            # We know that there is at least 1 remote, otherwise sync-to-remote state would be NO_REMOTES and not UNTRACKED
            print(f"Branch {bold(branch)} is untracked and there's no {bold('origin')} remote.")
            self.__pick_remote(
                branch=branch,
                is_called_from_traverse=is_called_from_traverse,
                is_called_from_code_hosting=is_called_from_code_hosting,
                opt_push_untracked=opt_push_untracked,
                opt_push_tracked=opt_push_tracked,
                opt_yes=opt_yes)

    def _handle_ahead_state(
            self,
            *,
            current_branch: LocalBranchShortName,
            remote: str,
            is_called_from_traverse: bool,
            opt_push_tracked: bool,
            opt_yes: bool
    ) -> None:
        self._print_new_line(False)
        choices = get_pretty_choices(*('y', 'N', 'q', 'yq') if is_called_from_traverse else ('y', 'N', 'q'))
        ans = self.ask_if(
            f"Push {bold(current_branch)} to {bold(remote)}?" + choices,
            f"Pushing {bold(current_branch)} to {bold(remote)}...",
            override_answer=None if opt_push_tracked else "N",
            opt_yes=opt_yes
        )
        if ans in ('y', 'yes', 'yq'):
            self._git.push(remote, current_branch)
            if ans == 'yq' and is_called_from_traverse:
                raise InteractionStopped
        elif ans in ('q', 'quit'):
            raise InteractionStopped

    def _handle_diverged_and_older_state(self, branch: LocalBranchShortName, *, opt_yes: bool) -> None:
        self._print_new_line(False)
        remote_branch = self._git.get_combined_counterpart_for_fetching_of_branch(branch)
        assert remote_branch is not None
        ans = self.ask_if(
            f"Branch {bold(branch)} diverged from (and has older commits than) its remote counterpart {bold(remote_branch)}.\n"
            f"Reset branch {bold(branch)} to the commit pointed by {bold(remote_branch)}?" + get_pretty_choices('y', 'N', 'q', 'yq'),
            f"Branch {bold(branch)} diverged from (and has older commits than) its remote counterpart {bold(remote_branch)}.\n"
            f"Resetting branch {bold(branch)} to the commit pointed by {bold(remote_branch)}...",
            opt_yes=opt_yes)
        if ans in ('y', 'yes', 'yq'):
            self._git.reset_keep(remote_branch)
            if ans == 'yq':
                raise InteractionStopped
        elif ans in ('q', 'quit'):
            raise InteractionStopped

    def _handle_behind_state(self, *, branch: LocalBranchShortName, remote: str, opt_yes: bool) -> None:
        self._print_new_line(False)
        remote_branch = self._git.get_combined_counterpart_for_fetching_of_branch(branch)
        assert remote_branch is not None
        ans = self.ask_if(
            f"Branch {bold(branch)} is behind its remote counterpart {bold(remote_branch)}.\n"
            f"Pull {bold(branch)} (fast-forward only) from {bold(remote)}?" + get_pretty_choices('y', 'N', 'q', 'yq'),
            f"Branch {bold(branch)} is behind its remote counterpart {bold(remote_branch)}.\n"
            f"Pulling {bold(branch)} (fast-forward only) from {bold(remote)}...",
            opt_yes=opt_yes)
        if ans in ('y', 'yes', 'yq'):
            self._git.pull_ff_only(remote, remote_branch)
            if ans == 'yq':
                raise InteractionStopped
        elif ans in ('q', 'quit'):
            raise InteractionStopped

    def delete_untracked(self, *, opt_yes: bool) -> None:
        print(bold('Checking for untracked managed branches with no downstream...'))
        branches_to_delete: List[LocalBranchShortName] = []
        for branch in self.managed_branches.copy():
            status, _ = self._git.get_combined_remote_sync_status(branch)
            if status == SyncToRemoteStatus.UNTRACKED and not self.down_branches_for(branch):
                branches_to_delete.append(branch)

        self._remove_branches_from_layout(branches_to_delete)
        self._delete_branches(branches_to_delete, opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=opt_yes)

    def _remove_branches_from_layout(self, branches_to_delete: List[LocalBranchShortName]) -> None:
        for branch in branches_to_delete:
            self.managed_branches.remove(branch)
            if branch in self._state.annotations:
                del self._state.annotations[branch]
            if branch in self._state.up_branch_for:
                upstream = self._state.up_branch_for[branch]
                del self._state.up_branch_for[branch]
                self._state.down_branches_for[upstream] = [
                    b for b in (self.down_branches_for(upstream) or []) if b != branch
                ]
            else:
                self._state.roots.remove(branch)

        self.save_branch_layout_file()
