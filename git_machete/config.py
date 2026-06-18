"""Typed interface to machete-specific git config values (with defaults)."""

from enum import auto
from typing import Optional

from git_machete.code_hosting import CodeHostingGitConfigKeys
from git_machete.git import Git
from git_machete.utils.exceptions import ParsableEnum


def _override_fork_point_to_key(branch: str) -> str:
    return f'machete.overrideForkPoint.{branch}.to'


def _override_fork_point_while_descendant_of_key(branch: str) -> str:
    # Deprecated; we still read/write for compatibility with older git-machete clients.
    return f'machete.overrideForkPoint.{branch}.whileDescendantOf'


def _traverse_remote_fetch_key(remote: str) -> str:
    return f'machete.traverse.fetch.{remote}'


class TraverseWhenBranchNotCheckedOutInAnyWorktree(ParsableEnum):
    CD_INTO_MAIN_WORKTREE = auto()
    CD_INTO_TEMPORARY_WORKTREE = auto()
    STAY_IN_THE_CURRENT_WORKTREE = auto()  # noqa: F841


class SquashMergeDetection(ParsableEnum):
    NONE = auto()
    SIMPLE = auto()
    EXACT = auto()


class PRDescriptionIntroStyle(ParsableEnum):
    FULL = auto()
    FULL_NO_BRANCHES = auto()
    UP_ONLY = auto()
    UP_ONLY_NO_BRANCHES = auto()
    NONE = auto()


