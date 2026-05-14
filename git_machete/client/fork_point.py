import sys
from typing import Optional

from git_machete.client.base import MacheteClient
from git_machete.git import AnyRevision, LocalBranchShortName
from git_machete.utils.exceptions import MacheteException
from git_machete.utils.markup import print_fmt, warn


class ForkPointMacheteClient(MacheteClient):
    def print_fork_point(self, *, opt_branch: Optional[LocalBranchShortName],
                         use_overrides: bool, explain: bool) -> None:
        branch = self._resolve_branch(opt_branch=opt_branch)
        if explain:
            fork_point, pairs = self.fork_point_and_inferring_branch_pairs(branch=branch, use_overrides=use_overrides)
            print(fork_point)
            if pairs:
                # Same wording as the `-> fork point ???` annotation rendered by `status -l` on yellow edges.
                formatted = " and ".join(sorted(f"<b>{lb_or_rb}</b>" for _, lb_or_rb in pairs))
                print_fmt(f"this commit seems to be a part of the unique history of {formatted}", file=sys.stderr)
            else:
                # Empty `pairs` is only reachable when an override short-circuits the inference;
                # otherwise `fork_point_and_inferring_branch_pairs` would have raised `MacheteException`.
                print_fmt(f"fork point of <b>{branch}</b> is overridden", file=sys.stderr)
        else:
            print(self.fork_point(branch=branch, use_overrides=use_overrides))

    def unset_fork_point_override(self, *, opt_branch: Optional[LocalBranchShortName]) -> None:
        branch = self._resolve_branch(opt_branch=opt_branch)
        self._config.unset_fork_point_override_to(branch)
        # We still unset the now-deprecated `whileDescendantOf` key.
        self._config.unset_fork_point_override_while_descendant_of(branch)

    def override_fork_point_to(self, *, opt_branch: Optional[LocalBranchShortName],
                               to_revision: AnyRevision, deprecated_flag_label: str,
                               revision_label: str) -> None:
        """Override the fork point of the chosen branch to `to_revision`,
        then emit a deprecation warning nudging the user toward the
        `update --fork-point=...` workflow.

        `deprecated_flag_label` is the human-readable name of the
        `fork-point` flag the user invoked, e.g. `"--override-to=..."`;
        `revision_label` is the noun phrase used in the warning to
        describe `to_revision` (e.g. `"selected commit"` or
        `"inferred commit"`).
        """
        branch = self._resolve_branch(opt_branch=opt_branch)
        self._set_fork_point_override(branch=branch, to_revision=to_revision)
        self._warn_on_deprecated_override(
            branch=branch, flag=deprecated_flag_label,
            revision=to_revision, revision_label=revision_label)

    def override_fork_point_to_inferred(self, *, opt_branch: Optional[LocalBranchShortName]) -> None:
        branch = self._resolve_branch(opt_branch=opt_branch)
        inferred = self.fork_point(branch=branch, use_overrides=False)
        self._set_fork_point_override(branch=branch, to_revision=inferred)
        self._warn_on_deprecated_override(
            branch=branch, flag="--override-to-inferred",
            revision=inferred, revision_label="inferred commit")

    def override_fork_point_to_parent(self, *, opt_branch: Optional[LocalBranchShortName]) -> None:
        branch = self._resolve_branch(opt_branch=opt_branch)
        parent = self.parent_of(branch)
        if parent is None:
            raise MacheteException(
                f"Branch <b>{branch}</b> does not have upstream (parent) branch")
        self._set_fork_point_override(branch=branch, to_revision=parent)

    def _resolve_branch(self, *, opt_branch: Optional[LocalBranchShortName]) -> LocalBranchShortName:
        branch = opt_branch or self._git.get_current_branch()
        self.expect_in_local_branches(branch)
        return branch

    def _set_fork_point_override(self, *, branch: LocalBranchShortName, to_revision: AnyRevision) -> None:
        to_hash = self._git.get_commit_hash_by_revision(to_revision)
        if not to_hash:
            raise MacheteException(f"Cannot find revision <b>{to_revision}</b>")
        if not self._git.is_ancestor_or_equal(to_hash.full_name(), branch.full_name()):
            raise MacheteException(
                f"Cannot override fork point: {self._get_revision_repr(to_revision)} is not an ancestor of <b>{branch}</b>")

        self._config.set_fork_point_override_to(branch, value=to_hash)
        # We still set the now-deprecated `whileDescendantOf` key to maintain compatibility with older git-machete clients.
        self._config.set_fork_point_override_while_descendant_of(branch, value=to_hash)

        short_hash = self._git.get_short_commit_hash_by_revision(to_hash)
        print_fmt(f"Fork point for <b>{branch}</b> is overridden to {self._get_revision_repr(to_revision)}.\n"
                  f"This applies as long as <b>{branch}</b> points to commit <b>{short_hash}</b> or its descendant.")

    def _warn_on_deprecated_override(
            self, *, branch: LocalBranchShortName, flag: str,
            revision: AnyRevision, revision_label: str) -> None:
        parent = self.parent_of(branch)
        # It's unlikely that anyone overrides fork point for a branch that doesn't have a parent,
        # also it's unclear what the suggested action should even be - so we just skip the case.
        if parent is None:
            return
        short_hash = self._git.get_short_commit_hash_by_revision_or_none(revision) or ''
        print()
        warn(
            f"`git machete fork-point {flag}` may lead to a confusing user experience and is deprecated.\n\n"
            f"If the commits between <b>{parent}</b> (parent of <b>{branch}</b>) "
            f"and {revision_label} <b>{short_hash}</b> "
            f"do NOT belong to <b>{branch}</b>, consider using:\n"
            f"    `git checkout {branch}`\n"
            f"    `git machete update --fork-point=\"{revision}\"`\n\n"
            "Otherwise, if you're okay with treating these commits "
            f"as a part of <b>{branch}</b>'s unique history, use instead:\n"
            f"    `git machete fork-point {branch} --override-to-parent`"
        )

    def _get_revision_repr(self, revision: AnyRevision) -> str:
        short_hash = self._git.get_short_commit_hash_by_revision_or_none(revision)
        if not short_hash or revision == short_hash:
            return f"commit <b>{revision}</b>"
        if self._git.is_full_hash(revision.full_name()):
            return f"commit <b>{short_hash}</b>"
        return f"<b>{revision}</b> (commit <b>{short_hash}</b>)"
