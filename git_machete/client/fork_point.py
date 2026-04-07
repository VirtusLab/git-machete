from git_machete.client.base import MacheteClient
from git_machete.git_operations import AnyRevision, LocalBranchShortName
from git_machete.utils import MacheteException, print_fmt


class ForkPointMacheteClient(MacheteClient):
    def unset_fork_point_override(self, branch: LocalBranchShortName) -> None:
        self._config.unset_fork_point_override_to(branch)
        # We still unset the now-deprecated `whileDescendantOf` key.
        self._config.unset_fork_point_override_while_descendant_of(branch)

    def set_fork_point_override(self, branch: LocalBranchShortName, to_revision: AnyRevision) -> None:  # noqa: KW
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

    def _get_revision_repr(self, revision: AnyRevision) -> str:
        short_hash = self._git.get_short_commit_hash_by_revision_or_none(revision)
        if not short_hash or revision == short_hash:
            return f"commit <b>{revision}</b>"
        if self._git.is_full_hash(revision.full_name()):
            return f"commit <b>{short_hash}</b>"
        return f"<b>{revision}</b> (commit <b>{short_hash}</b>)"
