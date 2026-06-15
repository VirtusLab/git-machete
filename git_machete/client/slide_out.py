from typing import Dict, List, NamedTuple, Optional

from git_machete.client.base import MacheteClient
from git_machete.client.state import ManagedBranchName
from git_machete.config import SquashMergeDetection
from git_machete.git import AnyRevision, LocalBranchShortName
from git_machete.utils.exceptions import MacheteException
from git_machete.utils.markup import green_ok, print_fmt


class Reattachment(NamedTuple):
    children: List[ManagedBranchName]
    new_parent: Optional[ManagedBranchName]


class HookInvocation(NamedTuple):
    new_parent: Optional[ManagedBranchName]
    slid_out_branch: ManagedBranchName
    new_children: List[ManagedBranchName]


class SlideOutMacheteClient(MacheteClient):
    def slide_out(self,
                  *,
                  opt_branches: Optional[List[LocalBranchShortName]],
                  opt_delete: bool,
                  opt_down_fork_point: Optional[AnyRevision],
                  opt_merge: bool,
                  opt_no_edit_merge: bool,
                  opt_no_interactive_rebase: bool,
                  opt_no_rebase: bool
                  ) -> None:
        self._git.expect_no_operation_in_progress()
        raw_branches: List[LocalBranchShortName] = opt_branches or [self._git.get_current_branch()]

        # Verify that all branches exist, are managed and are NOT annotated with slide-out=no qualifier.
        # `expect_in_managed_branches` narrows to `ManagedBranchName`, which we keep for the rest of the method
        # so we can hand the values to layout mutators (`splice_out`, `_remove_branches_from_layout`) without re-checking.
        branches_to_slide_out: List[ManagedBranchName] = []
        for branch in raw_branches:
            managed = self.expect_in_managed_branches(branch)
            branches_to_slide_out.append(managed)
            anno = self._state.get_annotation(managed)
            if anno and not anno.qualifiers.slide_out:
                raise MacheteException(f"Branch <b>{managed}</b> is annotated with `slide-out=no` qualifier, aborting.\n"
                                       f"Remove the qualifier using `git machete anno` or edit branch layout file directly.")

        # The set of branches being removed from the layout. The branches need not form a chain (or be related at all):
        # each one is spliced out independently, with its surviving children rewired to its nearest surviving ancestor.
        slide_out_set = set(branches_to_slide_out)

        def nearest_surviving_ancestor(branch: LocalBranchShortName) -> Optional[ManagedBranchName]:
            ancestor = self._state.get_parent(branch)
            while ancestor is not None and ancestor in slide_out_set:
                ancestor = self._state.get_parent(ancestor)
            return ancestor

        def surviving_children(branch: LocalBranchShortName) -> List[ManagedBranchName]:
            return [child for child in (self.children_of(branch) or []) if child not in slide_out_set]

        # "Pivots" are the slid-out branches that have at least one child which is NOT itself being slid out.
        # Those surviving children are the ones that get reattached (and, unless `--no-rebase`, synced) to a new parent.
        # In the classic "slide out a chain b1 -> ... -> bN" case there's exactly one pivot (bN); the interior branches
        # have their only child slid out alongside them, so they contribute no surviving children.
        # Any set of branches may be slid out at once: each pivot's children are reattached to (and, unless `--no-rebase`,
        # rebased/merged onto) that pivot's own nearest surviving ancestor, so multiple independent pivots are fine.
        # `reattachment_by_pivot` records, for each pivot, where its surviving children will be reattached. It's computed
        # once here (before the splice mutates the tree) and reused for the down-fork-point check, the rebase/merge,
        # the worktree preflight, the post-slide-out hook payloads and the user-visible summary.
        pivots: List[ManagedBranchName] = []
        reattachment_by_pivot: Dict[LocalBranchShortName, Reattachment] = {}
        for branch in branches_to_slide_out:
            children = surviving_children(branch)
            if children:
                pivots.append(branch)
                reattachment_by_pivot[branch] = Reattachment(children, nearest_surviving_ancestor(branch))

        if opt_down_fork_point:
            # `--down-fork-point` supplies a single fork point for a single rebase, so it only makes sense when there's
            # exactly one child to sync across all pivots. (`--down-fork-point` also conflicts with `--no-rebase`, rejected in the CLI.)
            children_to_sync = [child for pivot in pivots for child in reattachment_by_pivot[pivot].children]
            if not children_to_sync:
                raise MacheteException("Branch to slide out must have a child branch if option `--down-fork-point` is passed")
            if len(children_to_sync) > 1:
                raise MacheteException("Branch to slide out can't have more than one child branch "
                                       "if option `--down-fork-point` is passed")
            self.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
                fork_point=opt_down_fork_point,
                branch=children_to_sync[0])

        # Where to land if the current branch is one of the branches about to disappear from the layout:
        # its nearest surviving ancestor, or - failing that (it was effectively a root) - its first surviving child.
        current_branch = self._git.get_current_branch_or_none()
        landing_branch: Optional[LocalBranchShortName] = None
        if current_branch is not None and current_branch in slide_out_set:
            reattachment = reattachment_by_pivot.get(current_branch)
            if reattachment is not None:
                landing_branch = reattachment.new_parent or reattachment.children[0]
            else:
                landing_branch = nearest_surviving_ancestor(current_branch)

        # Post-slide-out hook payloads, computed before the splice mutates the tree. The hook fires once per pivot
        # (the branch(es) whose children are reparented); if nothing has surviving children we preserve the historical
        # single firing for the last specified branch (with an empty downstream list).
        hook_invocations: List[HookInvocation]
        if pivots:
            hook_invocations = [
                HookInvocation(reattachment_by_pivot[pivot].new_parent, pivot, reattachment_by_pivot[pivot].children)
                for pivot in pivots]
        else:
            last_branch = branches_to_slide_out[-1]
            hook_invocations = [HookInvocation(nearest_surviving_ancestor(last_branch), last_branch, [])]

        # Preflight: refuse upfront if any of the branches that the rest of slide-out would later need to
        # `git checkout` is already held by another linked worktree. Without this check we'd write the layout
        # file, fire the post-hook, and only THEN bail out at the first `git checkout` - leaving the layout
        # mutated but the rebase never performed (https://github.com/VirtusLab/git-machete/issues/1711).
        # Two sources of forthcoming checkouts:
        #   1. If the user is standing on a slid-out branch, we'll land them on `landing_branch`.
        #   2. If `--no-rebase` wasn't passed, we'll check out each surviving child to rebase/merge it onto its pivot's
        #      new parent, except children whose annotation opts them out of both (mirror the same gate as the rebase loop
        #      below so the preflight stays in lock-step with what actually gets checked out).
        branches_that_will_be_checked_out: List[LocalBranchShortName] = []
        if landing_branch is not None:
            branches_that_will_be_checked_out.append(landing_branch)
        if not opt_no_rebase:
            for reattachment in reattachment_by_pivot.values():
                if reattachment.new_parent is None:
                    continue
                for child in reattachment.children:
                    anno = self._state.get_annotation(child)
                    use_merge = opt_merge or (anno and anno.qualifiers.update_with_merge)
                    use_rebase = not use_merge and (not anno or anno.qualifiers.rebase)
                    if use_merge or use_rebase:
                        branches_that_will_be_checked_out.append(child)
        for branch in branches_that_will_be_checked_out:
            self._git.expect_branch_not_held_by_other_worktree(branch)

        for branch in branches_to_slide_out:
            print_fmt(f"Sliding out <b>{branch}</b>")
            self._state.splice_out(branch)

        for reattachment in reattachment_by_pivot.values():
            flat_children = ", ".join(f"<b>{child}</b>" for child in reattachment.children)
            if reattachment.new_parent is not None:
                print_fmt(f"Reattaching {flat_children} under <b>{reattachment.new_parent}</b>")
            else:
                noun = "branch" if len(reattachment.children) == 1 else "branches"
                print_fmt(f"Reattaching {flat_children} as new root {noun}")

        # Update definition, fire post-hook, and perform the branch update
        self.save_branch_layout_file()
        for hook_invocation in hook_invocations:
            self._run_post_slide_out_hook(
                new_parent=hook_invocation.new_parent,
                slid_out_branch=hook_invocation.slid_out_branch,
                new_children=hook_invocation.new_children)

        # Check out the landing branch if we were on a slid-out branch (and there's somewhere to land);
        # otherwise stay on the current (slid-out) branch.
        if landing_branch is not None:
            print_fmt(f"Checking out <b>{landing_branch}</b>... ", newline=False)
            self._git.checkout_in_current_worktree(landing_branch)
            print_fmt(green_ok())

        # Sync each pivot's surviving children onto that pivot's new parent (unless `--no-rebase`).
        # Pivots whose children became new roots (no surviving ancestor) have nothing to sync onto.
        if not opt_no_rebase:
            for reattachment in reattachment_by_pivot.values():
                new_parent = reattachment.new_parent
                if new_parent is None:
                    continue
                for child in reattachment.children:
                    anno = self._state.get_annotation(child)
                    use_merge = opt_merge or (anno and anno.qualifiers.update_with_merge)
                    use_rebase = not use_merge and (not anno or anno.qualifiers.rebase)
                    if use_merge or use_rebase:
                        print_fmt(f"Checking out <b>{child}</b>... ", newline=False)
                        self._git.checkout_in_current_worktree(child)
                        print_fmt(green_ok())
                    if use_merge:
                        print_fmt(f"Merging <b>{new_parent}</b> into <b>{child}</b>...")
                        self._git.merge(
                            branch=new_parent,
                            into=child,
                            opt_no_edit_merge=opt_no_edit_merge)
                    elif use_rebase:
                        print_fmt(f"Rebasing <b>{child}</b> onto <b>{new_parent}</b>...")
                        child_fork_point = opt_down_fork_point or self.fork_point(child, use_overrides=True)
                        self.rebase(
                            onto=new_parent.full_name(),
                            from_exclusive=child_fork_point,
                            branch=child,
                            opt_no_interactive_rebase=opt_no_interactive_rebase)

        if opt_delete:
            self._delete_branches(branches_to_delete=branches_to_slide_out,
                                  opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=False)

    def slide_out_removed_from_remote(self, *, opt_delete: bool) -> None:
        self._git.expect_no_operation_in_progress()

        slid_out_branches: List[ManagedBranchName] = []
        for branch in self.managed_branches.copy():
            if self._git.is_removed_from_remote(branch) and not self.children_of(branch):
                anno = self._state.get_annotation(branch)
                if anno and not anno.qualifiers.slide_out:
                    print_fmt(f"Skipping <b>{branch}</b> as it's marked as `slide-out=no`")
                else:
                    print_fmt(f"Sliding out <b>{branch}</b>")
                    slid_out_branches.append(branch)

        self._remove_branches_from_layout(slid_out_branches)
        if opt_delete:
            self._delete_branches(slid_out_branches, opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=True)
