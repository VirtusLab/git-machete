from typing import List, Optional

from git_machete.client.base import MacheteClient, PickRoot
from git_machete.exceptions import MacheteException, UnexpectedMacheteException
from git_machete.git_operations import LocalBranchShortName


class GoShowMacheteClient(MacheteClient):
    def parse_direction(
        self,
        param: str,
        *,
        branch: Optional[LocalBranchShortName],
        allow_current: bool,
        pick_if_multiple: bool
    ) -> List[LocalBranchShortName]:
        if param in ("c", "current") and allow_current:
            return [self._git.get_current_branch()]  # throws in case of detached HEAD, as in the spec
        elif param in ("d", "down"):
            if branch is None:
                raise MacheteException("Not currently on any branch")
            return self.get_or_pick_down_branch_for(branch, pick_if_multiple=pick_if_multiple)
        elif param in ("f", "first"):
            # If branch is None (detached HEAD), use first root then get first branch
            if branch is None:
                return [self.first_branch_for(self.first_root_branch())]
            else:
                return [self.first_branch_for(branch)]
        elif param in ("l", "last"):
            # If branch is None (detached HEAD), use last root then get last branch
            if branch is None:
                return [self.last_branch_for(self.last_root_branch())]
            else:
                return [self.last_branch_for(branch)]
        elif param in ("n", "next"):
            if branch is None:
                raise MacheteException("Not currently on any branch")
            return [self.next_branch_for(branch)]
        elif param in ("p", "prev"):
            if branch is None:
                raise MacheteException("Not currently on any branch")
            return [self.prev_branch_for(branch)]
        elif param in ("r", "root"):
            # If branch is None (detached HEAD), use first root
            if branch is None:
                return [self.first_root_branch()]
            else:
                return [self.root_branch_for(branch, if_unmanaged=PickRoot.FIRST)]
        elif param in ("u", "up"):
            if branch is None:
                raise MacheteException("Not currently on any branch")
            return [self.get_or_infer_up_branch_for(branch, prompt_if_inferred_msg=None, prompt_if_inferred_yes_opt_msg=None)]
        else:  # an unknown direction is handled by argparse
            raise UnexpectedMacheteException(f"Invalid direction: `{param}`.")
