import os
import shlex
import sys
import textwrap
from enum import Enum, auto
from typing import Callable, Dict, Iterator, List, NoReturn, Optional, Sequence, Tuple, TypeVar

from git_machete.client import branch_layout
from git_machete.client.state import MacheteState, ManagedBranchName
from git_machete.config import MacheteConfig, SquashMergeDetection
from git_machete.constants import INITIAL_COMMIT_COUNT_FOR_LOG, TOTAL_COMMIT_COUNT_FOR_LOG
from git_machete.git import (HEAD, AnyBranchName, AnyRevision, BranchPair, ForkPointOverrideData, FullCommitHash, Git, LocalBranchShortName,
                             RemoteBranchShortName, SyncToRemoteStatus)
from git_machete.utils import fs
from git_machete.utils.cmd import run_cmd
from git_machete.utils.collections import excluding, get_second, tupled
from git_machete.utils.debug_log import debug
from git_machete.utils.exceptions import InteractionStopped, MacheteException, UnexpectedMacheteException
from git_machete.utils.markup import input_fmt, pretty_choices, print_fmt, warn
from git_machete.utils.paths import AbsPath, Path

_BranchT = TypeVar("_BranchT", bound=LocalBranchShortName)


class PickRoot(Enum):
    FIRST = auto()
    LAST = auto()


