from typing import List, Optional

from git_machete.client.base import MacheteClient, SquashMergeDetection
from git_machete.exceptions import MacheteException
from git_machete.git_operations import AnyRevision, LocalBranchShortName
from git_machete.utils import bold, fmt


class SlideOutMacheteClient(MacheteClient):
    def slide_out(self,
                  *,
                  branches_to_slide_out: List[LocalBranchShortName],
                  opt_delete: bool,
                  opt_down_fork_point: Optional[AnyRevision],
                  opt_merge: bool,
                  opt_no_interactive_rebase: bool,
                  opt_no_edit_merge: bool
                  ) -> None:
        self._git.expect_no_operation_in_progress()

        # Verify that all branches exist, are managed, have an upstream and are NOT annotated with slide-out=no qualifier.
        for branch in branches_to_slide_out:
            self.expect_in_managed_branches(branch)
            anno = self.annotations.get(branch)
            if anno and not anno.qualifiers.slide_out:
                raise MacheteException(f"Branch {bold(branch)} is annotated with `slide-out=no` qualifier, aborting.\n"
                                       f"Remove the qualifier using `git machete anno` or edit branch layout file directly.")
            new_upstream = self.up_branch_for(branch)
            if not new_upstream:
                raise MacheteException(f"No upstream branch defined for {bold(branch)}, cannot slide out")

        if opt_down_fork_point:
            last_branch_to_slide_out = branches_to_slide_out[-1]
            children_of_the_last_branch_to_slide_out = self.down_branches_for(last_branch_to_slide_out)

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

        # Verify that all "interior" slide-out branches have a single downstream pointing to the next slide-out
        for bu, bd in zip(branches_to_slide_out[:-1], branches_to_slide_out[1:]):
            dbs = self.down_branches_for(bu)
            if not dbs or len(dbs) == 0:
                raise MacheteException(f"No downstream branch defined for {bold(bu)}, cannot slide out")
            elif len(dbs) > 1:
                flat_dbs = ", ".join(bold(x) for x in dbs)
                raise MacheteException(
                    f"Multiple downstream branches defined for {bold(bu)}: {flat_dbs}; cannot slide out")
            elif dbs != [bd]:
                raise MacheteException(f"{bold(bd)} is not downstream of {bold(bu)}, cannot slide out")

        # Get new branches
        new_upstream = self._state.up_branch_for[branches_to_slide_out[0]]
        new_downstreams = self.down_branches_for(branches_to_slide_out[-1]) or []

        # Remove the slid-out branches from the tree
        for branch in branches_to_slide_out:
            del self._state.up_branch_for[branch]
            if branch in self._state.down_branches_for:
                del self._state.down_branches_for[branch]
            self.managed_branches.remove(branch)

        assert new_upstream is not None
        self._state.down_branches_for[new_upstream] = [
            branch for branch in (self.down_branches_for(new_upstream) or [])
            if branch != branches_to_slide_out[0]]

        # Reconnect the downstreams to the new upstream in the tree
        for new_downstream in new_downstreams:
            self._state.up_branch_for[new_downstream] = new_upstream
            self._state.down_branches_for[new_upstream] += [new_downstream]

        # Update definition, fire post-hook, and perform the branch update
        self.save_branch_layout_file()
        self._run_post_slide_out_hook(
            new_upstream=new_upstream,
            slid_out_branch=branches_to_slide_out[-1],
            new_downstreams=new_downstreams)

        if self._git.get_current_branch_or_none() in branches_to_slide_out:
            self._git.checkout(new_upstream)

        for new_downstream in new_downstreams:
            anno = self.annotations.get(new_downstream)
            use_merge = opt_merge or (anno and anno.qualifiers.update_with_merge)
            use_rebase = not use_merge and (not anno or anno.qualifiers.rebase)
            if use_merge or use_rebase:
                self._git.checkout(new_downstream)
            if use_merge:
                print(f"Merging {bold(new_upstream)} into {bold(new_downstream)}...")
                self._git.merge(
                    branch=new_upstream,
                    into=new_downstream,
                    opt_no_edit_merge=opt_no_edit_merge)
            elif use_rebase:
                print(f"Rebasing {bold(new_downstream)} onto {bold(new_upstream)}...")
                down_fork_point = opt_down_fork_point or self.fork_point(new_downstream, use_overrides=True)
                self.rebase(
                    onto=new_upstream.full_name(),
                    from_exclusive=down_fork_point,
                    branch=new_downstream,
                    opt_no_interactive_rebase=opt_no_interactive_rebase)

        if opt_delete:
            self._delete_branches(branches_to_delete=branches_to_slide_out,
                                  opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=False)

    def slide_out_removed_from_remote(self, *, opt_delete: bool) -> None:
        self._git.expect_no_operation_in_progress()

        slid_out_branches: List[LocalBranchShortName] = []
        for branch in self.managed_branches.copy():
            if self._git.is_removed_from_remote(branch) and not self.down_branches_for(branch):
                anno = self.annotations.get(branch)
                if anno and not anno.qualifiers.slide_out:
                    print(fmt(f"Skipping <b>{branch}</b> as it's marked as `slide-out=no`"))
                else:
                    print(fmt(f"Sliding out <b>{branch}</b>"))
                    slid_out_branches.append(branch)

        self._remove_branches_from_layout(slid_out_branches)
        if opt_delete:
            self._delete_branches(slid_out_branches, opt_squash_merge_detection=SquashMergeDetection.NONE, opt_yes=True)
