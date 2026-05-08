from typing import Optional

from git_machete.client.base import MacheteClient
from git_machete.git import AnyRevision


class ReapplyMacheteClient(MacheteClient):
    def reapply(self, *, opt_fork_point: Optional[AnyRevision], opt_no_interactive_rebase: bool) -> None:
        current_branch = self._git.get_current_branch()
        if opt_fork_point is not None:
            self.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
                fork_point=opt_fork_point, branch=current_branch)
        reapply_fork_point = opt_fork_point or self.fork_point(branch=current_branch, use_overrides=True)
        self.rebase(
            onto=reapply_fork_point,
            from_exclusive=reapply_fork_point,
            branch=current_branch,
            opt_no_interactive_rebase=opt_no_interactive_rebase)
