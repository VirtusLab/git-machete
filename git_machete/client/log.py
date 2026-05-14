from typing import List, Optional

from git_machete.client.base import MacheteClient
from git_machete.git import LocalBranchShortName


class LogMacheteClient(MacheteClient):
    def display_log(self, *, opt_branch: Optional[LocalBranchShortName], extra_git_log_args: List[str]) -> None:
        branch = opt_branch or self._git.get_current_branch()
        fork_point = self.fork_point(branch, use_overrides=True)
        self._git.display_log_between(from_inclusive=branch.full_name(), until_exclusive=fork_point,
                                      extra_git_log_args=extra_git_log_args)
