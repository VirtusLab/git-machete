import datetime
import itertools
import os
from typing import List, Optional, Tuple

from git_machete.client.base import MacheteClient, SquashMergeDetection
from git_machete.constants import DISCOVER_DEFAULT_FRESH_BRANCH_COUNT
from git_machete.exceptions import MacheteException
from git_machete.git_operations import LocalBranchShortName
from git_machete.utils import (bold, debug, excluding, get_pretty_choices,
                               slurp_file, tupled, warn)


class DiscoverMacheteClient(MacheteClient):
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
        if opt_roots:
            self._state.roots = [LocalBranchShortName.of(opt_root) for opt_root in opt_roots]
        else:
            self._state.roots = []
            if "master" in self._git.get_local_branches():
                self._state.roots += [LocalBranchShortName.of("master")]
            elif "main" in self._git.get_local_branches():
                # See https://github.com/github/renaming
                self._state.roots += [LocalBranchShortName.of("main")]
            if "develop" in self._git.get_local_branches():
                self._state.roots += [LocalBranchShortName.of("develop")]
        self._state.down_branches_for = {}
        self._state.up_branch_for = {}
        self.__indent = "  "
        for branch in self.annotations.keys():
            self.annotations[branch] = self.annotations[branch]._replace(text_without_qualifiers='')

        root_of = dict((branch, branch) for branch in all_local_branches)

        def get_root_of(branch: LocalBranchShortName) -> LocalBranchShortName:
            if branch != root_of[branch]:
                root_of[branch] = get_root_of(root_of[branch])
            return root_of[branch]

        non_root_fixed_branches = excluding(all_local_branches, self._state.roots)
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
        self._state.managed_branches = excluding(all_local_branches, stale_non_root_fixed_branches)
        if opt_checked_out_since and not self.managed_branches:
            warn(
                "no branches satisfying the criteria. Try moving the value of "
                "`--checked-out-since` further to the past.")
            return

        for branch in excluding(non_root_fixed_branches, stale_non_root_fixed_branches):
            upstream = self._infer_upstream(
                branch,
                condition=lambda candidate: (get_root_of(candidate) != branch and candidate not in stale_non_root_fixed_branches),
                reject_reason_message=("choosing this candidate would form a "
                                       "cycle in the resulting graph or the candidate is a stale branch"))
            if upstream:
                debug(f"inferred upstream of {branch} is {upstream}, attaching {branch} as a child of {upstream}")
                self._state.up_branch_for[branch] = upstream
                root_of[branch] = upstream
                if upstream in self._state.down_branches_for:
                    self._state.down_branches_for[upstream] += [branch]
                else:
                    self._state.down_branches_for[upstream] = [branch]
            else:
                debug(f"inferred no upstream for {branch}, attaching {branch} as a new root")
                self._state.roots += [branch]

        # Let's remove merged branches for which no downstream branch have been found.
        merged_branches_to_skip = []
        for branch in self.managed_branches:
            upstream = self.up_branch_for(branch)
            if upstream and not self.down_branches_for(branch):
                if self.is_merged_to(
                        branch=branch,
                        upstream=upstream,
                        opt_squash_merge_detection=SquashMergeDetection.NONE
                ):
                    debug(f"inferred upstream of {branch} is {upstream}, but "
                          f"{branch} is merged to {upstream}; skipping {branch} from discovered tree")
                    merged_branches_to_skip += [branch]
        if merged_branches_to_skip:
            warn(
                "skipping %s since %s merged to another branch and would not "
                "have any downstream branches.\n"
                % (", ".join(bold(branch) for branch in merged_branches_to_skip),
                   "it's" if len(merged_branches_to_skip) == 1 else "they're"))
            self._state.managed_branches = excluding(self.managed_branches, merged_branches_to_skip)
            for branch in merged_branches_to_skip:
                upstream = self._state.up_branch_for[branch]
                self._state.down_branches_for[upstream] = excluding(self._state.down_branches_for[upstream], [branch])
                del self._state.up_branch_for[branch]
            # We're NOT applying the removal process recursively,
            # so it's theoretically possible that some merged branches became childless
            # after removing the outer layer of childless merged branches.
            # This is rare enough, however, that we can pretty much ignore this corner case.

        print(bold("Discovered tree of branch dependencies:\n"))
        self.status(
            warn_when_branch_in_sync_but_fork_point_off=False,
            opt_list_commits=opt_list_commits,
            opt_list_commits_with_hashes=False,
            opt_squash_merge_detection=SquashMergeDetection.NONE)
        print("")
        do_backup = os.path.isfile(self._branch_layout_file_path) and slurp_file(self._branch_layout_file_path).strip()
        backup_msg = (
            f"\nThe existing branch layout file will be backed up as {self._branch_layout_file_path}~"
            if do_backup else "")
        msg = f"Save the above tree to {self._branch_layout_file_path}?{backup_msg}" + get_pretty_choices('y', 'e[dit]', 'N')
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
