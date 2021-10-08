import datetime
import io
import itertools
import os
import shutil
import sys
from typing import List, Dict, Optional, Tuple, Generator, Callable

import git_machete.github
import git_machete.options
from git_machete import utils
from git_machete.constants import (
    DISCOVER_DEFAULT_FRESH_BRANCH_COUNT, PICK_FIRST_ROOT, UNTRACKED,
    AHEAD_OF_REMOTE, BEHIND_REMOTE, DIVERGED_FROM_AND_OLDER_THAN_REMOTE,
    DIVERGED_FROM_AND_NEWER_THAN_REMOTE, NO_REMOTES, IN_SYNC_WITH_REMOTE, PICK_LAST_ROOT, EscapeCodes)
from git_machete.exceptions import MacheteException, StopInteraction
from git_machete.git_operations import GitContext
from git_machete.github import (
    add_assignees_to_pull_request, add_reviewers_to_pull_request,
    create_pull_request, checkout_pr_refs, derive_pull_request_by_head, derive_pull_requests,
    get_parsed_github_remote_url, get_pull_request_by_number_or_none, GitHubPullRequest,
    is_github_remote_url, set_base_of_pull_request, set_milestone_of_pull_request)
from git_machete.utils import (
    get_pretty_choices, flat_map, excluding, fmt, tupled, warn, debug, bold,
    colored, underline, dim, get_second)


BRANCH_DEF = Tuple[str, str]
Hash_ShortHash_Message = Tuple[str, str, str]


# Allowed parameter values for show/go command
def allowed_directions(allow_current: bool) -> str:
    current = "c[urrent]|" if allow_current else ""
    return current + "d[own]|f[irst]|l[ast]|n[ext]|p[rev]|r[oot]|u[p]"


