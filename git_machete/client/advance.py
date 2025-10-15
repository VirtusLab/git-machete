from git_machete.client.base import MacheteClient, SquashMergeDetection
from git_machete.exceptions import MacheteException
from git_machete.git_operations import GitContext, LocalBranchShortName
from git_machete.utils import bold, flat_map, get_pretty_choices


class AdvanceMacheteClient(MacheteClient):
    def __init__(self, git: GitContext) -> None:
        super().__init__(git)

    def advance(self, *, opt_yes: bool) -> None:
        self._git.expect_no_operation_in_progress()

        branch = self._git.get_current_branch()
        self.expect_in_managed_branches(branch)

        down_branches = self.down_branches_for(branch)
        if not down_branches:
            raise MacheteException(
                f"{bold(branch)} does not have any downstream (child) branches to advance towards")

        def connected_with_green_edge(bd: LocalBranchShortName) -> bool:
            return bool(
                not self._is_merged_to_upstream(bd, opt_squash_merge_detection=SquashMergeDetection.NONE) and
                self._git.is_ancestor_or_equal(branch.full_name(), bd.full_name()) and
                (self._get_overridden_fork_point(bd) or
                 self._git.get_commit_hash_by_revision(branch) == self.fork_point(bd, use_overrides=False)))

        candidate_downstreams = list(filter(connected_with_green_edge, down_branches))
        if not candidate_downstreams:
            raise MacheteException(
                f"No downstream (child) branch of {bold(branch)} is connected to "
                f"{bold(branch)} with a green edge")
        if len(candidate_downstreams) > 1:
            if opt_yes:
                raise MacheteException(
                    f"More than one downstream (child) branch of {bold(branch)} is "
                    f"connected to {bold(branch)} with a green edge and `-y/--yes` option is specified")
            else:
                down_branch = self.pick(
                    candidate_downstreams,
                    f"downstream branch towards which {bold(branch)} is to be fast-forwarded")
                self._git.merge_fast_forward_only(down_branch)
        else:
            down_branch = candidate_downstreams[0]
            ans = self.ask_if(
                f"Fast-forward {bold(branch)} to match {bold(down_branch)}?" + get_pretty_choices('y', 'N'),
                f"Fast-forwarding {bold(branch)} to match {bold(down_branch)}...", opt_yes=opt_yes)
            if ans in ('y', 'yes'):
                self._git.merge_fast_forward_only(down_branch)
            else:
                return

        remote = self._git.get_combined_remote_for_fetching_of_branch(branch)
        anno = self.annotations.get(branch)
        if remote and (not anno or anno.qualifiers.push):
            push_msg = f"\nBranch {bold(branch)} is now fast-forwarded to match {bold(down_branch)}. " \
                f"Push {bold(branch)} to {bold(remote)}?" + get_pretty_choices('y', 'N')
            opt_yes_push_msg = f"\nBranch {bold(branch)} is now fast-forwarded to match {bold(down_branch)}. " \
                f"Pushing {bold(branch)} to {bold(remote)}..."
            ans = self.ask_if(push_msg, opt_yes_push_msg, opt_yes=opt_yes)
            if ans in ('y', 'yes'):
                self._git.push(remote, branch)
                branch_pushed_or_fast_forwarded_msg = f"\nBranch {bold(branch)} is now pushed to {bold(remote)}."
            else:
                branch_pushed_or_fast_forwarded_msg = f"\nBranch {bold(branch)} is now fast-forwarded to match {bold(down_branch)}."
        else:
            branch_pushed_or_fast_forwarded_msg = f"\nBranch {bold(branch)} is now fast-forwarded to match {bold(down_branch)}."

        down_anno = self.annotations.get(down_branch)
        if not down_anno or down_anno.qualifiers.slide_out:
            slide_out_msg = (f"{branch_pushed_or_fast_forwarded_msg} Slide {bold(down_branch)} out "
                             f"of the tree of branch dependencies?{get_pretty_choices('y', 'N')}")
            slide_out_opt_yes_msg = (f"{branch_pushed_or_fast_forwarded_msg} Sliding {bold(down_branch)} out "
                                     "of the tree of branch dependencies...")
            ans = self.ask_if(slide_out_msg, slide_out_opt_yes_msg, opt_yes=opt_yes)
            if ans in ('y', 'yes'):
                dds = self.down_branches_for(LocalBranchShortName.of(down_branch)) or []
                for dd in dds:
                    self._state.up_branch_for[dd] = branch
                self._state.down_branches_for[branch] = flat_map(
                    lambda bd: dds if bd == down_branch else [bd],
                    self.down_branches_for(branch) or [])
                self.save_branch_layout_file()
                self._run_post_slide_out_hook(new_upstream=branch, slid_out_branch=down_branch, new_downstreams=dds)
