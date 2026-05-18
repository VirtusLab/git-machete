from typing import List, Optional

from git_machete.client.base import MacheteClient
from git_machete.client.state import ManagedBranchName
from git_machete.config import SquashMergeDetection
from git_machete.git import AnyRevision, LocalBranchShortName
from git_machete.utils.exceptions import MacheteException
from git_machete.utils.markup import green_ok, print_fmt


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

        if opt_down_fork_point:
            last_branch_to_slide_out = branches_to_slide_out[-1]
            children_of_the_last_branch_to_slide_out = self.children_of(last_branch_to_slide_out)

            if children_of_the_last_branch_to_slide_out and len(children_of_the_last_branch_to_slide_out) > 1:
                raise MacheteException("Last branch to slide out can't have more than one child branch "
                                       "if option `--down-fork-point` is passed")

            if children_of_the_last_branch_to_slide_out:
                self.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
                    fork_point=opt_down_fork_point,
                    branch=children_of_the_last_branch_to_slide_out[0])
            else:
                raise MacheteException("Last branch to slide out must have a child branch "
                                       "if option `--down-fork-point` is passed")

        # Verify that all "interior" slide-out branches have a single child pointing to the next slide-out
        for bu, bd in zip(branches_to_slide_out[:-1], branches_to_slide_out[1:]):
            children = self.children_of(bu)
            if not children or len(children) == 0:
                raise MacheteException(f"No downstream branch defined for <b>{bu}</b>, cannot slide out")
            elif len(children) > 1:
                flat_children = ", ".join(f"<b>{x}</b>" for x in children)
                raise MacheteException(
                    f"Multiple downstream branches defined for <b>{bu}</b>: {flat_children}; cannot slide out")
            elif children != [bd]:
                raise MacheteException(f"<b>{bd}</b> is not downstream of <b>{bu}</b>, cannot slide out")

        # Read the connections we need for post-hook and checkout logic before mutating state
        new_parent = self._state.get_parent(branches_to_slide_out[0])
        new_children = self._state.get_children(branches_to_slide_out[-1]) or []

        for branch in branches_to_slide_out:
            self._state.splice_out(branch)

        # Update definition, fire post-hook, and perform the branch update
        self.save_branch_layout_file()
        self._run_post_slide_out_hook(
            new_parent=new_parent,
            slid_out_branch=branches_to_slide_out[-1],
            new_children=new_children)

        # Check out new parent if we were on a slid-out branch, but only if there is a parent
        if self._git.get_current_branch_or_none() in branches_to_slide_out:
            if new_parent is not None:
                print_fmt(f"Checking out <b>{new_parent}</b>... ", newline=False)
                self._git.checkout_in_current_worktree(new_parent)
                print_fmt(green_ok())
            elif new_children:
                # If no parent and there are children, check out the first child
                print_fmt(f"Checking out <b>{new_children[0]}</b>... ", newline=False)
                self._git.checkout_in_current_worktree(new_children[0])
                print_fmt(green_ok())
            # Otherwise, stay on the current (slid-out) branch

        # Only perform rebase/merge if there is a new parent
        if not opt_no_rebase and new_parent is not None:
            for child in new_children:
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
