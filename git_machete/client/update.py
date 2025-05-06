from typing import Optional

from git_machete.client.base import MacheteClient
from git_machete.git_operations import AnyRevision, LocalBranchShortName
from git_machete.utils import get_pretty_choices


class UpdateMacheteClient(MacheteClient):
    def update(
            self, *, opt_merge: bool, opt_no_edit_merge: bool,
            opt_no_interactive_rebase: bool, opt_fork_point: Optional[AnyRevision]) -> None:
        self._git.expect_no_operation_in_progress()
        current_branch = self._git.get_current_branch()
        use_merge = opt_merge or (current_branch in self.annotations and self.annotations[current_branch].qualifiers.update_with_merge)
        if use_merge:
            with_branch = self.get_or_infer_up_branch_for(
                current_branch,
                prompt_if_inferred_msg=("Branch <b>%s</b> not found in the tree of branch dependencies. "
                                        "Merge with the inferred upstream <b>%s</b>?" + get_pretty_choices('y', 'N')),
                prompt_if_inferred_yes_opt_msg=("Branch <b>%s</b> not found in the tree of branch dependencies. "
                                                "Merging with the inferred upstream <b>%s</b>..."))
            self._git.merge(branch=with_branch, into=current_branch, opt_no_edit_merge=opt_no_edit_merge)
        else:
            onto_branch = self.get_or_infer_up_branch_for(
                current_branch,
                prompt_if_inferred_msg=("Branch <b>%s</b> not found in the tree of branch dependencies. "
                                        "Rebase onto the inferred upstream <b>%s</b>?" + get_pretty_choices('y', 'N')),
                prompt_if_inferred_yes_opt_msg=("Branch <b>%s</b> not found in the tree of branch dependencies. "
                                                "Rebasing onto the inferred upstream <b>%s</b>..."))
            rebase_fork_point = opt_fork_point or self.fork_point(current_branch, use_overrides=True)

            self.rebase(
                onto=LocalBranchShortName.of(onto_branch).full_name(),
                from_exclusive=rebase_fork_point,
                branch=current_branch,
                opt_no_interactive_rebase=opt_no_interactive_rebase)
