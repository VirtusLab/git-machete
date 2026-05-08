import re
from typing import List

from git_machete.client.base import MacheteClient
from git_machete.git import LocalBranchShortName, RemoteBranchShortName
from git_machete.utils.collections import excluding, map_truthy_only


class ListMacheteClient(MacheteClient):

    @property
    def addable_branches(self) -> List[LocalBranchShortName]:
        def strip_remote_name(remote_branch: RemoteBranchShortName) -> LocalBranchShortName:
            return LocalBranchShortName.of(re.sub("^[^/]+/", "", remote_branch))

        remote_counterparts_of_local_branches = map_truthy_only(
            self._git.get_combined_counterpart_for_fetching_of_branch,
            self._git.get_local_branches())
        qualifying_remote_branches: List[RemoteBranchShortName] = \
            excluding(self._git.get_remote_branches(), remote_counterparts_of_local_branches)
        return excluding(self._git.get_local_branches(), self.managed_branches) + [
            strip_remote_name(branch) for branch in qualifying_remote_branches]

    @property
    def unmanaged_branches(self) -> List[LocalBranchShortName]:
        return excluding(self._git.get_local_branches(), self.managed_branches)

    @property
    def childless_managed_branches(self) -> List[LocalBranchShortName]:
        return [b for b in self._state.managed_branches if not self._state.get_children(b)]

    @property
    def branches_with_overridden_fork_point(self) -> List[LocalBranchShortName]:
        return [branch for branch in self._git.get_local_branches() if self.has_any_fork_point_override_config(branch)]

    @property
    def slidable_branches(self) -> List[LocalBranchShortName]:
        # All managed branches can be slid out, including root branches
        return self.managed_branches

    def get_slidable_after(self, branch: LocalBranchShortName) -> List[LocalBranchShortName]:
        if self._state.has_parent(branch):
            children = self.children_of(branch)
            if children and len(children) == 1:
                return children
        return []
