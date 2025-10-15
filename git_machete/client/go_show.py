from typing import List

from git_machete.client.base import MacheteClient, PickRoot
from git_machete.exceptions import UnexpectedMacheteException
from git_machete.git_operations import LocalBranchShortName


class GoShowMacheteClient(MacheteClient):
    def parse_direction(
        self,
        param: str,
        *,
        branch: LocalBranchShortName,
        allow_current: bool,
        pick_if_multiple: bool
    ) -> List[LocalBranchShortName]:
        if param in ("c", "current") and allow_current:
            return [self._git.get_current_branch()]  # throws in case of detached HEAD, as in the spec
        elif param in ("d", "down"):
            return self.get_or_pick_down_branch_for(branch, pick_if_multiple=pick_if_multiple)
        elif param in ("f", "first"):
            return [self.first_branch_for(branch)]
        elif param in ("l", "last"):
            return [self.last_branch_for(branch)]
        elif param in ("n", "next"):
            return [self.next_branch_for(branch)]
        elif param in ("p", "prev"):
            return [self.prev_branch_for(branch)]
        elif param in ("r", "root"):
            return [self.root_branch_for(branch, if_unmanaged=PickRoot.FIRST)]
        elif param in ("u", "up"):
            return [self.get_or_infer_up_branch_for(branch, prompt_if_inferred_msg=None, prompt_if_inferred_yes_opt_msg=None)]
        else:  # an unknown direction is handled by argparse
            raise UnexpectedMacheteException(f"Invalid direction: `{param}`.")
