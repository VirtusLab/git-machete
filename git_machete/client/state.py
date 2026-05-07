from typing import Dict, List, Optional

from git_machete.annotation import Annotation
from git_machete.git_operations import LocalBranchShortName
from git_machete.utils.collections_utils import flat_map


class MacheteState:
    """
    In-memory representation of the branch layout (.git/machete file).

    The five internal fields are kept mutually consistent:
      - `_managed_branches`: DFS-ordered flat list of every managed branch.
      - `_roots`: root branches (those with no parent in the layout).
      - `_parent_of`: child → parent mapping for every non-root branch.
      - `_children_of`: parent → ordered list of children.
      - `_annotations`: per-branch annotation metadata.

    All five fields are private.  Callers may read them freely through the
    properties and accessor methods below, but every structural change must go
    through the mutation methods so that the invariants above are never
    violated.
    """

    def __init__(self) -> None:
        self._managed_branches: List[LocalBranchShortName] = []
        self._roots: List[LocalBranchShortName] = []
        self._parent_of: Dict[LocalBranchShortName, LocalBranchShortName] = {}
        self._children_of: Dict[LocalBranchShortName, List[LocalBranchShortName]] = {}
        self._annotations: Dict[LocalBranchShortName, Annotation] = {}

    # ── Read-only accessors ─────────────────────────────────────────────────

    @property
    def managed_branches(self) -> List[LocalBranchShortName]:
        """DFS-ordered flat list of all managed branches. Returns a copy."""
        return list(self._managed_branches)

    @property
    def roots(self) -> List[LocalBranchShortName]:
        """Root branches (those with no parent). Returns a copy."""
        return list(self._roots)

    def is_managed(self, branch: LocalBranchShortName) -> bool:
        return branch in self._managed_branches

    def get_parent(self, branch: LocalBranchShortName) -> Optional[LocalBranchShortName]:
        return self._parent_of.get(branch)

    def has_parent(self, branch: LocalBranchShortName) -> bool:
        return branch in self._parent_of

    def get_children(self, branch: LocalBranchShortName) -> Optional[List[LocalBranchShortName]]:
        """Returns a copy of the children list, or None if branch has no children entry."""
        children = self._children_of.get(branch)
        return list(children) if children is not None else None

    def get_annotation(self, branch: LocalBranchShortName) -> Optional[Annotation]:
        return self._annotations.get(branch)

    def has_annotation(self, branch: LocalBranchShortName) -> bool:
        return branch in self._annotations

    # ── Adding branches ─────────────────────────────────────────────────────

    def add_branch(
        self,
        branch: LocalBranchShortName,
        *,
        parent: Optional[LocalBranchShortName],
        annotation: Optional[Annotation],
    ) -> None:
        """Add a branch to the layout, wiring it under parent (or as a root if parent is None)."""
        self._managed_branches.append(branch)
        if parent is not None:
            self._parent_of[branch] = parent
            if parent in self._children_of:
                self._children_of[parent].append(branch)
            else:
                self._children_of[parent] = [branch]
        else:
            self._roots.append(branch)
        if annotation is not None:
            self._annotations[branch] = annotation

    def bootstrap_as_single_managed(self, branch: LocalBranchShortName) -> None:
        """Bootstrap an empty layout with branch as the sole root and managed branch."""
        self._roots = [branch]
        self._managed_branches = [branch]

    def add_as_root(self, branch: LocalBranchShortName) -> None:
        """Add branch as a new root, appending it to managed_branches."""
        self._roots.append(branch)
        self._managed_branches.append(branch)

    def add_as_child(
        self,
        *,
        branch: LocalBranchShortName,
        parent: LocalBranchShortName,
        as_first_child: bool,
    ) -> None:
        """Add branch as a child of parent, appending it to managed_branches."""
        self._parent_of[branch] = parent
        existing = self._children_of.get(parent, [])
        self._children_of[parent] = ([branch] + existing) if as_first_child else (existing + [branch])
        self._managed_branches.append(branch)

    # ── Removing / rewiring branches ────────────────────────────────────────

    def splice_out(self, branch: LocalBranchShortName) -> None:
        """Remove a branch from the tree, wiring its children to its parent.

        If branch is a root, its children become new roots in its place.
        Removes branch from managed_branches and deletes its annotation.
        """
        children = list(self._children_of.get(branch) or [])
        parent = self._parent_of.get(branch)

        if parent is not None:
            for child in children:
                self._parent_of[child] = parent
            self._children_of[parent] = flat_map(
                lambda b: children if b == branch else [b],
                self._children_of.get(parent) or [],
            )
        else:
            for child in children:
                self._parent_of.pop(child, None)
            root_index = self._roots.index(branch)
            self._roots = self._roots[:root_index] + children + self._roots[root_index + 1:]

        self._parent_of.pop(branch, None)
        self._children_of.pop(branch, None)
        self._annotations.pop(branch, None)
        self._managed_branches.remove(branch)

    def remove_leaf(self, branch: LocalBranchShortName) -> None:
        """Remove a childless branch from the layout.

        Detaches it from its parent (or roots), removes it from managed_branches,
        and deletes its annotation.
        """
        self._managed_branches.remove(branch)
        self._annotations.pop(branch, None)
        if branch in self._parent_of:
            parent = self._parent_of.pop(branch)
            self._children_of[parent] = [
                b for b in (self._children_of.get(parent) or []) if b != branch
            ]
        else:
            self._roots.remove(branch)

    # ── Tree reset + incremental wiring (used when rebuilding from scratch) ─

    def reset_tree(self, initial_roots: List[LocalBranchShortName]) -> None:
        """Reset all tree structure to rebuild from scratch.

        Clears managed_branches, parent/children mappings, and sets roots to initial_roots.
        Annotations are preserved so they can be selectively updated afterwards.
        """
        self._roots = list(initial_roots)
        self._parent_of = {}
        self._children_of = {}
        self._managed_branches = []

    def wire_as_child(
        self, *, parent: LocalBranchShortName, child: LocalBranchShortName
    ) -> None:
        """Wire child under parent without touching managed_branches.

        Intended for incremental tree building when managed_branches will be
        set in bulk afterwards via set_managed().
        """
        self._parent_of[child] = parent
        if parent in self._children_of:
            self._children_of[parent].append(child)
        else:
            self._children_of[parent] = [child]

    def wire_as_root(self, branch: LocalBranchShortName) -> None:
        """Append branch to roots without touching managed_branches.

        Intended for incremental tree building when managed_branches will be
        set in bulk afterwards via set_managed().
        """
        self._roots.append(branch)

    def detach_leaf(self, branch: LocalBranchShortName) -> None:
        """Detach a childless branch from the tree without touching managed_branches.

        Intended for pruning during tree building before managed_branches is set.
        """
        parent = self._parent_of.pop(branch)
        self._children_of[parent] = [
            b for b in self._children_of.get(parent, []) if b != branch
        ]

    def set_managed(self, branches: List[LocalBranchShortName]) -> None:
        """Overwrite managed_branches with the given DFS-ordered list."""
        self._managed_branches = list(branches)

    # ── Rename ──────────────────────────────────────────────────────────────

    def rename_branch(
        self,
        *,
        old_name: LocalBranchShortName,
        new_name: LocalBranchShortName,
    ) -> None:
        """Rename a branch across all state fields."""
        idx = self._managed_branches.index(old_name)
        self._managed_branches[idx] = new_name

        if old_name in self._roots:
            ridx = self._roots.index(old_name)
            self._roots[ridx] = new_name

        if old_name in self._parent_of:
            parent = self._parent_of.pop(old_name)
            self._parent_of[new_name] = parent

        for k in list(self._parent_of):
            if self._parent_of[k] == old_name:
                self._parent_of[k] = new_name

        if old_name in self._children_of:
            children = self._children_of.pop(old_name)
            self._children_of[new_name] = children

        for children_list in self._children_of.values():
            if old_name in children_list:
                children_list[children_list.index(old_name)] = new_name

        if old_name in self._annotations:
            self._annotations[new_name] = self._annotations.pop(old_name)

    # ── Annotations ─────────────────────────────────────────────────────────

    def set_annotation(self, branch: LocalBranchShortName, annotation: Annotation) -> None:
        self._annotations[branch] = annotation

    def delete_annotation(self, branch: LocalBranchShortName) -> None:
        self._annotations.pop(branch, None)