class MacheteConfig:

    _ADVICE_MACHETE_EDITOR_SELECTION = 'advice.macheteEditorSelection'
    _SQUASH_MERGE_DETECTION = 'machete.squashMergeDetection'
    _STATUS_EXTRA_SPACE_BEFORE_BRANCH_NAME = 'machete.status.extraSpaceBeforeBranchName'
    _TRAVERSE_PUSH = 'machete.traverse.push'
    _TRAVERSE_WHEN_BRANCH_NOT_CHECKED_OUT_IN_ANY_WORKTREE = 'machete.traverse.whenBranchNotCheckedOutInAnyWorktree'
    _WORKTREE_USE_TOP_LEVEL_MACHETE_FILE = 'machete.worktree.useTopLevelMacheteFile'

    def __init__(self, git: Optional[Git] = None) -> None:
        # Default-construct `Git` so that early-startup code in `cli.py` can
        # read a config key (e.g. `machete.traverse.push`) without having to
        # build a `Git` instance itself just to feed it here. Clients that
        # already own a `Git` (i.e. `MacheteClient`) keep passing it in to
        # share the underlying caches.
        self._git: Git = git if git is not None else Git()

    def advice_machete_editor_selection(self) -> bool:
        return self._git.get_config_attr_or_none(self._ADVICE_MACHETE_EDITOR_SELECTION) != 'false'

    def core_editor(self) -> Optional[str]:
        return self._git.get_config_attr_or_none("core.editor")

    def squash_merge_detection(self) -> SquashMergeDetection:
        config_value_str = self._git.get_config_attr_or_none(self._SQUASH_MERGE_DETECTION)
        if config_value_str is None:
            return SquashMergeDetection.SIMPLE
        return SquashMergeDetection.from_string(
            config_value_str,
            f"`{self._SQUASH_MERGE_DETECTION}` git config key")

    def status_extra_space_before_branch_name(self) -> bool:
        return self._git.get_boolean_config_attr(
            key=self._STATUS_EXTRA_SPACE_BEFORE_BRANCH_NAME, default_value=False)

    def traverse_fetch_for_remote(self, remote: str) -> bool:
        return self._git.get_boolean_config_attr(
            key=_traverse_remote_fetch_key(remote), default_value=True)

    def traverse_push(self) -> Optional[bool]:
        return self._git.get_boolean_config_attr_or_none(self._TRAVERSE_PUSH)

    def traverse_when_branch_not_checked_out_in_any_worktree(self) -> TraverseWhenBranchNotCheckedOutInAnyWorktree:
        config_value_str = self._git.get_config_attr_or_none(self._TRAVERSE_WHEN_BRANCH_NOT_CHECKED_OUT_IN_ANY_WORKTREE)
        if config_value_str is None:
            return TraverseWhenBranchNotCheckedOutInAnyWorktree.CD_INTO_MAIN_WORKTREE
        return TraverseWhenBranchNotCheckedOutInAnyWorktree.from_string(
            config_value_str,
            f"`{self._TRAVERSE_WHEN_BRANCH_NOT_CHECKED_OUT_IN_ANY_WORKTREE}` git config key")

    def worktree_use_top_level_machete_file(self) -> bool:
        return self._git.get_boolean_config_attr(
            key=self._WORKTREE_USE_TOP_LEVEL_MACHETE_FILE, default_value=True)

    def fork_point_override_to_value(self, branch: str) -> Optional[str]:
        return self._git.get_config_attr_or_none(_override_fork_point_to_key(branch))

    def fork_point_override_while_descendant_of_value(self, branch: str) -> Optional[str]:
        # We still read the now-deprecated whileDescendantOf key for has_any_fork_point_override_config.
        return self._git.get_config_attr_or_none(_override_fork_point_while_descendant_of_key(branch))

    def set_fork_point_override_to(self, branch: str, *, value: str) -> None:
        self._git.set_config_attr(_override_fork_point_to_key(branch), value)

    def set_fork_point_override_while_descendant_of(self, branch: str, *, value: str) -> None:
        # We still set the now-deprecated whileDescendantOf key to maintain compatibility with older git-machete clients.
        self._git.set_config_attr(_override_fork_point_while_descendant_of_key(branch), value)

    def unset_fork_point_override_to(self, branch: str) -> None:
        self._git.unset_config_attr(_override_fork_point_to_key(branch))

    def unset_fork_point_override_while_descendant_of(self, branch: str) -> None:
        # We still unset the now-deprecated whileDescendantOf key.
        self._git.unset_config_attr(_override_fork_point_while_descendant_of_key(branch))

    def code_hosting_domain(self, keys: CodeHostingGitConfigKeys) -> Optional[str]:
        return self._git.get_config_attr_or_none(key=keys.domain)

    def code_hosting_remote(self, keys: CodeHostingGitConfigKeys) -> Optional[str]:
        return self._git.get_config_attr_or_none(key=keys.remote)

    def code_hosting_organization(self, keys: CodeHostingGitConfigKeys) -> Optional[str]:
        return self._git.get_config_attr_or_none(key=keys.organization)

    def code_hosting_repository(self, keys: CodeHostingGitConfigKeys) -> Optional[str]:
        return self._git.get_config_attr_or_none(key=keys.repository)

    def code_hosting_base_remote(self, keys: CodeHostingGitConfigKeys) -> Optional[str]:
        return self._git.get_config_attr_or_none(key=keys.base_remote)

    def code_hosting_base_organization(self, keys: CodeHostingGitConfigKeys) -> Optional[str]:
        return self._git.get_config_attr_or_none(key=keys.base_organization)

    def code_hosting_base_repository(self, keys: CodeHostingGitConfigKeys) -> Optional[str]:
        return self._git.get_config_attr_or_none(key=keys.base_repository)

    def code_hosting_annotate_with_urls(self, keys: CodeHostingGitConfigKeys) -> bool:
        return self._git.get_boolean_config_attr(key=keys.annotate_with_urls, default_value=False)

    def code_hosting_force_description_from_commit_message(self, keys: CodeHostingGitConfigKeys) -> bool:
        return self._git.get_boolean_config_attr(key=keys.force_description_from_commit_message, default_value=False)

    def code_hosting_pr_description_intro_style(self, keys: CodeHostingGitConfigKeys) -> PRDescriptionIntroStyle:
        value = self._git.get_config_attr(keys.pr_description_intro_style, default_value="up-only")
        return PRDescriptionIntroStyle.from_string(
            value=value,
            from_where=f"`{keys.pr_description_intro_style}` git config key")
