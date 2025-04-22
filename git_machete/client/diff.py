from typing import List, Optional

from git_machete.client.base import MacheteClient
from git_machete.git_operations import LocalBranchShortName


class DiffMacheteClient(MacheteClient):
    def display_diff(self, *, branch: Optional[LocalBranchShortName], opt_stat: bool, extra_git_diff_args: List[str]) -> None:
        diff_branch = branch or self._git.get_current_branch()
        fork_point = self.fork_point(diff_branch, use_overrides=True)

        self._git.display_diff(branch=branch, against=fork_point, opt_stat=opt_stat, extra_git_diff_args=extra_git_diff_args)
