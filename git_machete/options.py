from typing import Optional, List

from git_machete.exceptions import MacheteException
from git_machete.git_operations import AnyBranchName, AnyRevision, LocalBranchShortName


class CommandLineOptions:

    def __init__(self) -> None:
        self.opt_as_root: bool = False
        self.opt_branch: Optional[AnyBranchName] = None
        self.opt_checked_out_since: Optional[str] = None
        self.opt_color: str = "auto"
        self.opt_debug: bool = False
        self.opt_delete: bool = False
        self.opt_down_fork_point: Optional[AnyRevision] = None
        self.opt_draft: bool = False
        self.opt_fetch: bool = False
        self.opt_fork_point: Optional[AnyRevision] = None
        self.opt_inferred: bool = False
        self.opt_list_commits: bool = False
        self.opt_list_commits_with_hashes: bool = False
        self.opt_merge: bool = False
        self.opt_n: bool = False
        self.opt_no_detect_squash_merges: bool = False
        self.opt_no_edit_merge: bool = False
        self.opt_no_interactive_rebase: bool = False
        self.opt_onto: Optional[LocalBranchShortName] = None
        self.opt_override_to: Optional[str] = None
        self.opt_override_to_inferred: bool = False
        self.opt_override_to_parent: bool = False
        self.opt_push_tracked: Optional[bool] = True
        self.opt_push_untracked: Optional[bool] = True
        self.opt_return_to: str = "stay"
        self.opt_roots: List[LocalBranchShortName] = list()
        self.opt_start_from: str = "here"
        self.opt_stat: bool = False
        self.opt_sync_github_prs: bool = False
        self.opt_unset_override: bool = False
        self.opt_verbose: bool = False
        self.opt_yes: bool = False

    def validate(self) -> None:
        if self.opt_as_root and self.opt_onto:
            raise MacheteException(
                "Option `-R/--as-root` cannot be specified together with `-o/--onto`.")
        if self.opt_no_edit_merge and not self.opt_merge:
            raise MacheteException(
                "Option `--no-edit-merge` only makes sense when using merge and "
                "must be specified together with `-M/--merge`.")
        if self.opt_no_interactive_rebase and self.opt_merge:
            raise MacheteException(
                "Option `--no-interactive-rebase` only makes sense when using "
                "rebase and cannot be specified together with `-M/--merge`.")
        if self.opt_down_fork_point and self.opt_merge:
            raise MacheteException(
                "Option `-d/--down-fork-point` only makes sense when using "
                "rebase and cannot be specified together with `-M/--merge`.")
        if self.opt_fork_point and self.opt_merge:
            raise MacheteException(
                "Option `-f/--fork-point` only makes sense when using rebase and"
                " cannot be specified together with `-M/--merge`.")
