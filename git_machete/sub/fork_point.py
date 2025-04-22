from git_machete import git_config_keys

from git_machete.client import MacheteClient
from git_machete.git_operations import LocalBranchShortName, AnyRevision

import itertools
from typing import List, Optional

from git_machete.annotation import Annotation, Qualifiers
from git_machete.client import (MacheteClient, PickRoot, SquashMergeDetection,
                                TraverseReturnTo, TraverseStartFrom)
from git_machete.code_hosting import PullRequest
from git_machete.exceptions import (InteractionStopped, MacheteException,
                                    UnexpectedMacheteException)
from git_machete.git_operations import LocalBranchShortName, SyncToRemoteStatus
from git_machete.github import GitHubClient
from git_machete.gitlab import GitLabClient
from git_machete.sub.with_code_hosting import MacheteClientWithCodeHosting
from git_machete.utils import (bold, flat_map, fmt, get_pretty_choices,
                               get_right_arrow)


class ForkPointMacheteClient(MacheteClient):
    def unset_fork_point_override(self, branch: LocalBranchShortName) -> None:
        self._git.unset_config_attr(git_config_keys.override_fork_point_to(branch))
        # Note that we still unset the now-deprecated `whileDescendantOf` key.
        self._git.unset_config_attr(git_config_keys.override_fork_point_while_descendant_of(branch))

    def set_fork_point_override(self, branch: LocalBranchShortName, to_revision: AnyRevision) -> None:
        to_hash = self._git.get_commit_hash_by_revision(to_revision)
        if not to_hash:
            raise MacheteException(f"Cannot find revision {bold(to_revision)}")
        if not self._git.is_ancestor_or_equal(to_hash.full_name(), branch.full_name()):
            raise MacheteException(
                f"Cannot override fork point: {bold(self._git.get_revision_repr(to_revision))} is not an ancestor of {bold(branch)}")

        to_key = git_config_keys.override_fork_point_to(branch)
        self._git.set_config_attr(to_key, to_hash)

        # Let's still set the now-deprecated `whileDescendantOf` key to maintain compatibility with older git-machete clients
        # that still require that key for an override to apply.
        while_descendant_of_key = git_config_keys.override_fork_point_while_descendant_of(branch)
        self._git.set_config_attr(while_descendant_of_key, to_hash)

        print(fmt(f"Fork point for <b>{branch}</b> is overridden to {self._git.get_revision_repr(to_revision)}.\n",
                  f"This applies as long as <b>{branch}</b> is a descendant of commit <b>{to_hash}</b>.\n\n"
                  f"This information is stored under `{to_key}` git config key.\n\n"
                  f"To unset this override, use:\n  `git machete fork-point --unset-override {branch}`"))
