from typing import List, Optional

from .git_operations import AnyRevision, LocalBranchShortName


class CommandLineOptions:

    def __init__(self) -> None:
        self.opt_all: bool = False
        self.opt_as_first_child: bool = False
        self.opt_as_root: bool = False
        self.opt_branch: Optional[LocalBranchShortName] = None
        self.opt_by: Optional[str] = None
        self.opt_checked_out_since: Optional[str] = None
        self.opt_delete: bool = False
        self.opt_down_fork_point: Optional[AnyRevision] = None
        self.opt_draft: bool = False
        self.opt_fetch: bool = False
        self.opt_fork_point: Optional[AnyRevision] = None
        self.opt_ignore_if_missing: bool = False
        self.opt_inferred: bool = False
        self.opt_list_commits: bool = False
        self.opt_list_commits_with_hashes: bool = False
        self.opt_mine: bool = False
        self.opt_merge: bool = False
        self.opt_n: bool = False
        self.opt_no_edit_merge: bool = False
        self.opt_no_interactive_rebase: bool = False
        self.opt_onto: Optional[LocalBranchShortName] = None
        self.opt_override_to: Optional[str] = None
        self.opt_override_to_inferred: bool = False
        self.opt_override_to_parent: bool = False
        self.opt_push_tracked: bool = True
        self.opt_push_untracked: bool = True
        self.opt_related: bool = False
        self.opt_removed_from_remote: bool = False
        self.opt_return_to: str = "stay"
        self.opt_roots: List[LocalBranchShortName] = list()
        self.opt_squash_merge_detection_origin: Optional[str] = None
        self.opt_squash_merge_detection_string: str = "simple"
        self.opt_start_from: str = "here"
        self.opt_stat: bool = False
        self.opt_sync_github_prs: bool = False
        self.opt_sync_gitlab_mrs: bool = False
        self.opt_title: Optional[str] = None
        self.opt_unset_override: bool = False
        self.opt_update_related_descriptions: bool = False
        self.opt_with_urls: bool = False
        self.opt_yes: bool = False

    def __repr__(self) -> str:  # pragma: no cover; debug only
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"{self.__class__.__module__}.{self.__class__.__qualname__}({attrs})"