class MacheteClient:

    # === Initialization ===

    def __init__(self, *, read_layout_file: bool = True, verify_branches: bool = True,
                 interactively_slide_out_invalid_branches: bool = False) -> None:
        # Clients own their `Git` plumbing instance - command-dispatch code (`cli.py`) and tests never touch it directly.
        # Pass-throughs are avoided in favor of domain-specific methods on the client itself.
        self._git: Git = Git()
        self._config: MacheteConfig = MacheteConfig(self._git)
        self._git.owner = self

        self._branch_layout_file_path: AbsPath = self.__get_git_machete_branch_layout_file_path()
        # Cwd-relative rendition of the layout path, captured at init time for use in user-facing messages
        # (compact, points at the file as the user invoked us from).
        # I/O always uses the absolute path so it survives any mid-run `chdir` (e.g. into a linked worktree).
        try:
            self._branch_layout_file_path_for_display: Path = Path.relative(self._branch_layout_file_path)
        except Exception:  # pragma: no cover
            self._branch_layout_file_path_for_display = self._branch_layout_file_path
        if not os.path.exists(self._branch_layout_file_path):
            # We're opening in "append" and not "write" mode to avoid a race condition:
            # if other process writes to the file between we check the result of `os.path.exists` and call `open`,
            # then open(..., "w") would result in us clearing up the file contents, while open(..., "a") has no effect.
            with open(self._branch_layout_file_path, "a"):
                pass
        elif os.path.isdir(self._branch_layout_file_path):
            # Extremely unlikely case, basically checking if anybody tampered with the repository.
            raise MacheteException(
                f"{self._branch_layout_file_path_for_display} is a directory "
                "rather than a regular file, aborting")

        self.__init_state()

        # Load the layout file as part of construction so that callers consistently get a ready-to-use client;
        # subclasses don't need to remember a separate `client.read_branch_layout_file(...)` step
        # (and easily get its flags wrong for the command at hand).
        # `read_layout_file=False` is for the few commands (`edit`, `file`) that must work even when the layout file is malformed -
        # their whole point is to let the user inspect or fix it.
        if read_layout_file:
            self.read_branch_layout_file(
                verify_branches=verify_branches,
                interactively_slide_out_invalid_branches=interactively_slide_out_invalid_branches)

    def __get_git_machete_branch_layout_file_path(self) -> AbsPath:
        if self._config.worktree_use_top_level_machete_file():
            machete_file_directory = self._git.get_main_worktree_git_dir()
        else:
            machete_file_directory = self._git.get_current_worktree_git_dir()
        # Keep the path absolute: `traverse` and other commands may `chdir` into linked worktrees mid-run,
        # and a stored cwd-relative path would then resolve against the wrong directory -
        # inside a linked worktree `.git` is a gitdir-pointer file, so `.git/machete` no longer points at the layout file.
        # The underlying `get_SOMETHING_worktree_git_dir()` helpers already return absolute paths (via `git rev-parse` + `abs_path`).
        return machete_file_directory.join_fragments('machete')

    def __init_state(self) -> None:
        self._state = MacheteState()
        self.__indent: Optional[str] = None
        self.__has_trailing_blank_line: Optional[bool] = None
        self.__branch_pairs_by_hash_in_reflog: Optional[Dict[FullCommitHash, List[BranchPair]]] = None

    # === Branch listing ===

    @property
    def managed_branches(self) -> List[ManagedBranchName]:
        return self._state.managed_branches  # returns a copy

    def parent_of(self, branch: LocalBranchShortName) -> Optional[ManagedBranchName]:
        return self._state.get_parent(branch)

    def children_of(self, branch: LocalBranchShortName) -> Optional[List[ManagedBranchName]]:
        return self._state.get_children(branch)

    def is_managed(self, *, opt_branch: Optional[LocalBranchShortName]) -> bool:
        branch = opt_branch or self._git.get_current_branch_or_none()
        return branch is not None and branch in self.managed_branches

    # === Branch existence assertions ===

    def expect_in_managed_branches(self, branch: LocalBranchShortName) -> ManagedBranchName:
        """Verify `branch` lives in the layout file;
        on success, narrow its type to `ManagedBranchName` so the caller can pass it to layout-mutating APIs without a re-check."""
        managed = self._state.as_managed(branch)
        if managed is None:
            raise MacheteException(
                f"Branch <b>{branch}</b> not found in the tree of branch dependencies.\n"
                f"Use `git machete add {branch}` or `git machete edit`.")
        return managed

    def expect_in_local_branches(self, branch: LocalBranchShortName) -> None:
        if branch not in self._git.get_local_branches():
            raise MacheteException(f"<b>{branch}</b> is not a local branch")

    def expect_at_least_one_managed_branch(self) -> None:
        if not self._state.roots:  # property returns a copy; falsy check works fine
            self._raise_no_branches_error()

    def _raise_no_branches_error(self) -> NoReturn:
        raise MacheteException(
            textwrap.dedent(f"""
                No branches listed in {self._branch_layout_file_path_for_display}. Consider one of:
                * `git machete discover`
                * `git machete edit` or edit {self._branch_layout_file_path_for_display} manually
                * `git machete github checkout-prs --mine`
                * `git machete gitlab checkout-mrs --mine`"""[1:]))

    # === Branch layout file I/O ===

    @property
    def branch_layout_file_path(self) -> AbsPath:
        return self._branch_layout_file_path

    def read_branch_layout_file(self, *, interactively_slide_out_invalid_branches: bool = False, verify_branches: bool = True) -> None:
        self._state, self.__indent = branch_layout.parse(
            self._branch_layout_file_path,
            display_path=self._branch_layout_file_path_for_display)

        if not verify_branches:
            return
        local_branches = self._git.get_local_branches()
        invalid_branches = [b for b in self._state.managed_branches if b not in local_branches]

        if not invalid_branches:
            return

        if interactively_slide_out_invalid_branches:
            if len(invalid_branches) == 1:
                ans: str = self.ask_if(
                    f"Skipping <b>{invalid_branches[0]}</b> " +
                    "which is not a local branch (perhaps it has been deleted?).\n" +
                    "Slide it out from the branch layout file?" +
                    pretty_choices("y", "e[dit]", "N"), msg_if_opt_yes=None, opt_yes=False)
            else:
                ans = self.ask_if(
                    f"Skipping {', '.join(f'<b>{branch}</b>' for branch in invalid_branches)}"
                    " which are not local branches (perhaps they have been deleted?).\n"
                    "Slide them out from the branch layout file?" + pretty_choices("y", "e[dit]", "N"),
                    msg_if_opt_yes=None, opt_yes=False)
        else:
            if len(invalid_branches) == 1:
                what = f"invalid branch <b>{invalid_branches[0]}</b>"
            else:
                what = f"invalid branches {', '.join(f'<b>{branch}</b>' for branch in invalid_branches)}"
            print_fmt(f"Warning: sliding {what} out of the branch layout file", file=sys.stderr)
            ans = 'y'

        for branch in invalid_branches:
            self._state.splice_out(branch)
        if ans in ('y', 'yes'):
            self.save_branch_layout_file()
        elif ans in ('e', 'edit'):
            self.edit()
            self.__init_state()
            self.read_branch_layout_file(verify_branches=verify_branches)

    def save_branch_layout_file(self) -> None:
        branch_layout.save(self._branch_layout_file_path, self._state, indent=self.__indent or "  ")

    def _remove_branches_from_layout(self, branches_to_delete: List[ManagedBranchName]) -> None:
        for branch in branches_to_delete:
            self._state.remove_leaf(branch)
        self.save_branch_layout_file()

    # === Branch navigation ===

    def root_branch_for(self, branch: LocalBranchShortName, if_unmanaged: PickRoot) -> LocalBranchShortName:
        if branch not in self.managed_branches:
            roots = self._state.roots
            if roots:
                if if_unmanaged == PickRoot.FIRST:
                    warn(
                        f"<b>{branch}</b> is not a managed branch, assuming "
                        f"{roots[0]}{' (the first root)' if len(roots) > 1 else ''} instead as root")
                    return roots[0]
                else:  # if_unmanaged == PickRoot.LAST
                    warn(
                        f"<b>{branch}</b> is not a managed branch, assuming "
                        f"{roots[-1]}{' (the last root)' if len(roots) > 1 else ''} instead as root")
                    return roots[-1]
            else:
                self._raise_no_branches_error()
        parent = self.parent_of(branch)
        while parent:
            branch = parent
            parent = self.parent_of(branch)
        return branch

    def get_or_infer_parent_of(self,
                               branch: LocalBranchShortName,
                               prompt_if_inferred_msg: Optional[str],
                               prompt_if_inferred_yes_opt_msg: Optional[str]) -> LocalBranchShortName:
        if branch in self.managed_branches:
            managed_parent = self.parent_of(branch)
            if managed_parent:
                return managed_parent
            else:
                raise MacheteException(f"Branch <b>{branch}</b> has no upstream branch")
        else:
            parent = self._infer_parent(branch)
            if parent:
                if prompt_if_inferred_msg and prompt_if_inferred_yes_opt_msg:
                    if self.ask_if(
                            prompt_if_inferred_msg % (branch, parent),
                            prompt_if_inferred_yes_opt_msg % (branch, parent),
                            opt_yes=False
                    ) in ('y', 'yes'):
                        return parent
                    raise MacheteException("Aborting.")
                else:
                    warn(
                        f"branch <b>{branch}</b> not found in the tree of branch "
                        f"dependencies; the upstream has been inferred to <b>{parent}</b>")
                    return parent
            else:
                raise MacheteException(
                    f"Branch <b>{branch}</b> not found in the tree of branch "
                    f"dependencies and its upstream could not be inferred")

    # === Fork-point computation ===

    def fork_point_and_inferring_branch_pairs(
        self,
        branch: LocalBranchShortName,
        *,
        use_overrides: bool
    ) -> Tuple[FullCommitHash, List[BranchPair]]:
        parent = self.parent_of(branch)
        parent_hash = self._git.get_commit_hash_by_revision(parent) if parent else None

        if use_overrides:
            overridden_fork_point = self._get_overridden_fork_point(branch)
            if overridden_fork_point:
                if parent and parent_hash and \
                        self._git.is_ancestor_or_equal(parent.full_name(), branch.full_name()) and \
                        not self._git.is_ancestor_or_equal(parent.full_name(), overridden_fork_point):
                    # We need to handle the case when branch is a descendant of parent,
                    # but the fork point of branch is overridden to a commit that is NOT a descendant of parent.
                    # In this case it's more reasonable to assume that parent (and not overridden_fork_point) is the fork point.
                    debug(
                        f"{branch} is descendant of its parent {parent}, but overridden fork point commit {overridden_fork_point} "
                        f"is NOT a descendant of {parent}; falling back to {parent} as fork point")
                    return parent_hash, []
                elif parent and \
                        self._git.is_ancestor_or_equal(overridden_fork_point, parent.full_name()):
                    common_ancestor = self._git.get_merge_base(parent.full_name(), branch.full_name())
                    # We are sure that a common ancestor exists - `overridden_fork_point` is an ancestor of both `branch` and `parent`.
                    assert common_ancestor is not None
                    return common_ancestor, []
                else:
                    debug(f"fork point of {branch} is overridden to {overridden_fork_point}; skipping inference")
                    return overridden_fork_point, []

        try:
            computed_fork_point, inferring_branch_pairs = next(self.__match_log_to_filtered_reflogs(branch))
        except StopIteration:
            if parent and parent_hash:
                if self._git.is_ancestor_or_equal(parent.full_name(), branch.full_name()):
                    debug(
                        f"cannot find fork point, but {branch} is a descendant of its parent {parent}; "
                        f"falling back to {parent} as fork point")
                    return parent_hash, []
                else:
                    common_ancestor_hash = self._git.get_merge_base(parent.full_name(), branch.full_name())
                    if common_ancestor_hash:
                        debug(
                            f"cannot find fork point, and {branch} is NOT a descendant of its parent {parent}; "
                            f"falling back to common ancestor of {branch} and {parent} (commit {common_ancestor_hash}) as fork point")
                        return common_ancestor_hash, []
            raise MacheteException(f"Fork point not found for branch <b>{branch}</b>; "
                                   f"use `git machete fork-point {branch} --override-to...`")
        else:
            debug(f"commit {computed_fork_point} is the most recent point in history of {branch} to occur on "
                  "filtered reflog of any other branch or its remote counterpart "
                  f"(specifically: {' and '.join(map(get_second, inferring_branch_pairs))})")

            if parent and parent_hash and \
                    self._git.is_ancestor_or_equal(parent.full_name(), branch.full_name()) and \
                    not self._git.is_ancestor_or_equal(parent.full_name(), computed_fork_point):
                # That happens very rarely in practice (typically current head of any branch, including parent,
                # should occur on the reflog of this branch, thus is_ancestor(parent, branch) should imply is_ancestor(parent, FP(branch)),
                # but it's still possible in case reflog of parent is incomplete for whatever reason.
                debug(
                    f"{parent} is an ancestor of {branch}, "
                    f"but the inferred fork point commit {computed_fork_point} is NOT a descendant of {parent}; "
                    f"falling back to {parent} as fork point")
                return parent_hash, []
            elif parent and \
                    not self._git.is_ancestor_or_equal(parent.full_name(), branch.full_name()) and \
                    self._git.is_ancestor_or_equal(computed_fork_point, parent.full_name()):

                # We are sure that a common ancestor exists - `computed_fork_point` is an ancestor of both `branch` and `parent`.
                common_ancestor_hash = self._git.get_merge_base(parent.full_name(), branch.full_name())
                assert common_ancestor_hash is not None
                debug(
                    f"{parent} is NOT an ancestor of {branch}, "
                    f"but the inferred fork point commit {computed_fork_point} is an ancestor of {parent}; "
                    f"falling back to the common ancestor of {branch} and {parent} (commit {common_ancestor_hash}) as fork point")
                return common_ancestor_hash, []
            else:
                improved_fork_point = computed_fork_point
                improved_inferring_branch_pairs = inferring_branch_pairs
                for candidate_branch, original_matched_branch in inferring_branch_pairs:
                    merge_base = self._git.get_merge_base(original_matched_branch, branch)
                    debug(f"improving fork point {improved_fork_point} "
                          f"by checking for merge_base({original_matched_branch}, {branch}) = {merge_base}")
                    if merge_base:
                        if self._git.is_ancestor(improved_fork_point, merge_base):
                            debug(f"improving fork point {improved_fork_point} to {merge_base}")
                            improved_fork_point = merge_base
                            improved_inferring_branch_pairs = [BranchPair(candidate_branch, original_matched_branch)]
                debug(f"effective fork point of {branch} is {improved_fork_point}")
                return improved_fork_point, improved_inferring_branch_pairs

    def fork_point(self, branch: LocalBranchShortName, *, use_overrides: bool) -> FullCommitHash:
        hash, inferring_branch_pairs = self.fork_point_and_inferring_branch_pairs(branch, use_overrides=use_overrides)
        return FullCommitHash.of(hash)

    def fork_point_or_none(self, branch: LocalBranchShortName, *, use_overrides: bool) -> Optional[FullCommitHash]:
        try:
            return self.fork_point(branch, use_overrides=use_overrides)
        except MacheteException:
            return None

    def check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
            self, *, fork_point: AnyRevision, branch: AnyBranchName) -> None:
        if not self._git.is_ancestor_or_equal(
                earlier_revision=fork_point.full_name(),
                later_revision=branch.full_name()):
            raise MacheteException(
                f"Fork point <b>{fork_point}</b> is not ancestor of or the tip "
                f"of the <b>{branch}</b> branch.")

    def filtered_reflog(self, branch: AnyBranchName) -> List[FullCommitHash]:
        def is_excluded_reflog_subject(entry_hash: str, reflog_subject: str) -> bool:
            is_excluded = (reflog_subject.startswith("branch: Created from") or
                           reflog_subject == f"branch: Reset to {branch}" or
                           reflog_subject == "branch: Reset to HEAD" or
                           reflog_subject.startswith("reset: moving to ") or
                           reflog_subject.startswith("fetch . ") or
                           # The rare case of a no-op rebase, the exact wording
                           # likely depends on git version
                           reflog_subject == f"rebase finished: {branch.full_name()} onto {entry_hash}" or
                           reflog_subject == f"rebase -i (finish): {branch.full_name()} onto {entry_hash}" or
                           # For remote branches, let's NOT include the pushes,
                           # as a branch can be pushed directly after being created,
                           # which might lead to fork point being inferred too *late* in the history
                           reflog_subject == "update by push")
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

        result = [entry_hash for (entry_hash, reflog_subject) in branch_reflog if
                  entry_hash not in hashes_to_exclude and not is_excluded_reflog_subject(entry_hash, reflog_subject)]
        reflog = (", ".join(result) or "<empty>")
        debug("computed filtered reflog (= reflog without branch creation "
              f"and branch reset events irrelevant for fork point/parent inference): {reflog}")
        return result

    def __match_log_to_filtered_reflogs(self, branch: LocalBranchShortName) -> Iterator[Tuple[FullCommitHash, List[BranchPair]]]:

        if self.__branch_pairs_by_hash_in_reflog is None:
            def generate_entries() -> Iterator[Tuple[FullCommitHash, BranchPair]]:
                for lb in self._git.get_local_branches():
                    lb_hashes = set()
                    for commit_hash in self.filtered_reflog(lb):
                        lb_hashes.add(commit_hash)
                        yield FullCommitHash.of(commit_hash), BranchPair(lb, lb)
                    remote_branch = self._git.get_combined_counterpart_for_fetching_of_branch(lb)
                    if remote_branch:
                        for commit_hash in self.filtered_reflog(remote_branch):
                            if commit_hash not in lb_hashes:
                                yield FullCommitHash.of(commit_hash), BranchPair(lb, remote_branch)

            self.__branch_pairs_by_hash_in_reflog = {}
            for hash, branch_pair in generate_entries():
                # We dedup `branch_pair`s per hash so that a commit which appears multiple times in a single branch's filtered reflog
                # (e.g. via a `git reset --hard` back to it followed by an advance, then another reset back)
                # doesn't end up listed twice in `inferring_branches`.
                # Without this, `fork-point --explain` and `status -l` would print things like
                # "...part of the unique history of master and master".
                # The list-of-pairs shape is preserved (rather than a set) because downstream code relies on sorted ordering
                # and indexed iteration.
                existing = self.__branch_pairs_by_hash_in_reflog.setdefault(hash, [])
                if branch_pair not in existing:
                    existing.append(branch_pair)

            def log_result() -> Iterator[str]:
                entry_branch_pairs: List[BranchPair]
                entry_hash: FullCommitHash
                assert self.__branch_pairs_by_hash_in_reflog is not None
                for entry_hash, entry_branch_pairs in self.__branch_pairs_by_hash_in_reflog.items():
                    def branch_pair_to_str(lb: str, lb_or_rb: str) -> str:
                        return lb if lb == lb_or_rb else f"{lb_or_rb} (remote counterpart of {lb})"

                    joined_branch_pairs = ", ".join(map(tupled(branch_pair_to_str), entry_branch_pairs))
                    yield f"<dim>{entry_hash} => {joined_branch_pairs}</dim>"

            branches = "\n".join(log_result())
            debug(f"branches containing the given hash in their filtered reflog: \n{branches}\n")

        branch_full_hash = self._git.get_commit_hash_by_revision(branch)
        if not branch_full_hash:
            return

        for hash in self._git.spoonfeed_log_hashes(branch_full_hash,
                                                   initial_count=INITIAL_COMMIT_COUNT_FOR_LOG,
                                                   total_count=TOTAL_COMMIT_COUNT_FOR_LOG):
            if hash in self.__branch_pairs_by_hash_in_reflog:
                # The entries must be sorted by lb_or_rb to make sure the parent inference is deterministic
                # (and does not depend on the order in which `generate_entries` iterated through the local branches).
                branch_pairs: List[BranchPair] = self.__branch_pairs_by_hash_in_reflog[hash]

                def lb_is_not_b(lb: str, _lb_or_rb: str) -> bool:
                    return lb != branch

                inferring_branch_pairs = sorted(filter(tupled(lb_is_not_b), branch_pairs), key=get_second)
                if inferring_branch_pairs:
                    debug(f"commit {hash} found in filtered reflog of {' and '.join(map(get_second, branch_pairs))}")
                    yield hash, inferring_branch_pairs
                else:
                    debug(f"commit {hash} found only in filtered reflog of {' and '.join(map(get_second, branch_pairs))}; ignoring")
            else:
                debug(f"commit {hash} not found in any filtered reflog")

    def _infer_parent(self,
                      branch: LocalBranchShortName,
                      condition: Callable[[LocalBranchShortName], bool] = lambda parent: True,
                      *,
                      reject_reason_message: str = ""
                      ) -> Optional[LocalBranchShortName]:
        for hash, inferring_branch_pairs in self.__match_log_to_filtered_reflogs(branch):
            debug(f"commit {hash} found in filtered reflog of {' and '.join(map(get_second, inferring_branch_pairs))}")

            for candidate, original_matched_branch in inferring_branch_pairs:
                if candidate != original_matched_branch:
                    debug(f"parent candidate is {candidate}, which is the local counterpart of {original_matched_branch}")

                if condition(candidate):
                    debug(f"parent candidate {candidate} accepted")
                    return candidate
                else:
                    debug(f"parent candidate {candidate} rejected ({reject_reason_message})")
        return None

    # === Fork-point overrides ===

    # Also includes config that is invalid (corresponding to a non-existent/GCed commit etc.).
    def has_any_fork_point_override_config(self, branch: LocalBranchShortName) -> bool:
        return (self._config.fork_point_override_to_value(branch) or
                self._config.fork_point_override_while_descendant_of_value(branch)) is not None

    def __get_fork_point_override_data(self, branch: LocalBranchShortName) -> Optional[ForkPointOverrideData]:
        # Note that here we ignore the now-deprecated `whileDescendantOf`.
        to_value = self._config.fork_point_override_to_value(branch)
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
            warn(
                f"since branch <b>{branch}</b> is no longer a descendant of commit <b>{to}</b>, "
                "the fork point override to this commit no longer applies.\n"
                f"Consider running:\n  `git machete fork-point --unset-override {branch}`\n")
            return None
        debug(f"since branch {branch} is descendant of {to}, fork point of {branch} is overridden to {to}")
        return to

    # === Merge detection ===

    def is_merged_to(
            self,
            *,
            branch: AnyBranchName,
            parent: AnyBranchName,
            opt_squash_merge_detection: SquashMergeDetection
    ) -> bool:
        if self._git.is_ancestor_or_equal(branch.full_name(), parent.full_name()):
            # If branch is ancestor of or equal to the parent, we need to distinguish between the
            # case of branch being "recently" created from the parent and the case of
            # branch being fast-forward-merged to the parent.
            # The applied heuristics is to check if the filtered reflog of the branch
            # (reflog stripped of trivial events like branch creation, reset etc.)
            # is non-empty.
            return bool(self.filtered_reflog(branch))
        elif opt_squash_merge_detection == SquashMergeDetection.NONE:
            return False
        elif opt_squash_merge_detection == SquashMergeDetection.SIMPLE:
            # In the default mode.
            # If a commit with an identical tree state to branch is reachable from parent,
            # then branch may have been squashed or rebase-merged into parent.
            return self._git.is_equivalent_tree_reachable(equivalent_to=branch, reachable_from=parent)
        elif opt_squash_merge_detection == SquashMergeDetection.EXACT:
            # Let's try another way, a little more complex but takes into account the possibility
            # that there were other commits between the common ancestor of the two branches and the squashed merge.
            return self._git.is_equivalent_tree_reachable(equivalent_to=branch, reachable_from=parent) or \
                self._git.is_equivalent_patch_reachable(equivalent_to=branch, reachable_from=parent)
        else:  # pragma: no cover
            raise UnexpectedMacheteException(f"Invalid squash merged detection mode: {opt_squash_merge_detection}.")

    def _is_merged_to_parent(
            self, branch: LocalBranchShortName, *, opt_squash_merge_detection: SquashMergeDetection) -> bool:
        parent = self.parent_of(branch)
        if not parent:
            return False
        return self.is_merged_to(branch=branch, parent=parent, opt_squash_merge_detection=opt_squash_merge_detection)

    # === Branch addition ===

    def add(self,
            *,
            opt_branch: Optional[LocalBranchShortName],
            opt_onto: Optional[LocalBranchShortName],
            opt_as_first_child: bool,
            opt_as_root: bool,
            opt_yes: bool,
            verbose: bool,
            switch_head_if_new_branch: bool
            ) -> None:
        branch = opt_branch or self._git.get_current_branch()
        if branch in self.managed_branches:
            raise MacheteException(f"Branch <b>{branch}</b> already exists in the tree of branch dependencies")

        # `onto` is tracked as a `ManagedBranchName` from this point on so that the final `add_as_child(parent=...)` call type-checks;
        # every path that assigns to it (explicit `--onto`, current branch, inferred parent) is gated on the branch being in the layout.
        onto: Optional[ManagedBranchName] = self.expect_in_managed_branches(opt_onto) if opt_onto else None

        if branch not in self._git.get_local_branches():
            remote_branch: Optional[RemoteBranchShortName] = self._git.get_sole_remote_branch(branch)
            if remote_branch:
                common_line = (
                    f"A local branch <b>{branch}</b> does not exist, but a remote "
                    f"branch <b>{remote_branch}</b> exists.\n")
                msg = common_line + f"Check out <b>{branch}</b> locally?" + pretty_choices('y', 'N')
                opt_yes_msg = common_line + f"Checking out <b>{branch}</b> locally..."
                if self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes, verbose=verbose) in ('y', 'yes'):
                    self._git.create_branch(branch, remote_branch.full_name(), switch_head=switch_head_if_new_branch)
                else:
                    return
                # Not dealing with `onto` here. If it hasn't been explicitly specified via `--onto`, we'll try to infer it now.
            else:
                out_of = LocalBranchShortName.of(onto).full_name() if onto else HEAD
                out_of_str = f"<b>{onto}</b>" if onto else "the current HEAD"
                msg = (f"A local branch <b>{branch}</b> does not exist. Create out "
                       f"of {out_of_str}?" + pretty_choices('y', 'N'))
                opt_yes_msg = (f"A local branch <b>{branch}</b> does not exist. "
                               f"Creating out of {out_of_str}")
                if self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes, verbose=verbose) in ('y', 'yes'):
                    # If `--onto` hasn't been explicitly specified, let's try to
                    # assess if the current branch would be a good `onto`.
                    if not onto:
                        current_branch = self._git.get_current_branch_or_none()
                        if self._state.roots:
                            if current_branch and current_branch in self.managed_branches:
                                onto = ManagedBranchName(current_branch)
                        else:
                            if current_branch:
                                # In this case (empty .git/machete, creating a new branch with `git machete add`)
                                # it's usually pretty obvious that the current branch needs to be added as root first.
                                # Let's skip interactive questions so as not to confuse new users.
                                self._state.bootstrap_as_single_managed(current_branch)
                                # This section of code is only ever executed in verbose mode, but let's leave the `if` for consistency
                                if verbose:  # pragma: no branch
                                    print_fmt(f"Added branch <b>{current_branch}</b> as a new root")
                                onto = ManagedBranchName(current_branch)
                    self._git.create_branch(branch, out_of, switch_head=switch_head_if_new_branch)
                else:
                    return

        if opt_as_root or not self._state.roots:
            self._state.add_as_root(branch)
            if verbose:
                print_fmt(f"Added branch <b>{branch}</b> as a new root")
        else:
            if not onto:
                parent = self._infer_parent(
                    branch,
                    condition=lambda x: x in self.managed_branches,
                    reject_reason_message="this candidate is not a managed branch")
                if not parent:
                    raise MacheteException(
                        f"Could not automatically infer upstream (parent) branch for <b>{branch}</b>.\n"
                        "You can either:\n"
                        "1) specify the desired upstream branch with `--onto` or\n"
                        f"2) pass `--as-root` to attach <b>{branch}</b> as a new root or\n"
                        "3) edit the branch layout file manually with `git machete edit`")
                else:
                    msg = (f"Add <b>{branch}</b> onto the inferred upstream (parent) "
                           f"branch <b>{parent}</b>?" + pretty_choices('y', 'N'))
                    opt_yes_msg = (f"Adding <b>{branch}</b> onto the inferred upstream"
                                   f" (parent) branch <b>{parent}</b>")
                    if self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes, verbose=verbose) in ('y', 'yes'):
                        # `_infer_parent` was filtered by `x in self.managed_branches`
                        # above, so we can safely narrow here.
                        onto = ManagedBranchName(parent)
                    else:
                        return

            assert onto is not None  # established by the `if not onto: ...` block above
            self._state.add_as_child(branch=branch, parent=onto, as_first_child=opt_as_first_child)
            if verbose:
                print_fmt(f"Added branch <b>{branch}</b> onto <b>{onto}</b>")

        self.save_branch_layout_file()

    # === Branch deletion ===

    def delete_unmanaged(self, *, opt_squash_merge_detection: Optional[SquashMergeDetection], opt_yes: bool) -> None:
        # CLI flag > `machete.squashMergeDetection` config key > built-in `SIMPLE` default - see `CommandLineOptions`.
        # Internal callers (`clean`, `github sync`, `gitlab sync`) pass a concrete `SquashMergeDetection.NONE`, bypassing the fallback.
        if opt_squash_merge_detection is None:
            opt_squash_merge_detection = self._config.squash_merge_detection()
        print('Checking for unmanaged branches...')
        branches_to_delete = sorted(excluding(self._git.get_local_branches(), self.managed_branches))
        self._delete_branches(branches_to_delete=branches_to_delete,
                              opt_squash_merge_detection=opt_squash_merge_detection, opt_yes=opt_yes)

    def delete_untracked(self, *, opt_yes: bool) -> None:
        print_fmt("<b>Checking for untracked managed branches with no downstream...</b>")
        branches_to_delete: List[ManagedBranchName] = []
        for branch in self.managed_branches.copy():
            status, _ = self._git.get_combined_remote_sync_status(branch)
            if status == SyncToRemoteStatus.UNTRACKED and not self.children_of(branch):
                branches_to_delete.append(branch)

        self._remove_branches_from_layout(branches_to_delete)
        self._delete_branches(branches_to_delete, opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=opt_yes)

    def _delete_branches(
        self,
        branches_to_delete: Sequence[LocalBranchShortName],
        *,
        opt_squash_merge_detection: SquashMergeDetection,
        opt_yes: bool
    ) -> None:
        current_branch = self._git.get_current_branch_or_none()
        if current_branch and current_branch in branches_to_delete:
            branches_to_delete = excluding(branches_to_delete, [current_branch])
            print_fmt(f"Skipping current branch <b>{current_branch}</b>")
        if not branches_to_delete:
            print("No branches to delete")
            return

        if opt_yes:
            for branch in branches_to_delete:
                print_fmt(f"Deleting branch <b>{branch}</b>...")
                self._git.delete_branch(branch, force=True)
        else:
            for branch in branches_to_delete:
                if self.is_merged_to(branch=branch, parent=AnyBranchName('HEAD'), opt_squash_merge_detection=opt_squash_merge_detection):
                    remote_branch = self._git.get_strict_counterpart_for_fetching_of_branch(branch)
                    if remote_branch:
                        is_merged_to_remote = self.is_merged_to(
                            branch=branch,
                            parent=remote_branch,
                            opt_squash_merge_detection=opt_squash_merge_detection)
                    else:
                        is_merged_to_remote = True
                    if is_merged_to_remote:
                        msg_core_suffix = ''
                    else:
                        msg_core_suffix = f', but not merged to <b>{remote_branch}</b>'
                    msg_core = f"<b>{branch}</b> (merged to HEAD{msg_core_suffix})"
                else:
                    msg_core = f"<b>{branch}</b> (unmerged to HEAD)"
                msg = f"Delete branch {msg_core}?" + pretty_choices('y', 'N', 'q')
                ans = self.ask_if(msg, msg_if_opt_yes=None, opt_yes=False)
                if ans in ('y', 'yes'):
                    self._git.delete_branch(branch, force=True)
                elif ans in ('q', 'quit'):
                    return

    # === Rebase ===

    def rebase(
            self, *,
            onto: AnyRevision,
            from_exclusive: AnyRevision,
            branch: LocalBranchShortName,
            opt_no_interactive_rebase: bool
    ) -> None:
        self._git.expect_no_operation_in_progress()

        anno = self._state.get_annotation(branch)
        if anno and not anno.qualifiers.rebase:
            raise MacheteException(f"Branch <b>{branch}</b> is annotated with `rebase=no` qualifier, aborting.\n"
                                   f"Remove the qualifier using `git machete anno` or edit branch layout file directly.")
        # Let's use `OPTS` suffix for consistency with git's built-in env var `GIT_DIFF_OPTS`
        extra_rebase_opts = os.environ.get('GIT_MACHETE_REBASE_OPTS', '').split()

        hook_path = self._git.get_hook_path("machete-pre-rebase")
        if self._git.check_hook_executable(hook_path):
            debug(f"running machete-pre-rebase hook ({hook_path})")
            exit_code = self.__run_hook(hook_path, onto, from_exclusive, branch, cwd=self._git.get_current_worktree_root_dir())
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

    # === Editor (edit subcommand) ===

    def edit(self) -> int:
        default_editor_with_args: List[str] = self.__get_editor_with_args()
        if not default_editor_with_args:
            raise MacheteException(
                f"Cannot determine editor. Set `GIT_MACHETE_EDITOR` environment "
                f"variable or edit {self._branch_layout_file_path_for_display} directly.")

        command = default_editor_with_args[0]
        args = default_editor_with_args[1:] + [self._branch_layout_file_path_for_display]
        return run_cmd(command, *args)

    def __get_editor_with_args(self) -> List[str]:
        # Based on the git's own algorithm for identifying the editor.
        # '$GIT_MACHETE_EDITOR', 'editor' (to please Debian-based systems) and 'nano' have been added.
        git_machete_editor_var = "GIT_MACHETE_EDITOR"
        proposed_editor_funs: List[Tuple[str, Callable[[], Optional[str]]]] = [
            ("$" + git_machete_editor_var, lambda: os.environ.get(git_machete_editor_var)),
            ("$GIT_EDITOR", lambda: os.environ.get("GIT_EDITOR")),
            ("git config core.editor", lambda: self._config.core_editor()),
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

                if not fs.find_executable(editor_command):
                    debug(f"'{editor_command}' executable ('{name}') not found")
                    if name == "$" + git_machete_editor_var:
                        # In this specific case, when GIT_MACHETE_EDITOR is defined but doesn't point to a valid executable,
                        # it's more reasonable/less confusing to raise an error and exit without opening anything.
                        raise MacheteException(f"<b>{editor_repr}</b> is not available")
                else:
                    debug(f"'{editor_command}' executable ('{name}') found")
                    if name != "$" + git_machete_editor_var and self._config.advice_machete_editor_selection():
                        sample_alternative = 'nano' if editor_command.startswith('vi') else 'vi'
                        print_fmt(f"Opening <b>{editor_repr}</b>.\n"
                                  f"To override this choice, use <b>{git_machete_editor_var}</b> env var, e.g. `export "
                                  f"{git_machete_editor_var}={sample_alternative}`.\n\n"
                                  "See `git machete help edit` and `git machete edit --debug` for more details.\n\n"
                                  "Use `git config --global advice.macheteEditorSelection false` to suppress this message.",
                                  file=sys.stderr)
                    return editor_parsed

        # This case is extremely unlikely on a modern Unix-like system.
        return []

    # === Hooks ===

    def __run_hook(self, *args: str, cwd: Path) -> int:
        self._git.flush_caches()
        if sys.platform == "win32":
            return run_cmd("sh", *args, cwd=cwd)
        else:
            return run_cmd(*args, cwd=cwd)

    def _run_post_slide_out_hook(
        self,
        *,
        new_parent: Optional[LocalBranchShortName],
        slid_out_branch: LocalBranchShortName,
        new_children: List[ManagedBranchName]
    ) -> None:
        hook_path = self._git.get_hook_path("machete-post-slide-out")
        if self._git.check_hook_executable(hook_path):
            debug(f"running machete-post-slide-out hook ({hook_path})")
            new_children_strings: List[str] = [str(c) for c in new_children]
            # When sliding out root branches, new_parent is None; pass empty string to the hook.
            # Note: the hook protocol's CLI arguments are still called `<new-upstream>` and
            # `<new-downstreams>` for backwards compatibility - only the internal Python
            # keyword args have been renamed.
            new_parent_str = str(new_parent) if new_parent is not None else ""
            exit_code = self.__run_hook(hook_path, new_parent_str, slid_out_branch, *new_children_strings,
                                        cwd=self._git.get_current_worktree_root_dir())
            if exit_code != 0:
                raise MacheteException(f"The machete-post-slide-out hook exited with {exit_code}, aborting.")

    # === Sync-to-remote state handlers ===

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
            choices = pretty_choices(
                *('y', 'N', 'q', 'yq', other_remote_choice) if is_called_from_traverse else ('y', 'Q'))
            ask_message = f"Push untracked branch <b>{branch}</b> to <b>{new_remote}</b>?" + choices
            ask_opt_yes_message = f"Pushing untracked branch <b>{branch}</b> to <b>{new_remote}</b>..."
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
                f"Branch <b>{branch}</b> is untracked, but its remote counterpart candidate <b>{remote_branch}</b> "
                f"already exists and both branches point to the same commit.",
            SyncToRemoteStatus.BEHIND_REMOTE:
                f"Branch <b>{branch}</b> is untracked, but its remote counterpart candidate <b>{remote_branch}</b> "
                f"already exists and is ahead of <b>{branch}</b>.",
            SyncToRemoteStatus.AHEAD_OF_REMOTE:
                f"Branch <b>{branch}</b> is untracked, but its remote counterpart candidate <b>{remote_branch}</b> "
                f"already exists and is behind <b>{branch}</b>.",
            SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                f"Branch <b>{branch}</b> is untracked, it diverged from its remote counterpart candidate <b>{remote_branch}</b>, "
                f"and has <b>older</b> commits than <b>{remote_branch}</b>.",
            SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                f"Branch <b>{branch}</b> is untracked, it diverged from its remote counterpart candidate <b>{remote_branch}</b>, "
                f"and has <b>newer</b> commits than <b>{remote_branch}</b>."
        }[SyncToRemoteStatus(relation)]

        ask_message, ask_opt_yes_message = {
            SyncToRemoteStatus.IN_SYNC_WITH_REMOTE: (
                f"Set the remote of <b>{branch}</b> to <b>{new_remote}</b> without pushing or pulling?" +
                pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Setting the remote of <b>{branch}</b> to <b>{new_remote}</b>..."
            ),
            SyncToRemoteStatus.BEHIND_REMOTE: (
                f"Pull <b>{branch}</b> (fast-forward only) from <b>{new_remote}</b>?" +
                pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Pulling <b>{branch}</b> (fast-forward only) from <b>{new_remote}</b>..."
            ),
            SyncToRemoteStatus.AHEAD_OF_REMOTE: (
                f"Push branch <b>{branch}</b> to <b>{new_remote}</b>?" + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Pushing branch <b>{branch}</b> to <b>{new_remote}</b>..."
            ),
            SyncToRemoteStatus.DIVERGED_FROM_AND_OLDER_THAN_REMOTE: (
                f"Reset branch <b>{branch}</b> to the commit pointed by <b>{remote_branch}</b>?" +
                pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Resetting branch <b>{branch}</b> to the commit pointed by <b>{remote_branch}</b>..."
            ),
            SyncToRemoteStatus.DIVERGED_FROM_AND_NEWER_THAN_REMOTE: (
                f"Push branch <b>{branch}</b> with force-with-lease to <b>{new_remote}</b>?" +
                pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Pushing branch <b>{branch}</b> with force-with-lease to <b>{new_remote}</b>..."
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

        print_fmt(message)
        ans = self.ask_if(ask_message, ask_opt_yes_message, override_answer=override_answer, opt_yes=opt_yes)
        if ans in ('y', 'yes', 'yq'):
            yes_action()
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
        self._ensure_blank_separator()
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
            print_fmt(f"Branch <b>{branch}</b> is untracked and there's no <b>origin</b> remote.")
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
        self._ensure_blank_separator()
        choices = pretty_choices(*('y', 'N', 'q', 'yq') if is_called_from_traverse else ('y', 'N', 'q'))
        ans = self.ask_if(
            f"Push <b>{current_branch}</b> to <b>{remote}</b>?" + choices,
            f"Pushing <b>{current_branch}</b> to <b>{remote}</b>...",
            override_answer=None if opt_push_tracked else "N",
            opt_yes=opt_yes
        )
        if ans in ('y', 'yes', 'yq'):
            self._git.push(remote, current_branch)
            if ans == 'yq' and is_called_from_traverse:
                raise InteractionStopped
        elif ans in ('q', 'quit'):
            raise InteractionStopped

    def _handle_behind_state(self, *, branch: LocalBranchShortName, remote: str, opt_yes: bool) -> None:
        self._ensure_blank_separator()
        remote_branch = self._git.get_combined_counterpart_for_fetching_of_branch(branch)
        assert remote_branch is not None
        ans = self.ask_if(
            f"Branch <b>{branch}</b> is behind its remote counterpart <b>{remote_branch}</b>.\n"
            f"Pull <b>{branch}</b> (fast-forward only) from <b>{remote}</b>?" + pretty_choices('y', 'N', 'q', 'yq'),
            f"Branch <b>{branch}</b> is behind its remote counterpart <b>{remote_branch}</b>.\n"
            f"Pulling <b>{branch}</b> (fast-forward only) from <b>{remote}</b>...",
            opt_yes=opt_yes)
        if ans in ('y', 'yes', 'yq'):
            self._git.pull_ff_only(remote, remote_branch)
            if ans == 'yq':
                raise InteractionStopped
        elif ans in ('q', 'quit'):
            raise InteractionStopped

    def _handle_diverged_and_newer_state(
            self,
            *,
            current_branch: LocalBranchShortName,
            remote: str,
            is_called_from_traverse: bool = True,
            opt_push_tracked: bool,
            opt_yes: bool
    ) -> None:
        self._ensure_blank_separator()
        remote_branch = self._git.get_combined_counterpart_for_fetching_of_branch(current_branch)
        assert remote_branch is not None
        choices = pretty_choices(*('y', 'N', 'q', 'yq') if is_called_from_traverse else ('y', 'N', 'q'))
        ans = self.ask_if(
            f"Branch <b>{current_branch}</b> diverged from (and has newer commits than) its remote counterpart <b>{remote_branch}</b>.\n"
            f"Push <b>{current_branch}</b> with force-with-lease to <b>{remote}</b>?" + choices,
            f"Branch <b>{current_branch}</b> diverged from (and has newer commits than) its remote counterpart <b>{remote_branch}</b>.\n"
            f"Pushing <b>{current_branch}</b> with force-with-lease to <b>{remote}</b>...",
            override_answer=None if opt_push_tracked else "N", opt_yes=opt_yes)
        if ans in ('y', 'yes', 'yq'):
            self._git.push(remote, current_branch, force_with_lease=True)
            if ans == 'yq':
                raise InteractionStopped
        elif ans in ('q', 'quit'):
            raise InteractionStopped

    def _handle_diverged_and_older_state(self, branch: LocalBranchShortName, *, opt_yes: bool) -> None:
        self._ensure_blank_separator()
        remote_branch = self._git.get_combined_counterpart_for_fetching_of_branch(branch)
        assert remote_branch is not None
        ans = self.ask_if(
            f"Branch <b>{branch}</b> diverged from (and has older commits than) its remote counterpart <b>{remote_branch}</b>.\n"
            f"Reset branch <b>{branch}</b> to the commit pointed by <b>{remote_branch}</b>?" + pretty_choices('y', 'N', 'q', 'yq'),
            f"Branch <b>{branch}</b> diverged from (and has older commits than) its remote counterpart <b>{remote_branch}</b>.\n"
            f"Resetting branch <b>{branch}</b> to the commit pointed by <b>{remote_branch}</b>...",
            opt_yes=opt_yes)
        if ans in ('y', 'yes', 'yq'):
            self._git.reset_keep(remote_branch)
            if ans == 'yq':
                raise InteractionStopped
        elif ans in ('q', 'quit'):
            raise InteractionStopped

    # === Output formatting ===

    def _mark_trailing_blank_line(self) -> None:
        self.__has_trailing_blank_line = True

    def _ensure_blank_separator(self) -> None:
        if not self.__has_trailing_blank_line:
            print("")
        self.__has_trailing_blank_line = False

    # === User prompts ===

    @staticmethod
    def ask_if(
            msg: str,
            msg_if_opt_yes: Optional[str],
            *,
            opt_yes: bool,
            override_answer: Optional[str] = None,
            verbose: bool = True
    ) -> str:
        if override_answer:
            return override_answer
        if opt_yes and msg_if_opt_yes:
            if verbose:
                print_fmt(msg_if_opt_yes)
            return 'y'
        try:
            ans: str = input_fmt(msg).lower().strip()
        except InterruptedError:
            sys.exit(1)
        return ans

    @staticmethod
    def pick(choices: Sequence[_BranchT], name: str) -> _BranchT:
        # Generic in the branch type: when the caller hands us `List[ManagedBranchName]`
        # the returned element is also a `ManagedBranchName` (not just any `LocalBranchShortName`),
        # which matters when the result is then fed back into layout-mutating APIs.
        xs: str = "".join(f"[{index + 1}] {x}\n" for index, x in enumerate(choices))
        msg: str = xs + f"Specify {name} or hit <return> to skip: "
        try:
            ans: str = input_fmt(msg)
            if not ans:
                sys.exit(0)
            index: int = int(ans) - 1
        except ValueError:
            sys.exit(1)
        if index not in range(len(choices)):
            raise MacheteException(f"Invalid index: {index + 1}")
        return choices[index]

    # === Cache management ===

    def flush_caches(self) -> None:
        self.__branch_pairs_by_hash_in_reflog = None
