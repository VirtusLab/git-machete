import datetime
import io
import itertools
import os
import shutil
import sys
from typing import Callable, Dict, Generator, List, Optional, Tuple

import git_machete.github
import git_machete.options
from git_machete import utils
from git_machete.constants import (
    DISCOVER_DEFAULT_FRESH_BRANCH_COUNT, GitFormatPatterns, PICK_FIRST_ROOT, PICK_LAST_ROOT,
    SyncToRemoteStatuses)
from git_machete.exceptions import MacheteException, StopInteraction, UnprocessableEntityHTTPError
from git_machete.git_operations import (
    AnyBranchName, AnyRevision, ForkPointOverrideData,
    FullCommitHash, GitContext, GitLogEntry, HEAD, BranchPair, LocalBranchShortName, RemoteBranchShortName)
from git_machete.github import (
    add_assignees_to_pull_request, add_reviewers_to_pull_request,
    create_pull_request, checkout_pr_refs, derive_pull_request_by_head, derive_pull_requests,
    get_github_token_possible_providers, get_parsed_github_remote_url, get_pull_request_by_number_or_none, GitHubPullRequest,
    is_github_remote_url, RemoteAndOrganizationAndRepository, set_base_of_pull_request, set_milestone_of_pull_request)
from git_machete.utils import (
    get_pretty_choices, flat_map, excluding, fmt, tupled, warn, debug, bold,
    colored, underline, dim, get_second, AnsiEscapeCodes)


# Allowed parameter values for show/go command
def allowed_directions(allow_current: bool) -> str:
    current = "c[urrent]|" if allow_current else ""
    return current + "d[own]|f[irst]|l[ast]|n[ext]|p[rev]|r[oot]|u[p]"


