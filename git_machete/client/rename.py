from git_machete.client.base import MacheteClient
from git_machete.git_operations import (LocalBranchShortName,
                                        RemoteBranchShortName)
from git_machete.utils import MacheteException, print_fmt


class RenameMacheteClient(MacheteClient):

    def rename(self,
               *,
               branch: LocalBranchShortName,
               new_name: LocalBranchShortName,
               opt_repoint_tracking: bool) -> None:
        self.expect_in_managed_branches(branch)
        if new_name == branch:
            raise MacheteException(f"Branch is already named <b>{branch}</b>")
        if new_name in self._git.get_local_branches():
            raise MacheteException(f"Branch <b>{new_name}</b> already exists")

        # git branch -m automatically moves branch.*.remote and branch.*.merge configs,
        # so after rename the new branch keeps tracking the same remote branch as before.
        self._git.rename_local_branch(old_name=branch, new_name=new_name)

        self._state.rename_branch(old_name=branch, new_name=new_name)
        self.save_branch_layout_file()

        if opt_repoint_tracking:
            # After git branch -m the tracking config is moved but still points to the old remote branch name
            # (e.g. origin/old-name). With --repoint-tracking we try to repoint to origin/<new-name> instead.
            remote = self._git.get_strict_remote_for_fetching_of_branch(new_name)
            if remote is not None:
                new_remote_branch = RemoteBranchShortName.of(f"{remote}/{new_name}")
                if new_remote_branch in self._git.get_remote_branches():
                    self._git.set_upstream_of(branch=new_name, remote_branch=new_remote_branch)
                    print_fmt(f"Repointed tracking to <b>{new_remote_branch}</b>")
                else:
                    self._git.unset_upstream_of(new_name)
                    print_fmt(f"Unset tracking (remote branch <b>{new_remote_branch}</b> does not exist)")

        print_fmt(f"Renamed branch <b>{branch}</b> to <b>{new_name}</b>")
