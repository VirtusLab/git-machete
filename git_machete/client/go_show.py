from typing import List, Optional, Sequence

from git_machete.client.base import MacheteClient, PickRoot
from git_machete.client.state import ManagedBranchName
from git_machete.git import LocalBranchShortName
from git_machete.utils.exceptions import (MacheteException,
                                          UnexpectedMacheteException)
from git_machete.utils.markup import green_ok, print_fmt


class GoShowMacheteClient(MacheteClient):
    def first_branch_for(self, branch: LocalBranchShortName) -> LocalBranchShortName:
        root = self.root_branch_for(branch, if_unmanaged=PickRoot.FIRST)
        root_children = self.children_of(root)
        return root_children[0] if root_children else root

    def last_branch_for(self, branch: LocalBranchShortName) -> LocalBranchShortName:
        destination = self.root_branch_for(branch, if_unmanaged=PickRoot.LAST)
        while True:
            children = self._state.get_children(destination)
            if not children:
                break
            destination = children[-1]
        return destination

    def next_branch_for(self, branch: LocalBranchShortName) -> LocalBranchShortName:
        managed = self.expect_in_managed_branches(branch)
        index: int = self.managed_branches.index(managed) + 1
        if index == len(self.managed_branches):
            raise MacheteException(f"Branch <b>{branch}</b> has no successor")
        return self.managed_branches[index]

    def prev_branch_for(self, branch: LocalBranchShortName) -> LocalBranchShortName:
        managed = self.expect_in_managed_branches(branch)
        index: int = self.managed_branches.index(managed) - 1
        if index == -1:
            raise MacheteException(f"Branch <b>{branch}</b> has no predecessor")
        return self.managed_branches[index]

    def first_root_branch(self) -> LocalBranchShortName:
        roots = self._state.roots
        if roots:
            return roots[0]
        else:
            self._raise_no_branches_error()  # pragma: no cover; this case should never happen

    def last_root_branch(self) -> LocalBranchShortName:
        roots = self._state.roots
        if roots:
            return roots[-1]
        else:
            self._raise_no_branches_error()  # pragma: no cover; this case should never happen

    def get_or_pick_child_of(self, branch: LocalBranchShortName, *, pick_if_multiple: bool) -> List[ManagedBranchName]:
        self.expect_in_managed_branches(branch)
        children = self.children_of(branch)
        if not children:
            raise MacheteException(f"Branch <b>{branch}</b> has no downstream branch")
        elif len(children) == 1:
            return [children[0]]
        elif pick_if_multiple:
            return [self.pick(children, "downstream branch")]
        else:
            return children

    def go(self, direction: str) -> None:
        self._git.expect_no_operation_in_progress()
        current_branch = self._git.get_current_branch_or_none()
        # with pick_if_multiple=True, the returned list will have exactly one element
        dest = self._parse_direction(direction, branch=current_branch, allow_current=False, pick_if_multiple=True)[0]
        if dest != current_branch:
            print_fmt(f"Checking out <b>{dest}</b>... ", newline=False)
            self._git.checkout(dest)
            print_fmt(green_ok())

    def show(self, direction: str, *, opt_branch: Optional[LocalBranchShortName]) -> None:
        branch = opt_branch or self._git.get_current_branch_or_none()
        print('\n'.join(self._parse_direction(direction, branch=branch, allow_current=True, pick_if_multiple=False)))

    def _parse_direction(
        self,
        param: str,
        *,
        branch: Optional[LocalBranchShortName],
        allow_current: bool,
        pick_if_multiple: bool
    ) -> Sequence[LocalBranchShortName]:
        if param in ("c", "current") and allow_current:
            return [self._git.get_current_branch()]  # throws in case of detached HEAD, as in the spec
        elif param in ("d", "down"):
            if branch is None:
                raise MacheteException("Not currently on any branch")
            return self.get_or_pick_child_of(branch, pick_if_multiple=pick_if_multiple)
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
            return [self.get_or_infer_parent_of(branch, prompt_if_inferred_msg=None, prompt_if_inferred_yes_opt_msg=None)]
        else:  # an unknown direction is already rejected by the parser
            raise UnexpectedMacheteException(f"Invalid direction: `{param}`.")