class MacheteClient:

    def __init__(self, git: GitContext) -> None:
        self.__git: GitContext = git
        self._definition_file_path: str = self.__git.get_main_git_subpath("machete")
        self._managed_branches: List[LocalBranchShortName] = []
        self._up_branch: Dict[LocalBranchShortName, Optional[LocalBranchShortName]] = {}  # TODO (#110): default dict with None
        self.__down_branches: Dict[LocalBranchShortName, Optional[List[LocalBranchShortName]]] = {}  # TODO (#110): default dict with []
        self.__indent: Optional[str] = None
        self.__roots: List[LocalBranchShortName] = []
        self.__annotations: Dict[LocalBranchShortName, str] = {}
        self.__empty_line_status: Optional[bool] = None
        self.__branch_pairs_by_hash_in_reflog: Optional[Dict[FullCommitHash, Optional[List[BranchPair]]]] = None

    @property
    def definition_file_path(self) -> str:
        return self._definition_file_path

    @property
    def managed_branches(self) -> List[LocalBranchShortName]:
        return self._managed_branches

    @managed_branches.setter
    def managed_branches(self, val: List[LocalBranchShortName]) -> None:
        self._managed_branches = val

    @property
    def up_branch(self) -> Dict[LocalBranchShortName, Optional[LocalBranchShortName]]:
        return self._up_branch

    @up_branch.setter
    def up_branch(self, val: Dict[LocalBranchShortName, Optional[LocalBranchShortName]]) -> None:
        self._up_branch = val

    def expect_in_managed_branches(self, branch: LocalBranchShortName) -> None:
        if branch not in self.managed_branches:
            raise MacheteException(
                f"Branch `{branch}` not found in the tree of branch dependencies.\n"
                f"Use `git machete add {branch}` or `git machete edit`")

    def expect_at_least_one_managed_branch(self) -> None:
        if not self.__roots:
            self.__raise_no_branches_error()

    def __raise_no_branches_error(self) -> None:
        raise MacheteException(
            f"No branches listed in {self._definition_file_path}; use `git "
            f"machete discover` or `git machete edit`, or edit"
            f" {self._definition_file_path} manually.")

    def read_definition_file(self, perform_interactive_slide_out: bool, verify_branches: bool = True) -> None:
        with open(self._definition_file_path) as file:
            lines: List[str] = [line.rstrip() for line in file.readlines()]

        at_depth = {}
        last_depth = -1
        hint = "Edit the definition file manually with `git machete edit`"

        invalid_branches: List[LocalBranchShortName] = []
        for index, line in enumerate(lines):
            if line == "" or line.isspace():
                continue
            prefix = "".join(itertools.takewhile(str.isspace, line))
            if prefix and not self.__indent:
                self.__indent = prefix

            branch_and_maybe_annotation: List[LocalBranchShortName] = [LocalBranchShortName.of(entry) for entry in line.strip().split(" ", 1)]
            branch = branch_and_maybe_annotation[0]
            if len(branch_and_maybe_annotation) > 1:
                self.__annotations[branch] = branch_and_maybe_annotation[1]
            if branch in self.managed_branches:
                raise MacheteException(
                    f"{self._definition_file_path}, line {index + 1}: branch "
                    f"`{branch}` re-appears in the tree definition. {hint}")
            if verify_branches and branch not in self.__git.get_local_branches():
                invalid_branches += [branch]
            self.managed_branches += [branch]

            if prefix:
                depth: int = len(prefix) // len(self.__indent)
                if prefix != self.__indent * depth:
                    mapping: Dict[str, str] = {" ": "<SPACE>", "\t": "<TAB>"}
                    prefix_expanded: str = "".join(mapping[c] for c in prefix)
                    indent_expanded: str = "".join(mapping[c] for c in self.__indent)
                    raise MacheteException(
                        f"{self._definition_file_path}, line {index + 1}: "
                        f"invalid indent `{prefix_expanded}`, expected a multiply"
                        f" of `{indent_expanded}`. {hint}")
            else:
                depth = 0

            if depth > last_depth + 1:
                raise MacheteException(
                    f"{self._definition_file_path}, line {index + 1}: too much "
                    f"indent (level {depth}, expected at most {last_depth + 1}) "
                    f"for the branch `{branch}`. {hint}")
            last_depth = depth

            at_depth[depth] = branch
            if depth:
                p = at_depth[depth - 1]
                self.up_branch[branch] = p
                if p in self.__down_branches:
                    self.__down_branches[p] += [branch]
                else:
                    self.__down_branches[p] = [branch]
            else:
                self.__roots += [branch]

        if not invalid_branches:
            return

        if perform_interactive_slide_out:
            if len(invalid_branches) == 1:
                ans: str = self.ask_if(
                    f"Skipping `{invalid_branches[0]}` " +
                    "which is not a local branch (perhaps it has been deleted?).\n" +
                    "Slide it out from the definition file?" +
                    get_pretty_choices("y", "e[dit]", "N"), opt_yes_msg=None, opt_yes=False)
            else:
                ans = self.ask_if(
                    f"Skipping {', '.join(f'`{branch}`' for branch in invalid_branches)}"
                    " which are not local branches (perhaps they have been deleted?).\n"
                    "Slide them out from the definition file?" + get_pretty_choices("y", "e[dit]", "N"),
                    opt_yes_msg=None, opt_yes=False)
        else:
            if len(invalid_branches) > 0:
                print(f"Warning: sliding invalid branches: {', '.join(invalid_branches)} out of the definition file", file=sys.stderr)
            ans = 'y'

        def recursive_slide_out_invalid_branches(branch_: LocalBranchShortName) -> List[LocalBranchShortName]:
            new_down_branches = flat_map(
                recursive_slide_out_invalid_branches, self.__down_branches.get(branch_, []))
            if branch_ in invalid_branches:
                if branch_ in self.__down_branches:
                    del self.__down_branches[branch_]
                if branch_ in self.__annotations:
                    del self.__annotations[branch_]
                if branch_ in self.up_branch:
                    for down_branch in new_down_branches:
                        self.up_branch[down_branch] = self.up_branch[branch_]
                    del self.up_branch[branch_]
                else:
                    for down_branch in new_down_branches:
                        del self.up_branch[down_branch]
                return new_down_branches
            else:
                self.__down_branches[branch_] = new_down_branches
                return [branch_]

        self.__roots = flat_map(recursive_slide_out_invalid_branches, self.__roots)
        self.managed_branches = excluding(self.managed_branches, invalid_branches)
        if ans in ('y', 'yes'):
            self.save_definition_file()
        elif ans in ('e', 'edit'):
            self.edit()
            self.read_definition_file(verify_branches)

    def render_tree(self) -> List[str]:
        if not self.__indent:
            self.__indent = "\t"

        def render_dfs(branch: LocalBranchShortName, depth: int) -> List[str]:
            self.annotation = f" {self.__annotations[branch]}" if branch in self.__annotations else ""
            res: List[str] = [depth * self.__indent + branch + self.annotation]
            for down_branch in self.__down_branches.get(branch, []):
                res += render_dfs(down_branch, depth + 1)
            return res

        total: List[str] = []
        for root in self.__roots:
            total += render_dfs(root, depth=0)
        return total

    def back_up_definition_file(self) -> None:
        shutil.copyfile(self._definition_file_path, self._definition_file_path + "~")

    def save_definition_file(self) -> None:
        with open(self._definition_file_path, "w") as file:
            file.write("\n".join(self.render_tree()) + "\n")

    def add(self,
            *,
            branch: LocalBranchShortName,
            opt_onto: Optional[LocalBranchShortName],
            opt_as_root: bool,
            opt_yes: bool,
            verbose: bool,
            switch_head_if_new_branch: bool
            ) -> None:
        if branch in self.managed_branches:
            raise MacheteException(
                f"Branch `{branch}` already exists in the tree of branch dependencies")

        if opt_onto:
            self.expect_in_managed_branches(opt_onto)

        if branch not in self.__git.get_local_branches():
            remote_branch: Optional[RemoteBranchShortName] = self.__git.get_sole_remote_branch(branch)
            if remote_branch:
                common_line = (
                    f"A local branch `{branch}` does not exist, but a remote "
                    f"branch `{remote_branch}` exists.\n")
                msg = common_line + f"Check out `{branch}` locally?" + get_pretty_choices('y', 'N')
                opt_yes_msg = common_line + f"Checking out `{branch}` locally..."
                if self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes, verbose=verbose) in ('y', 'yes'):
                    self.__git.create_branch(branch, remote_branch.full_name(), switch_head=switch_head_if_new_branch)
                else:
                    return
                # Not dealing with `onto` here. If it hasn't been explicitly
                # specified via `--onto`, we'll try to infer it now.
            else:
                out_of = LocalBranchShortName.of(opt_onto).full_name() if opt_onto else HEAD
                out_of_str = f"`{opt_onto}`" if opt_onto else "the current HEAD"
                msg = (f"A local branch `{branch}` does not exist. Create (out "
                       f"of {out_of_str})?" + get_pretty_choices('y', 'N'))
                opt_yes_msg = (f"A local branch `{branch}` does not exist. "
                               f"Creating out of {out_of_str}")
                if self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes, verbose=verbose) in ('y', 'yes'):
                    # If `--onto` hasn't been explicitly specified, let's try to
                    # assess if the current branch would be a good `onto`.
                    if self.__roots and not opt_onto:
                        current_branch = self.__git.get_current_branch_or_none()
                        if current_branch and current_branch in self.managed_branches:
                            opt_onto = current_branch
                    self.__git.create_branch(branch, out_of, switch_head=switch_head_if_new_branch)
                else:
                    return

        if opt_as_root or not self.__roots:
            self.__roots += [branch]
            if verbose:
                print(fmt(f"Added branch `{branch}` as a new root"))
        else:
            if not opt_onto:
                upstream = self.__infer_upstream(
                    branch,
                    condition=lambda x: x in self.managed_branches,
                    reject_reason_message="this candidate is not a managed branch")
                if not upstream:
                    raise MacheteException(
                        f"Could not automatically infer upstream (parent) branch for `{branch}`.\n"
                        "You can either:\n"
                        "1) specify the desired upstream branch with `--onto` or\n"
                        f"2) pass `--as-root` to attach `{branch}` as a new root or\n"
                        "3) edit the definition file manually with `git machete edit`")
                else:
                    msg = (f"Add `{branch}` onto the inferred upstream (parent) "
                           f"branch `{upstream}`?" + get_pretty_choices('y', 'N'))
                    opt_yes_msg = (f"Adding `{branch}` onto the inferred upstream"
                                   f" (parent) branch `{upstream}`")
                    if self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes, verbose=verbose) in ('y', 'yes'):
                        opt_onto = upstream
                    else:
                        return

            self.up_branch[branch] = opt_onto
            if opt_onto in self.__down_branches:
                self.__down_branches[opt_onto].append(branch)
            else:
                self.__down_branches[opt_onto] = [branch]
            if verbose:
                print(fmt(f"Added branch `{branch}` onto `{opt_onto}`"))

        self.managed_branches += [branch]
        self.save_definition_file()

    def annotate(self, branch: LocalBranchShortName, words: List[str]) -> None:

        if branch in self.__annotations and words == ['']:
            del self.__annotations[branch]
        else:
            self.__annotations[branch] = " ".join(words)
        self.save_definition_file()

    def print_annotation(self, branch: LocalBranchShortName) -> None:
        if branch in self.__annotations:
            print(self.__annotations[branch])

    def update(
            self, *, opt_merge: bool, opt_no_edit_merge: bool,
            opt_no_interactive_rebase: bool, opt_fork_point: AnyRevision) -> None:
        current_branch = self.__git.get_current_branch()
        if opt_merge:
            with_branch = self.up(
                current_branch,
                prompt_if_inferred_msg=(
                    "Branch `%s` not found in the tree of branch dependencies. "
                    "Merge with the inferred upstream `%s`?" + get_pretty_choices('y', 'N')),
                prompt_if_inferred_yes_opt_msg=(
                    "Branch `%s` not found in the tree of branch dependencies. "
                    "Merging with the inferred upstream `%s`..."))
            self.__git.merge(with_branch, current_branch, opt_no_edit_merge)
        else:
            onto_branch = self.up(
                current_branch,
                prompt_if_inferred_msg=(
                    "Branch `%s` not found in the tree of branch dependencies. "
                    "Rebase onto the inferred upstream `%s`?" + get_pretty_choices('y', 'N')),
                prompt_if_inferred_yes_opt_msg=(
                    "Branch `%s` not found in the tree of branch dependencies. "
                    "Rebasing onto the inferred upstream `%s`..."))
            self.__git.rebase(
                LocalBranchShortName.of(onto_branch).full_name(),
                opt_fork_point or self.fork_point(
                    current_branch, use_overrides=True, opt_no_detect_squash_merges=False),
                current_branch, opt_no_interactive_rebase)

    def discover_tree(
            self,
            *,
            opt_checked_out_since: Optional[str],
            opt_list_commits: bool,
            opt_roots: List[LocalBranchShortName],
            opt_yes: bool
    ) -> None:
        all_local_branches = self.__git.get_local_branches()
        if not all_local_branches:
            raise MacheteException("No local branches found")
        for root in opt_roots:
            if root not in self.__git.get_local_branches():
                raise MacheteException(f"`{root}` is not a local branch")
        if opt_roots:
            self.__roots = list(map(LocalBranchShortName.of, opt_roots))
        else:
            self.__roots = []
            if "master" in self.__git.get_local_branches():
                self.__roots += [LocalBranchShortName.of("master")]
            elif "main" in self.__git.get_local_branches():
                # See https://github.com/github/renaming
                self.__roots += [LocalBranchShortName.of("main")]
            if "develop" in self.__git.get_local_branches():
                self.__roots += [LocalBranchShortName.of("develop")]
        self.__down_branches = {}
        self.up_branch = {}
        self.__indent = "\t"
        self.__annotations = {}

        root_of = dict((branch, branch) for branch in all_local_branches)

        def get_root_of(branch: LocalBranchShortName) -> LocalBranchShortName:
            if branch != root_of[branch]:
                root_of[branch] = get_root_of(root_of[branch])
            return root_of[branch]

        non_root_fixed_branches = excluding(all_local_branches, self.__roots)
        last_checkout_timestamps = self.__git.get_latest_checkout_timestamps()
        non_root_fixed_branches_by_last_checkout_timestamps = sorted(
            (last_checkout_timestamps.get(branch, 0), branch) for branch in non_root_fixed_branches)
        if opt_checked_out_since:
            threshold = self.__git.get_git_timespec_parsed_to_unix_timestamp(
                opt_checked_out_since)
            stale_non_root_fixed_branches = [LocalBranchShortName.of(branch) for (timestamp, branch) in itertools.takewhile(
                tupled(lambda timestamp, branch: timestamp < threshold),
                non_root_fixed_branches_by_last_checkout_timestamps
            )]
        else:
            c = DISCOVER_DEFAULT_FRESH_BRANCH_COUNT
            stale, fresh = non_root_fixed_branches_by_last_checkout_timestamps[:-c], non_root_fixed_branches_by_last_checkout_timestamps[-c:]
            stale_non_root_fixed_branches = [LocalBranchShortName.of(branch) for (timestamp, branch) in stale]
            if stale:
                threshold_date = datetime.datetime.utcfromtimestamp(fresh[0][0]).strftime("%Y-%m-%d")
                warn(
                    f"to keep the size of the discovered tree reasonable (ca. "
                    f"{c} branches), only branches checked out at or after ca. "
                    f"<b>{threshold_date}</b> are included.\n Use `git machete "
                    f"discover --checked-out-since=<date>` (where <date> can be "
                    f"e.g. `'2 weeks ago'` or `2020-06-01`) to change this "
                    f"threshold so that less or more branches are included.\n")
        self.managed_branches = excluding(all_local_branches, stale_non_root_fixed_branches)
        if opt_checked_out_since and not self.managed_branches:
            warn(
                "no branches satisfying the criteria. Try moving the value of "
                "`--checked-out-since` further to the past.")
            return

        for branch in excluding(non_root_fixed_branches, stale_non_root_fixed_branches):
            upstream = self.__infer_upstream(
                branch,
                condition=lambda candidate: (
                    get_root_of(candidate) != branch and
                    candidate not in stale_non_root_fixed_branches),
                reject_reason_message=(
                    "choosing this candidate would form a "
                    "cycle in the resulting graph or the candidate is a stale branch"))
            if upstream:
                debug(f"inferred upstream of {branch} is {upstream}, attaching {branch} as a child of {upstream}\n")
                self.up_branch[branch] = upstream
                root_of[branch] = upstream
                if upstream in self.__down_branches:
                    self.__down_branches[upstream].append(branch)
                else:
                    self.__down_branches[upstream] = [branch]
            else:
                debug(f"inferred no upstream for {branch}, attaching {branch} as a new root\n")
                self.__roots += [branch]

        # Let's remove merged branches for which no downstream branch have been found.
        merged_branches_to_skip = []
        for branch in self.managed_branches:
            if branch in self.up_branch and not self.__down_branches.get(branch):
                upstream = self.up_branch[branch]
                if self.is_merged_to(
                        branch=branch,
                        upstream=upstream,
                        opt_no_detect_squash_merges=False
                ):
                    debug(f"inferred upstream of {branch} is {upstream}, but "
                          f"{branch} is merged to {upstream}; skipping {branch}"
                          f" from discovered tree\n")
                    merged_branches_to_skip += [branch]
        if merged_branches_to_skip:
            warn(
                "skipping %s since %s merged to another branch and would not "
                "have any downstream branches.\n"
                % (", ".join(f"`{branch}`" for branch in merged_branches_to_skip),
                    "it's" if len(merged_branches_to_skip) == 1 else "they're"))
            self.managed_branches = excluding(self.managed_branches, merged_branches_to_skip)
            for branch in merged_branches_to_skip:
                upstream = self.up_branch[branch]
                self.__down_branches[upstream] = excluding(self.__down_branches[upstream], [branch])
                del self.up_branch[branch]
            # We're NOT applying the removal process recursively,
            # so it's theoretically possible that some merged branches became childless
            # after removing the outer layer of childless merged branches.
            # This is rare enough, however, that we can pretty much ignore this corner case.

        print(bold("Discovered tree of branch dependencies:\n"))
        self.status(
            warn_on_yellow_edges=False,
            opt_list_commits=opt_list_commits,
            opt_list_commits_with_hashes=False,
            opt_no_detect_squash_merges=False)
        print("")
        do_backup = os.path.isfile(self._definition_file_path)
        backup_msg = (
            f"\nThe existing definition file will be backed up as {self._definition_file_path}~"
            if do_backup else "")
        msg = f"Save the above tree to {self._definition_file_path}?{backup_msg}" + get_pretty_choices('y', 'e[dit]', 'N')
        opt_yes_msg = f"Saving the above tree to {self._definition_file_path}... {backup_msg}"
        ans = self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes)
        if ans in ('y', 'yes'):
            if do_backup:
                self.back_up_definition_file()
            self.save_definition_file()
        elif ans in ('e', 'edit'):
            if do_backup:
                self.back_up_definition_file()
            self.save_definition_file()
            self.edit()

    def slide_out(self,
                  *,
                  branches_to_slide_out: List[LocalBranchShortName],
                  opt_delete: bool,
                  opt_down_fork_point: Optional[AnyRevision],
                  opt_merge: bool,
                  opt_no_interactive_rebase: bool,
                  opt_no_edit_merge: bool
                  ) -> None:
        # Verify that all branches exist, are managed, and have an upstream.
        for branch in branches_to_slide_out:
            self.expect_in_managed_branches(branch)
            new_upstream = self.up_branch.get(branch)
            if not new_upstream:
                raise MacheteException(f"No upstream branch defined for `{branch}`, cannot slide out")

        if opt_down_fork_point:
            last_branch_to_slide_out = branches_to_slide_out[-1]
            children_of_the_last_branch_to_slide_out = self.__down_branches.get(
                last_branch_to_slide_out)

            if len(children_of_the_last_branch_to_slide_out) > 1:
                raise MacheteException(
                    "Last branch to slide out can't have more than one child branch "
                    "if option `--down-fork-point` is passed.")

            self.check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
                fork_point_hash=opt_down_fork_point,
                branch=children_of_the_last_branch_to_slide_out[0])

        # Verify that all "interior" slide-out branches have a single downstream pointing to the next slide-out
        for bu, bd in zip(branches_to_slide_out[:-1], branches_to_slide_out[1:]):
            dbs = self.__down_branches.get(bu)
            if not dbs or len(dbs) == 0:
                raise MacheteException(f"No downstream branch defined for `{bu}`, cannot slide out")
            elif len(dbs) > 1:
                flat_dbs = ", ".join(f"`{x}`" for x in dbs)
                raise MacheteException(
                    f"Multiple downstream branches defined for `{bu}`: {flat_dbs}; cannot slide out")
            elif dbs != [bd]:
                raise MacheteException(f"'{bd}' is not downstream of '{bu}', cannot slide out")

            if self.up_branch[bd] != bu:
                raise MacheteException(f"`{bu}` is not upstream of `{bd}`, cannot slide out")

        # Get new branches
        new_upstream = self.up_branch[branches_to_slide_out[0]]
        new_downstreams = self.__down_branches.get(branches_to_slide_out[-1], [])

        # Remove the slide-out branches from the tree
        for branch in branches_to_slide_out:
            self.up_branch[branch] = None
            self.__down_branches[branch] = None
            self.managed_branches.remove(branch)
        self.__down_branches[new_upstream] = [
            branch for branch in self.__down_branches[new_upstream]
            if branch != branches_to_slide_out[0]]

        # Reconnect the downstreams to the new upstream in the tree
        for new_downstream in new_downstreams:
            self.up_branch[new_downstream] = new_upstream
            self.__down_branches[new_upstream].append(new_downstream)

        # Update definition, fire post-hook, and perform the branch update
        self.save_definition_file()
        self.__run_post_slide_out_hook(new_upstream, branches_to_slide_out[-1], new_downstreams)

        self.__git.checkout(new_upstream)
        for new_downstream in new_downstreams:
            self.__git.checkout(new_downstream)
            if opt_merge:
                print(f"Merging {bold(new_upstream)} into {bold(new_downstream)}...")
                self.__git.merge(new_upstream, new_downstream, opt_no_edit_merge)
            else:
                print(f"Rebasing {bold(new_downstream)} onto {bold(new_upstream)}...")
                self.__git.rebase(
                    new_upstream.full_name(),
                    opt_down_fork_point or
                    self.fork_point(
                        new_downstream, use_overrides=True, opt_no_detect_squash_merges=False),
                    new_downstream,
                    opt_no_interactive_rebase)

        if opt_delete:
            self._delete_branches(branches_to_delete=branches_to_slide_out, opt_yes=False)

    def advance(self, *, branch: LocalBranchShortName, opt_yes: bool) -> None:
        if not self.__down_branches.get(branch):
            raise MacheteException(
                f"`{branch}` does not have any downstream (child) branches to advance towards")

        def connected_with_green_edge(bd: LocalBranchShortName) -> bool:
            return bool(
                not self.__is_merged_to_upstream(
                    bd, opt_no_detect_squash_merges=False) and
                self.__git.is_ancestor_or_equal(branch.full_name(), bd.full_name()) and
                (self.__get_overridden_fork_point(bd) or self.__git.get_commit_hash_by_revision(branch) == self.fork_point(bd, use_overrides=False, opt_no_detect_squash_merges=False)))

        candidate_downstreams = list(filter(connected_with_green_edge, self.__down_branches[branch]))
        if not candidate_downstreams:
            raise MacheteException(
                f"No downstream (child) branch of `{branch}` is connected to "
                f"`{branch}` with a green edge")
        if len(candidate_downstreams) > 1:
            if opt_yes:
                raise MacheteException(
                    f"More than one downstream (child) branch of `{branch}` is "
                    f"connected to `{branch}` with a green edge and `-y/--yes` option is specified")
            else:
                down_branch = self.pick(
                    candidate_downstreams,
                    f"downstream branch towards which `{branch}` is to be fast-forwarded")
                self.__git.merge_fast_forward_only(down_branch)
        else:
            down_branch = candidate_downstreams[0]
            ans = self.ask_if(
                f"Fast-forward {bold(branch)} to match {bold(down_branch)}?" + get_pretty_choices('y', 'N'),
                f"Fast-forwarding {bold(branch)} to match {bold(down_branch)}...", opt_yes=opt_yes)
            if ans in ('y', 'yes'):
                self.__git.merge_fast_forward_only(down_branch)
            else:
                return

        remote = self.__git.get_strict_remote_for_fetching_of_branch(branch)
        ans = self.ask_if(f"\nBranch {bold(branch)} is now fast-forwarded to match {bold(down_branch)}. Push {bold(branch)} to {bold(remote)}?" + get_pretty_choices('y', 'N'),
                          f"\nBranch {bold(branch)} is now fast-forwarded to match {bold(down_branch)}. Pushing {bold(branch)} to {bold(remote)}...", opt_yes=opt_yes)
        if ans in ('y', 'yes'):
            self.__git.push(remote, branch)
            branch_pushed_or_fast_forwarded_msg = f"\nBranch {bold(branch)} is now pushed to {bold(remote)}."
        else:
            branch_pushed_or_fast_forwarded_msg = f"\nBranch {bold(branch)} is now fast-forwarded to match {bold(down_branch)}."

        ans = self.ask_if(f"{branch_pushed_or_fast_forwarded_msg} Slide {bold(down_branch)} out of the tree of branch dependencies?" + get_pretty_choices('y', 'N'),
                          f"{branch_pushed_or_fast_forwarded_msg} Sliding {bold(down_branch)} out of the tree of branch dependencies...", opt_yes=opt_yes)
        if ans in ('y', 'yes'):
            dds = self.__down_branches.get(LocalBranchShortName.of(down_branch), [])
            for dd in dds:
                self.up_branch[dd] = branch
            self.__down_branches[branch] = flat_map(
                lambda bd: dds if bd == down_branch else [bd],
                self.__down_branches[branch])
            self.save_definition_file()
            self.__run_post_slide_out_hook(branch, down_branch, dds)

    def __print_new_line(self, new_status: bool) -> None:
        if not self.__empty_line_status:
            print("")
        self.__empty_line_status = new_status

    def traverse(
            self,
            *,
            opt_fetch: bool,
            opt_list_commits: bool,
            opt_merge: bool,
            opt_no_detect_squash_merges: bool,
            opt_no_edit_merge: bool,
            opt_no_interactive_rebase: bool,
            opt_push_tracked: bool,
            opt_push_untracked: bool,
            opt_return_to: str,
            opt_start_from: str,
            opt_yes: bool
    ) -> None:
        self.expect_at_least_one_managed_branch()

        self.__empty_line_status = True
        any_action_suggested: bool = False

        if opt_fetch:
            for remote in self.__git.get_remotes():
                print(f"Fetching {remote}...")
                self.__git.fetch_remote(remote)
            if self.__git.get_remotes():
                self.flush_caches()
                print("")

        initial_branch = nearest_remaining_branch = self.__git.get_current_branch()

        if opt_start_from == "root":
            dest = self.root_branch(self.__git.get_current_branch(), if_unmanaged=PICK_FIRST_ROOT)
            self.__print_new_line(False)
            print(f"Checking out the root branch ({bold(dest)})")
            self.__git.checkout(dest)
            current_branch = dest
        elif opt_start_from == "first-root":
            # Note that we already ensured that there is at least one managed branch.
            dest = self.managed_branches[0]
            self.__print_new_line(False)
            print(f"Checking out the first root branch ({bold(dest)})")
            self.__git.checkout(dest)
            current_branch = dest
        else:  # cli_opts.opt_start_from == "here"
            current_branch = self.__git.get_current_branch()
            self.expect_in_managed_branches(current_branch)

        branch: LocalBranchShortName
        for branch in itertools.dropwhile(lambda x: x != current_branch, self.managed_branches):
            upstream = self.up_branch.get(branch)

            needs_slide_out: bool = self.__is_merged_to_upstream(
                branch, opt_no_detect_squash_merges=opt_no_detect_squash_merges)
            s, remote = self.__git.get_strict_remote_sync_status(branch)
            statuses_to_sync = (
                SyncToRemoteStatuses.UNTRACKED,
                SyncToRemoteStatuses.AHEAD_OF_REMOTE,
                SyncToRemoteStatuses.BEHIND_REMOTE,
                SyncToRemoteStatuses.DIVERGED_FROM_AND_OLDER_THAN_REMOTE,
                SyncToRemoteStatuses.DIVERGED_FROM_AND_NEWER_THAN_REMOTE)
            needs_remote_sync = s in statuses_to_sync

            if needs_slide_out:
                # Avoid unnecessary fork point check if we already know that the
                # branch qualifies for slide out;
                # neither rebase nor merge will be suggested in such case anyway.
                needs_parent_sync: bool = False
            elif s == SyncToRemoteStatuses.DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                # Avoid unnecessary fork point check if we already know that the
                # branch qualifies for resetting to remote counterpart;
                # neither rebase nor merge will be suggested in such case anyway.
                needs_parent_sync = False
            elif opt_merge:
                needs_parent_sync = bool(
                    upstream and not self.__git.is_ancestor_or_equal(upstream.full_name(), branch.full_name()))
            else:  # using rebase
                needs_parent_sync = bool(
                    upstream and
                    not (self.__git.is_ancestor_or_equal(upstream.full_name(), branch.full_name()) and
                         (self.__git.get_commit_hash_by_revision(upstream) ==
                          self.fork_point(
                              branch, use_overrides=True,
                              opt_no_detect_squash_merges=opt_no_detect_squash_merges)))
                )

            if branch != current_branch and (needs_slide_out or needs_parent_sync or needs_remote_sync):
                self.__print_new_line(False)
                print(f"Checking out {bold(branch)}")
                self.__git.checkout(branch)
                current_branch = branch
                self.__print_new_line(False)
                self.status(
                    warn_on_yellow_edges=True,
                    opt_list_commits=opt_list_commits,
                    opt_list_commits_with_hashes=False,
                    opt_no_detect_squash_merges=opt_no_detect_squash_merges)
                self.__print_new_line(True)
            if needs_slide_out:
                any_action_suggested = True
                self.__print_new_line(False)
                ans: str = self.ask_if(f"Branch {bold(branch)} is merged into {bold(upstream)}. Slide {bold(branch)} out of the tree of branch dependencies?" + get_pretty_choices('y', 'N', 'q', 'yq'),
                                       f"Branch {bold(branch)} is merged into {bold(upstream)}. Sliding {bold(branch)} out of the tree of branch dependencies...", opt_yes=opt_yes)
                if ans in ('y', 'yes', 'yq'):
                    if nearest_remaining_branch == branch:
                        if self.__down_branches.get(branch):
                            nearest_remaining_branch = self.__down_branches[branch][0]
                        else:
                            nearest_remaining_branch = upstream
                    for down_branch in self.__down_branches.get(branch) or []:
                        self.up_branch[down_branch] = upstream
                    self.__down_branches[upstream] = flat_map(
                        lambda ud: (self.__down_branches.get(branch) or []) if ud == branch else [ud],
                        self.__down_branches[upstream])
                    if branch in self.__annotations:
                        del self.__annotations[branch]
                    self.save_definition_file()
                    self.__run_post_slide_out_hook(upstream, branch, self.__down_branches.get(branch) or [])
                    if ans == 'yq':
                        return
                    # No need to flush caches since nothing changed in commit/branch
                    # structure (only machete-specific changes happened).
                    continue  # No need to sync branch 'branch' with remote since it just got removed from the tree of dependencies.
                elif ans in ('q', 'quit'):
                    return
                # If user answered 'no', we don't try to rebase/merge but still
                # suggest to sync with remote (if needed; very rare in practice).
            elif needs_parent_sync:
                any_action_suggested = True
                self.__print_new_line(False)
                if opt_merge:
                    ans = self.ask_if(f"Merge {bold(upstream)} into {bold(branch)}?" + get_pretty_choices('y', 'N', 'q', 'yq'),
                                      f"Merging {bold(upstream)} into {bold(branch)}...", opt_yes=opt_yes)
                else:
                    ans = self.ask_if(f"Rebase {bold(branch)} onto {bold(upstream)}?" + get_pretty_choices('y', 'N', 'q', 'yq'),
                                      f"Rebasing {bold(branch)} onto {bold(upstream)}...", opt_yes=opt_yes)
                if ans in ('y', 'yes', 'yq'):
                    if opt_merge:
                        self.__git.merge(upstream, branch, opt_no_edit_merge)
                        # It's clearly possible that merge can be in progress
                        # after 'git merge' returned non-zero exit code;
                        # this happens most commonly in case of conflicts.
                        # As for now, we're not aware of any case when merge can
                        # be still in progress after 'git merge' returns zero,
                        # at least not with the options that git-machete passes
                        # to merge; this happens though in case of 'git merge
                        # --no-commit' (which we don't ever invoke).
                        # It's still better, however, to be on the safe side.
                        if self.__git.is_merge_in_progress():
                            print("\nMerge in progress; stopping the traversal")
                            return
                    else:
                        self.__git.rebase(
                            LocalBranchShortName.of(upstream).full_name(), self.fork_point(
                                branch,
                                use_overrides=True,
                                opt_no_detect_squash_merges=opt_no_detect_squash_merges),
                            branch, opt_no_interactive_rebase)
                        # It's clearly possible that rebase can be in progress
                        # after 'git rebase' returned non-zero exit code;
                        # this happens most commonly in case of conflicts,
                        # regardless of whether the rebase is interactive or not.
                        # But for interactive rebases, it's still possible that
                        # even if 'git rebase' returned zero, the rebase is still
                        # in progress; e.g. when interactive rebase gets to 'edit'
                        # command, it will exit returning zero, but the rebase
                        # will be still in progress, waiting for user edits and
                        # a subsequent 'git rebase --continue'.
                        rebased_branch = self.__git.get_currently_rebased_branch_or_none()
                        if rebased_branch:  # 'remote_branch' should be equal to 'branch' at this point anyway
                            print(fmt(f"\nRebase of `{rebased_branch}` in progress; stopping the traversal"))
                            return
                    if ans == 'yq':
                        return

                    self.flush_caches()
                    s, remote = self.__git.get_strict_remote_sync_status(branch)
                    needs_remote_sync = s in statuses_to_sync
                elif ans in ('q', 'quit'):
                    return

            if needs_remote_sync:
                any_action_suggested = True
                try:
                    if s == SyncToRemoteStatuses.BEHIND_REMOTE:
                        self.__handle_behind_state(current_branch, remote, opt_yes=opt_yes)
                    elif s == SyncToRemoteStatuses.AHEAD_OF_REMOTE:
                        self.__handle_ahead_state(
                            current_branch=current_branch,
                            remote=remote,
                            is_called_from_traverse=True,
                            opt_push_tracked=opt_push_tracked,
                            opt_yes=opt_yes)
                    elif s == SyncToRemoteStatuses.DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                        self.__handle_diverged_and_older_state(current_branch, opt_yes=opt_yes)
                    elif s == SyncToRemoteStatuses.DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                        self.__handle_diverged_and_newer_state(
                            current_branch=current_branch,
                            remote=remote,
                            opt_push_tracked=opt_push_tracked,
                            opt_yes=opt_yes)
                    elif s == SyncToRemoteStatuses.UNTRACKED:
                        self.__handle_untracked_state(
                            branch=current_branch,
                            is_called_from_traverse=True,
                            opt_push_untracked=opt_push_untracked,
                            opt_push_tracked=opt_push_tracked,
                            opt_yes=opt_yes)
                except StopInteraction:
                    return

        if opt_return_to == "here":
            self.__git.checkout(initial_branch)
        elif opt_return_to == "nearest-remaining":
            self.__git.checkout(nearest_remaining_branch)
        # otherwise opt_return_to == "stay", so no action is needed

        self.__print_new_line(False)
        self.status(
            warn_on_yellow_edges=True,
            opt_list_commits=opt_list_commits,
            opt_list_commits_with_hashes=False,
            opt_no_detect_squash_merges=opt_no_detect_squash_merges)
        print("")
        if current_branch == self.managed_branches[-1]:
            msg: str = f"Reached branch {bold(current_branch)} which has no successor"
        else:
            msg = f"No successor of {bold(current_branch)} needs to be slid out or synced with upstream branch or remote"
        print(f"{msg}; nothing left to update")
        if not any_action_suggested and initial_branch not in self.__roots:
            print(fmt("Tip: `traverse` by default starts from the current branch, "
                      "use flags (`--start-from=`, `--whole` or `-w`, `-W`) to change this behavior.\n"
                      "Further info under `git machete traverse --help`."))
        if opt_return_to == "here" or (
                opt_return_to == "nearest-remaining" and nearest_remaining_branch == initial_branch):
            print(f"Returned to the initial branch {bold(initial_branch)}")
        elif opt_return_to == "nearest-remaining" and nearest_remaining_branch != initial_branch:
            print(
                f"The initial branch {bold(initial_branch)} has been slid out. "
                f"Returned to nearest remaining managed branch {bold(nearest_remaining_branch)}")

    # TODO (#509): tidy up this method
    def status(
            self,
            *,
            warn_on_yellow_edges: bool,
            opt_list_commits: bool,
            opt_list_commits_with_hashes: bool,
            opt_no_detect_squash_merges: bool
    ) -> None:
        dfs_res: List[Tuple[LocalBranchShortName, List[Optional[LocalBranchShortName]]]] = []

        def prefix_dfs(u_: LocalBranchShortName, accumulated_path_: List[Optional[LocalBranchShortName]]) -> None:
            dfs_res.append((u_, accumulated_path_))
            if self.__down_branches.get(u_):
                for (v, nv) in zip(self.__down_branches[u_][:-1], self.__down_branches[u_][1:]):
                    prefix_dfs(v, accumulated_path_ + [nv])
                prefix_dfs(self.__down_branches[u_][-1], accumulated_path_ + [None])

        for upstream in self.__roots:
            prefix_dfs(upstream, accumulated_path_=[])

        out = io.StringIO()
        edge_color: Dict[LocalBranchShortName, str] = {}
        fp_hash_cached: Dict[LocalBranchShortName, Optional[FullCommitHash]] = {}  # TODO (#110): default dict with None
        fp_branches_cached: Dict[LocalBranchShortName, List[BranchPair]] = {}

        def fp_hash(branch_: LocalBranchShortName) -> Optional[FullCommitHash]:
            if branch not in fp_hash_cached:
                try:
                    # We're always using fork point overrides, even when status
                    # is launched from discover().
                    fp_hash_cached[branch_], fp_branches_cached[branch_] = self.__fork_point_and_containing_branch_pairs(
                        branch_,
                        use_overrides=True,
                        opt_no_detect_squash_merges=opt_no_detect_squash_merges)
                except MacheteException:
                    fp_hash_cached[branch_], fp_branches_cached[branch_] = None, []
            return fp_hash_cached[branch_]

        # Edge colors need to be precomputed
        # in order to render the leading parts of lines properly.
        branch: LocalBranchShortName
        for branch in self.up_branch:
            upstream = self.up_branch[branch]
            if self.is_merged_to(
                    branch=branch,
                    upstream=upstream,
                    opt_no_detect_squash_merges=opt_no_detect_squash_merges):
                edge_color[branch] = AnsiEscapeCodes.DIM
            elif not self.__git.is_ancestor_or_equal(upstream.full_name(), branch.full_name()):
                edge_color[branch] = AnsiEscapeCodes.RED
            elif self.__get_overridden_fork_point(branch) or self.__git.get_commit_hash_by_revision(upstream) == fp_hash(branch):
                edge_color[branch] = AnsiEscapeCodes.GREEN
            else:
                edge_color[branch] = AnsiEscapeCodes.YELLOW

        currently_rebased_branch = self.__git.get_currently_rebased_branch_or_none()
        currently_checked_out_branch = self.__git.get_currently_checked_out_branch_or_none()

        hook_path = self.__git.get_hook_path("machete-status-branch")
        hook_executable = self.__git.check_hook_executable(hook_path)

        maybe_space_before_branch_name = ' ' if self.__git.get_boolean_config_attr('machete.status.extraSpaceBeforeBranchName') else ''

        def print_line_prefix(branch_: LocalBranchShortName, suffix: str) -> None:
            out.write("  " + maybe_space_before_branch_name)
            for sibling in next_sibling_of_ancestor[:-1]:
                if not sibling:
                    out.write("  " + maybe_space_before_branch_name)
                else:
                    out.write(colored(f"{utils.get_vertical_bar()} " + maybe_space_before_branch_name, edge_color[sibling]))
            out.write(colored(suffix, edge_color[branch_]))

        next_sibling_of_ancestor: List[Optional[LocalBranchShortName]]
        for branch, next_sibling_of_ancestor in dfs_res:
            if branch in self.up_branch:
                print_line_prefix(branch, f"{utils.get_vertical_bar()} \n")
                if opt_list_commits:
                    if not fp_hash(branch):
                        # Rare case, but can happen e.g. due to reflog expiry.
                        commits: List[GitLogEntry] = []
                    elif edge_color[branch] == AnsiEscapeCodes.DIM:
                        commits = []
                    elif edge_color[branch] == AnsiEscapeCodes.YELLOW:
                        commits = self.__git.get_commits_between(self.up_branch[branch].full_name(), branch.full_name())
                    else:  # (AnsiEscapeCodes.RED, AnsiEscapeCodes.GREEN):
                        commits = self.__git.get_commits_between(fp_hash(branch), branch.full_name())

                    for commit in commits:
                        if commit.hash == fp_hash(branch):
                            # fp_branches_cached will already be there thanks to
                            # the above call to 'fp_hash'.
                            fp_branches_formatted: str = " and ".join(
                                sorted(underline(lb_or_rb) for lb, lb_or_rb in fp_branches_cached[branch]))
                            fp_suffix: str = " %s %s %s seems to be a part of the unique history of %s" % \
                                             (colored(utils.get_right_arrow(), AnsiEscapeCodes.RED), colored("fork point ???", AnsiEscapeCodes.RED),
                                              "this commit" if opt_list_commits_with_hashes else f"commit {commit.short_hash}",
                                              fp_branches_formatted)
                        else:
                            fp_suffix = ''
                        print_line_prefix(branch, utils.get_vertical_bar())
                        out.write(" %s%s%s\n" % (
                                  f"{dim(commit.short_hash)}  " if opt_list_commits_with_hashes else "", dim(commit.subject),
                                  fp_suffix))

                junction: str
                if utils.ascii_only:
                    junction_ascii_only: Dict[str, str] = {
                        AnsiEscapeCodes.DIM: "m-",
                        AnsiEscapeCodes.RED: "x-",
                        AnsiEscapeCodes.GREEN: "o-",
                        AnsiEscapeCodes.YELLOW: "?-"}
                    junction = junction_ascii_only[edge_color[branch]]
                else:
                    next_sibling_of_branch: Optional[LocalBranchShortName] = next_sibling_of_ancestor[-1]
                    if next_sibling_of_branch and edge_color[next_sibling_of_branch] == edge_color[branch]:
                        junction = u"├─"
                    else:
                        # The three-legged turnstile looks pretty bad when the upward and rightward leg
                        # have a different color than the downward leg.
                        # It's better to use a two-legged elbow
                        # in case `edge_color[next_sibling_of_branch] != edge_color[branch]`,
                        # at the expense of a little gap to the elbow/turnstile below.
                        junction = u"└─"
                print_line_prefix(branch, junction + maybe_space_before_branch_name)
            else:
                if branch != dfs_res[0][0]:
                    out.write("\n")
                out.write("  " + maybe_space_before_branch_name)

            if branch in (currently_checked_out_branch, currently_rebased_branch):  # i.e. if branch is the current branch (checked out or being rebased)
                if branch == currently_rebased_branch:
                    prefix = "REBASING "
                elif self.__git.is_am_in_progress():
                    prefix = "GIT AM IN PROGRESS "
                elif self.__git.is_cherry_pick_in_progress():
                    prefix = "CHERRY-PICKING "
                elif self.__git.is_merge_in_progress():
                    prefix = "MERGING "
                elif self.__git.is_revert_in_progress():
                    prefix = "REVERTING "
                else:
                    prefix = ""
                current = "%s%s" % (bold(colored(prefix, AnsiEscapeCodes.RED)), bold(underline(branch, star_if_ascii_only=True)))
            else:
                current = bold(branch)

            anno: str = f"  {dim(self.__annotations[branch])}" if branch in self.__annotations else ""

            s, remote = self.__git.get_combined_remote_sync_status(branch)
            sync_status = {
                SyncToRemoteStatuses.NO_REMOTES: "",
                SyncToRemoteStatuses.UNTRACKED: colored(" (untracked)", AnsiEscapeCodes.ORANGE),
                SyncToRemoteStatuses.IN_SYNC_WITH_REMOTE: "",
                SyncToRemoteStatuses.BEHIND_REMOTE: colored(f" (behind {remote})", AnsiEscapeCodes.RED),
                SyncToRemoteStatuses.AHEAD_OF_REMOTE: colored(f" (ahead of {remote})", AnsiEscapeCodes.RED),
                SyncToRemoteStatuses.DIVERGED_FROM_AND_OLDER_THAN_REMOTE: colored(f" (diverged from & older than {remote})", AnsiEscapeCodes.RED),
                SyncToRemoteStatuses.DIVERGED_FROM_AND_NEWER_THAN_REMOTE: colored(f" (diverged from {remote})", AnsiEscapeCodes.RED)
            }[SyncToRemoteStatuses(s)]

            hook_output = ""
            if hook_executable:
                debug(f"running machete-status-branch hook ({hook_path}) for branch {branch}")
                hook_env = dict(os.environ, ASCII_ONLY=str(utils.ascii_only).lower())
                status_code, stdout, stderr = utils.popen_cmd(hook_path, branch, cwd=self.__git.get_root_dir(), env=hook_env)
                if status_code == 0:
                    if not stdout.isspace():
                        hook_output = f"  {stdout.rstrip()}"
                else:
                    debug("machete-status-branch hook ({hook_path}) for branch {branch} returned {status_code}; stdout: '{stdout}'; stderr: '{stderr}'")

            out.write(current + anno + sync_status + hook_output + "\n")

        sys.stdout.write(out.getvalue())
        out.close()

        yellow_edge_branches = [k for k, v in edge_color.items() if v == AnsiEscapeCodes.YELLOW]
        if yellow_edge_branches and warn_on_yellow_edges:
            if len(yellow_edge_branches) == 1:
                first_part = f"yellow edge indicates that fork point for `{yellow_edge_branches[0]}` is probably incorrectly inferred,\n" \
                             f"or that some extra branch should be between `{self.up_branch[LocalBranchShortName.of(yellow_edge_branches[0])]}` and `{yellow_edge_branches[0]}`"
            else:
                affected_branches = ", ".join(map(lambda x: f"`{x}`", yellow_edge_branches))
                first_part = f"yellow edges indicate that fork points for {affected_branches} are probably incorrectly inferred,\n" \
                             f"or that some extra branch should be added between each of these branches and its parent"

            if not opt_list_commits:
                second_part = "Run `git machete status --list-commits` or `git machete status --list-commits-with-hashes` to see more details"
            elif len(yellow_edge_branches) == 1:
                second_part = f"Consider using `git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent {yellow_edge_branches[0]}`,\n" \
                              f"or reattaching `{yellow_edge_branches[0]}` under a different parent branch"
            else:
                second_part = "Consider using `git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent <branch>` for each affected branch,\n" \
                              "or reattaching the affected branches under different parent branches"

            print("", file=sys.stderr)
            warn(f"{first_part}.\n\n{second_part}.")

    def delete_unmanaged(self, *, opt_yes: bool) -> None:
        print(bold('Checking for unmanaged branches...'))
        branches_to_delete = excluding(self.__git.get_local_branches(), self.managed_branches)
        self._delete_branches(branches_to_delete=branches_to_delete, opt_yes=opt_yes)

    def _delete_branches(self, branches_to_delete: List[LocalBranchShortName], opt_yes: bool) -> None:
        current_branch = self.__git.get_current_branch_or_none()
        if current_branch and current_branch in branches_to_delete:
            branches_to_delete = excluding(branches_to_delete, [current_branch])
            print(fmt(f"Skipping current branch `{current_branch}`"))
        if branches_to_delete:
            branches_merged_to_head = self.__git.get_merged_local_branches()

            branches_to_delete_merged_to_head = [branch for branch in branches_to_delete if branch in branches_merged_to_head]
            for branch in branches_to_delete_merged_to_head:
                remote_branch = self.__git.get_strict_counterpart_for_fetching_of_branch(branch)
                is_merged_to_remote = self.__git.is_ancestor_or_equal(branch.full_name(), remote_branch.full_name()) if remote_branch else True
                msg_core = f"{bold(branch)} (merged to HEAD{'' if is_merged_to_remote else f', but not merged to {remote_branch}'})"
                msg = f"Delete branch {msg_core}?" + get_pretty_choices('y', 'N', 'q')
                opt_yes_msg = f"Deleting branch {msg_core}"
                ans = self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes)
                if ans in ('y', 'yes'):
                    self.__git.delete_branch(branch, force=is_merged_to_remote)
                elif ans in ('q', 'quit'):
                    return

            branches_to_delete_unmerged_to_head = [branch for branch in branches_to_delete if branch not in branches_merged_to_head]
            for branch in branches_to_delete_unmerged_to_head:
                msg_core = f"{bold(branch)} (unmerged to HEAD)"
                msg = f"Delete branch {msg_core}?" + get_pretty_choices('y', 'N', 'q')
                opt_yes_msg = f"Deleting branch {msg_core}"
                ans = self.ask_if(msg, opt_yes_msg, opt_yes=opt_yes)
                if ans in ('y', 'yes'):
                    self.__git.delete_branch(branch, force=True)
                elif ans in ('q', 'quit'):
                    return
        else:
            print("No branches to delete")

    def edit(self) -> int:
        default_editor_name: Optional[str] = self.__git.get_default_editor()
        if default_editor_name is None:
            raise MacheteException(
                f"Cannot determine editor. Set `GIT_MACHETE_EDITOR` environment "
                f"variable or edit {self._definition_file_path} directly.")
        return utils.run_cmd(default_editor_name, self._definition_file_path)

    def __fork_point_and_containing_branch_pairs(self, branch: LocalBranchShortName, use_overrides: bool, opt_no_detect_squash_merges: bool) -> Tuple[FullCommitHash, List[BranchPair]]:
        upstream = self.up_branch.get(branch)

        if use_overrides:
            overridden_fp_hash = self.__get_overridden_fork_point(branch)
            if overridden_fp_hash:
                if upstream and self.__git.is_ancestor_or_equal(upstream.full_name(), branch.full_name()) and not self.__git.is_ancestor_or_equal(upstream.full_name(), overridden_fp_hash.full_name()):
                    # We need to handle the case when branch is a descendant of upstream,
                    # but the fork point of branch is overridden to a commit that
                    # is NOT a descendant of upstream. In this case it's more
                    # reasonable to assume that upstream (and not overridden_fp_hash)
                    # is the fork point.
                    debug(f"{branch} is descendant of its upstream {upstream}, but overridden fork point commit {overridden_fp_hash} is NOT a descendant of {upstream}; falling back to {upstream} as fork point")
                    return self.__git.get_commit_hash_by_revision(upstream), []
                else:
                    debug(f"fork point of {branch} is overridden to {overridden_fp_hash}; skipping inference")
                    return overridden_fp_hash, []

        try:
            fp_hash, containing_branch_pairs = next(self.__match_log_to_filtered_reflogs(branch))
        except StopIteration:
            if upstream and self.__git.is_ancestor_or_equal(upstream.full_name(), branch.full_name()):
                debug(f"cannot find fork point, but {branch} is descendant of its upstream {upstream}; falling back to {upstream} as fork point")
                return self.__git.get_commit_hash_by_revision(upstream), []
            else:
                raise MacheteException(f"Cannot find fork point for branch `{branch}`")
        else:
            debug("commit {fp_hash} is the most recent point in history of {branch} to occur on "
                  "filtered reflog of any other branch or its remote counterpart "
                  f"(specifically: {' and '.join(map(utils.get_second, containing_branch_pairs))})")

            if upstream and self.__git.is_ancestor_or_equal(upstream.full_name(), branch.full_name()) and not self.__git.is_ancestor_or_equal(upstream.full_name(), fp_hash.full_name()):
                # That happens very rarely in practice (typically current head
                # of any branch, including upstream, should occur on the reflog
                # of this branch, thus is_ancestor(upstream, branch) should imply
                # is_ancestor(upstream, FP(branch)), but it's still possible in
                # case reflog of upstream is incomplete for whatever reason.
                debug(f"{upstream} is descendant of its upstream {branch}, but inferred fork point commit {fp_hash} is NOT a descendant of {upstream}; falling back to {upstream} as fork point")
                return self.__git.get_commit_hash_by_revision(upstream), []
            else:
                debug(f"choosing commit {fp_hash} as fork point")
                return fp_hash, containing_branch_pairs

    def fork_point(
            self,
            branch: LocalBranchShortName,
            use_overrides: bool,
            *,
            opt_no_detect_squash_merges: bool
    ) -> Optional[FullCommitHash]:
        hash, containing_branch_pairs = self.__fork_point_and_containing_branch_pairs(
            branch, use_overrides, opt_no_detect_squash_merges=opt_no_detect_squash_merges)
        return FullCommitHash.of(hash) if hash else None

    def diff(self, *, branch: Optional[LocalBranchShortName], opt_stat: bool) -> None:
        fp: FullCommitHash = self.fork_point(
            branch if branch else self.__git.get_current_branch(),
            use_overrides=True, opt_no_detect_squash_merges=False)
        self.__git.display_diff(
            branch=branch,
            fork_point=fp,
            format_with_stat=opt_stat)

    def log(self, branch: LocalBranchShortName) -> None:
        fork_point = self.fork_point(branch, use_overrides=True, opt_no_detect_squash_merges=False)
        self.__git.display_branch_history_from_fork_point(branch.full_name(), fork_point)

    def down(self, branch: LocalBranchShortName, pick_mode: bool) -> List[LocalBranchShortName]:
        self.expect_in_managed_branches(branch)
        dbs = self.__down_branches.get(branch)
        if not dbs:
            raise MacheteException(f"Branch `{branch}` has no downstream branch")
        elif len(dbs) == 1:
            return [dbs[0]]
        elif pick_mode:
            return [self.pick(dbs, "downstream branch")]
        else:
            return dbs

    def first_branch(self, branch: LocalBranchShortName) -> LocalBranchShortName:
        root = self.root_branch(branch, if_unmanaged=PICK_FIRST_ROOT)
        root_dbs = self.__down_branches.get(root)
        return root_dbs[0] if root_dbs else root

    def last_branch(self, branch: LocalBranchShortName) -> LocalBranchShortName:
        destination = self.root_branch(branch, if_unmanaged=PICK_LAST_ROOT)
        while self.__down_branches.get(destination):
            destination = self.__down_branches[destination][-1]
        return destination

    def next_branch(self, branch: LocalBranchShortName) -> LocalBranchShortName:
        self.expect_in_managed_branches(branch)
        index: int = self.managed_branches.index(branch) + 1
        if index == len(self.managed_branches):
            raise MacheteException(f"Branch `{branch}` has no successor")
        return self.managed_branches[index]

    def prev_branch(self, branch: LocalBranchShortName) -> LocalBranchShortName:
        self.expect_in_managed_branches(branch)
        index: int = self.managed_branches.index(branch) - 1
        if index == -1:
            raise MacheteException(f"Branch `{branch}` has no predecessor")
        return self.managed_branches[index]

    def root_branch(self, branch: LocalBranchShortName, if_unmanaged: int) -> LocalBranchShortName:
        if branch not in self.managed_branches:
            if self.__roots:
                if if_unmanaged == PICK_FIRST_ROOT:
                    warn(
                        f"{branch} is not a managed branch, assuming "
                        f"{self.__roots[0]} (the first root) instead as root")
                    return self.__roots[0]
                else:  # if_unmanaged == PICK_LAST_ROOT
                    warn(
                        f"{branch} is not a managed branch, assuming "
                        f"{self.__roots[-1]} (the last root) instead as root")
                    return self.__roots[-1]
            else:
                self.__raise_no_branches_error()
        upstream = self.up_branch.get(branch)
        while upstream:
            branch = upstream
            upstream = self.up_branch.get(branch)
        return branch

    def up(self, branch: LocalBranchShortName, prompt_if_inferred_msg: Optional[str],
           prompt_if_inferred_yes_opt_msg: Optional[str]) -> LocalBranchShortName:
        if branch in self.managed_branches:
            upstream = self.up_branch.get(branch)
            if upstream:
                return upstream
            else:
                raise MacheteException(f"Branch `{branch}` has no upstream branch")
        else:
            upstream = self.__infer_upstream(branch)
            if upstream:
                if prompt_if_inferred_msg:
                    if self.ask_if(
                            prompt_if_inferred_msg % (branch, upstream),
                            prompt_if_inferred_yes_opt_msg % (branch, upstream),
                            opt_yes=False
                    ) in ('y', 'yes'):
                        return upstream
                    raise MacheteException("Aborting.")
                else:
                    warn(
                        f"branch `{branch}` not found in the tree of branch "
                        f"dependencies; the upstream has been inferred to `{upstream}`")
                    return upstream
            else:
                raise MacheteException(
                    f"Branch `{branch}` not found in the tree of branch "
                    f"dependencies and its upstream could not be inferred")

    def get_slidable_branches(self) -> List[LocalBranchShortName]:
        return [branch for branch in self.managed_branches if branch in self.up_branch]

    def get_slidable_after(self, branch: LocalBranchShortName) -> List[LocalBranchShortName]:
        if branch in self.up_branch:
            dbs = self.__down_branches.get(branch)
            if dbs and len(dbs) == 1:
                return dbs
        return []

    def __is_merged_to_upstream(
            self, branch: LocalBranchShortName, *, opt_no_detect_squash_merges: bool) -> bool:
        if branch not in self.up_branch:
            return False
        return self.is_merged_to(
            branch,
            self.up_branch[branch],
            opt_no_detect_squash_merges=opt_no_detect_squash_merges)

    def __run_post_slide_out_hook(self, new_upstream: LocalBranchShortName, slid_out_branch: LocalBranchShortName,
                                  new_downstreams: List[LocalBranchShortName]) -> None:
        hook_path = self.__git.get_hook_path("machete-post-slide-out")
        if self.__git.check_hook_executable(hook_path):
            debug("running machete-post-slide-out hook ({hook_path})")
            new_downstreams_strings: List[str] = [str(db) for db in new_downstreams]
            exit_code = utils.run_cmd(hook_path, new_upstream, slid_out_branch, *new_downstreams_strings,
                                      cwd=self.__git.get_root_dir())
            if exit_code != 0:
                raise MacheteException(
                    f"The machete-post-slide-out hook exited with {exit_code}, aborting.\n")

    def squash(self, *, current_branch: LocalBranchShortName, opt_fork_point: AnyRevision) -> None:
        commits: List[GitLogEntry] = self.__git.get_commits_between(
            opt_fork_point, current_branch)
        if not commits:
            raise MacheteException(
                "No commits to squash. Use `-f` or `--fork-point` to specify the "
                "start of range of commits to squash.")
        if len(commits) == 1:
            print(f"Exactly one commit ({commits[0].short_hash}) to squash, ignoring.\n")
            print("Tip: use `-f` or `--fork-point` to specify where the range of "
                  "commits to squash starts.")
            return

        earliest_commit = commits[0]
        earliest_full_body = self.__git.get_commit_information(FullCommitHash.of(earliest_commit.hash), GitFormatPatterns.RAW_BODY).strip()
        # %ai for ISO-8601 format; %aE/%aN for respecting .mailmap; see `git rev-list --help`
        earliest_author_date = self.__git.get_commit_information(FullCommitHash.of(earliest_commit.hash), GitFormatPatterns.AUTHOR_DATE).strip()
        earliest_author_email = self.__git.get_commit_information(FullCommitHash.of(earliest_commit.hash), GitFormatPatterns.AUTHOR_EMAIL).strip()
        earliest_author_name = self.__git.get_commit_information(FullCommitHash.of(earliest_commit.hash), GitFormatPatterns.AUTHOR_NAME).strip()

        # Following the convention of `git cherry-pick`, `git commit --amend`, `git rebase` etc.,
        # let's retain the original author (only committer will be overwritten).
        author_env = dict(os.environ,
                          GIT_AUTHOR_DATE=earliest_author_date,
                          GIT_AUTHOR_EMAIL=earliest_author_email,
                          GIT_AUTHOR_NAME=earliest_author_name)
        # Using `git commit-tree` since it's cleaner than any high-level command
        # like `git merge --squash` or `git rebase --interactive`.
        # The tree (HEAD^{tree}) argument must be passed as first,
        # otherwise the entire `commit-tree` will fail on some ancient supported
        # versions of git (at least on v1.7.10).
        squashed_hash = FullCommitHash.of(self.__git.commit_tree_with_given_parent_and_message_and_env(
            opt_fork_point, earliest_full_body, author_env).strip())

        # This can't be done with `git reset` since it doesn't allow for a custom reflog message.
        # Even worse, reset's reflog message would be filtered out in our fork point algorithm,
        # so the squashed commit would not even be considered to "belong"
        # (in the FP sense) to the current branch's history.
        self.__git.update_head_ref_to_new_hash_with_reflog_subject(
            squashed_hash, f"squash: {earliest_commit.subject}")

        print(f"Squashed {len(commits)} commits:")
        print()
        for commit in commits:
            print(f"\t{commit.short_hash} {commit.subject}")

        print()
        print("To restore the original pre-squash commit, run:")
        print()
        print(fmt(f"\t`git reset {commits[-1].hash}`"))

    def filtered_reflog(self, branch: AnyBranchName) -> List[FullCommitHash]:
        def is_excluded_reflog_subject(hash_: str, gs_: str) -> bool:
            is_excluded = (gs_.startswith("branch: Created from") or
                           gs_ == f"branch: Reset to {branch}" or
                           gs_ == "branch: Reset to HEAD" or
                           gs_.startswith("reset: moving to ") or
                           gs_.startswith("fetch . ") or
                           # The rare case of a no-op rebase, the exact wording
                           # likely depends on git version
                           gs_ == f"rebase finished: {branch.full_name()} onto {hash_}" or
                           gs_ == f"rebase -i (finish): {branch.full_name()} onto {hash_}"
                           )
            if is_excluded:
                debug("skipping reflog entry")
            return is_excluded

        branch_reflog = self.__git.get_reflog(branch.full_name())
        if not branch_reflog:
            return []

        earliest_hash, earliest_gs = branch_reflog[-1]  # Note that the reflog is returned from latest to earliest entries.
        hashes_to_exclude = set()
        if earliest_gs.startswith("branch: Created from"):
            debug(f"skipping any reflog entry with the hash equal to the hash of the earliest (branch creation) entry: {earliest_hash}")
            hashes_to_exclude.add(earliest_hash)

        result = [hash for (hash, gs) in branch_reflog if
                  hash not in hashes_to_exclude and not is_excluded_reflog_subject(hash, gs)]
        debug("computed filtered reflog (= reflog without branch creation "
              "and branch reset events irrelevant for fork point/upstream inference): %s\n" % (", ".join(result) or "<empty>"))
        return result

    def sync_annotations_to_github_prs(self) -> None:
        remote, org, repo = self.__derive_remote_and_github_org_and_repo()
        current_user: Optional[str] = git_machete.github.derive_current_user_login()
        debug('Current GitHub user is ' + (current_user or '<none>'))
        pr: GitHubPullRequest
        all_prs: List[GitHubPullRequest] = derive_pull_requests(org, repo)
        self.__sync_annotations_to_definition_file(all_prs, current_user)

    def __sync_annotations_to_definition_file(self, prs: List[GitHubPullRequest], current_user: Optional[str] = None, verbose: bool = True) -> None:
        for pr in prs:
            if LocalBranchShortName.of(pr.head) in self.managed_branches:
                debug(f'{pr} corresponds to a managed branch')
                anno: str = f'PR #{pr.number}'
                if pr.user != current_user:
                    anno += f' ({pr.user})'
                upstream: Optional[LocalBranchShortName] = self.up_branch.get(LocalBranchShortName.of(pr.head))
                if pr.base != upstream:
                    warn(f'branch `{pr.head}` has a different base in PR #{pr.number} (`{pr.base}`) '
                         f'than in machete file (`{upstream or "<none, is a root>"}`)')
                    anno += f" WRONG PR BASE or MACHETE PARENT? PR has '{pr.base}'"
                if self.__annotations.get(LocalBranchShortName.of(pr.head)) != anno:
                    if verbose:
                        print(fmt(f'Annotating `{pr.head}` as `{anno}`'))
                    self.__annotations[LocalBranchShortName.of(pr.head)] = anno
            else:
                debug(f'{pr} does NOT correspond to a managed branch')
        self.save_definition_file()

    # Parse and evaluate direction against current branch for show/go commands
    def parse_direction(self, param: str, branch: LocalBranchShortName, allow_current: bool, down_pick_mode: bool) -> List[LocalBranchShortName]:
        if param in ("c", "current") and allow_current:
            return [self.__git.get_current_branch()]  # throws in case of detached HEAD, as in the spec
        elif param in ("d", "down"):
            return self.down(branch, pick_mode=down_pick_mode)
        elif param in ("f", "first"):
            return [self.first_branch(branch)]
        elif param in ("l", "last"):
            return [self.last_branch(branch)]
        elif param in ("n", "next"):
            return [self.next_branch(branch)]
        elif param in ("p", "prev"):
            return [self.prev_branch(branch)]
        elif param in ("r", "root"):
            return [self.root_branch(branch, if_unmanaged=PICK_FIRST_ROOT)]
        elif param in ("u", "up"):
            return [self.up(branch, prompt_if_inferred_msg=None, prompt_if_inferred_yes_opt_msg=None)]
        else:
            raise MacheteException(f"Invalid direction: `{param}`; expected: {allowed_directions(allow_current)}")

    def __match_log_to_filtered_reflogs(self, branch: LocalBranchShortName) -> Generator[Tuple[FullCommitHash, List[BranchPair]], None, None]:

        if branch not in self.__git.get_local_branches():
            raise MacheteException(f"`{branch}` is not a local branch")

        if self.__branch_pairs_by_hash_in_reflog is None:
            def generate_entries() -> Generator[Tuple[FullCommitHash, BranchPair], None, None]:
                for lb in self.__git.get_local_branches():
                    lb_hashes = set()
                    for hash_ in self.filtered_reflog(lb):
                        lb_hashes.add(hash_)
                        yield FullCommitHash.of(hash_), BranchPair(lb, lb)
                    remote_branch = self.__git.get_combined_counterpart_for_fetching_of_branch(lb)
                    if remote_branch:
                        for hash_ in self.filtered_reflog(remote_branch):
                            if hash_ not in lb_hashes:
                                yield FullCommitHash.of(hash_), BranchPair(lb, remote_branch)

            self.__branch_pairs_by_hash_in_reflog = {}
            for hash, branch_pair in generate_entries():
                if hash in self.__branch_pairs_by_hash_in_reflog:
                    # The practice shows that it's rather unlikely for a given
                    # commit to appear on filtered reflogs of two unrelated branches
                    # ("unrelated" as in, not a local branch and its remote
                    # counterpart) but we need to handle this case anyway.
                    self.__branch_pairs_by_hash_in_reflog[hash] += [branch_pair]
                else:
                    self.__branch_pairs_by_hash_in_reflog[hash] = [branch_pair]

            def log_result() -> Generator[str, None, None]:
                branch_pairs_: List[BranchPair]
                hash_: FullCommitHash
                for hash_, branch_pairs_ in self.__branch_pairs_by_hash_in_reflog.items():
                    def branch_pair_to_str(lb: str, lb_or_rb: str) -> str:
                        return lb if lb == lb_or_rb else f"{lb_or_rb} (remote counterpart of {lb})"

                    joined_branch_pairs = ", ".join(map(tupled(branch_pair_to_str), branch_pairs_))
                    yield dim(f"{hash_} => {joined_branch_pairs}")

            debug("branches containing the given hash in their filtered reflog: \n%s\n" % "\n".join(log_result()))

        branch_full_hash: FullCommitHash = self.__git.get_commit_hash_by_revision(branch)

        for hash in self.__git.spoonfeed_log_hashes(branch_full_hash):
            if hash in self.__branch_pairs_by_hash_in_reflog:
                # The entries must be sorted by lb_or_rb to make sure the
                # upstream inference is deterministic (and does not depend on the
                # order in which `generate_entries` iterated through the local branches).
                branch_pairs: List[BranchPair] = self.__branch_pairs_by_hash_in_reflog[hash]

                def lb_is_not_b(lb: str, lb_or_rb: str) -> bool:
                    return lb != branch

                containing_branch_pairs = sorted(filter(tupled(lb_is_not_b), branch_pairs), key=get_second)
                if containing_branch_pairs:
                    debug(f"commit {hash} found in filtered reflog of {' and '.join(map(get_second, branch_pairs))}")
                    yield hash, containing_branch_pairs
                else:
                    debug(f"commit {hash} found only in filtered reflog of {' and '.join(map(get_second, branch_pairs))}; ignoring")
            else:
                debug(f"commit {hash} not found in any filtered reflog")

    def __infer_upstream(self, branch: LocalBranchShortName, condition: Callable[[LocalBranchShortName], bool] = lambda upstream: True, reject_reason_message: str = "") -> Optional[LocalBranchShortName]:
        for hash, containing_branch_pairs in self.__match_log_to_filtered_reflogs(branch):
            debug(f"commit {hash} found in filtered reflog of {' and '.join(map(get_second, containing_branch_pairs))}")

            for candidate, original_matched_branch in containing_branch_pairs:
                if candidate != original_matched_branch:
                    debug(f"upstream candidate is {candidate}, which is the local counterpart of {original_matched_branch}")

                if condition(candidate):
                    debug(f"upstream candidate {candidate} accepted")
                    return candidate
                else:
                    debug(f"upstream candidate {candidate} rejected ({reject_reason_message})")
        return None

    @staticmethod
    def config_key_for_override_fork_point_to(branch: LocalBranchShortName) -> str:
        return f"machete.overrideForkPoint.{branch}.to"

    @staticmethod
    def config_key_for_override_fork_point_while_descendant_of(branch: LocalBranchShortName) -> str:
        return f"machete.overrideForkPoint.{branch}.whileDescendantOf"

    # Also includes config that is incomplete (only one entry out of two) or otherwise invalid.
    def has_any_fork_point_override_config(self, branch: LocalBranchShortName) -> bool:
        return (self.__git.get_config_attr_or_none(self.config_key_for_override_fork_point_to(branch)) or
                self.__git.get_config_attr_or_none(self.config_key_for_override_fork_point_while_descendant_of(branch))) is not None

    def __get_fork_point_override_data(self, branch: LocalBranchShortName) -> Optional[ForkPointOverrideData]:
        to_key = self.config_key_for_override_fork_point_to(branch)
        to = FullCommitHash.of(self.__git.get_config_attr_or_none(to_key) or "")
        while_descendant_of_key = self.config_key_for_override_fork_point_while_descendant_of(branch)
        while_descendant_of = FullCommitHash.of(self.__git.get_config_attr_or_none(while_descendant_of_key) or "")
        if not to and not while_descendant_of:
            return None
        if to and not while_descendant_of:
            warn(f"{to_key} config is set but {while_descendant_of_key} config is missing")
            return None
        if not to and while_descendant_of:
            warn(f"{while_descendant_of_key} config is set but {to_key} config is missing")
            return None

        to_hash: Optional[FullCommitHash] = self.__git.get_commit_hash_by_revision(to)
        while_descendant_of_hash: Optional[FullCommitHash] = self.__git.get_commit_hash_by_revision(while_descendant_of)
        if not to_hash or not while_descendant_of_hash:
            if not to_hash:
                warn(f"{to_key} config value `{to}` does not point to a valid commit")
            if not while_descendant_of_hash:
                warn(f"{while_descendant_of_key} config value `{while_descendant_of}` does not point to a valid commit")
            return None
        # This check needs to be performed every time the config is retrieved.
        # We can't rely on the values being validated in set_fork_point_override(),
        # since the config could have been modified outside of git-machete.
        if not self.__git.is_ancestor_or_equal(to_hash.full_name(), while_descendant_of_hash.full_name()):
            warn(
                f"commit {self.__git.get_short_commit_hash_by_revision(to)} pointed by {to_key} config "
                f"is not an ancestor of commit {self.__git.get_short_commit_hash_by_revision(while_descendant_of)} "
                f"pointed by {while_descendant_of_key} config")
            return None
        return ForkPointOverrideData(to_hash, while_descendant_of_hash)

    def __get_overridden_fork_point(self, branch: LocalBranchShortName) -> Optional[FullCommitHash]:
        override_data: ForkPointOverrideData = self.__get_fork_point_override_data(branch)
        if not override_data:
            return None

        to, while_descendant_of = override_data.to_hash, override_data.while_descendant_of_hash
        # Note that this check is distinct from the is_ancestor check performed in
        # get_fork_point_override_data.
        # While the latter checks the sanity of fork point override configuration,
        # the former checks if the override still applies to wherever the given
        # branch currently points.
        if not self.__git.is_ancestor_or_equal(while_descendant_of.full_name(), branch.full_name()):
            warn(fmt(
                f"since branch <b>{branch}</b> is no longer a descendant of commit {self.__git.get_short_commit_hash_by_revision(while_descendant_of)}, ",
                f"the fork point override to commit {self.__git.get_short_commit_hash_by_revision(to)} no longer applies.\n",
                "Consider running:\n",
                f"  `git machete fork-point --unset-override {branch}`\n"))
            return None
        debug(f"since branch {branch} is descendant of while_descendant_of={while_descendant_of}, fork point of {branch} is overridden to {to}")
        return to

    def unset_fork_point_override(self, branch: LocalBranchShortName) -> None:
        self.__git.unset_config_attr(self.config_key_for_override_fork_point_to(branch))
        self.__git.unset_config_attr(self.config_key_for_override_fork_point_while_descendant_of(branch))

    def set_fork_point_override(self, branch: LocalBranchShortName, to_revision: AnyRevision) -> None:
        if branch not in self.__git.get_local_branches():
            raise MacheteException(f"`{branch}` is not a local branch")
        to_hash = self.__git.get_commit_hash_by_revision(to_revision)
        if not to_hash:
            raise MacheteException(f"Cannot find revision {to_revision}")
        if not self.__git.is_ancestor_or_equal(to_hash.full_name(), branch.full_name()):
            raise MacheteException(
                f"Cannot override fork point: {self.__git.get_revision_repr(to_revision)} is not an ancestor of {branch}")

        to_key = self.config_key_for_override_fork_point_to(branch)
        self.__git.set_config_attr(to_key, to_hash)

        while_descendant_of_key = self.config_key_for_override_fork_point_while_descendant_of(branch)
        branch_hash = self.__git.get_commit_hash_by_revision(branch)
        self.__git.set_config_attr(while_descendant_of_key, branch_hash)

        print(fmt(f"Fork point for <b>{branch}</b> is overridden to "
                  f"<b>{self.__git.get_revision_repr(to_revision)}</b>.\n",
                  f"This applies as long as {branch} points to (or is descendant of)"
                  " its current head (commit "
                  f"{self.__git.get_short_commit_hash_by_revision(branch_hash)}).\n\n",
                  f"This information is stored under git config keys:\n"
                  f"  * `{to_key}`\n"
                  f"  * `{while_descendant_of_key}`\n\n",
                  "To unset this override, use:\n  `git machete fork-point "
                  f"--unset-override {branch}`"))

    def __pick_remote(
            self,
            *,
            branch: LocalBranchShortName,
            is_called_from_traverse: bool,
            is_called_from_create_pr: bool,
            opt_push_untracked: bool,
            opt_push_tracked: bool,
            opt_yes: bool
    ) -> None:
        rems = self.__git.get_remotes()
        print("\n".join(f"[{index + 1}] {rem}" for index, rem in enumerate(rems)))
        msg = f"Select number 1..{len(rems)} to specify the destination remote " \
              "repository, or 'n' to skip this branch, or " \
              "'q' to quit the traverse: " if is_called_from_traverse \
              else f"Select number 1..{len(rems)} to specify the destination remote " \
                   "repository, or 'q' to quit creating pull request: "

        ans = input(msg).lower()
        if ans in ('q', 'quit'):
            raise StopInteraction
        try:
            index = int(ans) - 1
            if index not in range(len(rems)):
                raise MacheteException(f"Invalid index: {index + 1}")
            self.handle_untracked_branch(
                new_remote=rems[index],
                branch=branch,
                is_called_from_traverse=is_called_from_traverse,
                is_called_from_create_pr=is_called_from_create_pr,
                opt_push_untracked=opt_push_untracked,
                opt_push_tracked=opt_push_tracked,
                opt_yes=opt_yes)
        except ValueError:
            if not is_called_from_traverse:
                raise MacheteException('Could not establish remote repository, pull request creation interrupted.')

    def handle_untracked_branch(
            self,
            *,
            new_remote: str,
            branch: LocalBranchShortName,
            is_called_from_traverse: bool,
            is_called_from_create_pr: bool,
            opt_push_untracked: bool,
            opt_push_tracked: bool,
            opt_yes: bool
    ) -> None:
        rems: List[str] = self.__git.get_remotes()
        can_pick_other_remote = len(rems) > 1 and not is_called_from_create_pr
        other_remote_choice = "o[ther-remote]" if can_pick_other_remote else ""
        remote_branch = RemoteBranchShortName.of(f"{new_remote}/{branch}")
        if not self.__git.get_commit_hash_by_revision(remote_branch):
            choices = get_pretty_choices(*('y', 'N', 'q', 'yq', other_remote_choice) if is_called_from_traverse else ('y', 'Q', other_remote_choice))
            ask_message = f"Push untracked branch {bold(branch)} to {bold(new_remote)}?" + choices
            ask_opt_yes_message = f"Pushing untracked branch {bold(branch)} to {bold(new_remote)}..."
            ans = self.ask_if(
                ask_message,
                ask_opt_yes_message,
                opt_yes=opt_yes,
                override_answer=None if opt_push_untracked else "N")
            if is_called_from_traverse:
                if ans in ('y', 'yes', 'yq'):
                    self.__git.push(new_remote, branch)
                    if ans == 'yq':
                        raise StopInteraction
                    self.flush_caches()
                elif can_pick_other_remote and ans in ('o', 'other'):
                    self.__pick_remote(
                        branch=branch,
                        is_called_from_traverse=is_called_from_traverse,
                        is_called_from_create_pr=is_called_from_create_pr,
                        opt_push_untracked=opt_push_untracked,
                        opt_push_tracked=opt_push_tracked,
                        opt_yes=opt_yes)
                elif ans in ('q', 'quit'):
                    raise StopInteraction
                return
            else:
                if ans in ('y', 'yes'):
                    self.__git.push(new_remote, branch)
                    self.flush_caches()
                elif can_pick_other_remote and ans in ('o', 'other'):
                    self.__pick_remote(
                        branch=branch,
                        is_called_from_traverse=is_called_from_traverse,
                        is_called_from_create_pr=is_called_from_create_pr,
                        opt_push_untracked=opt_push_untracked,
                        opt_push_tracked=opt_push_tracked,
                        opt_yes=opt_yes)
                elif ans in ('q', 'quit'):
                    raise StopInteraction
                else:
                    raise MacheteException(f'Cannot create pull request from untracked branch `{branch}`')
                return

        relation: int = self.__git.get_relation_to_remote_counterpart(branch, remote_branch)

        message: str = {
            SyncToRemoteStatuses.IN_SYNC_WITH_REMOTE:
                f"Branch {bold(branch)} is untracked, but its remote counterpart candidate {bold(remote_branch)} already exists and both branches point to the same commit.",
            SyncToRemoteStatuses.BEHIND_REMOTE:
                f"Branch {bold(branch)} is untracked, but its remote counterpart candidate {bold(remote_branch)} already exists and is ahead of {bold(branch)}.",
            SyncToRemoteStatuses.AHEAD_OF_REMOTE:
                f"Branch {bold(branch)} is untracked, but its remote counterpart candidate {bold(remote_branch)} already exists and is behind {bold(branch)}.",
            SyncToRemoteStatuses.DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                f"Branch {bold(branch)} is untracked, it diverged from its remote counterpart candidate {bold(remote_branch)}, and has {bold('older')} commits than {bold(remote_branch)}.",
            SyncToRemoteStatuses.DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                f"Branch {bold(branch)} is untracked, it diverged from its remote counterpart candidate {bold(remote_branch)}, and has {bold('newer')} commits than {bold(remote_branch)}."
        }[SyncToRemoteStatuses(relation)]

        ask_message, ask_opt_yes_message = {
            SyncToRemoteStatuses.IN_SYNC_WITH_REMOTE: (
                f"Set the remote of {bold(branch)} to {bold(new_remote)} without pushing or pulling?" + get_pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Setting the remote of {bold(branch)} to {bold(new_remote)}..."
            ),
            SyncToRemoteStatuses.BEHIND_REMOTE: (
                f"Pull {bold(branch)} (fast-forward only) from {bold(new_remote)}?" + get_pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Pulling {bold(branch)} (fast-forward only) from {bold(new_remote)}..."
            ),
            SyncToRemoteStatuses.AHEAD_OF_REMOTE: (
                f"Push branch {bold(branch)} to {bold(new_remote)}?" + get_pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Pushing branch {bold(branch)} to {bold(new_remote)}..."
            ),
            SyncToRemoteStatuses.DIVERGED_FROM_AND_OLDER_THAN_REMOTE: (
                f"Reset branch {bold(branch)} to the commit pointed by {bold(remote_branch)}?" + get_pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Resetting branch {bold(branch)} to the commit pointed by {bold(remote_branch)}..."
            ),
            SyncToRemoteStatuses.DIVERGED_FROM_AND_NEWER_THAN_REMOTE: (
                f"Push branch {bold(branch)} with force-with-lease to {bold(new_remote)}?" + get_pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Pushing branch {bold(branch)} with force-with-lease to {bold(new_remote)}..."
            )
        }[SyncToRemoteStatuses(relation)]

        override_answer: Optional[str] = {
            SyncToRemoteStatuses.IN_SYNC_WITH_REMOTE: None,
            SyncToRemoteStatuses.BEHIND_REMOTE: None,
            SyncToRemoteStatuses.AHEAD_OF_REMOTE: None if opt_push_tracked else "N",
            SyncToRemoteStatuses.DIVERGED_FROM_AND_OLDER_THAN_REMOTE: None,
            SyncToRemoteStatuses.DIVERGED_FROM_AND_NEWER_THAN_REMOTE: None if opt_push_tracked else "N",
        }[SyncToRemoteStatuses(relation)]

        yes_action: Callable[[], None] = {
            SyncToRemoteStatuses.IN_SYNC_WITH_REMOTE: lambda: self.__git.set_upstream_to(remote_branch),
            SyncToRemoteStatuses.BEHIND_REMOTE: lambda: self.__git.pull_ff_only(new_remote, remote_branch),
            SyncToRemoteStatuses.AHEAD_OF_REMOTE: lambda: self.__git.push(new_remote, branch),
            SyncToRemoteStatuses.DIVERGED_FROM_AND_OLDER_THAN_REMOTE: lambda: self.__git.reset_keep(remote_branch),
            SyncToRemoteStatuses.DIVERGED_FROM_AND_NEWER_THAN_REMOTE: lambda: self.__git.push(
                new_remote, branch, force_with_lease=True)
        }[SyncToRemoteStatuses(relation)]

        print(message)
        ans = self.ask_if(ask_message, ask_opt_yes_message, override_answer=override_answer, opt_yes=opt_yes)
        if ans in ('y', 'yes', 'yq'):
            yes_action()
            if ans == 'yq':
                raise StopInteraction
            self.flush_caches()
        elif can_pick_other_remote and ans in ('o', 'other'):
            self.__pick_remote(
                branch=branch,
                is_called_from_traverse=is_called_from_traverse,
                is_called_from_create_pr=is_called_from_create_pr,
                opt_push_untracked=opt_push_untracked,
                opt_push_tracked=opt_push_tracked,
                opt_yes=opt_yes)
        elif ans in ('q', 'quit'):
            raise StopInteraction

    def is_merged_to(self, branch: LocalBranchShortName, upstream: AnyBranchName, *, opt_no_detect_squash_merges: bool) -> bool:
        if self.__git.is_ancestor_or_equal(branch.full_name(), upstream.full_name()):
            # If branch is ancestor of or equal to the upstream, we need to distinguish between the
            # case of branch being "recently" created from the upstream and the case of
            # branch being fast-forward-merged to the upstream.
            # The applied heuristics is to check if the filtered reflog of the branch
            # (reflog stripped of trivial events like branch creation, reset etc.)
            # is non-empty.
            return bool(self.filtered_reflog(branch))
        elif opt_no_detect_squash_merges:
            return False
        else:
            # In the default mode.
            # If a commit with an identical tree state to branch is reachable from upstream,
            # then branch may have been squashed or rebase-merged into upstream.
            return self.__git.is_equivalent_tree_reachable(branch, upstream)

    @staticmethod
    def ask_if(
            msg: str,
            opt_yes_msg: Optional[str],
            opt_yes: bool,
            override_answer: Optional[str] = None,
            apply_fmt: bool = True,
            verbose: bool = True
    ) -> str:
        if override_answer:
            return override_answer
        if opt_yes and opt_yes_msg:
            if verbose:
                print(fmt(opt_yes_msg) if apply_fmt else opt_yes_msg)
            return 'y'
        return input(fmt(msg) if apply_fmt else msg).lower()

    @staticmethod
    def pick(choices: List[LocalBranchShortName], name: str, apply_fmt: bool = True) -> LocalBranchShortName:
        xs: str = "".join(f"[{index + 1}] {x}\n" for index, x in enumerate(choices))
        msg: str = xs + f"Specify {name} or hit <return> to skip: "
        try:
            ans: str = input(fmt(msg) if apply_fmt else msg)
            if not ans:
                sys.exit(0)
            index: int = int(ans) - 1
        except ValueError:
            sys.exit(1)
        if index not in range(len(choices)):
            raise MacheteException(f"Invalid index: {index + 1}")
        return choices[index]

    def flush_caches(self) -> None:
        self.__branch_pairs_by_hash_in_reflog = None
        self.__git.flush_caches()

    def check_that_fork_point_is_ancestor_or_equal_to_tip_of_branch(
            self, fork_point_hash: AnyRevision, branch: AnyBranchName) -> None:
        if not self.__git.is_ancestor_or_equal(
                earlier_revision=fork_point_hash.full_name(),
                later_revision=branch.full_name()):
            raise MacheteException(
                f"Fork point {fork_point_hash} is not ancestor of or the tip "
                f"of the {branch} branch.")

    def checkout_github_prs(self,
                            pr_nos: Optional[List[int]],
                            *,
                            all_opened_prs: bool = False,
                            my_opened_prs: bool = False,
                            opened_by: str = None,
                            verbose: bool = False,
                            fail_on_missing_current_user_for_my_opened_prs: bool = True
                            ) -> None:
        print(bold('Checking for open GitHub PRs...'))
        org: str
        repo: str
        remote: str
        remote, org, repo = self.__derive_remote_and_github_org_and_repo()
        current_user: Optional[str] = git_machete.github.derive_current_user_login()
        if not current_user and my_opened_prs:
            msg = ("Could not determine current user name, please check that the GitHub API token provided by one of the: "
                   f"{get_github_token_possible_providers()}is valid.")
            if fail_on_missing_current_user_for_my_opened_prs:
                warn(msg)
                return
            else:
                raise MacheteException(msg)
        all_open_prs: List[GitHubPullRequest] = derive_pull_requests(org, repo)
        applicable_prs: List[GitHubPullRequest] = self.__get_applicable_pull_requests(pr_nos,
                                                                                      all_opened_prs_from_github=all_open_prs,
                                                                                      org=org,
                                                                                      repo=repo,
                                                                                      all=all_opened_prs,
                                                                                      my=my_opened_prs,
                                                                                      by=opened_by,
                                                                                      user=current_user)

        debug(f'organization is {org}, repository is {repo}')
        if verbose:
            print(f"Fetching {remote}...")
        self.__git.fetch_remote(remote)

        pr: Optional[GitHubPullRequest] = None
        checked_out_prs: List[GitHubPullRequest] = []
        for pr in sorted(applicable_prs, key=lambda x: x.number):
            if pr.full_repository_name:
                if '/'.join([remote, pr.head]) not in self.__git.get_remote_branches():
                    remote_already_added: Optional[str] = self.__get_added_remote_name_or_none(pr.repository_url)
                    if not remote_already_added:
                        remote_from_pr: str = pr.full_repository_name.split('/')[0]
                        if remote_from_pr not in self.__git.get_remotes():
                            self.__git.add_remote(remote_from_pr, pr.repository_url)
                        remote_to_fetch: str = remote_from_pr
                    else:
                        remote_to_fetch = remote_already_added
                    if remote != remote_to_fetch:
                        if verbose:
                            print(f"Fetching {remote_to_fetch}...")
                        self.__git.fetch_remote(remote_to_fetch)
                    if '/'.join([remote_to_fetch, pr.head]) not in self.__git.get_remote_branches():
                        raise MacheteException(f"Could not check out PR #{pr.number} because its head branch `{pr.head}` is already deleted from `{remote_to_fetch}`.")
            else:
                warn(f'Pull request #{pr.number} comes from fork and its repository is already deleted. No remote tracking data will be set up for `{pr.head}` branch.')
                if verbose:
                    print(fmt(f"Checking out `{pr.head}` locally..."))
                checkout_pr_refs(self.__git, remote, pr.number, LocalBranchShortName.of(pr.head))
                self.flush_caches()
            if pr.state == 'closed':
                warn(f'Pull request #{pr.number} is already closed.')
            debug(f'found {pr}')

            path: List[LocalBranchShortName] = self.__get_path_from_pr_chain(pr, all_open_prs)
            reversed_path: List[LocalBranchShortName] = path[::-1]  # need to add from root downwards
            for index, branch in enumerate(reversed_path):
                if branch not in self.managed_branches:
                    if index == 0:
                        self.add(
                            branch=branch,
                            opt_as_root=True,
                            opt_onto=None,
                            opt_yes=True,
                            verbose=verbose,
                            switch_head_if_new_branch=False)
                    else:
                        self.add(
                            branch=branch,
                            opt_onto=reversed_path[index - 1],
                            opt_as_root=False,
                            opt_yes=True,
                            verbose=verbose,
                            switch_head_if_new_branch=False)
                    if pr not in checked_out_prs:
                        print(fmt(f"Pull request `#{pr.number}` checked out at local branch `{pr.head}`"))
                        checked_out_prs.append(pr)

        debug('Current GitHub user is ' + (current_user or '<none>'))
        self.__sync_annotations_to_definition_file(all_open_prs, current_user, verbose=verbose)
        if pr and len(checked_out_prs) == 1:
            self.__git.checkout(LocalBranchShortName.of(pr.head))
            if verbose:
                print(fmt(f"Switched to local branch `{pr.head}`"))

    @staticmethod
    def __get_path_from_pr_chain(current_pr: GitHubPullRequest, all_open_prs: List[GitHubPullRequest]) -> List[LocalBranchShortName]:
        path: List[LocalBranchShortName] = [LocalBranchShortName.of(current_pr.head)]
        while current_pr:
            path.append(LocalBranchShortName.of(current_pr.base))
            current_pr = utils.find_or_none(lambda x: x.head == current_pr.base, all_open_prs)
        return path

    @staticmethod
    def __get_applicable_pull_requests(prs_list: Optional[List[int]],
                                       all_opened_prs_from_github: List[GitHubPullRequest],
                                       org: str,
                                       repo: str,
                                       all: bool,
                                       my: bool,
                                       by: Optional[str],
                                       user: Optional[str]) -> List[GitHubPullRequest]:
        result: List[GitHubPullRequest] = []
        if prs_list:
            for pr_no in prs_list:
                _pr: Optional[GitHubPullRequest] = utils.find_or_none(lambda x: x.number == pr_no,
                                                                      all_opened_prs_from_github)
                if _pr:
                    result.append(_pr)
                else:
                    pr_from_github = get_pull_request_by_number_or_none(pr_no, org, repo)
                    if pr_from_github:
                        result.append(pr_from_github)
                    else:
                        raise MacheteException(f"PR #{pr_no} is not found in repository `{org}/{repo}`")
            if not result:
                raise MacheteException(
                    f"Given PRs: {', '.join(map(str, prs_list))} are not found in repository `{org}/{repo}`")
            return result
        if all:
            if not all_opened_prs_from_github:
                warn(f"Currently there are no pull requests opened in repository `{org}/{repo}`")
                return []
            return all_opened_prs_from_github
        elif my and user:
            result = [pr for pr in all_opened_prs_from_github if pr.user == user]
            if not result:
                warn(f"Current user `{user}` has no open pull request in repository `{org}/{repo}`")
                return []
            return result
        elif by:
            result = [pr for pr in all_opened_prs_from_github if pr.user == by]
            if not result:
                warn(f"User `{by}` has no open pull request in repository `{org}/{repo}`")
                return []
            return result
        return []

    def __get_added_remote_name_or_none(self, remote_url: str) -> Optional[str]:
        """
        Function to check if remote is added locally by its url,
        because it may happen that remote is already added under a name different from the name of organization on GitHub
        """
        url_for_remote: Dict[str, str] = {
            remote: self.__git.get_url_of_remote(remote) for remote in self.__git.get_remotes()
        }

        for remote, url in url_for_remote.items():
            url = url if url.endswith('.git') else url + '.git'
            remote_url = remote_url if remote_url.endswith('.git') else remote_url + '.git'
            if is_github_remote_url(url) and get_parsed_github_remote_url(url, remote) == get_parsed_github_remote_url(remote_url, remote):
                return remote
        return None

    def retarget_github_pr(self, head: LocalBranchShortName) -> None:
        org: str
        repo: str
        _, org, repo = self.__derive_remote_and_github_org_and_repo()

        debug(f'organization is {org}, repository is {repo}')

        pr: Optional[GitHubPullRequest] = derive_pull_request_by_head(org, repo, head)
        if not pr:
            raise MacheteException(f'No PR is opened in `{org}/{repo}` for branch `{head}`')
        debug(f'found {pr}')

        new_base: Optional[LocalBranchShortName] = self.up_branch.get(LocalBranchShortName.of(head))
        if not new_base:
            raise MacheteException(
                f'Branch `{head}` does not have a parent branch (it is a root) '
                f'even though there is an open PR #{pr.number} to `{pr.base}`.\n'
                'Consider modifying the branch definition file (`git machete edit`)'
                f' so that `{head}` is a child of `{pr.base}`.')

        if pr.base != new_base:
            set_base_of_pull_request(org, repo, pr.number, base=new_base)
            print(fmt(f'The base branch of PR #{pr.number} has been switched to `{new_base}`'))
        else:
            print(fmt(f'The base branch of PR #{pr.number} is already `{new_base}`'))

    def __derive_remote_and_github_org_and_repo(self) -> RemoteAndOrganizationAndRepository:
        remote_and_organization_and_repository_for_custom_url = self.__get_remote_and_organization_and_repository_name_for_custom_url()
        if all(remote_and_organization_and_repository_for_custom_url):
            return remote_and_organization_and_repository_for_custom_url

        url_for_remote: Dict[str, str] = {
            remote: self.__git.get_url_of_remote(remote) for remote in self.__git.get_remotes()
        }
        if not url_for_remote:
            raise MacheteException(fmt('No remotes defined for this repository (see `git remote`)'))

        remote_and_github_org_and_repo: Dict[str, RemoteAndOrganizationAndRepository] = {
            remote: get_parsed_github_remote_url(url, remote) for remote, url in url_for_remote.items() if is_github_remote_url(url)
        }
        if not remote_and_github_org_and_repo:
            raise MacheteException(
                fmt('Remotes are defined for this repository, but none of them '
                    'corresponds to GitHub (see `git remote -v` for details). \n'
                    'It is possible that you are using custom GitHub URL.\n'
                    'If that is the case, you can provide repository information explicitly, via these 3 git config keys: '
                    '`machete.github.{remote,organization,repository}`\n'))

        if len(remote_and_github_org_and_repo) == 1:
            return remote_and_github_org_and_repo[list(remote_and_github_org_and_repo.keys())[0]]

        if 'origin' in remote_and_github_org_and_repo:
            return remote_and_github_org_and_repo['origin']

        raise MacheteException(
            f'Multiple non-origin remotes correspond to GitHub in this repository: '
            f'{", ".join(remote_and_github_org_and_repo.keys())}, aborting. \n'
            f'You can also select the repository by providing 3 git config keys: '
            '`machete.github.{remote,organization,repository}`\n')

    def __get_remote_and_organization_and_repository_name_for_custom_url(self) -> RemoteAndOrganizationAndRepository:
        return RemoteAndOrganizationAndRepository(remote=self.__git.get_config_attr_or_none("machete.github.remote"),
                                                  organization=self.__git.get_config_attr_or_none("machete.github.organization"),
                                                  repository=self.__git.get_config_attr_or_none("machete.github.repository"))

    def create_github_pr(
            self, *, head: LocalBranchShortName, opt_draft: bool, opt_onto: Optional[LocalBranchShortName]) -> None:
        # first make sure that head branch is synced with remote
        self.__sync_before_creating_pr(opt_onto=opt_onto, opt_yes=False)
        self.flush_caches()

        base: Optional[LocalBranchShortName] = self.up_branch.get(LocalBranchShortName.of(head))
        if not base:
            raise MacheteException(f'Could not determine base branch for PR. Branch `{head}` is a root branch.')
        org: str
        repo: str
        remote, org, repo = self.__derive_remote_and_github_org_and_repo()
        print(f"Fetching {remote}...")
        self.__git.fetch_remote(remote)
        if '/'.join([remote, base]) not in self.__git.get_remote_branches():
            warn(f'Base branch for this PR (`{base}`) is not found on remote, pushing...')
            self.handle_untracked_branch(
                branch=base,
                new_remote=remote,
                is_called_from_traverse=False,
                is_called_from_create_pr=True,
                opt_push_tracked=False,
                opt_push_untracked=True,
                opt_yes=False)

        current_user: Optional[str] = git_machete.github.derive_current_user_login()
        debug('organization is {org}, repository is {repo}')
        debug('current GitHub user is ' + (current_user or '<none>'))

        fork_point = self.fork_point(head, use_overrides=True, opt_no_detect_squash_merges=False)
        if not fork_point:
            raise MacheteException(f"Could not find a fork-point for branch {head}.")
        commits: List[GitLogEntry] = self.__git.get_commits_between(fork_point, head)
        description_path = self.__git.get_main_git_subpath('info', 'description')
        description: str = utils.slurp_file_or_empty(description_path)

        ok_str = ' <green><b>OK</b></green>'
        print(fmt(f'Creating a {"draft " if opt_draft else ""}PR from `{head}` to `{base}`...'), end='', flush=True)
        pr: GitHubPullRequest = create_pull_request(org, repo, head=head, base=base, title=commits[0].subject,
                                                    description=description, draft=opt_draft)
        print(fmt(f'{ok_str}, see <b>{pr.html_url}</b>'))

        milestone_path: str = self.__git.get_main_git_subpath('info', 'milestone')
        milestone: str = utils.slurp_file_or_empty(milestone_path).strip()
        if milestone:
            print(fmt(f'Setting milestone of PR #{pr.number} to {milestone}...'), end='', flush=True)
            set_milestone_of_pull_request(org, repo, pr.number, milestone=milestone)
            print(fmt(ok_str))

        if current_user:
            print(fmt(f'Adding `{current_user}` as assignee to PR #{pr.number}...'), end='', flush=True)
            add_assignees_to_pull_request(org, repo, pr.number, [current_user])
            print(fmt(ok_str))

        reviewers_path = self.__git.get_main_git_subpath('info', 'reviewers')
        reviewers: List[str] = utils.get_non_empty_lines(utils.slurp_file_or_empty(reviewers_path))
        if reviewers:
            print(
                fmt(f'Adding {", ".join(f"`{reviewer}`" for reviewer in reviewers)} as reviewer{"s" if len(reviewers) > 1 else ""} to PR #{pr.number}...'),
                end='', flush=True)
            try:
                add_reviewers_to_pull_request(org, repo, pr.number, reviewers)
            except UnprocessableEntityHTTPError as e:
                if 'Reviews may only be requested from collaborators.' in e.msg:
                    warn(f"There are some invalid reviewers in {self.__git.get_main_git_subpath('info', 'reviewers')} file.\n"
                         "Skipping adding reviewers to pull request.")
                else:
                    raise e
            print(fmt(ok_str))

        self.__annotations[head] = f'PR #{pr.number}'
        self.save_definition_file()

    def __handle_diverged_and_newer_state(
            self,
            *,
            current_branch: LocalBranchShortName,
            remote: str,
            is_called_from_traverse: bool = True,
            opt_push_tracked: bool,
            opt_yes: bool
    ) -> None:
        self.__print_new_line(False)
        remote_branch = self.__git.get_strict_counterpart_for_fetching_of_branch(current_branch)
        choices = get_pretty_choices(*('y', 'N', 'q', 'yq') if is_called_from_traverse else ('y', 'N', 'q'))
        ans = self.ask_if(
            f"Branch {bold(current_branch)} diverged from (and has newer commits than) its remote counterpart {bold(remote_branch)}.\n"
            f"Push {bold(current_branch)} with force-with-lease to {bold(remote)}?" + choices,
            f"Branch {bold(current_branch)} diverged from (and has newer commits than) its remote counterpart {bold(remote_branch)}.\n"
            f"Pushing {bold(current_branch)} with force-with-lease to {bold(remote)}...",
            override_answer=None if opt_push_tracked else "N", opt_yes=opt_yes)
        if ans in ('y', 'yes', 'yq'):
            self.__git.push(remote, current_branch, force_with_lease=True)
            if ans == 'yq':
                if is_called_from_traverse:
                    raise StopInteraction
            self.flush_caches()
        elif ans in ('q', 'quit'):
            raise StopInteraction

    def __handle_untracked_state(
            self,
            *,
            branch: LocalBranchShortName,
            is_called_from_traverse: bool,
            opt_push_tracked: bool,
            opt_push_untracked: bool,
            opt_yes: bool
    ) -> None:
        rems: List[str] = self.__git.get_remotes()
        rmt: Optional[str] = self.__git.get_inferred_remote_for_fetching_of_branch(branch)
        self.__print_new_line(False)
        if rmt:
            self.handle_untracked_branch(
                new_remote=rmt,
                branch=branch,
                is_called_from_traverse=is_called_from_traverse,
                is_called_from_create_pr=False,
                opt_push_untracked=opt_push_untracked,
                opt_push_tracked=opt_push_tracked,
                opt_yes=opt_yes)
        elif len(rems) == 1:
            self.handle_untracked_branch(
                new_remote=rems[0],
                branch=branch,
                is_called_from_traverse=is_called_from_traverse,
                is_called_from_create_pr=False,
                opt_push_untracked=opt_push_untracked,
                opt_push_tracked=opt_push_tracked,
                opt_yes=opt_yes)
        elif "origin" in rems:
            self.handle_untracked_branch(
                new_remote="origin",
                branch=branch,
                is_called_from_traverse=is_called_from_traverse,
                is_called_from_create_pr=False,
                opt_push_untracked=opt_push_untracked,
                opt_push_tracked=opt_push_tracked,
                opt_yes=opt_yes)
        else:
            # We know that there is at least 1 remote, otherwise 's' would be 'NO_REMOTES'
            print(fmt(f"Branch `{bold(branch)}` is untracked and there's no `{bold('origin')}` repository."))
            self.__pick_remote(
                branch=branch,
                is_called_from_traverse=is_called_from_traverse,
                is_called_from_create_pr=False,
                opt_push_untracked=opt_push_untracked,
                opt_push_tracked=opt_push_tracked,
                opt_yes=opt_yes)

    def __handle_ahead_state(
            self,
            *,
            current_branch: LocalBranchShortName,
            remote: str,
            is_called_from_traverse: bool,
            opt_push_tracked: bool,
            opt_yes: bool
    ) -> None:
        self.__print_new_line(False)
        choices = get_pretty_choices(*('y', 'N', 'q', 'yq') if is_called_from_traverse else ('y', 'N', 'q'))
        ans = self.ask_if(
            f"Push {bold(current_branch)} to {bold(remote)}?" + choices,
            f"Pushing {bold(current_branch)} to {bold(remote)}...",
            override_answer=None if opt_push_tracked else "N",
            opt_yes=opt_yes
        )
        if ans in ('y', 'yes', 'yq'):
            self.__git.push(remote, current_branch)
            if ans == 'yq' and is_called_from_traverse:
                raise StopInteraction
            self.flush_caches()
        elif ans in ('q', 'quit'):
            raise StopInteraction

    def __handle_diverged_and_older_state(self, branch: LocalBranchShortName, opt_yes: bool) -> None:
        self.__print_new_line(False)
        remote_branch = self.__git.get_strict_counterpart_for_fetching_of_branch(branch)
        ans = self.ask_if(
            f"Branch {bold(branch)} diverged from (and has older commits than) its remote counterpart {bold(remote_branch)}.\nReset branch {bold(branch)} to the commit pointed by {bold(remote_branch)}?" + get_pretty_choices(
                'y', 'N', 'q', 'yq'),
            f"Branch {bold(branch)} diverged from (and has older commits than) its remote counterpart {bold(remote_branch)}.\nResetting branch {bold(branch)} to the commit pointed by {bold(remote_branch)}...",
            opt_yes=opt_yes)
        if ans in ('y', 'yes', 'yq'):
            self.__git.reset_keep(remote_branch)
            if ans == 'yq':
                raise StopInteraction
            self.flush_caches()
        elif ans in ('q', 'quit'):
            raise StopInteraction

    def __handle_behind_state(self, branch: LocalBranchShortName, remote: str, opt_yes: bool) -> None:
        remote_branch = self.__git.get_strict_counterpart_for_fetching_of_branch(branch)
        ans = self.ask_if(
            f"Branch {bold(branch)} is behind its remote counterpart {bold(remote_branch)}.\n"
            f"Pull {bold(branch)} (fast-forward only) from {bold(remote)}?" + get_pretty_choices('y', 'N', 'q', 'yq'),
            f"Branch {bold(branch)} is behind its remote counterpart {bold(remote_branch)}.\nPulling {bold(branch)} (fast-forward only) from {bold(remote)}...",
            opt_yes=opt_yes)
        if ans in ('y', 'yes', 'yq'):
            self.__git.pull_ff_only(remote, remote_branch)
            if ans == 'yq':
                raise StopInteraction
            self.flush_caches()
            print("")
        elif ans in ('q', 'quit'):
            raise StopInteraction

    def __sync_before_creating_pr(self, *, opt_onto: Optional[LocalBranchShortName], opt_yes: bool) -> None:

        self.expect_at_least_one_managed_branch()
        self.__empty_line_status = True

        current_branch = self.__git.get_current_branch()
        if current_branch not in self.managed_branches:
            self.add(branch=current_branch,
                     opt_onto=opt_onto,
                     opt_as_root=False,
                     opt_yes=opt_yes,
                     verbose=True,
                     switch_head_if_new_branch=True)
            if current_branch not in self.managed_branches:
                raise MacheteException(
                    "Command `github create-pr` can NOT be executed on the branch"
                    " that is not managed by git machete (is not present in git "
                    "machete definition file). To successfully execute this command "
                    "either add current branch to the file via commands `add`, "
                    "`discover` or `edit` or agree on adding the branch to the "
                    "definition file during the execution of `github create-pr` command.")

        up_branch: Optional[LocalBranchShortName] = self.up_branch.get(current_branch)
        if not up_branch:
            raise MacheteException(
                f'Branch `{current_branch}` does not have a parent branch (it is a root), '
                'base branch for the PR cannot be established.')

        if self.__git.is_ancestor_or_equal(current_branch.full_name(), up_branch.full_name()):
            raise MacheteException(
                f'All commits in `{current_branch}` branch are already included in `{up_branch}` branch.\nCannot create pull request.')

        s, remote = self.__git.get_strict_remote_sync_status(current_branch)
        statuses_to_sync = (
            SyncToRemoteStatuses.UNTRACKED,
            SyncToRemoteStatuses.AHEAD_OF_REMOTE,
            SyncToRemoteStatuses.DIVERGED_FROM_AND_NEWER_THAN_REMOTE)
        needs_remote_sync = s in statuses_to_sync

        if needs_remote_sync:
            if s == SyncToRemoteStatuses.AHEAD_OF_REMOTE:
                self.__handle_ahead_state(
                    current_branch=current_branch,
                    remote=remote,
                    is_called_from_traverse=False,
                    opt_push_tracked=True,
                    opt_yes=opt_yes)
            elif s == SyncToRemoteStatuses.UNTRACKED:
                self.__handle_untracked_state(
                    branch=current_branch,
                    is_called_from_traverse=False,
                    opt_push_tracked=True,
                    opt_push_untracked=True,
                    opt_yes=opt_yes)
            elif s == SyncToRemoteStatuses.DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                self.__handle_diverged_and_newer_state(
                    current_branch=current_branch,
                    remote=remote,
                    is_called_from_traverse=False,
                    opt_push_tracked=True,
                    opt_yes=opt_yes)

            self.__print_new_line(False)
            self.status(
                warn_on_yellow_edges=True,
                opt_list_commits=False,
                opt_list_commits_with_hashes=False,
                opt_no_detect_squash_merges=False)
            self.__print_new_line(False)

        else:
            if s == SyncToRemoteStatuses.BEHIND_REMOTE:
                warn(f"Branch {current_branch} is in <b>BEHIND_REMOTE</b> state.\nConsider using 'git pull'.\n")
                self.__print_new_line(False)
                ans = self.ask_if("Proceed with pull request creation?" + get_pretty_choices('y', 'Q'),
                                  "Proceeding with pull request creation...", opt_yes=opt_yes)
            elif s == SyncToRemoteStatuses.DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                warn(f"Branch {current_branch} is in <b>DIVERGED_FROM_AND_OLDER_THAN_REMOTE</b> state.\nConsider using 'git reset --keep'.\n")
                self.__print_new_line(False)
                ans = self.ask_if("Proceed with pull request creation?" + get_pretty_choices('y', 'Q'),
                                  "Proceeding with pull request creation...", opt_yes=opt_yes)
            elif s == SyncToRemoteStatuses.NO_REMOTES:
                raise MacheteException(
                    "Could not create pull request - there are no remote repositories!")
            else:
                ans = 'y'  # only IN SYNC status is left

            if ans in ('y', 'yes'):
                return
            raise MacheteException('Pull request creation interrupted.')

    def delete_untracked(self, opt_yes: bool) -> None:
        print(bold('Checking for untracked managed branches with no downstream...'))
        branches_to_delete: List[LocalBranchShortName] = []
        # TODO (#453): Consider switching to immutable collections for keeping the state (managed_branches etc.).
        for managed_branch in self.managed_branches.copy():
            status, _ = self.__git.get_strict_remote_sync_status(managed_branch)
            if status == SyncToRemoteStatuses.UNTRACKED:
                if not self.__down_branches.get(managed_branch):
                    branches_to_delete.append(managed_branch)
                    self.managed_branches.remove(managed_branch)
                    self.up_branch[managed_branch] = None

        self._delete_branches(branches_to_delete=branches_to_delete, opt_yes=opt_yes)
        self.save_definition_file()

    @staticmethod
    def should_perform_interactive_slide_out(cmd: str) -> bool:
        interactive_slide_out_safe_commands = {'traverse', 'status'}
        return sys.stdout.isatty() and cmd in interactive_slide_out_safe_commands
