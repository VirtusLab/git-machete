import datetime
import itertools
import os
import shutil
from typing import List, Optional, Tuple

from git_machete.client.status import StatusMacheteClient
from git_machete.config import SquashMergeDetection
from git_machete.constants import DISCOVER_DEFAULT_FRESH_BRANCH_COUNT
from git_machete.git import LocalBranchShortName
from git_machete.utils.collections import excluding, tupled
from git_machete.utils.debug_log import debug
from git_machete.utils.exceptions import MacheteException
from git_machete.utils.fs import slurp_file
from git_machete.utils.markup import pretty_choices, print_fmt, warn


class DiscoverMacheteClient(StatusMacheteClient):
    def back_up_branch_layout_file(self) -> None:
        shutil.copyfile(self._branch_layout_file_path, self._branch_layout_file_path + "~")

    def discover(
            self,
            *,
            opt_checked_out_since: Optional[str],
            opt_list_commits: bool,
            opt_roots: List[LocalBranchShortName],
            opt_yes: bool
    ) -> None:
        all_local_branches = self._git.get_local_branches()
        if not all_local_branches:
            raise MacheteException("No local branches found")
        for root in opt_roots:
            self.expect_in_local_branches(root)
        initial_roots: List[LocalBranchShortName] = []
        if opt_roots:
            initial_roots = [LocalBranchShortName.of(opt_root) for opt_root in opt_roots]
        else:
            if "master" in self._git.get_local_branches():
                initial_roots.append(LocalBranchShortName.of("master"))
            elif "main" in self._git.get_local_branches():
                # See https://github.com/github/renaming
                initial_roots.append(LocalBranchShortName.of("main"))
            if "develop" in self._git.get_local_branches():
                initial_roots.append(LocalBranchShortName.of("develop"))
        for branch in self._state.managed_branches:
            anno = self._state.get_annotation(branch)
            if anno is not None:
                self._state.set_annotation(branch, anno._replace(text_without_qualifiers=''))
        self._state.reset_tree(initial_roots)

        root_of = dict((branch, branch) for branch in all_local_branches)

        def get_root_of(branch: LocalBranchShortName) -> LocalBranchShortName:
            if branch != root_of[branch]:
                root_of[branch] = get_root_of(root_of[branch])
            return root_of[branch]

        non_root_fixed_branches = excluding(all_local_branches, self._state.roots)  # property returns a copy
        last_checkout_timestamps = self._git.get_latest_checkout_timestamps()
        non_root_fixed_branches_by_last_checkout_timestamps: List[Tuple[int, LocalBranchShortName]] = sorted(
            (last_checkout_timestamps.get(branch, 0), branch) for branch in non_root_fixed_branches)
        if opt_checked_out_since:
            threshold = self._git.get_git_timespec_parsed_to_unix_timestamp(opt_checked_out_since)
            stale_non_root_fixed_branches = [LocalBranchShortName.of(branch) for (timestamp, branch) in itertools.takewhile(
                tupled(lambda timestamp, _branch: timestamp < threshold),
                non_root_fixed_branches_by_last_checkout_timestamps
            )]
        else:
            c = DISCOVER_DEFAULT_FRESH_BRANCH_COUNT
            stale, fresh = non_root_fixed_branches_by_last_checkout_timestamps[:-c], \
                non_root_fixed_branches_by_last_checkout_timestamps[-c:]
            stale_non_root_fixed_branches = [LocalBranchShortName.of(branch) for (timestamp, branch) in stale]
            if stale:
                threshold_date = datetime.datetime.fromtimestamp(fresh[0][0], tz=datetime.timezone.utc).strftime("%Y-%m-%d")
                warn(
                    f"to keep the size of the discovered tree reasonable (ca. {c} branches), "
                    f"only branches checked out at or after ca. <b>{threshold_date}</b> are included.\n"
                    "Use `git machete discover --checked-out-since=<date>` (where <date> can be e.g. `'2 weeks ago'` or `2020-06-01`) "
                    "to change this threshold so that less or more branches are included.\n")
        fresh_branches = excluding(all_local_branches, stale_non_root_fixed_branches)
        if opt_checked_out_since and not fresh_branches:
            warn(
                "no branches satisfying the criteria. Try moving the value of "
                "`--checked-out-since` further to the past.")
            return

        for branch in excluding(non_root_fixed_branches, stale_non_root_fixed_branches):
            parent = self._infer_upstream(
                branch,
                condition=lambda candidate: (get_root_of(candidate) != branch and candidate not in stale_non_root_fixed_branches),
                reject_reason_message=("choosing this candidate would form a "
                                       "cycle in the resulting graph or the candidate is a stale branch"))
            if parent:
                debug(f"inferred parent of {branch} is {parent}, attaching {branch} as a child of {parent}")
                self._state.wire_as_child(parent=parent, child=branch)
                root_of[branch] = parent
            else:
                debug(f"inferred no parent for {branch}, attaching {branch} as a new root")
                self._state.wire_as_root(branch)

        # Let's remove merged branches for which no downstream branch have been found.
        merged_branches_to_skip = []
        for branch in fresh_branches:
            parent = self.parent_of(branch)
            if parent and not self.children_of(branch):
                if self.is_merged_to(
                        branch=branch,
                        parent=parent,
                        opt_squash_merge_detection=SquashMergeDetection.SIMPLE
                ):
                    debug(f"inferred parent of {branch} is {parent}, but "
                          f"{branch} is merged to {parent}; skipping {branch} from discovered tree")
                    merged_branches_to_skip += [branch]
        if merged_branches_to_skip:
            warn(
                "skipping %s since %s merged to another branch and would not "
                "have any downstream branches.\n"
                % (", ".join(f"<b>{branch}</b>" for branch in merged_branches_to_skip),
                   "it's" if len(merged_branches_to_skip) == 1 else "they're"))
            for branch in merged_branches_to_skip:
                self._state.detach_leaf(branch)
            # We're NOT applying the removal process recursively,
            # so it's theoretically possible that some merged branches became childless
            # after removing the outer layer of childless merged branches.
            # This is rare enough, however, that we can pretty much ignore this corner case.

        # Order managed_branches by DFS from roots (same order as in .git/machete file)
        dfs_branches: List[LocalBranchShortName] = []

        def collect_branches_dfs(parent: LocalBranchShortName) -> None:
            dfs_branches.append(parent)
            for child in self._state.get_children(parent) or []:
                collect_branches_dfs(child)

        for root in self._state.roots:
            collect_branches_dfs(root)
        self._state.set_managed(dfs_branches)

        print_fmt("<b>Discovered tree of branch dependencies:</b>\n")
        self.status(
            warn_when_branch_in_sync_but_fork_point_off=False,
            opt_list_commits=opt_list_commits,
            opt_list_commits_with_hashes=False,
            opt_squash_merge_detection=SquashMergeDetection.SIMPLE)
        print("")
        do_backup = os.path.isfile(self._branch_layout_file_path) and slurp_file(self._branch_layout_file_path).strip()
        backup_msg = (
            f"\nThe existing branch layout file will be backed up as {self._branch_layout_file_path}~"
            if do_backup else "")
        msg = f"Save the above tree to {self._branch_layout_file_path}?{backup_msg}" + pretty_choices('y', 'e[dit]', 'N')
        opt_yes_msg = f"Saving the above tree to {self._branch_layout_file_path}...{backup_msg}"
        ans = self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes)
        if ans in ('y', 'yes'):
            if do_backup:
                self.back_up_branch_layout_file()
            self.save_branch_layout_file()
        elif ans in ('e', 'edit'):
            if do_backup:
                self.back_up_branch_layout_file()
            self.save_branch_layout_file()
            self.edit()