class MacheteClient:

    def __init__(self, cli_opts: git_machete.options.CommandLineOptions, git: GitContext) -> None:
        self.__cli_opts: git_machete.options.CommandLineOptions = cli_opts
        self.__git: GitContext = git
        self._definition_file_path: str = self.__git.get_git_subpath("machete")
        self._managed_branches: List[str] = []
        self._up_branch: Dict[str, str] = {}  # TODO (#110): default dict with None
        self.__down_branches: Dict[str, List[str]] = {}  # TODO (#110): default dict with []
        self.__indent: Optional[str] = None
        self.__roots: List[str] = []
        self.__annotations: Dict[str, str] = {}
        self.__empty_line_status: Optional[bool] = None
        self.__branch_defs_by_sha_in_reflog: Optional[
            Dict[str, Optional[List[Tuple[str, str]]]]] = None

    @property
    def definition_file_path(self) -> str:
        return self._definition_file_path

    @property
    def managed_branches(self) -> List[str]:
        return self._managed_branches

    @managed_branches.setter
    def managed_branches(self, val: List[str]) -> None:
        self._managed_branches = val

    @property
    def up_branch(self) -> Dict[str, str]:
        return self._up_branch

    @up_branch.setter
    def up_branch(self, val: Dict[str, str]) -> None:
        self._up_branch = val

    def expect_in_managed_branches(self, branch: str) -> None:
        if branch not in self.managed_branches:
            raise MacheteException(
                f"Branch `{branch}` not found in the tree of branch dependencies."
                f"\nUse `git machete add {branch}` or `git machete edit`")

    def expect_at_least_one_managed_branch(self) -> None:
        if not self.__roots:
            self.__raise_no_branches_error()

    def __raise_no_branches_error(self) -> None:
        raise MacheteException(
            f"No branches listed in {self._definition_file_path}; use `git "
            f"machete discover` or `git machete edit`, or edit"
            f" {self._definition_file_path} manually.")

    def read_definition_file(self, verify_branches: bool = True) -> None:
        with open(self._definition_file_path) as file:
            lines: List[str] = [line.rstrip() for line in file.readlines()]

        at_depth = {}
        last_depth = -1

        hint = "Edit the definition file manually with `git machete edit`"

        invalid_branches: List[str] = []
        for index, line in enumerate(lines):
            if line == "" or line.isspace():
                continue
            prefix = "".join(itertools.takewhile(str.isspace, line))
            if prefix and not self.__indent:
                self.__indent = prefix

            b_a: List[str] = line.strip().split(" ", 1)
            branch = b_a[0]
            if len(b_a) > 1:
                self.__annotations[branch] = b_a[1]
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

        if len(invalid_branches) == 1:
            ans: str = self.ask_if(
                f"Skipping `{invalid_branches[0]}` " +
                "which is not a local branch (perhaps it has been deleted?).\n" +
                "Slide it out from the definition file?" +
                get_pretty_choices("y", "e[dit]", "N"), opt_yes_msg=None)
        else:
            ans = self.ask_if(
                f"Skipping {', '.join(f'`{branch}`' for branch in invalid_branches)}"
                " which are not local branches (perhaps they have been deleted?).\n"
                "Slide them out from the definition file?" + get_pretty_choices("y", "e[dit]", "N"),
                opt_yes_msg=None)

        def recursive_slide_out_invalid_branches(branch: str) -> List[str]:
            new_down_branches = flat_map(
                recursive_slide_out_invalid_branches, self.__down_branches.get(branch, []))
            if branch in invalid_branches:
                if branch in self.__down_branches:
                    del self.__down_branches[branch]
                if branch in self.__annotations:
                    del self.__annotations[branch]
                if branch in self.up_branch:
                    for down_branch in new_down_branches:
                        self.up_branch[down_branch] = self.up_branch[branch]
                    del self.up_branch[branch]
                else:
                    for down_branch in new_down_branches:
                        del self.up_branch[down_branch]
                return new_down_branches
            else:
                self.__down_branches[branch] = new_down_branches
                return [branch]

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

        def render_dfs(branch: str, depth: int) -> List[str]:
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

    def add(self, branch: str) -> None:
        if branch in self.managed_branches:
            raise MacheteException(
                f"Branch `{branch}` already exists in the tree of branch dependencies")

        onto: Optional[str] = self.__cli_opts.opt_onto
        if onto:
            self.expect_in_managed_branches(onto)

        if branch not in self.__git.get_local_branches():
            remote_branch: Optional[str] = self.__git.get_sole_remote_branch(branch)
            if remote_branch:
                common_line = (
                    f"A local branch `{branch}` does not exist, but a remote "
                    f"branch `{remote_branch}` exists.\n")
                msg = common_line + f"Check out `{branch}` locally?" + get_pretty_choices('y', 'N')
                opt_yes_msg = common_line + f"Checking out `{branch}` locally..."
                if self.ask_if(msg, opt_yes_msg) in ('y', 'yes'):
                    self.__git.create_branch(branch, f"refs/remotes/{remote_branch}")
                else:
                    return
                # Not dealing with `onto` here. If it hasn't been explicitly
                # specified via `--onto`, we'll try to infer it now.
            else:
                out_of = f"refs/heads/{onto}" if onto else "HEAD"
                out_of_str = f"`{onto}`" if onto else "the current HEAD"
                msg = (f"A local branch `{branch}` does not exist. Create (out "
                       f"of {out_of_str})?" + get_pretty_choices('y', 'N'))
                opt_yes_msg = (f"A local branch `{branch}` does not exist. "
                               f"Creating out of {out_of_str}")
                if self.ask_if(msg, opt_yes_msg) in ('y', 'yes'):
                    # If `--onto` hasn't been explicitly specified, let's try to
                    # assess if the current branch would be a good `onto`.
                    if self.__roots and not onto:
                        current_branch = self.__git.get_current_branch_or_none()
                        if current_branch and current_branch in self.managed_branches:
                            onto = current_branch
                    self.__git.create_branch(branch, out_of)
                else:
                    return

        if self.__cli_opts.opt_as_root or not self.__roots:
            self.__roots += [branch]
            print(fmt(f"Added branch `{branch}` as a new root"))
        else:
            if not onto:
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
                    if self.ask_if(msg, opt_yes_msg) in ('y', 'yes'):
                        onto = upstream
                    else:
                        return

            self.up_branch[branch] = onto
            if onto in self.__down_branches:
                self.__down_branches[onto].append(branch)
            else:
                self.__down_branches[onto] = [branch]
            print(fmt(f"Added branch `{branch}` onto `{onto}`"))

        self.managed_branches += [branch]
        self.save_definition_file()

    def annotate(self, branch: str, words: List[str]) -> None:

        if branch in self.__annotations and words == ['']:
            del self.__annotations[branch]
        else:
            self.__annotations[branch] = " ".join(words)
        self.save_definition_file()

    def print_annotation(self, branch: str) -> None:
        if branch in self.__annotations:
            print(self.__annotations[branch])

    def update(self) -> None:
        current_branch = self.__git.get_current_branch()
        if self.__cli_opts.opt_merge:
            with_branch = self.up(
                current_branch,
                prompt_if_inferred_msg=(
                    "Branch `%s` not found in the tree of branch dependencies. "
                    "Merge with the inferred upstream `%s`?" + get_pretty_choices('y', 'N')),
                prompt_if_inferred_yes_opt_msg=(
                    "Branch `%s` not found in the tree of branch dependencies. "
                    "Merging with the inferred upstream `%s`..."))
            self.__git.merge(with_branch, current_branch)
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
                f"refs/heads/{onto_branch}",
                self.__cli_opts.opt_fork_point or self.fork_point(current_branch, use_overrides=True),
                current_branch)

    def discover_tree(self) -> None:
        all_local_branches = self.__git.get_local_branches()
        if not all_local_branches:
            raise MacheteException("No local branches found")
        for root in self.__cli_opts.opt_roots:
            if root not in self.__git.get_local_branches():
                raise MacheteException(f"`{root}` is not a local branch")
        if self.__cli_opts.opt_roots:
            self.__roots = list(self.__cli_opts.opt_roots)
        else:
            self.__roots = []
            if "master" in self.__git.get_local_branches():
                self.__roots += ["master"]
            elif "main" in self.__git.get_local_branches():
                # See https://github.com/github/renaming
                self.__roots += ["main"]
            if "develop" in self.__git.get_local_branches():
                self.__roots += ["develop"]
        self.__down_branches = {}
        self.up_branch = {}
        self.__indent = "\t"
        self.__annotations = {}

        root_of = dict((branch, branch) for branch in all_local_branches)

        def get_root_of(branch: str) -> str:
            if branch != root_of[branch]:
                root_of[branch] = get_root_of(root_of[branch])
            return root_of[branch]

        non_root_fixed_branches = excluding(all_local_branches, self.__roots)
        last_checkout_timestamps = self.__git.get_latest_checkout_timestamps()
        non_root_fixed_branches_by_last_checkout_timestamps = sorted(
            (last_checkout_timestamps.get(branch, 0), branch) for branch in non_root_fixed_branches)
        if self.__cli_opts.opt_checked_out_since:
            threshold = self.__git.get_git_timespec_parsed_to_unix_timestamp(
                self.__cli_opts.opt_checked_out_since)
            stale_non_root_fixed_branches = [branch for (timestamp, branch) in itertools.takewhile(
                tupled(lambda timestamp, branch: timestamp < threshold),
                non_root_fixed_branches_by_last_checkout_timestamps
            )]
        else:
            c = DISCOVER_DEFAULT_FRESH_BRANCH_COUNT
            stale, fresh = non_root_fixed_branches_by_last_checkout_timestamps[:-c], non_root_fixed_branches_by_last_checkout_timestamps[-c:]
            stale_non_root_fixed_branches = [branch for (timestamp, branch) in stale]
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
        if self.__cli_opts.opt_checked_out_since and not self.managed_branches:
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
                debug(
                    "discover_tree()",
                    (f"inferred upstream of {branch} is {upstream}, attaching "
                     f"{branch} as a child of {upstream}\n")
                )
                self.up_branch[branch] = upstream
                root_of[branch] = upstream
                if upstream in self.__down_branches:
                    self.__down_branches[upstream].append(branch)
                else:
                    self.__down_branches[upstream] = [branch]
            else:
                debug(
                    "discover_tree()",
                    f"inferred no upstream for {branch}, attaching {branch} as a new root\n")
                self.__roots += [branch]

        # Let's remove merged branches for which no downstream branch have been found.
        merged_branches_to_skip = []
        for branch in self.managed_branches:
            if branch in self.up_branch and not self.__down_branches.get(branch):
                upstream = self.up_branch[branch]
                if self.is_merged_to(branch, upstream):
                    debug(
                        "discover_tree()",
                        (f"inferred upstream of {branch} is {upstream}, but "
                         f"{branch} is merged to {upstream}; skipping {branch}"
                         f" from discovered tree\n")
                    )
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
        self.status(warn_on_yellow_edges=False)
        print("")
        do_backup = os.path.isfile(self._definition_file_path)
        backup_msg = (
            f"\nThe existing definition file will be backed up as {self._definition_file_path}~"
            if do_backup else "")
        msg = f"Save the above tree to {self._definition_file_path}?{backup_msg}" + get_pretty_choices('y', 'e[dit]', 'N')
        opt_yes_msg = f"Saving the above tree to {self._definition_file_path}... {backup_msg}"
        ans = self.ask_if(msg, opt_yes_msg)
        if ans in ('y', 'yes'):
            if do_backup:
                self.back_up_definition_file()
            self.save_definition_file()
        elif ans in ('e', 'edit'):
            if do_backup:
                self.back_up_definition_file()
            self.save_definition_file()
            self.edit()

    def slide_out(self, branches_to_slide_out: List[str]) -> None:
        # Verify that all branches exist, are managed, and have an upstream.
        for branch in branches_to_slide_out:
            self.expect_in_managed_branches(branch)
            new_upstream = self.up_branch.get(branch)
            if not new_upstream:
                raise MacheteException(f"No upstream branch defined for `{branch}`, cannot slide out")

        # Verify that all "interior" slide-out branches have a single downstream
        # pointing to the next slide-out
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
            if self.__cli_opts.opt_merge:
                print(f"Merging {bold(new_upstream)} into {bold(new_downstream)}...")
                self.__git.merge(new_upstream, new_downstream)
            else:
                print(f"Rebasing {bold(new_downstream)} onto {bold(new_upstream)}...")
                self.__git.rebase(
                    f"refs/heads/{new_upstream}",
                    self.__cli_opts.opt_down_fork_point or
                    self.fork_point(new_downstream, use_overrides=True), new_downstream)

    def advance(self, branch: str) -> None:
        if not self.__down_branches.get(branch):
            raise MacheteException(
                f"`{branch}` does not have any downstream (child) branches to advance towards")

        def connected_with_green_edge(bd: str) -> bool:
            return bool(
                not self.__is_merged_to_upstream(bd) and
                self.__git.is_ancestor_or_equal(branch, bd) and
                (self.__get_overridden_fork_point(bd) or self.__git.get_commit_sha_by_revision(branch) == self.fork_point(bd, use_overrides=False)))

        candidate_downstreams = list(filter(connected_with_green_edge, self.__down_branches[branch]))
        if not candidate_downstreams:
            raise MacheteException(
                f"No downstream (child) branch of `{branch}` is connected to "
                f"`{branch}` with a green edge")
        if len(candidate_downstreams) > 1:
            if self.__cli_opts.opt_yes:
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
                f"Fast-forwarding {bold(branch)} to match {bold(down_branch)}...")
            if ans in ('y', 'yes'):
                self.__git.merge_fast_forward_only(down_branch)
            else:
                return

        ans = self.ask_if(f"\nBranch {bold(down_branch)} is now merged into {bold(branch)}. Slide {bold(down_branch)} out of the tree of branch dependencies?" + get_pretty_choices('y', 'N'),
                          f"\nBranch {bold(down_branch)} is now merged into {bold(branch)}. Sliding {bold(down_branch)} out of the tree of branch dependencies...")
        if ans in ('y', 'yes'):
            dds = self.__down_branches.get(down_branch, [])
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

    def traverse(self) -> None:

        self.expect_at_least_one_managed_branch()

        self.__empty_line_status = True

        if self.__cli_opts.opt_fetch:
            for remote in self.__git.get_remotes():
                print(f"Fetching {remote}...")
                self.__git.fetch_remote(remote)
            if self.__git.get_remotes():
                self.flush_caches()
                print("")

        initial_branch = nearest_remaining_branch = self.__git.get_current_branch()

        if self.__cli_opts.opt_start_from == "root":
            dest = self.root_branch(self.__git.get_current_branch(), if_unmanaged=PICK_FIRST_ROOT)
            self.__print_new_line(False)
            print(f"Checking out the root branch ({bold(dest)})")
            self.__git.checkout(dest)
            current_branch = dest
        elif self.__cli_opts.opt_start_from == "first-root":
            # Note that we already ensured that there is at least one managed branch.
            dest = self.managed_branches[0]
            self.__print_new_line(False)
            print(f"Checking out the first root branch ({bold(dest)})")
            self.__git.checkout(dest)
            current_branch = dest
        else:  # cli_opts.opt_start_from == "here"
            current_branch = self.__git.get_current_branch()
            self.expect_in_managed_branches(current_branch)

        branch: str
        for branch in itertools.dropwhile(lambda x: x != current_branch, self.managed_branches):
            upstream = self.up_branch.get(branch)

            needs_slide_out: bool = self.__is_merged_to_upstream(branch)
            s, remote = self.__git.get_strict_remote_sync_status(branch)
            statuses_to_sync = (UNTRACKED,
                                AHEAD_OF_REMOTE,
                                BEHIND_REMOTE,
                                DIVERGED_FROM_AND_OLDER_THAN_REMOTE,
                                DIVERGED_FROM_AND_NEWER_THAN_REMOTE)
            needs_remote_sync = s in statuses_to_sync

            if needs_slide_out:
                # Avoid unnecessary fork point check if we already know that the
                # branch qualifies for slide out;
                # neither rebase nor merge will be suggested in such case anyway.
                needs_parent_sync: bool = False
            elif s == DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                # Avoid unnecessary fork point check if we already know that the
                # branch qualifies for resetting to remote counterpart;
                # neither rebase nor merge will be suggested in such case anyway.
                needs_parent_sync = False
            elif self.__cli_opts.opt_merge:
                needs_parent_sync = bool(
                    upstream and not self.__git.is_ancestor_or_equal(upstream, branch))
            else:  # using rebase
                needs_parent_sync = bool(
                    upstream and
                    not (self.__git.is_ancestor_or_equal(upstream, branch) and
                         (self.__git.get_commit_sha_by_revision(upstream) ==
                          self.fork_point(branch, use_overrides=True)))
                )

            if branch != current_branch and (needs_slide_out or needs_parent_sync or needs_remote_sync):
                self.__print_new_line(False)
                sys.stdout.write(f"Checking out {bold(branch)}\n")
                self.__git.checkout(branch)
                current_branch = branch
                self.__print_new_line(False)
                self.status(warn_on_yellow_edges=True)
                self.__print_new_line(True)
            if needs_slide_out:
                self.__print_new_line(False)
                ans: str = self.ask_if(f"Branch {bold(branch)} is merged into {bold(upstream)}. Slide {bold(branch)} out of the tree of branch dependencies?" + get_pretty_choices('y', 'N', 'q', 'yq'),
                                       f"Branch {bold(branch)} is merged into {bold(upstream)}. Sliding {bold(branch)} out of the tree of branch dependencies...")
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
                self.__print_new_line(False)
                if self.__cli_opts.opt_merge:
                    ans = self.ask_if(f"Merge {bold(upstream)} into {bold(branch)}?" + get_pretty_choices('y', 'N', 'q', 'yq'),
                                      f"Merging {bold(upstream)} into {bold(branch)}...")
                else:
                    ans = self.ask_if(f"Rebase {bold(branch)} onto {bold(upstream)}?" + get_pretty_choices('y', 'N', 'q', 'yq'),
                                      f"Rebasing {bold(branch)} onto {bold(upstream)}...")
                if ans in ('y', 'yes', 'yq'):
                    if self.__cli_opts.opt_merge:
                        self.__git.merge(upstream, branch)
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
                            sys.stdout.write("\nMerge in progress; stopping the traversal\n")
                            return
                    else:
                        self.__git.rebase(f"refs/heads/{upstream}", self.fork_point(branch, use_overrides=True), branch)
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
                            sys.stdout.write(
                                fmt(f"\nRebase of `{rebased_branch}` in progress; stopping the traversal\n"))
                            return
                    if ans == 'yq':
                        return

                    self.flush_caches()
                    s, remote = self.__git.get_strict_remote_sync_status(branch)
                    needs_remote_sync = s in statuses_to_sync
                elif ans in ('q', 'quit'):
                    return

            if needs_remote_sync:
                try:
                    if s == BEHIND_REMOTE:
                        self.__handle_behind_state(current_branch, remote)
                    elif s == AHEAD_OF_REMOTE:
                        self.__handle_ahead_state(
                            current_branch, remote, is_called_from_traverse=True)
                    elif s == DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                        self.__handle_diverged_and_older_state(current_branch)
                    elif s == DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                        self.__handle_diverged_and_newer_state(current_branch, remote)
                    elif s == UNTRACKED:
                        self.__handle_untracked_state(current_branch, is_called_from_traverse=True)
                except StopInteraction:
                    return

        if self.__cli_opts.opt_return_to == "here":
            self.__git.checkout(initial_branch)
        elif self.__cli_opts.opt_return_to == "nearest-remaining":
            self.__git.checkout(nearest_remaining_branch)
        # otherwise cli_opts.opt_return_to == "stay", so no action is needed

        self.__print_new_line(False)
        self.status(warn_on_yellow_edges=True)
        print("")
        if current_branch == self.managed_branches[-1]:
            msg: str = f"Reached branch {bold(current_branch)} which has no successor"
        else:
            msg = f"No successor of {bold(current_branch)} needs to be slid out or synced with upstream branch or remote"
        sys.stdout.write(f"{msg}; nothing left to update\n")

        if self.__cli_opts.opt_return_to == "here" or (
                self.__cli_opts.opt_return_to == "nearest-remaining" and nearest_remaining_branch == initial_branch):
            print(f"Returned to the initial branch {bold(initial_branch)}")
        elif self.__cli_opts.opt_return_to == "nearest-remaining" and nearest_remaining_branch != initial_branch:
            print(
                f"The initial branch {bold(initial_branch)} has been slid out. "
                f"Returned to nearest remaining managed branch {bold(nearest_remaining_branch)}")

    def status(self, warn_on_yellow_edges: bool) -> None:
        dfs_res = []

        def prefix_dfs(u_: str, accumulated_path: List[Optional[str]]) -> None:
            dfs_res.append((u_, accumulated_path))
            if self.__down_branches.get(u_):
                for (v, nv) in zip(self.__down_branches[u_][:-1], self.__down_branches[u_][1:]):
                    prefix_dfs(v, accumulated_path + [nv])
                prefix_dfs(self.__down_branches[u_][-1], accumulated_path + [None])

        for upstream in self.__roots:
            prefix_dfs(upstream, accumulated_path=[])

        out = io.StringIO()
        edge_color: Dict[str, str] = {}
        fp_sha_cached: Dict[str, Optional[str]] = {}  # TODO (#110): default dict with None
        fp_branches_cached: Dict[str, List[BRANCH_DEF]] = {}

        def fp_sha(branch: str) -> Optional[str]:
            if branch not in fp_sha_cached:
                try:
                    # We're always using fork point overrides, even when status
                    # is launched from discover().
                    fp_sha_cached[branch], fp_branches_cached[branch] = self.__fork_point_and_containing_branch_defs(branch, use_overrides=True)
                except MacheteException:
                    fp_sha_cached[branch], fp_branches_cached[branch] = None, []
            return fp_sha_cached[branch]

        # Edge colors need to be precomputed
        # in order to render the leading parts of lines properly.
        for branch in self.up_branch:
            upstream = self.up_branch[branch]
            if self.is_merged_to(branch, upstream):
                edge_color[branch] = EscapeCodes.DIM
            elif not self.__git.is_ancestor_or_equal(upstream, branch):
                edge_color[branch] = EscapeCodes.RED
            elif self.__get_overridden_fork_point(branch) or self.__git.get_commit_sha_by_revision(upstream) == fp_sha(branch):
                edge_color[branch] = EscapeCodes.GREEN
            else:
                edge_color[branch] = EscapeCodes.YELLOW

        currently_rebased_branch = self.__git.get_currently_rebased_branch_or_none()
        currently_checked_out_branch = self.__git.get_currently_checked_out_branch_or_none()

        hook_path = self.__git.get_hook_path("machete-status-branch")
        hook_executable = self.__git.check_hook_executable(hook_path)

        def print_line_prefix(b_: str, suffix: str) -> None:
            out.write("  ")
            for p in accumulated_path[:-1]:
                if not p:
                    out.write("  ")
                else:
                    out.write(colored(f"{utils.get_vertical_bar()} ", edge_color[p]))
            out.write(colored(suffix, edge_color[b_]))

        for branch, accumulated_path in dfs_res:
            if branch in self.up_branch:
                print_line_prefix(branch, f"{utils.get_vertical_bar()} \n")
                if self.__cli_opts.opt_list_commits:
                    if edge_color[branch] in (EscapeCodes.RED, EscapeCodes.DIM):
                        commits: List[Hash_ShortHash_Message] = self.__git.get_commits_between(fp_sha(branch), f"refs/heads/{branch}") if fp_sha(branch) else []
                    elif edge_color[branch] == EscapeCodes.YELLOW:
                        commits = self.__git.get_commits_between(f"refs/heads/{self.up_branch[branch]}", f"refs/heads/{branch}")
                    else:  # edge_color == EscapeCodes.GREEN
                        commits = self.__git.get_commits_between(fp_sha(branch), f"refs/heads/{branch}")

                    for sha, short_sha, subject in commits:
                        if sha == fp_sha(branch):
                            # fp_branches_cached will already be there thanks to
                            # the above call to 'fp_sha'.
                            fp_branches_formatted: str = " and ".join(
                                sorted(underline(lb_or_rb) for lb, lb_or_rb in fp_branches_cached[branch]))
                            fp_suffix: str = " %s %s %s seems to be a part of the unique history of %s" % \
                                             (colored(utils.get_right_arrow(), EscapeCodes.RED), colored("fork point ???", EscapeCodes.RED),
                                              "this commit" if self.__cli_opts.opt_list_commits_with_hashes else f"commit {short_sha}",
                                              fp_branches_formatted)
                        else:
                            fp_suffix = ''
                        print_line_prefix(branch, utils.get_vertical_bar())
                        out.write(" %s%s%s\n" % (
                                  f"{dim(short_sha)}  " if self.__cli_opts.opt_list_commits_with_hashes else "", dim(subject),
                                  fp_suffix))
                elbow_ascii_only: Dict[str, str] = {EscapeCodes.DIM: "m-", EscapeCodes.RED: "x-", EscapeCodes.GREEN: "o-", EscapeCodes.YELLOW: "?-"}
                elbow: str = u"└─" if not utils.ascii_only else elbow_ascii_only[edge_color[branch]]
                print_line_prefix(branch, elbow)
            else:
                if branch != dfs_res[0][0]:
                    out.write("\n")
                out.write("  ")

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
                current = "%s%s" % (bold(colored(prefix, EscapeCodes.RED)), bold(underline(branch, star_if_ascii_only=True)))
            else:
                current = bold(branch)

            anno: str = f"  {dim(self.__annotations[branch])}" if branch in self.__annotations else ""

            s, remote = self.__git.get_combined_remote_sync_status(branch)
            sync_status = {
                NO_REMOTES: "",
                UNTRACKED: colored(" (untracked)", EscapeCodes.ORANGE),
                IN_SYNC_WITH_REMOTE: "",
                BEHIND_REMOTE: colored(f" (behind {remote})", EscapeCodes.RED),
                AHEAD_OF_REMOTE: colored(f" (ahead of {remote})", EscapeCodes.RED),
                DIVERGED_FROM_AND_OLDER_THAN_REMOTE: colored(f" (diverged from & older than {remote})", EscapeCodes.RED),
                DIVERGED_FROM_AND_NEWER_THAN_REMOTE: colored(f" (diverged from {remote})", EscapeCodes.RED)
            }[s]

            hook_output = ""
            if hook_executable:
                debug("status()", f"running machete-status-branch hook ({hook_path}) for branch {branch}")
                hook_env = dict(os.environ, ASCII_ONLY=str(utils.ascii_only).lower())
                status_code, stdout, stderr = utils.popen_cmd(hook_path, branch, cwd=self.__git.get_root_dir(), env=hook_env)
                if status_code == 0:
                    if not stdout.isspace():
                        hook_output = f"  {stdout.rstrip()}"
                else:
                    debug("status()",
                          f"machete-status-branch hook ({hook_path}) for branch {branch} returned {status_code}; stdout: '{stdout}'; stderr: '{stderr}'")

            out.write(current + anno + sync_status + hook_output + "\n")

        sys.stdout.write(out.getvalue())
        out.close()

        yellow_edge_branches = [k for k, v in edge_color.items() if v == EscapeCodes.YELLOW]
        if yellow_edge_branches and warn_on_yellow_edges:
            if len(yellow_edge_branches) == 1:
                first_part = f"yellow edge indicates that fork point for `{yellow_edge_branches[0]}` is probably incorrectly inferred,\n" \
                             f"or that some extra branch should be between `{self.up_branch[yellow_edge_branches[0]]}` and `{yellow_edge_branches[0]}`"
            else:
                affected_branches = ", ".join(map(lambda x: f"`{x}`", yellow_edge_branches))
                first_part = f"yellow edges indicate that fork points for {affected_branches} are probably incorrectly inferred" \
                             f"or that some extra branch should be added between each of these branches and its parent"

            if not self.__cli_opts.opt_list_commits:
                second_part = "Run `git machete status --list-commits` or `git machete status --list-commits-with-hashes` to see more details"
            elif len(yellow_edge_branches) == 1:
                second_part = f"Consider using `git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent {yellow_edge_branches[0]}`\n" \
                              f"or reattaching `{yellow_edge_branches[0]}` under a different parent branch"
            else:
                second_part = "Consider using `git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent <branch>` for each affected branch" \
                              "or reattaching the affected branches under different parent branches"

            sys.stderr.write("\n")
            warn(f"{first_part}.\n\n{second_part}.")

    def delete_unmanaged(self) -> None:
        branches_to_delete = excluding(self.__git.get_local_branches(), self.managed_branches)
        current_branch = self.__git.get_current_branch_or_none()
        if current_branch and current_branch in branches_to_delete:
            branches_to_delete = excluding(branches_to_delete, [current_branch])
            print(fmt(f"Skipping current branch `{current_branch}`"))
        if branches_to_delete:
            branches_merged_to_head = self.__git.get_merged_local_branches()

            branches_to_delete_merged_to_head = [branch for branch in branches_to_delete if branch in branches_merged_to_head]
            for branch in branches_to_delete_merged_to_head:
                remote_branch = self.__git.get_strict_counterpart_for_fetching_of_branch(branch)
                is_merged_to_remote = self.__git.is_ancestor_or_equal(branch, remote_branch, later_prefix="refs/remotes/") if remote_branch else True
                msg_core = f"{bold(branch)} (merged to HEAD{'' if is_merged_to_remote else f', but not merged to {remote_branch}'})"
                msg = f"Delete branch {msg_core}?" + get_pretty_choices('y', 'N', 'q')
                opt_yes_msg = f"Deleting branch {msg_core}"
                ans = self.ask_if(msg, opt_yes_msg)
                if ans in ('y', 'yes'):
                    self.__git.delete_branch(branch, force=is_merged_to_remote)
                elif ans in ('q', 'quit'):
                    return

            branches_to_delete_unmerged_to_head = [branch for branch in branches_to_delete if branch not in branches_merged_to_head]
            for branch in branches_to_delete_unmerged_to_head:
                msg_core = f"{bold(branch)} (unmerged to HEAD)"
                msg = f"Delete branch {msg_core}?" + get_pretty_choices('y', 'N', 'q')
                opt_yes_msg = f"Deleting branch {msg_core}"
                ans = self.ask_if(msg, opt_yes_msg)
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

    def __fork_point_and_containing_branch_defs(self, branch: str, use_overrides: bool) -> Tuple[Optional[str], List[BRANCH_DEF]]:
        upstream = self.up_branch.get(branch)

        if self.__is_merged_to_upstream(branch):
            fp_sha = self.__git.get_commit_sha_by_revision(branch)
            debug(f"fork_point_and_containing_branch_defs({branch})",
                  f"{branch} is merged to {upstream}; skipping inference, using tip of {branch} ({fp_sha}) as fork point")
            return fp_sha, []

        if use_overrides:
            overridden_fp_sha = self.__get_overridden_fork_point(branch)
            if overridden_fp_sha:
                if upstream and self.__git.is_ancestor_or_equal(upstream, branch) and not self.__git.is_ancestor_or_equal(upstream, overridden_fp_sha, later_prefix=""):
                    # We need to handle the case when branch is a descendant of upstream,
                    # but the fork point of branch is overridden to a commit that
                    # is NOT a descendant of upstream. In this case it's more
                    # reasonable to assume that upstream (and not overridden_fp_sha)
                    # is the fork point.
                    debug(f"fork_point_and_containing_branch_defs({branch})",
                          f"{branch} is descendant of its upstream {upstream}, but overridden fork point commit {overridden_fp_sha} is NOT a descendant of {upstream}; falling back to {upstream} as fork point")
                    return self.__git.get_commit_sha_by_revision(upstream), []
                else:
                    debug(f"fork_point_and_containing_branch_defs({branch})",
                          f"fork point of {branch} is overridden to {overridden_fp_sha}; skipping inference")
                    return overridden_fp_sha, []

        try:
            fp_sha, containing_branch_defs = next(self.__match_log_to_filtered_reflogs(branch))
        except StopIteration:
            if upstream and self.__git.is_ancestor_or_equal(upstream, branch):
                debug(f"fork_point_and_containing_branch_defs({branch})",
                      f"cannot find fork point, but {branch} is descendant of its upstream {upstream}; falling back to {upstream} as fork point")
                return self.__git.get_commit_sha_by_revision(upstream), []
            else:
                raise MacheteException(f"Cannot find fork point for branch `{branch}`")
        else:
            debug("fork_point_and_containing_branch_defs({branch})",
                  f"commit {fp_sha} is the most recent point in history of {branch} to occur on "
                  "filtered reflog of any other branch or its remote counterpart "
                  f"(specifically: {' and '.join(map(utils.get_second, containing_branch_defs))})")

            if upstream and self.__git.is_ancestor_or_equal(upstream, branch) and not self.__git.is_ancestor_or_equal(upstream, fp_sha, later_prefix=""):
                # That happens very rarely in practice (typically current head
                # of any branch, including upstream, should occur on the reflog
                # of this branch, thus is_ancestor(upstream, branch) should imply
                # is_ancestor(upstream, FP(branch)), but it's still possible in
                # case reflog of upstream is incomplete for whatever reason.
                debug(f"fork_point_and_containing_branch_defs({branch})",
                      f"{upstream} is descendant of its upstream {branch}, but inferred fork point commit {fp_sha} is NOT a descendant of {upstream}; falling back to {upstream} as fork point")
                return self.__git.get_commit_sha_by_revision(upstream), []
            else:
                debug(f"fork_point_and_containing_branch_defs({branch})",
                      f"choosing commit {fp_sha} as fork point")
                return fp_sha, containing_branch_defs

    def fork_point(self, branch: str, use_overrides: bool) -> Optional[str]:
        sha, containing_branch_defs = self.__fork_point_and_containing_branch_defs(
            branch, use_overrides)
        return sha

    def diff(self, branch: Optional[str]) -> None:
        fp: str = self.fork_point(
            branch if branch else self.__git.get_current_branch(),
            use_overrides=True)
        self.__git.display_diff(
            branch=branch,
            forkpoint=fp,
            format_with_stat=self.__cli_opts.opt_stat)

    def log(self, branch: str) -> None:
        full_branch_name = f"refs/heads{branch}"
        forkpoint = self.fork_point(branch, use_overrides=True)
        self.__git.display_branch_history_from_forkpoint(full_branch_name, forkpoint)

    def down(self, branch: str, pick_mode: bool) -> str:
        self.expect_in_managed_branches(branch)
        dbs = self.__down_branches.get(branch)
        if not dbs:
            raise MacheteException(f"Branch `{branch}` has no downstream branch")
        elif len(dbs) == 1:
            return dbs[0]
        elif pick_mode:
            return self.pick(dbs, "downstream branch")
        else:
            return "\n".join(dbs)

    def first_branch(self, branch: str) -> str:
        root = self.root_branch(branch, if_unmanaged=PICK_FIRST_ROOT)
        root_dbs = self.__down_branches.get(root)
        return root_dbs[0] if root_dbs else root

    def last_branch(self, branch: str) -> str:
        destination = self.root_branch(branch, if_unmanaged=PICK_LAST_ROOT)
        while self.__down_branches.get(destination):
            destination = self.__down_branches[destination][-1]
        return destination

    def next_branch(self, branch: str) -> str:
        self.expect_in_managed_branches(branch)
        index: int = self.managed_branches.index(branch) + 1
        if index == len(self.managed_branches):
            raise MacheteException(f"Branch `{branch}` has no successor")
        return self.managed_branches[index]

    def prev_branch(self, branch: str) -> str:
        self.expect_in_managed_branches(branch)
        index: int = self.managed_branches.index(branch) - 1
        if index == -1:
            raise MacheteException(f"Branch `{branch}` has no predecessor")
        return self.managed_branches[index]

    def root_branch(self, branch: str, if_unmanaged: int) -> str:
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

    def up(self, branch: str, prompt_if_inferred_msg: Optional[str],
           prompt_if_inferred_yes_opt_msg: Optional[str]) -> str:
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
                            prompt_if_inferred_yes_opt_msg % (branch, upstream)
                    ) in ('y', 'yes'):
                        return upstream
                    else:
                        sys.exit(1)
                else:
                    warn(
                        f"branch `{branch}` not found in the tree of branch "
                        f"dependencies; the upstream has been inferred to `{upstream}`")
                    return upstream
            else:
                raise MacheteException(
                    f"Branch `{branch}` not found in the tree of branch "
                    f"dependencies and its upstream could not be inferred")

    def slidable(self) -> List[str]:
        return [branch for branch in self.managed_branches if branch in self.up_branch]

    def slidable_after(self, branch: str) -> List[str]:
        if branch in self.up_branch:
            dbs = self.__down_branches.get(branch)
            if dbs and len(dbs) == 1:
                return dbs
        return []

    def __is_merged_to_upstream(self, branch: str) -> bool:
        if branch not in self.up_branch:
            return False
        return self.is_merged_to(branch, self.up_branch[branch])

    def __run_post_slide_out_hook(self, new_upstream: str, slid_out_branch: str,
                                  new_downstreams: List[str]) -> None:
        hook_path = self.__git.get_hook_path("machete-post-slide-out")
        if self.__git.check_hook_executable(hook_path):
            debug(f"run_post_slide_out_hook({new_upstream}, {slid_out_branch}, {new_downstreams})",
                  f"running machete-post-slide-out hook ({hook_path})")
            exit_code = utils.run_cmd(hook_path, new_upstream, slid_out_branch, *new_downstreams,
                                      cwd=self.__git.get_root_dir())
            if exit_code != 0:
                sys.stderr.write(
                    f"The machete-post-slide-out hook exited with {exit_code}, aborting.\n")
                sys.exit(exit_code)

    def squash(self, current_branch: str, fork_commit: str) -> None:
        commits: List[Hash_ShortHash_Message] = self.__git.get_commits_between(
            fork_commit, current_branch)
        if not commits:
            raise MacheteException(
                "No commits to squash. Use `-f` or `--fork-point` to specify the "
                "start of range of commits to squash.")
        if len(commits) == 1:
            sha, short_sha, subject = commits[0]
            print(f"Exactly one commit ({short_sha}) to squash, ignoring.\n")
            print("Tip: use `-f` or `--fork-point` to specify where the range of "
                  "commits to squash starts.")
            return

        earliest_sha, earliest_short_sha, earliest_subject = commits[0]
        earliest_full_body = self.__git.get_commit_information("raw body", earliest_sha).strip()
        # %ai for ISO-8601 format; %aE/%aN for respecting .mailmap; see `git rev-list --help`
        earliest_author_date = self.__git.get_commit_information("author date", earliest_sha).strip()
        earliest_author_email = self.__git.get_commit_information("author email", earliest_sha).strip()
        earliest_author_name = self.__git.get_commit_information("author name", earliest_sha).strip()

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
        squashed_sha = self.__git.squash_commits_with_msg_and_new_env(
            fork_commit, earliest_full_body, author_env).strip()

        # This can't be done with `git reset` since it doesn't allow for a custom reflog message.
        # Even worse, reset's reflog message would be filtered out in our fork point algorithm,
        # so the squashed commit would not even be considered to "belong"
        # (in the FP sense) to the current branch's history.
        self.__git.update_head_ref_to_new_hash_with_msg(
            squashed_sha, f"squash: {earliest_subject}")

        print(f"Squashed {len(commits)} commits:")
        print()
        for sha, short_sha, subject in commits:
            print(f"\t{short_sha} {subject}")

        latest_sha, latest_short_sha, latest_subject = commits[-1]
        print()
        print("To restore the original pre-squash commit, run:")
        print()
        print(fmt(f"\t`git reset {latest_sha}`"))

    def filtered_reflog(self, branch: str, prefix: str) -> List[str]:
        def is_excluded_reflog_subject(sha_: str, gs_: str) -> bool:
            is_excluded = (gs_.startswith("branch: Created from") or
                           gs_ == f"branch: Reset to {branch}" or
                           gs_ == "branch: Reset to HEAD" or
                           gs_.startswith("reset: moving to ") or
                           gs_.startswith("fetch . ") or
                           # The rare case of a no-op rebase, the exact wording
                           # likely depends on git version
                           gs_ == f"rebase finished: {prefix}{branch} onto {sha_}" or
                           gs_ == f"rebase -i (finish): {prefix}{branch} onto {sha_}"
                           )
            if is_excluded:
                debug(
                    (f"filtered_reflog({branch}, {prefix}) -> is_excluded_reflog_subject({sha_},"
                     f" <<<{gs_}>>>)"),
                    "skipping reflog entry")
            return is_excluded

        branch_reflog = self.__git.get_reflog(prefix + branch)
        if not branch_reflog:
            return []

        earliest_sha, earliest_gs = branch_reflog[-1]  # Note that the reflog is returned from latest to earliest entries.
        shas_to_exclude = set()
        if earliest_gs.startswith("branch: Created from"):
            debug(f"filtered_reflog({branch}, {prefix})",
                  f"skipping any reflog entry with the hash equal to the hash of the earliest (branch creation) entry: {earliest_sha}")
            shas_to_exclude.add(earliest_sha)

        result = [sha for (sha, gs) in branch_reflog if
                  sha not in shas_to_exclude and not is_excluded_reflog_subject(sha, gs)]
        debug(f"filtered_reflog({branch}, {prefix})",
              "computed filtered reflog (= reflog without branch creation "
              "and branch reset events irrelevant for fork point/upstream inference): %s\n" % (", ".join(result) or "<empty>"))
        return result

    def sync_annotations_to_github_prs(self) -> None:

        url_for_remote: Dict[str, str] = {remote: self.__git.get_url_of_remote(remote) for remote in
                                          self.__git.get_remotes()}
        if not url_for_remote:
            raise MacheteException(fmt('No remotes defined for this repository (see `git remote`)'))

        optional_org_name_for_github_remote: Dict[str, Optional[Tuple[str, str]]] = {
            remote: get_parsed_github_remote_url(url) for remote, url in url_for_remote.items()}
        org_name_for_github_remote: Dict[str, Tuple[str, str]] = {remote: org_name for remote, org_name in
                                                                  optional_org_name_for_github_remote.items() if
                                                                  org_name}
        if not org_name_for_github_remote:
            raise MacheteException(
                fmt('Remotes are defined for this repository, but none of them '
                    'corresponds to GitHub (see `git remote -v` for details)'))

        org: str
        repo: str
        if len(org_name_for_github_remote) == 1:
            org, repo = list(org_name_for_github_remote.values())[0]
        elif len(org_name_for_github_remote) > 1:
            if 'origin' in org_name_for_github_remote:
                org, repo = org_name_for_github_remote['origin']
            else:
                raise MacheteException(
                    f'Multiple non-origin remotes correspond to GitHub in this repository: '
                    f'{", ".join(org_name_for_github_remote.keys())}, aborting')
        current_user: Optional[str] = git_machete.github.derive_current_user_login()
        debug('sync_annotations_to_github_prs()',
              'Current GitHub user is ' + (current_user or '<none>'))
        pr: GitHubPullRequest
        all_prs: List[GitHubPullRequest] = derive_pull_requests(org, repo)
        self.__sync_annotations_to_definition_file(all_prs, current_user)

    def __sync_annotations_to_definition_file(self, prs: List[GitHubPullRequest], current_user: Optional[str] = None) -> None:
        for pr in prs:
            if pr.head in self.managed_branches:
                debug('sync_annotations_to_definition_file()',
                      f'{pr} corresponds to a managed branch')
                anno: str = f'PR #{pr.number}'
                if pr.user != current_user:
                    anno += f' ({pr.user})'
                upstream: Optional[str] = self.up_branch.get(pr.head)
                if pr.base != upstream:
                    warn(f'branch `{pr.head}` has a different base in PR #{pr.number} (`{pr.base}`) '
                         f'than in machete file (`{upstream or "<none, is a root>"}`)')
                    anno += f" WRONG PR BASE or MACHETE PARENT? PR has '{pr.base}'"
                if self.__annotations.get(pr.head) != anno:
                    print(fmt(f'Annotating <b>{pr.head}</b> as `{anno}`'))
                    self.__annotations[pr.head] = anno
            else:
                debug('sync_annotations_to_definition_file()',
                      f'{pr} does NOT correspond to a managed branch')
        self.save_definition_file()

    # Parse and evaluate direction against current branch for show/go commands
    def parse_direction(self, param: str, branch: str, allow_current: bool, down_pick_mode: bool) -> str:
        if param in ("c", "current") and allow_current:
            return self.__git.get_current_branch()  # throws in case of detached HEAD, as in the spec
        elif param in ("d", "down"):
            return self.down(branch, pick_mode=down_pick_mode)
        elif param in ("f", "first"):
            return self.first_branch(branch)
        elif param in ("l", "last"):
            return self.last_branch(branch)
        elif param in ("n", "next"):
            return self.next_branch(branch)
        elif param in ("p", "prev"):
            return self.prev_branch(branch)
        elif param in ("r", "root"):
            return self.root_branch(branch, if_unmanaged=PICK_FIRST_ROOT)
        elif param in ("u", "up"):
            return self.up(branch, prompt_if_inferred_msg=None, prompt_if_inferred_yes_opt_msg=None)
        else:
            raise MacheteException(f"Invalid direction: `{param}` expected: {allowed_directions(allow_current)}")

    def __match_log_to_filtered_reflogs(self, branch: str) -> Generator[Tuple[str, List[BRANCH_DEF]], None, None]:

        if branch not in self.__git.get_local_branches():
            raise MacheteException(f"`{branch}` is not a local branch")

        if self.__branch_defs_by_sha_in_reflog is None:
            def generate_entries() -> Generator[Tuple[str, BRANCH_DEF], None, None]:
                for lb in self.__git.get_local_branches():
                    lb_shas = set()
                    for sha_ in self.filtered_reflog(lb, prefix="refs/heads/"):
                        lb_shas.add(sha_)
                        yield sha_, (lb, lb)
                    remote_branch = self.__git.get_combined_counterpart_for_fetching_of_branch(lb)
                    if remote_branch:
                        for sha_ in self.filtered_reflog(remote_branch, prefix="refs/remotes/"):
                            if sha_ not in lb_shas:
                                yield sha_, (lb, remote_branch)

            self.__branch_defs_by_sha_in_reflog = {}
            for sha, branch_def in generate_entries():
                if sha in self.__branch_defs_by_sha_in_reflog:
                    # The practice shows that it's rather unlikely for a given
                    # commit to appear on filtered reflogs of two unrelated branches
                    # ("unrelated" as in, not a local branch and its remote
                    # counterpart) but we need to handle this case anyway.
                    self.__branch_defs_by_sha_in_reflog[sha] += [branch_def]
                else:
                    self.__branch_defs_by_sha_in_reflog[sha] = [branch_def]

            def log_result() -> Generator[str, None, None]:
                branch_defs: List[BRANCH_DEF]
                sha_: str
                for sha_, branch_defs in self.__branch_defs_by_sha_in_reflog.items():
                    def branch_def_to_str(lb: str, lb_or_rb: str) -> str:
                        return lb if lb == lb_or_rb else f"{lb_or_rb} (remote counterpart of {lb})"

                    joined_branch_defs = ", ".join(map(tupled(branch_def_to_str), branch_defs))
                    yield dim(f"{sha_} => {joined_branch_defs}")

            debug(f"match_log_to_filtered_reflogs({branch})",
                  "branches containing the given SHA in their filtered reflog: \n%s\n" % "\n".join(log_result()))

        for sha in self.__git.spoonfeed_log_shas(branch):
            if sha in self.__branch_defs_by_sha_in_reflog:
                # The entries must be sorted by lb_or_rb to make sure the
                # upstream inference is deterministic (and does not depend on the
                # order in which `generate_entries` iterated through the local branches).
                branch_defs: List[BRANCH_DEF] = self.__branch_defs_by_sha_in_reflog[sha]

                def lb_is_not_b(lb: str, lb_or_rb: str) -> bool:
                    return lb != branch

                containing_branch_defs = sorted(filter(tupled(lb_is_not_b), branch_defs), key=get_second)
                if containing_branch_defs:
                    debug(f"match_log_to_filtered_reflogs({branch})",
                          f"commit {sha} found in filtered reflog of {' and '.join(map(get_second, branch_defs))}")
                    yield sha, containing_branch_defs
                else:
                    debug(f"match_log_to_filtered_reflogs({branch})",
                          f"commit {sha} found only in filtered reflog of {' and '.join(map(get_second, branch_defs))}; ignoring")
            else:
                debug(f"match_log_to_filtered_reflogs({branch})",
                      f"commit {sha} not found in any filtered reflog")

    def __infer_upstream(self, branch: str, condition: Callable[[str], bool] = lambda upstream: True, reject_reason_message: str = "") -> Optional[str]:
        for sha, containing_branch_defs in self.__match_log_to_filtered_reflogs(branch):
            debug(f"infer_upstream({branch})",
                  f"commit {sha} found in filtered reflog of {' and '.join(map(get_second, containing_branch_defs))}")

            for candidate, original_matched_branch in containing_branch_defs:
                if candidate != original_matched_branch:
                    debug(f"infer_upstream({branch})",
                          f"upstream candidate is {candidate}, which is the local counterpart of {original_matched_branch}")

                if condition(candidate):
                    debug(f"infer_upstream({branch})", f"upstream candidate {candidate} accepted")
                    return candidate
                else:
                    debug(f"infer_upstream({branch})",
                          f"upstream candidate {candidate} rejected ({reject_reason_message})")
        return None

    @staticmethod
    def config_key_for_override_fork_point_to(branch: str) -> str:
        return f"machete.overrideForkPoint.{branch}.to"

    @staticmethod
    def config_key_for_override_fork_point_while_descendant_of(branch: str) -> str:
        return f"machete.overrideForkPoint.{branch}.whileDescendantOf"

    # Also includes config that is incomplete (only one entry out of two) or otherwise invalid.
    def has_any_fork_point_override_config(self, branch: str) -> bool:
        return (self.__git.get_config_attr_or_none(self.config_key_for_override_fork_point_to(branch)) or
                self.__git.get_config_attr_or_none(self.config_key_for_override_fork_point_while_descendant_of(branch))) is not None

    def __get_fork_point_override_data(self, branch: str) -> Optional[Tuple[str, str]]:
        to_key = self.config_key_for_override_fork_point_to(branch)
        to = self.__git.get_config_attr_or_none(to_key)
        while_descendant_of_key = self.config_key_for_override_fork_point_while_descendant_of(branch)
        while_descendant_of = self.__git.get_config_attr_or_none(while_descendant_of_key)
        if not to and not while_descendant_of:
            return None
        if to and not while_descendant_of:
            warn(f"{to_key} config is set but {while_descendant_of_key} config is missing")
            return None
        if not to and while_descendant_of:
            warn(f"{while_descendant_of_key} config is set but {to_key} config is missing")
            return None

        to_sha: Optional[str] = self.__git.get_commit_sha_by_revision(to, prefix="")
        while_descendant_of_sha: Optional[str] = self.__git.get_commit_sha_by_revision(while_descendant_of, prefix="")
        if not to_sha or not while_descendant_of_sha:
            if not to_sha:
                warn(f"{to_key} config value `{to}` does not point to a valid commit")
            if not while_descendant_of_sha:
                warn(f"{while_descendant_of_key} config value `{while_descendant_of}` does not point to a valid commit")
            return None
        # This check needs to be performed every time the config is retrieved.
        # We can't rely on the values being validated in set_fork_point_override(),
        # since the config could have been modified outside of git-machete.
        if not self.__git.is_ancestor_or_equal(to_sha, while_descendant_of_sha, earlier_prefix="", later_prefix=""):
            warn(
                f"commit {self.__git.get_short_commit_sha_by_revision(to)} pointed by {to_key} config "
                f"is not an ancestor of commit {self.__git.get_short_commit_sha_by_revision(while_descendant_of)} "
                f"pointed by {while_descendant_of_key} config")
            return None
        return to_sha, while_descendant_of_sha

    def __get_overridden_fork_point(self, branch: str) -> Optional[str]:
        override_data = self.__get_fork_point_override_data(branch)
        if not override_data:
            return None

        to, while_descendant_of = override_data
        # Note that this check is distinct from the is_ancestor check performed in
        # get_fork_point_override_data.
        # While the latter checks the sanity of fork point override configuration,
        # the former checks if the override still applies to wherever the given
        # branch currently points.
        if not self.__git.is_ancestor_or_equal(while_descendant_of, branch, earlier_prefix=""):
            warn(fmt(
                f"since branch <b>{branch}</b> is no longer a descendant of commit {self.__git.get_short_commit_sha_by_revision(while_descendant_of)}, ",
                f"the fork point override to commit {self.__git.get_short_commit_sha_by_revision(to)} no longer applies.\n",
                "Consider running:\n",
                f"  `git machete fork-point --unset-override {branch}`\n"))
            return None
        debug(f"get_overridden_fork_point({branch})",
              f"since branch {branch} is descendant of while_descendant_of={while_descendant_of}, fork point of {branch} is overridden to {to}")
        return to

    def unset_fork_point_override(self, branch: str) -> None:
        self.__git.unset_config_attr(self.config_key_for_override_fork_point_to(branch))
        self.__git.unset_config_attr(self.config_key_for_override_fork_point_while_descendant_of(branch))

    def set_fork_point_override(self, branch: str, to_revision: str) -> None:
        if branch not in self.__git.get_local_branches():
            raise MacheteException(f"`{branch}` is not a local branch")
        to_sha = self.__git.get_commit_sha_by_revision(to_revision, prefix="")
        if not to_sha:
            raise MacheteException(f"Cannot find revision {to_revision}")
        if not self.__git.is_ancestor_or_equal(to_sha, branch, earlier_prefix=""):
            raise MacheteException(
                f"Cannot override fork point: {self.__git.get_revision_repr(to_revision)} is not an ancestor of {branch}")

        to_key = self.config_key_for_override_fork_point_to(branch)
        self.__git.set_config_attr(to_key, to_sha)

        while_descendant_of_key = self.config_key_for_override_fork_point_while_descendant_of(branch)
        b_sha = self.__git.get_commit_sha_by_revision(branch, prefix="refs/heads/")
        self.__git.set_config_attr(while_descendant_of_key, b_sha)

        sys.stdout.write(
            fmt(f"Fork point for <b>{branch}</b> is overridden to <b>{self.__git.get_revision_repr(to_revision)}</b>.\n", f"This applies as long as {branch} points to (or is descendant of) its current head (commit {self.__git.get_short_commit_sha_by_revision(b_sha)}).\n\n", f"This information is stored under git config keys:\n  * `{to_key}`\n  * `{while_descendant_of_key}`\n\n", f"To unset this override, use:\n  `git machete fork-point --unset-override {branch}`\n"))

    def __pick_remote(self, branch: str, is_called_from_traverse: bool) -> None:
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
            self.handle_untracked_branch(rems[index], branch, is_called_from_traverse)
        except ValueError:
            if not is_called_from_traverse:
                raise MacheteException('Could not establish remote repository, pull request creation interrupted.')

    def handle_untracked_branch(self, new_remote: str, branch: str, is_called_from_traverse: bool) -> None:
        rems: List[str] = self.__git.get_remotes()
        can_pick_other_remote = len(rems) > 1
        other_remote_choice = "o[ther-remote]" if can_pick_other_remote else ""
        remote_branch = f"{new_remote}/{branch}"
        if not self.__git.get_commit_sha_by_revision(remote_branch, prefix="refs/remotes/"):
            choices = get_pretty_choices(*('y', 'N', 'q', 'yq', other_remote_choice) if is_called_from_traverse else ('y', 'Q', other_remote_choice))
            ask_message = f"Push untracked branch {bold(branch)} to {bold(new_remote)}?" + choices
            ask_opt_yes_message = f"Pushing untracked branch {bold(branch)} to {bold(new_remote)}..."
            ans = self.ask_if(ask_message, ask_opt_yes_message,
                              override_answer=None if self.__git._cli_opts.opt_push_untracked else "N")
            if is_called_from_traverse:
                if ans in ('y', 'yes', 'yq'):
                    self.__git.push(new_remote, branch)
                    if ans == 'yq':
                        raise StopInteraction
                    self.flush_caches()
                elif can_pick_other_remote and ans in ('o', 'other'):
                    self.__pick_remote(branch, is_called_from_traverse)
                elif ans in ('q', 'quit'):
                    raise StopInteraction
                return
            else:
                if ans in ('y', 'yes'):
                    self.__git.push(new_remote, branch)
                    self.flush_caches()
                elif can_pick_other_remote and ans in ('o', 'other'):
                    self.__pick_remote(branch, is_called_from_traverse)
                elif ans in ('q', 'quit'):
                    raise StopInteraction
                else:
                    raise MacheteException(f'Cannot create pull request from untracked branch `{branch}`')
                return

        relation: int = self.__git.get_relation_to_remote_counterpart(branch, remote_branch)

        message: str = {
            IN_SYNC_WITH_REMOTE:
                f"Branch {bold(branch)} is untracked, but its remote counterpart candidate {bold(remote_branch)} already exists and both branches point to the same commit.",
            BEHIND_REMOTE:
                f"Branch {bold(branch)} is untracked, but its remote counterpart candidate {bold(remote_branch)} already exists and is ahead of {bold(branch)}.",
            AHEAD_OF_REMOTE:
                f"Branch {bold(branch)} is untracked, but its remote counterpart candidate {bold(remote_branch)} already exists and is behind {bold(branch)}.",
            DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                f"Branch {bold(branch)} is untracked, it diverged from its remote counterpart candidate {bold(remote_branch)}, and has {bold('older')} commits than {bold(remote_branch)}.",
            DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                f"Branch {bold(branch)} is untracked, it diverged from its remote counterpart candidate {bold(remote_branch)}, and has {bold('newer')} commits than {bold(remote_branch)}."
        }[relation]

        ask_message, ask_opt_yes_message = {
            IN_SYNC_WITH_REMOTE: (
                f"Set the remote of {bold(branch)} to {bold(new_remote)} without pushing or pulling?" + get_pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Setting the remote of {bold(branch)} to {bold(new_remote)}..."
            ),
            BEHIND_REMOTE: (
                f"Pull {bold(branch)} (fast-forward only) from {bold(new_remote)}?" + get_pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Pulling {bold(branch)} (fast-forward only) from {bold(new_remote)}..."
            ),
            AHEAD_OF_REMOTE: (
                f"Push branch {bold(branch)} to {bold(new_remote)}?" + get_pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Pushing branch {bold(branch)} to {bold(new_remote)}..."
            ),
            DIVERGED_FROM_AND_OLDER_THAN_REMOTE: (
                f"Reset branch {bold(branch)} to the commit pointed by {bold(remote_branch)}?" + get_pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Resetting branch {bold(branch)} to the commit pointed by {bold(remote_branch)}..."
            ),
            DIVERGED_FROM_AND_NEWER_THAN_REMOTE: (
                f"Push branch {bold(branch)} with force-with-lease to {bold(new_remote)}?" + get_pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Pushing branch {bold(branch)} with force-with-lease to {bold(new_remote)}..."
            )
        }[relation]

        override_answer: Optional[str] = {
            IN_SYNC_WITH_REMOTE: None,
            BEHIND_REMOTE: None,
            AHEAD_OF_REMOTE: None if self.__cli_opts.opt_push_tracked else "N",
            DIVERGED_FROM_AND_OLDER_THAN_REMOTE: None,
            DIVERGED_FROM_AND_NEWER_THAN_REMOTE: None if self.__cli_opts.opt_push_tracked else "N",
        }[relation]

        yes_action: Callable[[], None] = {
            IN_SYNC_WITH_REMOTE: lambda: self.__git.set_upstream_to(remote_branch),
            BEHIND_REMOTE: lambda: self.__git.pull_ff_only(new_remote, remote_branch),
            AHEAD_OF_REMOTE: lambda: self.__git.push(new_remote, branch),
            DIVERGED_FROM_AND_OLDER_THAN_REMOTE: lambda: self.__git.reset_keep(remote_branch),
            DIVERGED_FROM_AND_NEWER_THAN_REMOTE: lambda: self.__git.push(
                new_remote, branch, force_with_lease=True)
        }[relation]

        print(message)
        ans = self.ask_if(ask_message, ask_opt_yes_message, override_answer=override_answer)
        if ans in ('y', 'yes', 'yq'):
            yes_action()
            if ans == 'yq':
                raise StopInteraction
            self.flush_caches()
        elif can_pick_other_remote and ans in ('o', 'other'):
            self.__pick_remote(branch, is_called_from_traverse)
        elif ans in ('q', 'quit'):
            raise StopInteraction

    def is_merged_to(self, branch: str, target: str) -> bool:
        if self.__git.is_ancestor_or_equal(branch, target):
            # If branch is ancestor of or equal to the target, we need to distinguish between the
            # case of branch being "recently" created from the target and the case of
            # branch being fast-forward-merged to the target.
            # The applied heuristics is to check if the filtered reflog of the branch
            # (reflog stripped of trivial events like branch creation, reset etc.)
            # is non-empty.
            return bool(self.filtered_reflog(branch, prefix="refs/heads/"))
        elif self.__cli_opts.opt_no_detect_squash_merges:
            return False
        else:
            # In the default mode.
            # If there is a commit in target with an identical tree state to branch,
            # then branch may be squash or rebase merged into target.
            return self.__git.does_contain_equivalent_tree(branch, target)

    def ask_if(self, msg: str, opt_yes_msg: Optional[str],
               override_answer: Optional[str] = None,
               apply_fmt: bool = True) -> str:
        if override_answer:
            return override_answer
        if self.__cli_opts.opt_yes and opt_yes_msg:
            print(fmt(opt_yes_msg) if apply_fmt else opt_yes_msg)
            return 'y'
        return input(fmt(msg) if apply_fmt else msg).lower()

    @staticmethod
    def pick(choices: List[str], name: str, apply_fmt: bool = True) -> str:
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
        self.__branch_defs_by_sha_in_reflog = None
        self.__git.flush_caches()

    def checkout_github_prs(self, pr_no: int) -> None:
        org: str
        repo: str
        remote: str
        remote, (org, repo) = self.__derive_remote_and_github_org_and_repo()
        current_user: Optional[str] = git_machete.github.derive_current_user_login()
        debug('checkout_github_pr()', f'organization is {org}, repository is {repo}')

        pr = get_pull_request_by_number_or_none(pr_no, org, repo)
        if not pr:
            raise MacheteException(f"PR #{pr_no} is not found in repository `{org}/{repo}`")
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
                print(f"Fetching {remote_to_fetch}...")
                self.__git.fetch_remote(remote_to_fetch)
                if '/'.join([remote_to_fetch, pr.head]) not in self.__git.get_remote_branches():
                    raise MacheteException(f"Could not check out PR #{pr_no} because its head branch `{pr.head}` is already deleted from `{remote_to_fetch}`.")
        else:
            warn(f'Pull request #{pr_no} comes from fork and its repository is already deleted. No remote tracking data will be set up for `{pr.head}` branch.')
            print(fmt(f"Checking out `{pr.head}` locally..."))
            checkout_pr_refs(self.__git, remote, pr_no, pr.head)
            self.flush_caches()
        if pr.state == 'closed':
            warn(f'Pull request #{pr_no} is already closed.')
        debug('checkout_github_pr()', f'found {pr}')

        all_open_prs: List[GitHubPullRequest] = derive_pull_requests(org, repo)

        self.__cli_opts.opt_yes = True  # TODO (#161): pass only needed options to methods
        path: List[str] = self.__get_path_from_pr_chain(pr, all_open_prs)
        reversed_path: List[str] = path[::-1]  # need to add from root downwards
        for index, branch in enumerate(reversed_path):
            if branch not in self.managed_branches:
                if index == 0:
                    self.__cli_opts.opt_as_root = True
                    self.add(branch)
                    self.__cli_opts.opt_as_root = False
                else:
                    self.__cli_opts.opt_onto = reversed_path[index - 1]
                    self.add(branch)
        self.__cli_opts.opt_yes = False

        debug('checkout_github_pr()',
              'Current GitHub user is ' + (current_user or '<none>'))
        self.__sync_annotations_to_definition_file(all_open_prs, current_user)

        self.__git.checkout(pr.head)
        print(fmt(f"Pull request `#{pr.number}` checked out at local branch `{pr.head}`"))

    def __get_path_from_pr_chain(self, current_pr: GitHubPullRequest, all_open_prs: List[GitHubPullRequest]) -> List[str]:
        path: List[str] = [current_pr.head]
        while current_pr:
            path.append(current_pr.base)
            current_pr = utils.find_or_none(lambda x: x.head == current_pr.base, all_open_prs)
        return path

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
            if is_github_remote_url(url) and get_parsed_github_remote_url(url) == get_parsed_github_remote_url(remote_url):
                return remote
        return None

    def retarget_github_pr(self, head: str) -> None:
        org: str
        repo: str
        _, (org, repo) = self.__derive_remote_and_github_org_and_repo()

        debug(f'retarget_github_pr({head})', f'organization is {org}, repository is {repo}')

        pr: Optional[GitHubPullRequest] = derive_pull_request_by_head(org, repo, head)
        if not pr:
            raise MacheteException(f'No PR is opened in `{org}/{repo}` for branch `{head}`')
        debug(f'retarget_github_pr({head})', f'found {pr}')

        new_base: Optional[str] = self.up_branch.get(head)
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

    def __derive_remote_and_github_org_and_repo(self) -> Tuple[str, Tuple[str, str]]:
        url_for_remote: Dict[str, str] = {
            remote: self.__git.get_url_of_remote(remote) for remote in self.__git.get_remotes()
        }
        if not url_for_remote:
            raise MacheteException(fmt('No remotes defined for this repository (see `git remote`)'))

        org_and_repo_for_github_remote: Dict[str, Tuple[str, str]] = {
            remote: get_parsed_github_remote_url(url) for remote, url in url_for_remote.items() if is_github_remote_url(url)
        }
        if not org_and_repo_for_github_remote:
            raise MacheteException(
                fmt('Remotes are defined for this repository, but none of them '
                    'corresponds to GitHub (see `git remote -v` for details)\n'))

        if len(org_and_repo_for_github_remote) == 1:
            return list(org_and_repo_for_github_remote.items())[0]

        if 'origin' in org_and_repo_for_github_remote:
            return 'origin', org_and_repo_for_github_remote['origin']

        raise MacheteException(
            f'Multiple non-origin remotes correspond to GitHub in this repository: '
            f'{", ".join(org_and_repo_for_github_remote.keys())}, aborting')

    def create_github_pr(self, head: str, draft: bool) -> None:
        # first make sure that head branch is synced with remote
        self.__sync_before_creating_pr()
        self.flush_caches()

        base: Optional[str] = self.up_branch.get(head)
        org: str
        repo: str
        _, (org, repo) = self.__derive_remote_and_github_org_and_repo()
        current_user: Optional[str] = git_machete.github.derive_current_user_login()
        debug(f'create_github_pr({head})', f'organization is {org}, repository is {repo}')
        debug(f'create_github_pr({head})', 'current GitHub user is ' + (current_user or '<none>'))

        title: str = self.__git.get_commit_information("subject").strip()
        description_path = self.__git.get_git_subpath('info', 'description')
        description: str = utils.slurp_file_or_empty(description_path)

        ok_str = ' <green><b>OK</b></green>'
        print(fmt(f'Creating a {"draft " if draft else ""}PR from `{head}` to `{base}`...'), end='', flush=True)
        pr: GitHubPullRequest = create_pull_request(org, repo, head=head, base=base, title=title,
                                                    description=description, draft=draft)
        print(fmt(f'{ok_str}, see <b>{pr.html_url}</b>'))

        milestone_path: str = self.__git.get_git_subpath('info', 'milestone')
        milestone: str = utils.slurp_file_or_empty(milestone_path).strip()
        if milestone:
            print(fmt(f'Setting milestone of PR #{pr.number} to {milestone}...'), end='', flush=True)
            set_milestone_of_pull_request(org, repo, pr.number, milestone=milestone)
            print(fmt(ok_str))

        if current_user:
            print(fmt(f'Adding `{current_user}` as assignee to PR #{pr.number}...'), end='', flush=True)
            add_assignees_to_pull_request(org, repo, pr.number, [current_user])
            print(fmt(ok_str))

        reviewers_path = self.__git.get_git_subpath('info', 'reviewers')
        reviewers: List[str] = utils.get_non_empty_lines(utils.slurp_file_or_empty(reviewers_path))
        if reviewers:
            print(
                fmt(f'Adding {", ".join(f"`{reviewer}`" for reviewer in reviewers)} as reviewer{"s" if len(reviewers) > 1 else ""} to PR #{pr.number}...'),
                end='', flush=True)
            add_reviewers_to_pull_request(org, repo, pr.number, reviewers)
            print(fmt(ok_str))

        self.__annotations[head] = f'PR #{pr.number}'
        self.save_definition_file()

    def __handle_diverged_and_newer_state(self, current_branch: str, remote: str, is_called_from_traverse: bool = True) -> None:
        self.__print_new_line(False)
        remote_branch = self.__git.get_strict_counterpart_for_fetching_of_branch(current_branch)
        choices = get_pretty_choices(*('y', 'N', 'q', 'yq') if is_called_from_traverse else ('y', 'N', 'q'))
        ans = self.ask_if(
            f"Branch {bold(current_branch)} diverged from (and has newer commits than) its remote counterpart {bold(remote_branch)}.\n"
            f"Push {bold(current_branch)} with force-with-lease to {bold(remote)}?" + choices,
            f"Branch {bold(current_branch)} diverged from (and has newer commits than) its remote counterpart {bold(remote_branch)}.\n"
            f"Pushing {bold(current_branch)} with force-with-lease to {bold(remote)}...",
            override_answer=None if self.__cli_opts.opt_push_tracked else "N")
        if ans in ('y', 'yes', 'yq'):
            self.__git.push(remote, current_branch, force_with_lease=True)
            if ans == 'yq':
                if is_called_from_traverse:
                    raise StopInteraction
            self.flush_caches()
        elif ans in ('q', 'quit'):
            if is_called_from_traverse:
                raise StopInteraction

    def __handle_untracked_state(self, branch: str, is_called_from_traverse: bool) -> None:
        rems: List[str] = self.__git.get_remotes()
        rmt: Optional[str] = self.__git.get_inferred_remote_for_fetching_of_branch(branch)
        self.__print_new_line(False)
        if rmt:
            self.handle_untracked_branch(rmt, branch, is_called_from_traverse)
        elif len(rems) == 1:
            self.handle_untracked_branch(rems[0], branch, is_called_from_traverse)
        elif "origin" in rems:
            self.handle_untracked_branch("origin", branch, is_called_from_traverse)
        else:
            # We know that there is at least 1 remote, otherwise 's' would be 'NO_REMOTES'
            print(fmt(f"Branch `{bold(branch)}` is untracked and there's no `{bold('origin')}` repository."))
            self.__pick_remote(branch, is_called_from_traverse)

    def __handle_ahead_state(self, current_branch: str, remote: str, is_called_from_traverse: bool) -> None:
        self.__print_new_line(False)
        choices = get_pretty_choices(*('y', 'N', 'q', 'yq') if is_called_from_traverse else ('y', 'N', 'q'))
        ans = self.ask_if(
            f"Push {bold(current_branch)} to {bold(remote)}?" + choices,
            f"Pushing {bold(current_branch)} to {bold(remote)}...",
            override_answer=None if self.__cli_opts.opt_push_tracked else "N"
        )
        if ans in ('y', 'yes', 'yq'):
            self.__git.push(remote, current_branch)
            if ans == 'yq':
                if is_called_from_traverse:
                    raise StopInteraction
            self.flush_caches()
        elif ans in ('q', 'quit'):
            if is_called_from_traverse:
                raise StopInteraction

    def __handle_diverged_and_older_state(self, branch: str) -> None:
        self.__print_new_line(False)
        remote_branch = self.__git.get_strict_counterpart_for_fetching_of_branch(branch)
        ans = self.ask_if(
            f"Branch {bold(branch)} diverged from (and has older commits than) its remote counterpart {bold(remote_branch)}.\nReset branch {bold(branch)} to the commit pointed by {bold(remote_branch)}?" + get_pretty_choices(
                'y', 'N', 'q', 'yq'),
            f"Branch {bold(branch)} diverged from (and has older commits than) its remote counterpart {bold(remote_branch)}.\nResetting branch {bold(branch)} to the commit pointed by {bold(remote_branch)}...")
        if ans in ('y', 'yes', 'yq'):
            self.__git.reset_keep(remote_branch)
            if ans == 'yq':
                raise StopInteraction
            self.flush_caches()
        elif ans in ('q', 'quit'):
            raise StopInteraction

    def __handle_behind_state(self, branch: str, remote: str) -> None:
        remote_branch = self.__git.get_strict_counterpart_for_fetching_of_branch(branch)
        ans = self.ask_if(
            f"Branch {bold(branch)} is behind its remote counterpart {bold(remote_branch)}.\n"
            f"Pull {bold(branch)} (fast-forward only) from {bold(remote)}?" + get_pretty_choices('y', 'N', 'q', 'yq'),
            f"Branch {bold(branch)} is behind its remote counterpart {bold(remote_branch)}.\nPulling {bold(branch)} (fast-forward only) from {bold(remote)}...")
        if ans in ('y', 'yes', 'yq'):
            self.__git.pull_ff_only(remote, remote_branch)
            if ans == 'yq':
                raise StopInteraction
            self.flush_caches()
            print("")
        elif ans in ('q', 'quit'):
            raise StopInteraction

    def __sync_before_creating_pr(self) -> None:

        self.expect_at_least_one_managed_branch()
        self.__empty_line_status = True

        current_branch = self.__git.get_current_branch()
        if current_branch not in self.managed_branches:
            self.add(current_branch)
            if current_branch not in self.managed_branches:
                raise MacheteException(
                    "Command `github create-pr` can NOT be executed on the branch"
                    " that is not managed by git machete (is not present in git "
                    "machete definition file). To successfully execute this command "
                    "either add current branch to the file via commands `add`, "
                    "`discover` or `edit` or agree on adding the branch to the "
                    "definition file during the execution of `github create-pr` command.")

        up_branch: Optional[str] = self.up_branch.get(current_branch)
        if not up_branch:
            raise MacheteException(
                f'Branch `{current_branch}` does not have a parent branch (it is a root), '
                'base branch for the PR cannot be established.')

        if self.__git.is_ancestor_or_equal(current_branch, up_branch):
            raise MacheteException(
                f'All commits in `{current_branch}` branch  are already included in `{up_branch}` branch.\nCannot create pull request.')

        s, remote = self.__git.get_strict_remote_sync_status(current_branch)
        statuses_to_sync = (UNTRACKED, AHEAD_OF_REMOTE, DIVERGED_FROM_AND_NEWER_THAN_REMOTE)
        needs_remote_sync = s in statuses_to_sync

        if needs_remote_sync:
            if s == AHEAD_OF_REMOTE:
                self.__handle_ahead_state(current_branch, remote, is_called_from_traverse=False)
            elif s == UNTRACKED:
                self.__handle_untracked_state(current_branch, is_called_from_traverse=False)
            elif s == DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                self.__handle_diverged_and_newer_state(
                    current_branch, remote, is_called_from_traverse=False)

            self.__print_new_line(False)
            self.status(warn_on_yellow_edges=True)
            self.__print_new_line(False)

        else:
            if s == BEHIND_REMOTE:
                warn(f"Branch {current_branch} is in <b>BEHIND_REMOTE</b> state.\nConsider using 'git pull'.\n")
                self.__print_new_line(False)
                ans = self.ask_if("Proceed with pull request creation?" + get_pretty_choices('y', 'Q'),
                                  "Proceeding with pull request creation...")
            elif s == DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                warn(f"Branch {current_branch} is in <b>DIVERGED_FROM_AND_OLDER_THAN_REMOTE</b> state.\nConsider using 'git reset --keep'.\n")
                self.__print_new_line(False)
                ans = self.ask_if("Proceed with pull request creation?" + get_pretty_choices('y', 'Q'),
                                  "Proceeding with pull request creation...")
            elif s == NO_REMOTES:
                raise MacheteException(
                    "Could not create pull request - there are no remote repositories!")
            else:
                ans = 'y'  # only IN SYNC status is left

            if ans in ('y', 'yes'):
                return
            else:
                raise MacheteException('Pull request creation interrupted.')
