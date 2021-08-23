from typing import Optional, List


class CommandLineOptions:
    opt_debug: bool = False
    opt_verbose: bool = False

    def __init__(self) -> None:
        self.opt_as_root: bool = False
        self.opt_branch: Optional[str] = None
        self.opt_checked_out_since: Optional[str] = None
        self.opt_color: str = "auto"
        self.opt_down_fork_point: Optional[str] = None
        self.opt_draft: bool = False
        self.opt_fetch: bool = False
        self.opt_fork_point: Optional[str] = None
        self.opt_inferred: bool = False
        self.opt_list_commits: bool = False
        self.opt_list_commits_with_hashes: bool = False
        self.opt_merge: bool = False
        self.opt_n: bool = False
        self.opt_no_detect_squash_merges: bool = False
        self.opt_no_edit_merge: bool = False
        self.opt_no_interactive_rebase: bool = False
        self.opt_onto: Optional[str] = None
        self.opt_override_to: Optional[str] = None
        self.opt_override_to_inferred: bool = False
        self.opt_override_to_parent: bool = False
        self.opt_push_tracked: Optional[bool] = True
        self.opt_push_untracked: Optional[bool] = True
        self.opt_return_to: str = "stay"
        self.opt_roots: List[str] = list()
        self.opt_start_from: str = "here"
        self.opt_stat: bool = False
        self.opt_sync_github_prs: bool = False
        self.opt_unset_override: bool = False
        self.opt_yes: bool = False
