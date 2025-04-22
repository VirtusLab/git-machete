from typing import List

from git_machete.client.base import MacheteClient
from git_machete.git_operations import LocalBranchShortName


class LogMacheteClient(MacheteClient):
    def display_log(self, branch: LocalBranchShortName, extra_git_log_args: List[str]) -> None:
        fork_point = self.fork_point(branch, use_overrides=True)
        self._git.display_log_between(from_inclusive=branch.full_name(), until_exclusive=fork_point,
                                      extra_git_log_args=extra_git_log_args)
