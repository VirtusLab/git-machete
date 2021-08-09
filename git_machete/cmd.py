#!/usr/bin/env python

from typing import Callable, Dict, Generator, List, Optional, Tuple, TypeVar

from git_machete import __version__
import datetime
import getopt
import io
import itertools
import os
import re
import shutil
import sys
import textwrap

from git_machete import utils
from git_machete.utils import dim, pretty_choices, bold, colored, debug, fmt, underline, flat_map, tupled, get_second, excluding, warn
from git_machete.options import CommandLineOptions
from git_machete.exceptions import MacheteException, StopTraversal
from git_machete.docs import short_docs, long_docs
from git_machete.git_operations import GitContext
from git_machete.constants import AHEAD_OF_REMOTE, BEHIND_REMOTE, BOLD, DIM, DISCOVER_DEFAULT_FRESH_BRANCH_COUNT, \
    DIVERGED_FROM_AND_NEWER_THAN_REMOTE, DIVERGED_FROM_AND_OLDER_THAN_REMOTE, ENDC, GREEN, IN_SYNC_WITH_REMOTE, \
    NO_REMOTES, ORANGE, PICK_FIRST_ROOT, PICK_LAST_ROOT, RED, UNTRACKED, YELLOW


# Core utils

T = TypeVar('T')

BRANCH_DEF = Tuple[str, str]
Hash_ShortHash_Message = Tuple[str, str, str]
initial_current_directory: Optional[str] = utils.current_directory_or_none() or os.getenv('PWD')


# Manipulation on definition file/tree of branches


class MacheteClient:

    def __init__(self, cli_opts: CommandLineOptions, git: GitContext) -> None:
        self.cli_opts: CommandLineOptions = cli_opts
        self.git: GitContext = git
        self._definition_file_path: str = self.git.get_git_subpath("machete")
        self._managed_branches: List[str] = []
        self.down_branches: Dict[str, List[str]] = {}  # TODO (#110): default dict with []
        self.up_branch: Dict[str, str] = {}  # TODO (#110): default dict with None
        self.__indent: Optional[str] = None
        self.__roots: List[str] = []
        self.__annotations: Dict[str, str] = {}
        self.__empty_line_status: Optional[bool] = None

    @property
    def definition_file_path(self) -> str:
        return self._definition_file_path

    @definition_file_path.setter
    def definition_file_path(self, val: str) -> None:
        self._definition_file_path = val

    @property
    def managed_branches(self) -> List[str]:
        return self._managed_branches

    @managed_branches.setter
    def managed_branches(self, val: List[str]) -> None:
        self._managed_branches = val

    def expect_in_managed_branches(self, b: str) -> None:
        if b not in self.managed_branches:
            raise MacheteException(
                f"Branch `{b}` not found in the tree of branch dependencies.\nUse `git machete add {b}` or `git machete edit`")

    def expect_at_least_one_managed_branch(self) -> None:
        if not self.__roots:
            self.__raise_no_branches_error()

    def __raise_no_branches_error(self) -> None:
        raise MacheteException(
            f"No branches listed in {self._definition_file_path}; use `git machete discover` or `git machete edit`, or edit {self._definition_file_path} manually.")

    def read_definition_file(self, verify_branches: bool = True) -> None:
        with open(self._definition_file_path) as f:
            lines: List[str] = [line.rstrip() for line in f.readlines() if not line.isspace()]

        at_depth = {}
        last_depth = -1

        hint = "Edit the definition file manually with `git machete edit`"

        invalid_branches: List[str] = []
        for index, line in enumerate(lines):
            prefix = "".join(itertools.takewhile(str.isspace, line))
            if prefix and not self.__indent:
                self.__indent = prefix

            b_a: List[str] = line.strip().split(" ", 1)
            b = b_a[0]
            if len(b_a) > 1:
                self.__annotations[b] = b_a[1]
            if b in self.managed_branches:
                raise MacheteException(
                    f"{self._definition_file_path}, line {index + 1}: branch `{b}` re-appears in the tree definition. {hint}")
            if verify_branches and b not in self.git.local_branches():
                invalid_branches += [b]
            self.managed_branches += [b]

            if prefix:
                depth: int = len(prefix) // len(self.__indent)
                if prefix != self.__indent * depth:
                    mapping: Dict[str, str] = {" ": "<SPACE>", "\t": "<TAB>"}
                    prefix_expanded: str = "".join(mapping[c] for c in prefix)
                    indent_expanded: str = "".join(mapping[c] for c in self.__indent)
                    raise MacheteException(
                        f"{self._definition_file_path}, line {index + 1}: invalid indent `{prefix_expanded}`, expected a multiply of `{indent_expanded}`. {hint}")
            else:
                depth = 0

            if depth > last_depth + 1:
                raise MacheteException(
                    f"{self._definition_file_path}, line {index + 1}: too much indent (level {depth}, expected at most {last_depth + 1}) for the branch `{b}`. {hint}")
            last_depth = depth

            at_depth[depth] = b
            if depth:
                p = at_depth[depth - 1]
                self.up_branch[b] = p
                if p in self.down_branches:
                    self.down_branches[p] += [b]
                else:
                    self.down_branches[p] = [b]
            else:
                self.__roots += [b]

        if not invalid_branches:
            return

        if len(invalid_branches) == 1:
            ans: str = self.ask_if(f"Skipping `{invalid_branches[0]}` " +
                                   "which is not a local branch (perhaps it has been deleted?).\n" +
                                   "Slide it out from the definition file?" +
                                   pretty_choices("y", "e[dit]", "N"), opt_yes_msg=None)
        else:
            ans = self.ask_if(f"Skipping {', '.join(f'`{b}`' for b in invalid_branches)} " +
                              "which are not local branches (perhaps they have been deleted?).\n" +
                              "Slide them out from the definition file?" +
                              pretty_choices("y", "e[dit]", "N"), opt_yes_msg=None)

        def recursive_slide_out_invalid_branches(b: str) -> List[str]:
            new_down_branches = flat_map(recursive_slide_out_invalid_branches, self.down_branches.get(b, []))
            if b in invalid_branches:
                if b in self.down_branches:
                    del self.down_branches[b]
                if b in self.__annotations:
                    del self.__annotations[b]
                if b in self.up_branch:
                    for d in new_down_branches:
                        self.up_branch[d] = self.up_branch[b]
                    del self.up_branch[b]
                else:
                    for d in new_down_branches:
                        del self.up_branch[d]
                return new_down_branches
            else:
                self.down_branches[b] = new_down_branches
                return [b]

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

        def render_dfs(b: str, depth: int) -> List[str]:
            self.annotation = f" {self.__annotations[b]}" if b in self.__annotations else ""
            res: List[str] = [depth * self.__indent + b + self.annotation]
            for d in self.down_branches.get(b, []):
                res += render_dfs(d, depth + 1)
            return res

        total: List[str] = []
        for r in self.__roots:
            total += render_dfs(r, depth=0)
        return total

    def back_up_definition_file(self) -> None:
        shutil.copyfile(self._definition_file_path, self._definition_file_path + "~")

    def save_definition_file(self) -> None:
        with open(self._definition_file_path, "w") as f:
            f.write("\n".join(self.render_tree()) + "\n")

    def add(self, b: str) -> None:
        if b in self.managed_branches:
            raise MacheteException(f"Branch `{b}` already exists in the tree of branch dependencies")

        onto: Optional[str] = self.cli_opts.opt_onto
        if onto:
            self.expect_in_managed_branches(onto)

        if b not in self.git.local_branches():
            rb: Optional[str] = self.git.get_sole_remote_branch(b)
            if rb:
                common_line = f"A local branch `{b}` does not exist, but a remote branch `{rb}` exists.\n"
                msg = common_line + f"Check out `{b}` locally?" + pretty_choices('y', 'N')
                opt_yes_msg = common_line + f"Checking out `{b}` locally..."
                if self.ask_if(msg, opt_yes_msg) in ('y', 'yes'):
                    self.git.create_branch(b, f"refs/remotes/{rb}")
                else:
                    return
                # Not dealing with `onto` here. If it hasn't been explicitly specified via `--onto`, we'll try to infer it now.
            else:
                out_of = f"refs/heads/{onto}" if onto else "HEAD"
                out_of_str = f"`{onto}`" if onto else "the current HEAD"
                msg = f"A local branch `{b}` does not exist. Create (out of {out_of_str})?" + pretty_choices('y', 'N')
                opt_yes_msg = f"A local branch `{b}` does not exist. Creating out of {out_of_str}"
                if self.ask_if(msg, opt_yes_msg) in ('y', 'yes'):
                    # If `--onto` hasn't been explicitly specified, let's try to assess if the current branch would be a good `onto`.
                    if self.__roots and not onto:
                        cb = self.git.current_branch_or_none()
                        if cb and cb in self.managed_branches:
                            onto = cb
                    self.git.create_branch(b, out_of)
                else:
                    return

        if self.cli_opts.opt_as_root or not self.__roots:
            self.__roots += [b]
            print(fmt(f"Added branch `{b}` as a new root"))
        else:
            if not onto:
                u = self.__infer_upstream(b, condition=lambda x: x in self.managed_branches, reject_reason_message="this candidate is not a managed branch")
                if not u:
                    raise MacheteException(f"Could not automatically infer upstream (parent) branch for `{b}`.\n"
                                           "You can either:\n"
                                           "1) specify the desired upstream branch with `--onto` or\n"
                                           f"2) pass `--as-root` to attach `{b}` as a new root or\n"
                                           "3) edit the definition file manually with `git machete edit`")
                else:
                    msg = f"Add `{b}` onto the inferred upstream (parent) branch `{u}`?" + pretty_choices('y', 'N')
                    opt_yes_msg = f"Adding `{b}` onto the inferred upstream (parent) branch `{u}`"
                    if self.ask_if(msg, opt_yes_msg) in ('y', 'yes'):
                        onto = u
                    else:
                        return

            self.up_branch[b] = onto
            if onto in self.down_branches:
                self.down_branches[onto].append(b)
            else:
                self.down_branches[onto] = [b]
            print(fmt(f"Added branch `{b}` onto `{onto}`"))

        self.save_definition_file()

    def annotate(self, b: str, words: List[str]) -> None:

        if b in self.__annotations and words == ['']:
            del self.__annotations[b]
        else:
            self.__annotations[b] = " ".join(words)
        self.save_definition_file()

    def print_annotation(self, b: str) -> None:
        if b in self.__annotations:
            print(self.__annotations[b])

    def update(self) -> None:
        cb = self.git.current_branch()
        if self.cli_opts.opt_merge:
            with_branch = self.up(cb,
                                  prompt_if_inferred_msg="Branch `%s` not found in the tree of branch dependencies. Merge with the inferred upstream `%s`?" + pretty_choices('y', 'N'),
                                  prompt_if_inferred_yes_opt_msg="Branch `%s` not found in the tree of branch dependencies. Merging with the inferred upstream `%s`...")
            self.git.merge(with_branch, cb)
        else:
            onto_branch = self.up(cb,
                                  prompt_if_inferred_msg="Branch `%s` not found in the tree of branch dependencies. Rebase onto the inferred upstream `%s`?" + pretty_choices('y', 'N'),
                                  prompt_if_inferred_yes_opt_msg="Branch `%s` not found in the tree of branch dependencies. Rebasing onto the inferred upstream `%s`...")
            self.git.rebase(f"refs/heads/{onto_branch}", self.cli_opts.opt_fork_point or self.fork_point(cb, use_overrides=True), cb)

    def discover_tree(self) -> None:
        all_local_branches = self.git.local_branches()
        if not all_local_branches:
            raise MacheteException("No local branches found")
        for r in self.cli_opts.opt_roots:
            if r not in self.git.local_branches():
                raise MacheteException(f"`{r}` is not a local branch")
        if self.cli_opts.opt_roots:
            self.__roots = list(self.cli_opts.opt_roots)
        else:
            self.__roots = []
            if "master" in self.git.local_branches():
                self.__roots += ["master"]
            elif "main" in self.git.local_branches():
                # See https://github.com/github/renaming
                self.__roots += ["main"]
            if "develop" in self.git.local_branches():
                self.__roots += ["develop"]
        self.down_branches = {}
        self.up_branch = {}
        self.__indent = "\t"
        self.__annotations = {}

        root_of = dict((b, b) for b in all_local_branches)

        def get_root_of(b: str) -> str:
            if b != root_of[b]:
                root_of[b] = get_root_of(root_of[b])
            return root_of[b]

        non_root_fixed_branches = excluding(all_local_branches, self.__roots)
        last_checkout_timestamps = self.git.get_latest_checkout_timestamps()
        non_root_fixed_branches_by_last_checkout_timestamps = sorted(
            (last_checkout_timestamps.get(b, 0), b) for b in non_root_fixed_branches)
        if self.cli_opts.opt_checked_out_since:
            threshold = self.git.parse_git_timespec_to_unix_timestamp(self.cli_opts.opt_checked_out_since)
            stale_non_root_fixed_branches = [b for (timestamp, b) in itertools.takewhile(
                tupled(lambda timestamp, b: timestamp < threshold),
                non_root_fixed_branches_by_last_checkout_timestamps
            )]
        else:
            c = DISCOVER_DEFAULT_FRESH_BRANCH_COUNT
            stale, fresh = non_root_fixed_branches_by_last_checkout_timestamps[:-c], non_root_fixed_branches_by_last_checkout_timestamps[-c:]
            stale_non_root_fixed_branches = [b for (timestamp, b) in stale]
            if stale:
                threshold_date = datetime.datetime.utcfromtimestamp(fresh[0][0]).strftime("%Y-%m-%d")
                warn(f"to keep the size of the discovered tree reasonable (ca. {c} branches), "
                     f"only branches checked out at or after ca. <b>{threshold_date}</b> are included.\n"
                     "Use `git machete discover --checked-out-since=<date>` (where <date> can be e.g. `'2 weeks ago'` or `2020-06-01`) "
                     "to change this threshold so that less or more branches are included.\n")
        self.managed_branches = excluding(all_local_branches, stale_non_root_fixed_branches)
        if self.cli_opts.opt_checked_out_since and not self.managed_branches:
            warn("no branches satisfying the criteria. Try moving the value of `--checked-out-since` further to the past.")
            return

        for b in excluding(non_root_fixed_branches, stale_non_root_fixed_branches):
            u = self.__infer_upstream(b, condition=lambda candidate: get_root_of(candidate) != b and candidate not in stale_non_root_fixed_branches, reject_reason_message="choosing this candidate would form a cycle in the resulting graph or the candidate is a stale branch")
            if u:
                debug("discover_tree()", f"inferred upstream of {b} is {u}, attaching {b} as a child of {u}\n")
                self.up_branch[b] = u
                root_of[b] = u
                if u in self.down_branches:
                    self.down_branches[u].append(b)
                else:
                    self.down_branches[u] = [b]
            else:
                debug("discover_tree()", f"inferred no upstream for {b}, attaching {b} as a new root\n")
                self.__roots += [b]

        # Let's remove merged branches for which no downstream branch have been found.
        merged_branches_to_skip = []
        for b in self.managed_branches:
            if b in self.up_branch and not self.down_branches.get(b):
                u = self.up_branch[b]
                if self.is_merged_to(b, u):
                    debug("discover_tree()",
                          f"inferred upstream of {b} is {u}, but {b} is merged to {u}; skipping {b} from discovered tree\n")
                    merged_branches_to_skip += [b]
        if merged_branches_to_skip:
            warn("skipping %s since %s merged to another branch and would not have any downstream branches.\n"
                 % (", ".join(f"`{b}`" for b in merged_branches_to_skip),
                    "it's" if len(merged_branches_to_skip) == 1 else "they're"))
            self.managed_branches = excluding(self.managed_branches, merged_branches_to_skip)
            for b in merged_branches_to_skip:
                u = self.up_branch[b]
                self.down_branches[u] = excluding(self.down_branches[u], [b])
                del self.up_branch[b]
            # We're NOT applying the removal process recursively,
            # so it's theoretically possible that some merged branches became childless
            # after removing the outer layer of childless merged branches.
            # This is rare enough, however, that we can pretty much ignore this corner case.

        print(bold("Discovered tree of branch dependencies:\n"))
        self.status(warn_on_yellow_edges=False)
        print("")
        do_backup = os.path.isfile(self._definition_file_path)
        backup_msg = f"\nThe existing definition file will be backed up as {self._definition_file_path}~" if do_backup else ""
        msg = f"Save the above tree to {self._definition_file_path}?{backup_msg}" + pretty_choices('y', 'e[dit]', 'N')
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
        for b in branches_to_slide_out:
            self.expect_in_managed_branches(b)
            new_upstream = self.up_branch.get(b)
            if not new_upstream:
                raise MacheteException(f"No upstream branch defined for `{b}`, cannot slide out")

        # Verify that all "interior" slide-out branches have a single downstream pointing to the next slide-out
        for bu, bd in zip(branches_to_slide_out[:-1], branches_to_slide_out[1:]):
            dbs = self.down_branches.get(bu)
            if not dbs or len(dbs) == 0:
                raise MacheteException(f"No downstream branch defined for `{bu}`, cannot slide out")
            elif len(dbs) > 1:
                flat_dbs = ", ".join(f"`{x}`" for x in dbs)
                raise MacheteException(f"Multiple downstream branches defined for `{bu}`: {flat_dbs}; cannot slide out")
            elif dbs != [bd]:
                raise MacheteException(f"'{bd}' is not downstream of '{bu}', cannot slide out")

            if self.up_branch[bd] != bu:
                raise MacheteException(f"`{bu}` is not upstream of `{bd}`, cannot slide out")

        # Get new branches
        new_upstream = self.up_branch[branches_to_slide_out[0]]
        new_downstreams = self.down_branches.get(branches_to_slide_out[-1], [])

        # Remove the slide-out branches from the tree
        for b in branches_to_slide_out:
            self.up_branch[b] = None
            self.down_branches[b] = None
        self.down_branches[new_upstream] = [b for b in self.down_branches[new_upstream] if b != branches_to_slide_out[0]]

        # Reconnect the downstreams to the new upstream in the tree
        for new_downstream in new_downstreams:
            self.up_branch[new_downstream] = new_upstream
            self.down_branches[new_upstream].append(new_downstream)

        # Update definition, fire post-hook, and perform the branch update
        self.save_definition_file()
        self.__run_post_slide_out_hook(new_upstream, branches_to_slide_out[-1], new_downstreams)

        self.git.checkout(new_upstream)
        for new_downstream in new_downstreams:
            self.git.checkout(new_downstream)
            if self.cli_opts.opt_merge:
                print(f"Merging {bold(new_upstream)} into {bold(new_downstream)}...")
                self.git.merge(new_upstream, new_downstream)
            else:
                print(f"Rebasing {bold(new_downstream)} onto {bold(new_upstream)}...")
                self.git.rebase(f"refs/heads/{new_upstream}", self.cli_opts.opt_down_fork_point or self.fork_point(new_downstream, use_overrides=True), new_downstream)

    def advance(self, b: str) -> None:
        if not self.down_branches.get(b):
            raise MacheteException(f"`{b}` does not have any downstream (child) branches to advance towards")

        def connected_with_green_edge(bd: str) -> bool:
            return bool(
                not self.__is_merged_to_upstream(bd) and
                self.git.is_ancestor_or_equal(b, bd) and
                (self.__get_overridden_fork_point(bd) or self.git.commit_sha_by_revision(b) == self.fork_point(bd, use_overrides=False)))

        candidate_downstreams = list(filter(connected_with_green_edge, self.down_branches[b]))
        if not candidate_downstreams:
            raise MacheteException(f"No downstream (child) branch of `{b}` is connected to `{b}` with a green edge")
        if len(candidate_downstreams) > 1:
            if self.cli_opts.opt_yes:
                raise MacheteException(
                    f"More than one downstream (child) branch of `{b}` is connected to `{b}` with a green edge and `-y/--yes` option is specified")
            else:
                d = self.pick(candidate_downstreams, f"downstream branch towards which `{b}` is to be fast-forwarded")
                self.git.merge_fast_forward_only(d)
        else:
            d = candidate_downstreams[0]
            ans = self.ask_if(f"Fast-forward {bold(b)} to match {bold(d)}?" + pretty_choices('y', 'N'),
                              f"Fast-forwarding {bold(b)} to match {bold(d)}...")
            if ans in ('y', 'yes'):
                self.git.merge_fast_forward_only(d)
            else:
                return

        ans = self.ask_if(f"\nBranch {bold(d)} is now merged into {bold(b)}. Slide {bold(d)} out of the tree of branch dependencies?" + pretty_choices('y', 'N'),
                          f"\nBranch {bold(d)} is now merged into {bold(b)}. Sliding {bold(d)} out of the tree of branch dependencies...")
        if ans in ('y', 'yes'):
            dds = self.down_branches.get(d, [])
            for dd in dds:
                self.up_branch[dd] = b
            self.down_branches[b] = flat_map(
                lambda bd: dds if bd == d else [bd],
                self.down_branches[b])
            self.save_definition_file()
            self.__run_post_slide_out_hook(b, d, dds)

    def traverse(self) -> None:

        self.expect_at_least_one_managed_branch()

        self.__empty_line_status = True

        def print_new_line(new_status: bool) -> None:
            if not self.__empty_line_status:
                print("")
            self.__empty_line_status = new_status

        if self.cli_opts.opt_fetch:
            for r in self.git.remotes():
                print(f"Fetching {r}...")
                self.git.fetch_remote(r)
            if self.git.remotes():
                self.git.flush_caches()
                print("")

        initial_branch = nearest_remaining_branch = self.git.current_branch()

        if self.cli_opts.opt_start_from == "root":
            dest = self.root_branch(self.git.current_branch(), if_unmanaged=PICK_FIRST_ROOT)
            print_new_line(False)
            print(f"Checking out the root branch ({bold(dest)})")
            self.git.checkout(dest)
            cb = dest
        elif self.cli_opts.opt_start_from == "first-root":
            # Note that we already ensured that there is at least one managed branch.
            dest = self.managed_branches[0]
            print_new_line(False)
            print(f"Checking out the first root branch ({bold(dest)})")
            self.git.checkout(dest)
            cb = dest
        else:  # cli_opts.opt_start_from == "here"
            cb = self.git.current_branch()
            self.expect_in_managed_branches(cb)

        b: str
        for b in itertools.dropwhile(lambda x: x != cb, self.managed_branches):
            u = self.up_branch.get(b)

            needs_slide_out: bool = self.__is_merged_to_upstream(b)
            s, remote = self.git.get_strict_remote_sync_status(b)
            statuses_to_sync = (UNTRACKED,
                                AHEAD_OF_REMOTE,
                                BEHIND_REMOTE,
                                DIVERGED_FROM_AND_OLDER_THAN_REMOTE,
                                DIVERGED_FROM_AND_NEWER_THAN_REMOTE)
            needs_remote_sync = s in statuses_to_sync

            if needs_slide_out:
                # Avoid unnecessary fork point check if we already know that the branch qualifies for slide out;
                # neither rebase nor merge will be suggested in such case anyway.
                needs_parent_sync: bool = False
            elif s == DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                # Avoid unnecessary fork point check if we already know that the branch qualifies for resetting to remote counterpart;
                # neither rebase nor merge will be suggested in such case anyway.
                needs_parent_sync = False
            elif self.cli_opts.opt_merge:
                needs_parent_sync = bool(u and not self.git.is_ancestor_or_equal(u, b))
            else:  # using rebase
                needs_parent_sync = bool(u and not (self.git.is_ancestor_or_equal(u, b) and self.git.commit_sha_by_revision(u) == self.fork_point(b, use_overrides=True)))

            if b != cb and (needs_slide_out or needs_parent_sync or needs_remote_sync):
                print_new_line(False)
                sys.stdout.write(f"Checking out {bold(b)}\n")
                self.git.checkout(b)
                cb = b
                print_new_line(False)
                self.status(warn_on_yellow_edges=True)
                print_new_line(True)
            if needs_slide_out:
                print_new_line(False)
                ans: str = self.ask_if(f"Branch {bold(b)} is merged into {bold(u)}. Slide {bold(b)} out of the tree of branch dependencies?" + pretty_choices('y', 'N', 'q', 'yq'),
                                       f"Branch {bold(b)} is merged into {bold(u)}. Sliding {bold(b)} out of the tree of branch dependencies...")
                if ans in ('y', 'yes', 'yq'):
                    if nearest_remaining_branch == b:
                        if self.down_branches.get(b):
                            nearest_remaining_branch = self.down_branches[b][0]
                        else:
                            nearest_remaining_branch = u
                    for d in self.down_branches.get(b) or []:
                        self.up_branch[d] = u
                    self.down_branches[u] = flat_map(
                        lambda ud: (self.down_branches.get(b) or []) if ud == b else [ud],
                        self.down_branches[u])
                    if b in self.__annotations:
                        del self.__annotations[b]
                    self.save_definition_file()
                    self.__run_post_slide_out_hook(u, b, self.down_branches.get(b) or [])
                    if ans == 'yq':
                        return
                    # No need to flush caches since nothing changed in commit/branch structure (only machete-specific changes happened).
                    continue  # No need to sync branch 'b' with remote since it just got removed from the tree of dependencies.
                elif ans in ('q', 'quit'):
                    return
                # If user answered 'no', we don't try to rebase/merge but still suggest to sync with remote (if needed; very rare in practice).
            elif needs_parent_sync:
                print_new_line(False)
                if self.cli_opts.opt_merge:
                    ans = self.ask_if(f"Merge {bold(u)} into {bold(b)}?" + pretty_choices('y', 'N', 'q', 'yq'),
                                      f"Merging {bold(u)} into {bold(b)}...")
                else:
                    ans = self.ask_if(f"Rebase {bold(b)} onto {bold(u)}?" + pretty_choices('y', 'N', 'q', 'yq'),
                                      f"Rebasing {bold(b)} onto {bold(u)}...")
                if ans in ('y', 'yes', 'yq'):
                    if self.cli_opts.opt_merge:
                        self.git.merge(u, b)
                        # It's clearly possible that merge can be in progress after 'git merge' returned non-zero exit code;
                        # this happens most commonly in case of conflicts.
                        # As for now, we're not aware of any case when merge can be still in progress after 'git merge' returns zero,
                        # at least not with the options that git-machete passes to merge; this happens though in case of 'git merge --no-commit' (which we don't ever invoke).
                        # It's still better, however, to be on the safe side.
                        if self.git.is_merge_in_progress():
                            sys.stdout.write("\nMerge in progress; stopping the traversal\n")
                            return
                    else:
                        self.git.rebase(f"refs/heads/{u}", self.fork_point(b, use_overrides=True), b)
                        # It's clearly possible that rebase can be in progress after 'git rebase' returned non-zero exit code;
                        # this happens most commonly in case of conflicts, regardless of whether the rebase is interactive or not.
                        # But for interactive rebases, it's still possible that even if 'git rebase' returned zero,
                        # the rebase is still in progress; e.g. when interactive rebase gets to 'edit' command, it will exit returning zero,
                        # but the rebase will be still in progress, waiting for user edits and a subsequent 'git rebase --continue'.
                        rb = self.git.currently_rebased_branch_or_none()
                        if rb:  # 'rb' should be equal to 'b' at this point anyway
                            sys.stdout.write(fmt(f"\nRebase of `{rb}` in progress; stopping the traversal\n"))
                            return
                    if ans == 'yq':
                        return

                    self.git.flush_caches()
                    s, remote = self.git.get_strict_remote_sync_status(b)
                    needs_remote_sync = s in statuses_to_sync
                elif ans in ('q', 'quit'):
                    return

            if needs_remote_sync:
                if s == BEHIND_REMOTE:
                    rb = self.git.strict_counterpart_for_fetching_of_branch(b)
                    ans = self.ask_if(f"Branch {bold(b)} is behind its remote counterpart {bold(rb)}.\n"
                                      f"Pull {bold(b)} (fast-forward only) from {bold(remote)}?" + pretty_choices('y', 'N', 'q', 'yq'), f"Branch {bold(b)} is behind its remote counterpart {bold(rb)}.\nPulling {bold(b)} (fast-forward only) from {bold(remote)}...")
                    if ans in ('y', 'yes', 'yq'):
                        self.git.pull_ff_only(remote, rb)
                        if ans == 'yq':
                            return
                        self.git.flush_caches()
                        print("")
                    elif ans in ('q', 'quit'):
                        return

                elif s == AHEAD_OF_REMOTE:
                    print_new_line(False)
                    ans = self.ask_if(f"Push {bold(b)} to {bold(remote)}?" + pretty_choices('y', 'N', 'q', 'yq'),
                                      f"Pushing {bold(b)} to {bold(remote)}...",
                                      override_answer=None if self.cli_opts.opt_push_tracked else "N")
                    if ans in ('y', 'yes', 'yq'):
                        self.git.push(remote, b)
                        if ans == 'yq':
                            return
                        self.git.flush_caches()
                    elif ans in ('q', 'quit'):
                        return

                elif s == DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                    print_new_line(False)
                    rb = self.git.strict_counterpart_for_fetching_of_branch(b)
                    ans = self.ask_if(f"Branch {bold(b)} diverged from (and has older commits than) its remote counterpart {bold(rb)}.\nReset branch {bold(b)} to the commit pointed by {bold(rb)}?" + pretty_choices('y', 'N', 'q', 'yq'),
                                      f"Branch {bold(b)} diverged from (and has older commits than) its remote counterpart {bold(rb)}.\nResetting branch {bold(b)} to the commit pointed by {bold(rb)}...")
                    if ans in ('y', 'yes', 'yq'):
                        self.git.reset_keep(rb)
                        if ans == 'yq':
                            return
                        self.git.flush_caches()
                    elif ans in ('q', 'quit'):
                        return

                elif s == DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                    print_new_line(False)
                    rb = self.git.strict_counterpart_for_fetching_of_branch(b)
                    ans = self.ask_if(f"Branch {bold(b)} diverged from (and has newer commits than) its remote counterpart {bold(rb)}.\n"
                                      f"Push {bold(b)} with force-with-lease to {bold(remote)}?" + pretty_choices('y', 'N', 'q', 'yq'),
                                      f"Branch {bold(b)} diverged from (and has newer commits than) its remote counterpart {bold(rb)}.\n"
                                      f"Pushing {bold(b)} with force-with-lease to {bold(remote)}...",
                                      override_answer=None if self.cli_opts.opt_push_tracked else "N")
                    if ans in ('y', 'yes', 'yq'):
                        self.git.push(remote, b, force_with_lease=True)
                        if ans == 'yq':
                            return
                        self.git.flush_caches()
                    elif ans in ('q', 'quit'):
                        return

                elif s == UNTRACKED:
                    rems: List[str] = self.git.remotes()
                    rmt: Optional[str] = self.git.inferred_remote_for_fetching_of_branch(b)
                    print_new_line(False)
                    if rmt:
                        self.handle_untracked_branch(rmt, b)
                    elif len(rems) == 1:
                        self.handle_untracked_branch(rems[0], b)
                    elif "origin" in rems:
                        self.handle_untracked_branch("origin", b)
                    else:
                        # We know that there is at least 1 remote, otherwise 's' would be 'NO_REMOTES'
                        print(fmt(f"Branch `{bold(b)}` is untracked and there's no `{bold('origin')}` repository."))
                        self.__pick_remote(b)

        if self.cli_opts.opt_return_to == "here":
            self.git.checkout(initial_branch)
        elif self.cli_opts.opt_return_to == "nearest-remaining":
            self.git.checkout(nearest_remaining_branch)
        # otherwise cli_opts.opt_return_to == "stay", so no action is needed

        print_new_line(False)
        self.status(warn_on_yellow_edges=True)
        print("")
        if cb == self.managed_branches[-1]:
            msg: str = f"Reached branch {bold(cb)} which has no successor"
        else:
            msg = f"No successor of {bold(cb)} needs to be slid out or synced with upstream branch or remote"
        sys.stdout.write(f"{msg}; nothing left to update\n")

        if self.cli_opts.opt_return_to == "here" or (
                self.cli_opts.opt_return_to == "nearest-remaining" and nearest_remaining_branch == initial_branch):
            print(f"Returned to the initial branch {bold(initial_branch)}")
        elif self.cli_opts.opt_return_to == "nearest-remaining" and nearest_remaining_branch != initial_branch:
            print(
                f"The initial branch {bold(initial_branch)} has been slid out. Returned to nearest remaining managed branch {bold(nearest_remaining_branch)}")

    def status(self, warn_on_yellow_edges: bool) -> None:
        dfs_res = []

        def prefix_dfs(u_: str, accumulated_path: List[Optional[str]]) -> None:
            dfs_res.append((u_, accumulated_path))
            if self.down_branches.get(u_):
                for (v, nv) in zip(self.down_branches[u_][:-1], self.down_branches[u_][1:]):
                    prefix_dfs(v, accumulated_path + [nv])
                prefix_dfs(self.down_branches[u_][-1], accumulated_path + [None])

        for u in self.__roots:
            prefix_dfs(u, accumulated_path=[])

        out = io.StringIO()
        edge_color: Dict[str, str] = {}
        fp_sha_cached: Dict[str, Optional[str]] = {}  # TODO (#110): default dict with None
        fp_branches_cached: Dict[str, List[BRANCH_DEF]] = {}

        def fp_sha(b: str) -> Optional[str]:
            if b not in fp_sha_cached:
                try:
                    # We're always using fork point overrides, even when status is launched from discover().
                    fp_sha_cached[b], fp_branches_cached[b] = self.__fork_point_and_containing_branch_defs(b, use_overrides=True)
                except MacheteException:
                    fp_sha_cached[b], fp_branches_cached[b] = None, []
            return fp_sha_cached[b]

        # Edge colors need to be precomputed
        # in order to render the leading parts of lines properly.
        for b in self.up_branch:
            u = self.up_branch[b]
            if self.is_merged_to(b, u):
                edge_color[b] = DIM
            elif not self.git.is_ancestor_or_equal(u, b):
                edge_color[b] = RED
            elif self.__get_overridden_fork_point(b) or self.git.commit_sha_by_revision(u) == fp_sha(b):
                edge_color[b] = GREEN
            else:
                edge_color[b] = YELLOW

        crb = self.git.currently_rebased_branch_or_none()
        ccob = self.git.currently_checked_out_branch_or_none()

        hook_path = self.git.get_hook_path("machete-status-branch")
        hook_executable = self.git.check_hook_executable(hook_path)

        def print_line_prefix(b_: str, suffix: str) -> None:
            out.write("  ")
            for p in accumulated_path[:-1]:
                if not p:
                    out.write("  ")
                else:
                    out.write(colored(f"{utils.vertical_bar()} ", edge_color[p]))
            out.write(colored(suffix, edge_color[b_]))

        for b, accumulated_path in dfs_res:
            if b in self.up_branch:
                print_line_prefix(b, f"{utils.vertical_bar()} \n")
                if self.cli_opts.opt_list_commits:
                    if edge_color[b] in (RED, DIM):
                        commits: List[Hash_ShortHash_Message] = self.git.commits_between(fp_sha(b), f"refs/heads/{b}") if fp_sha(b) else []
                    elif edge_color[b] == YELLOW:
                        commits = self.git.commits_between(f"refs/heads/{self.up_branch[b]}", f"refs/heads/{b}")
                    else:  # edge_color == GREEN
                        commits = self.git.commits_between(fp_sha(b), f"refs/heads/{b}")

                    for sha, short_sha, subject in commits:
                        if sha == fp_sha(b):
                            # fp_branches_cached will already be there thanks to the above call to 'fp_sha'.
                            fp_branches_formatted: str = " and ".join(
                                sorted(underline(lb_or_rb) for lb, lb_or_rb in fp_branches_cached[b]))
                            fp_suffix: str = " %s %s %s seems to be a part of the unique history of %s" % \
                                             (colored(utils.right_arrow(), RED), colored("fork point ???", RED),
                                              "this commit" if self.cli_opts.opt_list_commits_with_hashes else f"commit {short_sha}",
                                              fp_branches_formatted)
                        else:
                            fp_suffix = ''
                        print_line_prefix(b, utils.vertical_bar())
                        out.write(" %s%s%s\n" % (
                                  f"{dim(short_sha)}  " if self.cli_opts.opt_list_commits_with_hashes else "", dim(subject),
                                  fp_suffix))
                elbow_ascii_only: Dict[str, str] = {DIM: "m-", RED: "x-", GREEN: "o-", YELLOW: "?-"}
                elbow: str = u"└─" if not utils.ascii_only else elbow_ascii_only[edge_color[b]]
                print_line_prefix(b, elbow)
            else:
                if b != dfs_res[0][0]:
                    out.write("\n")
                out.write("  ")

            if b in (ccob, crb):  # i.e. if b is the current branch (checked out or being rebased)
                if b == crb:
                    prefix = "REBASING "
                elif self.git.is_am_in_progress():
                    prefix = "GIT AM IN PROGRESS "
                elif self.git.is_cherry_pick_in_progress():
                    prefix = "CHERRY-PICKING "
                elif self.git.is_merge_in_progress():
                    prefix = "MERGING "
                elif self.git.is_revert_in_progress():
                    prefix = "REVERTING "
                else:
                    prefix = ""
                current = "%s%s" % (bold(colored(prefix, RED)), bold(underline(b, star_if_ascii_only=True)))
            else:
                current = bold(b)

            anno: str = f"  {dim(self.__annotations[b])}" if b in self.__annotations else ""

            s, remote = self.git.get_combined_remote_sync_status(b)
            sync_status = {
                NO_REMOTES: "",
                UNTRACKED: colored(" (untracked)", ORANGE),
                IN_SYNC_WITH_REMOTE: "",
                BEHIND_REMOTE: colored(f" (behind {remote})", RED),
                AHEAD_OF_REMOTE: colored(f" (ahead of {remote})", RED),
                DIVERGED_FROM_AND_OLDER_THAN_REMOTE: colored(f" (diverged from & older than {remote})", RED),
                DIVERGED_FROM_AND_NEWER_THAN_REMOTE: colored(f" (diverged from {remote})", RED)
            }[s]

            hook_output = ""
            if hook_executable:
                debug("status()", f"running machete-status-branch hook ({hook_path}) for branch {b}")
                hook_env = dict(os.environ, ASCII_ONLY=str(utils.ascii_only).lower())
                status_code, stdout, stderr = utils.popen_cmd(hook_path, b, cwd=self.git.get_root_dir(),
                                                              env=hook_env)
                if status_code == 0:
                    if not stdout.isspace():
                        hook_output = f"  {stdout.rstrip()}"
                else:
                    debug("status()",
                          f"machete-status-branch hook ({hook_path}) for branch {b} returned {status_code}; stdout: '{stdout}'; stderr: '{stderr}'")

            out.write(current + anno + sync_status + hook_output + "\n")

        sys.stdout.write(out.getvalue())
        out.close()

        yellow_edge_branches = [k for k, v in edge_color.items() if v == YELLOW]
        if yellow_edge_branches and warn_on_yellow_edges:
            if len(yellow_edge_branches) == 1:
                first_part = f"yellow edge indicates that fork point for `{yellow_edge_branches[0]}` is probably incorrectly inferred,\n" \
                             f"or that some extra branch should be between `{self.up_branch[yellow_edge_branches[0]]}` and `{yellow_edge_branches[0]}`"
            else:
                affected_branches = ", ".join(map(lambda x: f"`{x}`", yellow_edge_branches))
                first_part = f"yellow edges indicate that fork points for {affected_branches} are probably incorrectly inferred" \
                             f"or that some extra branch should be added between each of these branches and its parent"

            if not self.cli_opts.opt_list_commits:
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
        branches_to_delete = excluding(self.git.local_branches(), self.managed_branches)
        cb = self.git.current_branch_or_none()
        if cb and cb in branches_to_delete:
            branches_to_delete = excluding(branches_to_delete, [cb])
            print(fmt(f"Skipping current branch `{cb}`"))
        if branches_to_delete:
            branches_merged_to_head = self.git.merged_local_branches()

            branches_to_delete_merged_to_head = [b for b in branches_to_delete if b in branches_merged_to_head]
            for b in branches_to_delete_merged_to_head:
                rb = self.git.strict_counterpart_for_fetching_of_branch(b)
                is_merged_to_remote = self.git.is_ancestor_or_equal(b, rb, later_prefix="refs/remotes/") if rb else True
                msg_core = f"{bold(b)} (merged to HEAD{'' if is_merged_to_remote else f', but not merged to {rb}'})"
                msg = f"Delete branch {msg_core}?" + pretty_choices('y', 'N', 'q')
                opt_yes_msg = f"Deleting branch {msg_core}"
                ans = self.ask_if(msg, opt_yes_msg)
                if ans in ('y', 'yes'):
                    self.git.run_git("branch", "-d" if is_merged_to_remote else "-D", b)
                elif ans in ('q', 'quit'):
                    return

            branches_to_delete_unmerged_to_head = [b for b in branches_to_delete if b not in branches_merged_to_head]
            for b in branches_to_delete_unmerged_to_head:
                msg_core = f"{bold(b)} (unmerged to HEAD)"
                msg = f"Delete branch {msg_core}?" + pretty_choices('y', 'N', 'q')
                opt_yes_msg = f"Deleting branch {msg_core}"
                ans = self.ask_if(msg, opt_yes_msg)
                if ans in ('y', 'yes'):
                    self.git.run_git("branch", "-D", b)
                elif ans in ('q', 'quit'):
                    return
        else:
            print("No branches to delete")

    def edit(self) -> int:
        default_editor_name: Optional[str] = self.git.get_default_editor()
        if default_editor_name is None:
            raise MacheteException(f"Cannot determine editor. Set `GIT_MACHETE_EDITOR` environment variable or edit {self._definition_file_path} directly.")
        return utils.run_cmd(default_editor_name, self._definition_file_path)

    def __fork_point_and_containing_branch_defs(self, b: str, use_overrides: bool) -> Tuple[Optional[str], List[BRANCH_DEF]]:
        u = self.up_branch.get(b)

        if self.__is_merged_to_upstream(b):
            fp_sha = self.git.commit_sha_by_revision(b)
            debug(f"fork_point_and_containing_branch_defs({b})",
                  f"{b} is merged to {u}; skipping inference, using tip of {b} ({fp_sha}) as fork point")
            return fp_sha, []

        if use_overrides:
            overridden_fp_sha = self.__get_overridden_fork_point(b)
            if overridden_fp_sha:
                if u and self.git.is_ancestor_or_equal(u, b) and not self.git.is_ancestor_or_equal(u, overridden_fp_sha, later_prefix=""):
                    # We need to handle the case when b is a descendant of u,
                    # but the fork point of b is overridden to a commit that is NOT a descendant of u.
                    # In this case it's more reasonable to assume that u (and not overridden_fp_sha) is the fork point.
                    debug(f"fork_point_and_containing_branch_defs({b})",
                          f"{b} is descendant of its upstream {u}, but overridden fork point commit {overridden_fp_sha} is NOT a descendant of {u}; falling back to {u} as fork point")
                    return self.git.commit_sha_by_revision(u), []
                else:
                    debug(f"fork_point_and_containing_branch_defs({b})",
                          f"fork point of {b} is overridden to {overridden_fp_sha}; skipping inference")
                    return overridden_fp_sha, []

        try:
            fp_sha, containing_branch_defs = next(self.__match_log_to_filtered_reflogs(b))
        except StopIteration:
            if u and self.git.is_ancestor_or_equal(u, b):
                debug(f"fork_point_and_containing_branch_defs({b})",
                      f"cannot find fork point, but {b} is descendant of its upstream {u}; falling back to {u} as fork point")
                return self.git.commit_sha_by_revision(u), []
            else:
                raise MacheteException(f"Cannot find fork point for branch `{b}`")
        else:
            debug("fork_point_and_containing_branch_defs({b})",
                  f"commit {fp_sha} is the most recent point in history of {b} to occur on "
                  "filtered reflog of any other branch or its remote counterpart "
                  f"(specifically: {' and '.join(map(utils.get_second, containing_branch_defs))})")

            if u and self.git.is_ancestor_or_equal(u, b) and not self.git.is_ancestor_or_equal(u, fp_sha, later_prefix=""):
                # That happens very rarely in practice (typically current head of any branch, including u, should occur on the reflog of this
                # branch, thus is_ancestor(u, b) should imply is_ancestor(u, FP(b)), but it's still possible in case reflog of
                # u is incomplete for whatever reason.
                debug(f"fork_point_and_containing_branch_defs({b})",
                      f"{u} is descendant of its upstream {b}, but inferred fork point commit {fp_sha} is NOT a descendant of {u}; falling back to {u} as fork point")
                return self.git.commit_sha_by_revision(u), []
            else:
                debug(f"fork_point_and_containing_branch_defs({b})",
                      f"choosing commit {fp_sha} as fork point")
                return fp_sha, containing_branch_defs

    def fork_point(self, b: str, use_overrides: bool) -> Optional[str]:
        sha, containing_branch_defs = self.__fork_point_and_containing_branch_defs(b, use_overrides)
        return sha

    def diff(self, branch: Optional[str]) -> None:
        fp: str = self.fork_point(branch if branch else self.git.current_branch(), use_overrides=True)
        params = \
            (["--stat"] if self.cli_opts.opt_stat else []) + \
            [fp] + \
            ([f"refs/heads/{branch}"] if branch else []) + \
            ["--"]
        self.git.run_git("diff", *params)

    def log(self, branch: str) -> None:
        self.git.run_git("log", "^" + self.fork_point(branch, use_overrides=True), f"refs/heads/{branch}")

    def down(self, b: str, pick_mode: bool) -> str:
        self.expect_in_managed_branches(b)
        dbs = self.down_branches.get(b)
        if not dbs:
            raise MacheteException(f"Branch `{b}` has no downstream branch")
        elif len(dbs) == 1:
            return dbs[0]
        elif pick_mode:
            return self.pick(dbs, "downstream branch")
        else:
            return "\n".join(dbs)

    def first_branch(self, b: str) -> str:
        root = self.root_branch(b, if_unmanaged=PICK_FIRST_ROOT)
        root_dbs = self.down_branches.get(root)
        return root_dbs[0] if root_dbs else root

    def last_branch(self, b: str) -> str:
        destination = self.root_branch(b, if_unmanaged=PICK_LAST_ROOT)
        while self.down_branches.get(destination):
            destination = self.down_branches[destination][-1]
        return destination

    def next_branch(self, b: str) -> str:
        self.expect_in_managed_branches(b)
        index: int = self.managed_branches.index(b) + 1
        if index == len(self.managed_branches):
            raise MacheteException(f"Branch `{b}` has no successor")
        return self.managed_branches[index]

    def prev_branch(self, b: str) -> str:
        self.expect_in_managed_branches(b)
        index: int = self.managed_branches.index(b) - 1
        if index == -1:
            raise MacheteException(f"Branch `{b}` has no predecessor")
        return self.managed_branches[index]

    def root_branch(self, b: str, if_unmanaged: int) -> str:
        if b not in self.managed_branches:
            if self.__roots:
                if if_unmanaged == PICK_FIRST_ROOT:
                    warn(
                        f"{b} is not a managed branch, assuming {self.__roots[0]} (the first root) instead as root")
                    return self.__roots[0]
                else:  # if_unmanaged == PICK_LAST_ROOT
                    warn(
                        f"{b} is not a managed branch, assuming {self.__roots[-1]} (the last root) instead as root")
                    return self.__roots[-1]
            else:
                self.__raise_no_branches_error()
        u = self.up_branch.get(b)
        while u:
            b = u
            u = self.up_branch.get(b)
        return b

    def up(self, b: str, prompt_if_inferred_msg: Optional[str],
           prompt_if_inferred_yes_opt_msg: Optional[str]) -> str:
        if b in self.managed_branches:
            u = self.up_branch.get(b)
            if u:
                return u
            else:
                raise MacheteException(f"Branch `{b}` has no upstream branch")
        else:
            u = self.__infer_upstream(b)
            if u:
                if prompt_if_inferred_msg:
                    if self.ask_if(prompt_if_inferred_msg % (b, u), prompt_if_inferred_yes_opt_msg % (b, u)) in ('y', 'yes'):
                        return u
                    else:
                        sys.exit(1)
                else:
                    warn(
                        f"branch `{b}` not found in the tree of branch dependencies; the upstream has been inferred to `{u}`")
                    return u
            else:
                raise MacheteException(
                    f"Branch `{b}` not found in the tree of branch dependencies and its upstream could not be inferred")

    def slidable(self) -> List[str]:
        return [b for b in self.managed_branches if b in self.up_branch]

    def slidable_after(self, b: str) -> List[str]:
        if b in self.up_branch:
            dbs = self.down_branches.get(b)
            if dbs and len(dbs) == 1:
                return dbs
        return []

    def __is_merged_to_upstream(self, b: str) -> bool:
        if b not in self.up_branch:
            return False
        return self.is_merged_to(b, self.up_branch[b])

    def __run_post_slide_out_hook(self, new_upstream: str, slid_out_branch: str,
                                  new_downstreams: List[str]) -> None:
        hook_path = self.git.get_hook_path("machete-post-slide-out")
        if self.git.check_hook_executable(hook_path):
            debug(f"run_post_slide_out_hook({new_upstream}, {slid_out_branch}, {new_downstreams})",
                  f"running machete-post-slide-out hook ({hook_path})")
            exit_code = utils.run_cmd(hook_path, new_upstream, slid_out_branch, *new_downstreams,
                                      cwd=self.git.get_root_dir())
            if exit_code != 0:
                sys.stderr.write(f"The machete-post-slide-out hook exited with {exit_code}, aborting.\n")
                sys.exit(exit_code)

    def squash(self, cb: str, fork_commit: str) -> None:
        commits: List[Hash_ShortHash_Message] = self.git.commits_between(fork_commit, cb)
        if not commits:
            raise MacheteException(
                "No commits to squash. Use `-f` or `--fork-point` to specify the start of range of commits to squash.")
        if len(commits) == 1:
            sha, short_sha, subject = commits[0]
            print(f"Exactly one commit ({short_sha}) to squash, ignoring.\n")
            print("Tip: use `-f` or `--fork-point` to specify where the range of commits to squash starts.")
            return

        earliest_sha, earliest_short_sha, earliest_subject = commits[0]
        earliest_full_body = self.git.popen_git("log", "-1", "--format=%B", earliest_sha).strip()
        # %ai for ISO-8601 format; %aE/%aN for respecting .mailmap; see `git rev-list --help`
        earliest_author_date = self.git.popen_git("log", "-1", "--format=%ai", earliest_sha).strip()
        earliest_author_email = self.git.popen_git("log", "-1", "--format=%aE", earliest_sha).strip()
        earliest_author_name = self.git.popen_git("log", "-1", "--format=%aN", earliest_sha).strip()

        # Following the convention of `git cherry-pick`, `git commit --amend`, `git rebase` etc.,
        # let's retain the original author (only committer will be overwritten).
        author_env = dict(os.environ,
                          GIT_AUTHOR_DATE=earliest_author_date,
                          GIT_AUTHOR_EMAIL=earliest_author_email,
                          GIT_AUTHOR_NAME=earliest_author_name)
        # Using `git commit-tree` since it's cleaner than any high-level command
        # like `git merge --squash` or `git rebase --interactive`.
        # The tree (HEAD^{tree}) argument must be passed as first,
        # otherwise the entire `commit-tree` will fail on some ancient supported versions of git (at least on v1.7.10).
        squashed_sha = self.git.popen_git("commit-tree", "HEAD^{tree}", "-p", fork_commit, "-m", earliest_full_body, env=author_env).strip()

        # This can't be done with `git reset` since it doesn't allow for a custom reflog message.
        # Even worse, reset's reflog message would be filtered out in our fork point algorithm,
        # so the squashed commit would not even be considered to "belong"
        # (in the FP sense) to the current branch's history.
        self.git.run_git("update-ref", "HEAD", squashed_sha, "-m", f"squash: {earliest_subject}")

        print(f"Squashed {len(commits)} commits:")
        print()
        for sha, short_sha, subject in commits:
            print(f"\t{short_sha} {subject}")

        latest_sha, latest_short_sha, latest_subject = commits[-1]
        print()
        print("To restore the original pre-squash commit, run:")
        print()
        print(fmt(f"\t`git reset {latest_sha}`"))

    def filtered_reflog(self, b: str, prefix: str) -> List[str]:
        def is_excluded_reflog_subject(sha_: str, gs_: str) -> bool:
            is_excluded = (gs_.startswith("branch: Created from") or
                           gs_ == f"branch: Reset to {b}" or
                           gs_ == "branch: Reset to HEAD" or
                           gs_.startswith("reset: moving to ") or
                           gs_.startswith("fetch . ") or
                           # The rare case of a no-op rebase, the exact wording likely depends on git version
                           gs_ == f"rebase finished: {prefix}{b} onto {sha_}" or
                           gs_ == f"rebase -i (finish): {prefix}{b} onto {sha_}"
                           )
            if is_excluded:
                debug(f"filtered_reflog({b}, {prefix}) -> is_excluded_reflog_subject({sha_}, <<<{gs_}>>>)",
                      "skipping reflog entry")
            return is_excluded

        b_reflog = self.git.reflog(prefix + b)
        if not b_reflog:
            return []

        earliest_sha, earliest_gs = b_reflog[-1]  # Note that the reflog is returned from latest to earliest entries.
        shas_to_exclude = set()
        if earliest_gs.startswith("branch: Created from"):
            debug(f"filtered_reflog({b}, {prefix})",
                  f"skipping any reflog entry with the hash equal to the hash of the earliest (branch creation) entry: {earliest_sha}")
            shas_to_exclude.add(earliest_sha)

        result = [sha for (sha, gs) in b_reflog if
                  sha not in shas_to_exclude and not is_excluded_reflog_subject(sha, gs)]
        debug(f"filtered_reflog({b}, {prefix})",
              "computed filtered reflog (= reflog without branch creation "
              "and branch reset events irrelevant for fork point/upstream inference): %s\n" % (", ".join(result) or "<empty>"))
        return result

    def sync_annotations_to_github_prs(self) -> None:
        from git_machete.github import derive_current_user_login, derive_pull_requests, GitHubPullRequest, \
            parse_github_remote_url

        url_for_remote: Dict[str, str] = {r: self.git.get_url_of_remote(r) for r in
                                          self.git.remotes()}
        if not url_for_remote:
            raise MacheteException(fmt('No remotes defined for this repository (see `git remote`)'))

        optional_org_name_for_github_remote: Dict[str, Optional[Tuple[str, str]]] = {
            remote: parse_github_remote_url(url) for remote, url in url_for_remote.items()}
        org_name_for_github_remote: Dict[str, Tuple[str, str]] = {remote: org_name for remote, org_name in
                                                                  optional_org_name_for_github_remote.items() if
                                                                  org_name}
        if not org_name_for_github_remote:
            raise MacheteException(
                fmt('Remotes are defined for this repository, but none of them corresponds to GitHub (see `git remote -v` for details)'))

        org: str
        repo: str
        if len(org_name_for_github_remote) == 1:
            org, repo = list(org_name_for_github_remote.values())[0]
        elif len(org_name_for_github_remote) > 1:
            if 'origin' in org_name_for_github_remote:
                org, repo = org_name_for_github_remote['origin']
            else:
                raise MacheteException(f'Multiple non-origin remotes correspond to GitHub in this repository: '
                                       f'{", ".join(org_name_for_github_remote.keys())}, aborting')
        current_user: Optional[str] = derive_current_user_login()
        debug('sync_annotations_to_github_prs()',
              'Current GitHub user is ' + (current_user or '<none>'))
        pr: GitHubPullRequest
        for pr in derive_pull_requests(org, repo):
            if pr.head in self.managed_branches:
                debug('sync_annotations_to_github_prs()',
                      f'{pr} corresponds to a managed branch')
                anno: str = f'PR #{pr.number}'
                if pr.user != current_user:
                    anno += f' ({pr.user})'
                u: Optional[str] = self.up_branch.get(pr.head)
                if pr.base != u:
                    warn(f'branch `{pr.head}` has a different base in PR #{pr.number} (`{pr.base}`) '
                         f'than in machete file (`{u or "<none, is a root>"}`)')
                    anno += f" WRONG PR BASE or MACHETE PARENT? PR has '{pr.base}'"
                if self.__annotations.get(pr.head) != anno:
                    print(fmt(f'Annotating <b>{pr.head}</b> as `{anno}`'))
                    self.__annotations[pr.head] = anno
            else:
                debug('sync_annotations_to_github_prs()',
                      f'{pr} does NOT correspond to a managed branch')
        self.save_definition_file()

    # Parse and evaluate direction against current branch for show/go commands
    def parse_direction(self, param: str, b: str, allow_current: bool, down_pick_mode: bool) -> str:
        if param in ("c", "current") and allow_current:
            return self.git.current_branch()  # throws in case of detached HEAD, as in the spec
        elif param in ("d", "down"):
            return self.down(b, pick_mode=down_pick_mode)
        elif param in ("f", "first"):
            return self.first_branch(b)
        elif param in ("l", "last"):
            return self.last_branch(b)
        elif param in ("n", "next"):
            return self.next_branch(b)
        elif param in ("p", "prev"):
            return self.prev_branch(b)
        elif param in ("r", "root"):
            return self.root_branch(b, if_unmanaged=PICK_FIRST_ROOT)
        elif param in ("u", "up"):
            return self.up(b, prompt_if_inferred_msg=None, prompt_if_inferred_yes_opt_msg=None)
        else:
            raise MacheteException(f"Invalid direction: `{param}` expected: {allowed_directions(allow_current)}")

    def __match_log_to_filtered_reflogs(self, b: str) -> Generator[Tuple[str, List[BRANCH_DEF]], None, None]:

        if b not in self.git.local_branches():
            raise MacheteException(f"`{b}` is not a local branch")

        if self.git.branch_defs_by_sha_in_reflog is None:
            def generate_entries() -> Generator[Tuple[str, BRANCH_DEF], None, None]:
                for lb in self.git.local_branches():
                    lb_shas = set()
                    for sha_ in self.filtered_reflog(lb, prefix="refs/heads/"):
                        lb_shas.add(sha_)
                        yield sha_, (lb, lb)
                    rb = self.git.combined_counterpart_for_fetching_of_branch(lb)
                    if rb:
                        for sha_ in self.filtered_reflog(rb, prefix="refs/remotes/"):
                            if sha_ not in lb_shas:
                                yield sha_, (lb, rb)

            self.git.branch_defs_by_sha_in_reflog = {}
            for sha, branch_def in generate_entries():
                if sha in self.git.branch_defs_by_sha_in_reflog:
                    # The practice shows that it's rather unlikely for a given commit to appear on filtered reflogs of two unrelated branches
                    # ("unrelated" as in, not a local branch and its remote counterpart) but we need to handle this case anyway.
                    self.git.branch_defs_by_sha_in_reflog[sha] += [branch_def]
                else:
                    self.git.branch_defs_by_sha_in_reflog[sha] = [branch_def]

            def log_result() -> Generator[str, None, None]:
                branch_defs: List[BRANCH_DEF]
                sha_: str
                for sha_, branch_defs in self.git.branch_defs_by_sha_in_reflog.items():
                    def branch_def_to_str(lb: str, lb_or_rb: str) -> str:
                        return lb if lb == lb_or_rb else f"{lb_or_rb} (remote counterpart of {lb})"

                    joined_branch_defs = ", ".join(map(tupled(branch_def_to_str), branch_defs))
                    yield dim(f"{sha_} => {joined_branch_defs}")

            debug(f"match_log_to_filtered_reflogs({b})",
                  "branches containing the given SHA in their filtered reflog: \n%s\n" % "\n".join(log_result()))

        for sha in self.git.spoonfeed_log_shas(b):
            if sha in self.git.branch_defs_by_sha_in_reflog:
                # The entries must be sorted by lb_or_rb to make sure the upstream inference is deterministic
                # (and does not depend on the order in which `generate_entries` iterated through the local branches).
                branch_defs: List[BRANCH_DEF] = self.git.branch_defs_by_sha_in_reflog[sha]

                def lb_is_not_b(lb: str, lb_or_rb: str) -> bool:
                    return lb != b

                containing_branch_defs = sorted(filter(tupled(lb_is_not_b), branch_defs), key=get_second)
                if containing_branch_defs:
                    debug(f"match_log_to_filtered_reflogs({b})",
                          f"commit {sha} found in filtered reflog of {' and '.join(map(get_second, branch_defs))}")
                    yield sha, containing_branch_defs
                else:
                    debug(f"match_log_to_filtered_reflogs({b})",
                          f"commit {sha} found only in filtered reflog of {' and '.join(map(get_second, branch_defs))}; ignoring")
            else:
                debug(f"match_log_to_filtered_reflogs({b})", f"commit {sha} not found in any filtered reflog")

    def __infer_upstream(self, b: str, condition: Callable[[str], bool] = lambda u: True, reject_reason_message: str = "") -> Optional[str]:
        for sha, containing_branch_defs in self.__match_log_to_filtered_reflogs(b):
            debug(f"infer_upstream({b})",
                  f"commit {sha} found in filtered reflog of {' and '.join(map(get_second, containing_branch_defs))}")

            for candidate, original_matched_branch in containing_branch_defs:
                if candidate != original_matched_branch:
                    debug(f"infer_upstream({b})",
                          f"upstream candidate is {candidate}, which is the local counterpart of {original_matched_branch}")

                if condition(candidate):
                    debug(f"infer_upstream({b})", f"upstream candidate {candidate} accepted")
                    return candidate
                else:
                    debug(f"infer_upstream({b})",
                          f"upstream candidate {candidate} rejected ({reject_reason_message})")
        return None

    @staticmethod
    def config_key_for_override_fork_point_to(b: str) -> str:
        return f"machete.overrideForkPoint.{b}.to"

    @staticmethod
    def config_key_for_override_fork_point_while_descendant_of(b: str) -> str:
        return f"machete.overrideForkPoint.{b}.whileDescendantOf"

    # Also includes config that is incomplete (only one entry out of two) or otherwise invalid.
    def has_any_fork_point_override_config(self, b: str) -> bool:
        return (self.git.get_config_or_none(self.config_key_for_override_fork_point_to(b)) or
                self.git.get_config_or_none(self.config_key_for_override_fork_point_while_descendant_of(b))) is not None

    def __get_fork_point_override_data(self, b: str) -> Optional[Tuple[str, str]]:
        to_key = self.config_key_for_override_fork_point_to(b)
        to = self.git.get_config_or_none(to_key)
        while_descendant_of_key = self.config_key_for_override_fork_point_while_descendant_of(b)
        while_descendant_of = self.git.get_config_or_none(while_descendant_of_key)
        if not to and not while_descendant_of:
            return None
        if to and not while_descendant_of:
            warn(f"{to_key} config is set but {while_descendant_of_key} config is missing")
            return None
        if not to and while_descendant_of:
            warn(f"{while_descendant_of_key} config is set but {to_key} config is missing")
            return None

        to_sha: Optional[str] = self.git.commit_sha_by_revision(to, prefix="")
        while_descendant_of_sha: Optional[str] = self.git.commit_sha_by_revision(while_descendant_of, prefix="")
        if not to_sha or not while_descendant_of_sha:
            if not to_sha:
                warn(f"{to_key} config value `{to}` does not point to a valid commit")
            if not while_descendant_of_sha:
                warn(f"{while_descendant_of_key} config value `{while_descendant_of}` does not point to a valid commit")
            return None
        # This check needs to be performed every time the config is retrieved.
        # We can't rely on the values being validated in set_fork_point_override(), since the config could have been modified outside of git-machete.
        if not self.git.is_ancestor_or_equal(to_sha, while_descendant_of_sha, earlier_prefix="", later_prefix=""):
            warn(
                f"commit {self.git.short_commit_sha_by_revision(to)} pointed by {to_key} config "
                f"is not an ancestor of commit {self.git.short_commit_sha_by_revision(while_descendant_of)} "
                f"pointed by {while_descendant_of_key} config")
            return None
        return to_sha, while_descendant_of_sha

    def __get_overridden_fork_point(self, b: str) -> Optional[str]:
        override_data = self.__get_fork_point_override_data(b)
        if not override_data:
            return None

        to, while_descendant_of = override_data
        # Note that this check is distinct from the is_ancestor check performed in get_fork_point_override_data.
        # While the latter checks the sanity of fork point override configuration,
        # the former checks if the override still applies to wherever the given branch currently points.
        if not self.git.is_ancestor_or_equal(while_descendant_of, b, earlier_prefix=""):
            warn(fmt(
                f"since branch <b>{b}</b> is no longer a descendant of commit {self.git.short_commit_sha_by_revision(while_descendant_of)}, ",
                f"the fork point override to commit {self.git.short_commit_sha_by_revision(to)} no longer applies.\n",
                "Consider running:\n",
                f"  `git machete fork-point --unset-override {b}`\n"))
            return None
        debug(f"get_overridden_fork_point({b})",
              f"since branch {b} is descendant of while_descendant_of={while_descendant_of}, fork point of {b} is overridden to {to}")
        return to

    def unset_fork_point_override(self, b: str) -> None:
        self.git.unset_config(self.config_key_for_override_fork_point_to(b))
        self.git.unset_config(self.config_key_for_override_fork_point_while_descendant_of(b))

    def set_fork_point_override(self, b: str, to_revision: str) -> None:
        if b not in self.git.local_branches():
            raise MacheteException(f"`{b}` is not a local branch")
        to_sha = self.git.commit_sha_by_revision(to_revision, prefix="")
        if not to_sha:
            raise MacheteException(f"Cannot find revision {to_revision}")
        if not self.git.is_ancestor_or_equal(to_sha, b, earlier_prefix=""):
            raise MacheteException(
                f"Cannot override fork point: {self.git.get_revision_repr(to_revision)} is not an ancestor of {b}")

        to_key = self.config_key_for_override_fork_point_to(b)
        self.git.set_config(to_key, to_sha)

        while_descendant_of_key = self.config_key_for_override_fork_point_while_descendant_of(b)
        b_sha = self.git.commit_sha_by_revision(b, prefix="refs/heads/")
        self.git.set_config(while_descendant_of_key, b_sha)

        sys.stdout.write(
            fmt(f"Fork point for <b>{b}</b> is overridden to <b>{self.git.get_revision_repr(to_revision)}</b>.\n",
                f"This applies as long as {b} points to (or is descendant of) its current head (commit {self.git.short_commit_sha_by_revision(b_sha)}).\n\n",
                f"This information is stored under git config keys:\n  * `{to_key}`\n  * `{while_descendant_of_key}`\n\n",
                f"To unset this override, use:\n  `git machete fork-point --unset-override {b}`\n"))

    def __pick_remote(self, b: str) -> None:
        rems = self.git.remotes()
        print("\n".join(f"[{index + 1}] {r}" for index, r in enumerate(rems)))
        msg = f"Select number 1..{len(rems)} to specify the destination remote " \
              "repository, or 'n' to skip this branch, or " \
              "'q' to quit the traverse: "
        ans = input(msg).lower()
        if ans in ('q', 'quit'):
            raise StopTraversal
        try:
            index = int(ans) - 1
            if index not in range(len(rems)):
                raise MacheteException(f"Invalid index: {index + 1}")
            self.handle_untracked_branch(rems[index], b)
        except ValueError:
            pass

    def handle_untracked_branch(self, new_remote: str, b: str) -> None:
        rems: List[str] = self.git.remotes()
        can_pick_other_remote = len(rems) > 1
        other_remote_choice = "o[ther-remote]" if can_pick_other_remote else ""
        rb = f"{new_remote}/{b}"
        if not self.git.commit_sha_by_revision(rb, prefix="refs/remotes/"):
            ask_message = f"Push untracked branch {bold(b)} to {bold(new_remote)}?" + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice)
            ask_opt_yes_message = f"Pushing untracked branch {bold(b)} to {bold(new_remote)}..."
            ans = self.ask_if(ask_message, ask_opt_yes_message,
                              override_answer=None if self.git.cli_opts.opt_push_untracked else "N")
            if ans in ('y', 'yes', 'yq'):
                self.git.push(new_remote, b)
                if ans == 'yq':
                    raise StopTraversal
                self.git.flush_caches()
            elif can_pick_other_remote and ans in ('o', 'other'):
                self.__pick_remote(b)
            elif ans in ('q', 'quit'):
                raise StopTraversal
            return

        relation: int = self.git.get_relation_to_remote_counterpart(b, rb)

        message: str = {
            IN_SYNC_WITH_REMOTE:
                f"Branch {bold(b)} is untracked, but its remote counterpart candidate {bold(rb)} already exists and both branches point to the same commit.",
            BEHIND_REMOTE:
                f"Branch {bold(b)} is untracked, but its remote counterpart candidate {bold(rb)} already exists and is ahead of {bold(b)}.",
            AHEAD_OF_REMOTE:
                f"Branch {bold(b)} is untracked, but its remote counterpart candidate {bold(rb)} already exists and is behind {bold(b)}.",
            DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                f"Branch {bold(b)} is untracked, it diverged from its remote counterpart candidate {bold(rb)}, and has {bold('older')} commits than {bold(rb)}.",
            DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                f"Branch {bold(b)} is untracked, it diverged from its remote counterpart candidate {bold(rb)}, and has {bold('newer')} commits than {bold(rb)}."
        }[relation]

        ask_message, ask_opt_yes_message = {
            IN_SYNC_WITH_REMOTE: (
                f"Set the remote of {bold(b)} to {bold(new_remote)} without pushing or pulling?" + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Setting the remote of {bold(b)} to {bold(new_remote)}..."
            ),
            BEHIND_REMOTE: (
                f"Pull {bold(b)} (fast-forward only) from {bold(new_remote)}?" + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
                f"Pulling {bold(b)} (fast-forward only) from {bold(new_remote)}..."
            ),
            AHEAD_OF_REMOTE: (
                f"Push branch {bold(b)} to {bold(new_remote)}?" + pretty_choices('y', 'N', 'q', 'yq',
                                                                                 other_remote_choice),
                f"Pushing branch {bold(b)} to {bold(new_remote)}..."
            ),
            DIVERGED_FROM_AND_OLDER_THAN_REMOTE: (
                f"Reset branch {bold(b)} to the commit pointed by {bold(rb)}?" + pretty_choices('y', 'N', 'q', 'yq',
                                                                                                other_remote_choice),
                f"Resetting branch {bold(b)} to the commit pointed by {bold(rb)}..."
            ),
            DIVERGED_FROM_AND_NEWER_THAN_REMOTE: (
                f"Push branch {bold(b)} with force-with-lease to {bold(new_remote)}?" + pretty_choices('y', 'N', 'q',
                                                                                                       'yq',
                                                                                                       other_remote_choice),
                f"Pushing branch {bold(b)} with force-with-lease to {bold(new_remote)}..."
            )
        }[relation]

        override_answer: Optional[str] = {
            IN_SYNC_WITH_REMOTE: None,
            BEHIND_REMOTE: None,
            AHEAD_OF_REMOTE: None if self.cli_opts.opt_push_tracked else "N",
            DIVERGED_FROM_AND_OLDER_THAN_REMOTE: None,
            DIVERGED_FROM_AND_NEWER_THAN_REMOTE: None if self.cli_opts.opt_push_tracked else "N",
        }[relation]

        yes_action: Callable[[], None] = {
            IN_SYNC_WITH_REMOTE: lambda: self.git.set_upstream_to(rb),
            BEHIND_REMOTE: lambda: self.git.pull_ff_only(new_remote, rb),
            AHEAD_OF_REMOTE: lambda: self.git.push(new_remote, b),
            DIVERGED_FROM_AND_OLDER_THAN_REMOTE: lambda: self.git.reset_keep(rb),
            DIVERGED_FROM_AND_NEWER_THAN_REMOTE: lambda: self.git.push(new_remote, b, force_with_lease=True)
        }[relation]

        print(message)
        ans = self.ask_if(ask_message, ask_opt_yes_message, override_answer=override_answer)
        if ans in ('y', 'yes', 'yq'):
            yes_action()
            if ans == 'yq':
                raise StopTraversal
            self.git.flush_caches()
        elif can_pick_other_remote and ans in ('o', 'other'):
            self.__pick_remote(b)
        elif ans in ('q', 'quit'):
            raise StopTraversal

    def is_merged_to(self, b: str, target: str) -> bool:
        if self.git.is_ancestor_or_equal(b, target):
            # If branch is ancestor of or equal to the target, we need to distinguish between the
            # case of branch being "recently" created from the target and the case of
            # branch being fast-forward-merged to the target.
            # The applied heuristics is to check if the filtered reflog of the branch
            # (reflog stripped of trivial events like branch creation, reset etc.)
            # is non-empty.
            return bool(self.filtered_reflog(b, prefix="refs/heads/"))
        elif self.cli_opts.opt_no_detect_squash_merges:
            return False
        else:
            # In the default mode.
            # If there is a commit in target with an identical tree state to b,
            # then b may be squash or rebase merged into target.
            return self.git.contains_equivalent_tree(b, target)

    def ask_if(self, msg: str, opt_yes_msg: Optional[str],
               override_answer: Optional[str] = None,
               apply_fmt: bool = True) -> str:
        if override_answer:
            return override_answer
        if self.cli_opts.opt_yes and opt_yes_msg:
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


# Allowed parameter values for show/go command
def allowed_directions(allow_current: bool) -> str:
    current = "c[urrent]|" if allow_current else ""
    return current + "d[own]|f[irst]|l[ast]|n[ext]|p[rev]|r[oot]|u[p]"


# Main

alias_by_command: Dict[str, str] = {
    "diff": "d",
    "edit": "e",
    "go": "g",
    "log": "l",
    "status": "s"
}
command_by_alias: Dict[str, str] = {v: k for k, v in alias_by_command.items()}

command_groups: List[Tuple[str, List[str]]] = [
    # 'is-managed' is mostly for scripting use and therefore skipped
    ("General topics", ["file", "help", "hooks", "version"]),
    ("Build, display and modify the tree of branch dependencies", ["add", "anno", "discover", "edit", "status"]),
    ("List, check out and delete branches", ["delete-unmanaged", "go", "list", "show"]),
    ("Determine changes specific to the given branch", ["diff", "fork-point", "log"]),
    ("Update git history in accordance with the tree of branch dependencies", ["advance", "reapply", "slide-out", "squash", "traverse", "update"])
]


def usage(c: str = None) -> None:

    if c and c in command_by_alias:
        c = command_by_alias[c]
    if c and c in long_docs:
        print(fmt(textwrap.dedent(long_docs[c])))
    else:
        print()
        short_usage()
        if c and c not in long_docs:
            print(f"\nUnknown command: '{c}'")
        print(fmt("\n<u>TL;DR tip</u>\n\n"
              "    Get familiar with the help for <b>format</b>, <b>edit</b>, <b>status</b> and <b>update</b>, in this order.\n"))
        for hdr, cmds in command_groups:
            print(underline(hdr))
            print("")
            for cm in cmds:
                alias = f", {alias_by_command[cm]}" if cm in alias_by_command else ""
                print("    %s%-18s%s%s" % (BOLD, cm + alias, ENDC, short_docs[cm]))  # bold(...) can't be used here due to the %-18s format specifier
            sys.stdout.write("\n")
        print(fmt(textwrap.dedent("""
            <u>General options</u>\n
                <b>--debug</b>           Log detailed diagnostic info, including outputs of the executed git commands.
                <b>-h, --help</b>        Print help and exit.
                <b>-v, --verbose</b>     Log the executed git commands.
                <b>--version</b>         Print version and exit.
        """[1:])))


def short_usage() -> None:
    print(fmt("<b>Usage: git machete [--debug] [-h] [-v|--verbose] [--version] <command> [command-specific options] [command-specific argument]</b>"))


def version() -> None:
    print(f"git-machete version {__version__}")


def main() -> None:
    launch(sys.argv[1:])


def launch(orig_args: List[str]) -> None:

    cli_opts = CommandLineOptions()
    git = GitContext(cli_opts)
    machete_client = MacheteClient(cli_opts, git)

    if sys.version_info.major == 2 or (sys.version_info.major == 3 and sys.version_info.minor < 6):
        version_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        sys.stderr.write(f"Python {version_str} is no longer supported. Please switch to Python 3.6 or higher.\n")
        sys.exit(1)

    def parse_options(in_args: List[str], short_opts: str = "", long_opts: List[str] = [], allow_intermixing_options_and_params: bool = True) -> List[str]:

        fun = getopt.gnu_getopt if allow_intermixing_options_and_params else getopt.getopt
        opts, rest = fun(in_args, short_opts + "hv", long_opts + ['debug', 'help', 'verbose', 'version'])

        for opt, arg in opts:
            if opt in ("-b", "--branch"):
                cli_opts.opt_branch = arg
            elif opt in ("-C", "--checked-out-since"):
                cli_opts.opt_checked_out_since = arg
            elif opt == "--color":
                cli_opts.opt_color = arg
            elif opt in ("-d", "--down-fork-point"):
                cli_opts.opt_down_fork_point = arg
            elif opt == "--debug":
                CommandLineOptions.opt_debug = True
            elif opt in ("-F", "--fetch"):
                cli_opts.opt_fetch = True
            elif opt in ("-f", "--fork-point"):
                cli_opts.opt_fork_point = arg
            elif opt in ("-H", "--sync-github-prs"):
                cli_opts.opt_sync_github_prs = True
            elif opt in ("-h", "--help"):
                usage(cmd)
                sys.exit()
            elif opt == "--inferred":
                cli_opts.opt_inferred = True
            elif opt in ("-L", "--list-commits-with-hashes"):
                cli_opts.opt_list_commits = cli_opts.opt_list_commits_with_hashes = True
            elif opt in ("-l", "--list-commits"):
                cli_opts.opt_list_commits = True
            elif opt in ("-M", "--merge"):
                cli_opts.opt_merge = True
            elif opt == "-n":
                cli_opts.opt_n = True
            elif opt == "--no-detect-squash-merges":
                cli_opts.opt_no_detect_squash_merges = True
            elif opt == "--no-edit-merge":
                cli_opts.opt_no_edit_merge = True
            elif opt == "--no-interactive-rebase":
                cli_opts.opt_no_interactive_rebase = True
            elif opt == "--no-push":
                cli_opts.opt_push_tracked = False
                cli_opts.opt_push_untracked = False
            elif opt == "--no-push-untracked":
                cli_opts.opt_push_untracked = False
            elif opt in ("-o", "--onto"):
                cli_opts.opt_onto = arg
            elif opt == "--override-to":
                cli_opts.opt_override_to = arg
            elif opt == "--override-to-inferred":
                cli_opts.opt_override_to_inferred = True
            elif opt == "--override-to-parent":
                cli_opts.opt_override_to_parent = True
            elif opt == "--push":
                cli_opts.opt_push_tracked = True
                cli_opts.opt_push_untracked = True
            elif opt == "--push-untracked":
                cli_opts.opt_push_untracked = True
            elif opt in ("-R", "--as-root"):
                cli_opts.opt_as_root = True
            elif opt in ("-r", "--roots"):
                cli_opts.opt_roots = arg.split(",")
            elif opt == "--return-to":
                cli_opts.opt_return_to = arg
            elif opt in ("-s", "--stat"):
                cli_opts.opt_stat = True
            elif opt == "--start-from":
                cli_opts.opt_start_from = arg
            elif opt == "--unset-override":
                cli_opts.opt_unset_override = True
            elif opt in ("-v", "--verbose"):
                CommandLineOptions.opt_verbose = True
            elif opt == "--version":
                version()
                sys.exit()
            elif opt == "-W":
                cli_opts.opt_fetch = True
                cli_opts.opt_start_from = "first-root"
                cli_opts.opt_n = True
                cli_opts.opt_return_to = "nearest-remaining"
            elif opt in ("-w", "--whole"):
                cli_opts.opt_start_from = "first-root"
                cli_opts.opt_n = True
                cli_opts.opt_return_to = "nearest-remaining"
            elif opt in ("-y", "--yes"):
                cli_opts.opt_yes = cli_opts.opt_no_interactive_rebase = True

        if cli_opts.opt_color not in ("always", "auto", "never"):
            raise MacheteException("Invalid argument for `--color`. Valid arguments: `always|auto|never`.")
        else:
            utils.ascii_only = cli_opts.opt_color == "never" or (cli_opts.opt_color == "auto" and not sys.stdout.isatty())

        if cli_opts.opt_as_root and cli_opts.opt_onto:
            raise MacheteException("Option `-R/--as-root` cannot be specified together with `-o/--onto`.")

        if cli_opts.opt_no_edit_merge and not cli_opts.opt_merge:
            raise MacheteException("Option `--no-edit-merge` only makes sense when using merge and must be specified together with `-M/--merge`.")
        if cli_opts.opt_no_interactive_rebase and cli_opts.opt_merge:
            raise MacheteException("Option `--no-interactive-rebase` only makes sense when using rebase and cannot be specified together with `-M/--merge`.")
        if cli_opts.opt_down_fork_point and cli_opts.opt_merge:
            raise MacheteException("Option `-d/--down-fork-point` only makes sense when using rebase and cannot be specified together with `-M/--merge`.")
        if cli_opts.opt_fork_point and cli_opts.opt_merge:
            raise MacheteException("Option `-f/--fork-point` only makes sense when using rebase and cannot be specified together with `-M/--merge`.")

        if cli_opts.opt_n and cli_opts.opt_merge:
            cli_opts.opt_no_edit_merge = True
        if cli_opts.opt_n and not cli_opts.opt_merge:
            cli_opts.opt_no_interactive_rebase = True

        return rest

    def expect_no_param(in_args: List[str], extra_explanation: str = '') -> None:
        if len(in_args) > 0:
            raise MacheteException(f"No argument expected for `{cmd}`{extra_explanation}")

    def check_optional_param(in_args: List[str]) -> Optional[str]:
        if not in_args:
            return None
        elif len(in_args) > 1:
            raise MacheteException(f"`{cmd}` accepts at most one argument")
        elif not in_args[0]:
            raise MacheteException(f"Argument to `{cmd}` cannot be empty")
        elif in_args[0][0] == "-":
            raise MacheteException(f"Option `{in_args[0]}` not recognized")
        else:
            return in_args[0]

    def check_required_param(in_args: List[str], allowed_values_string: str) -> str:
        if not in_args or len(in_args) > 1:
            raise MacheteException(f"`{cmd}` expects exactly one argument: one of {allowed_values_string}")
        elif not in_args[0]:
            raise MacheteException(f"Argument to `{cmd}` cannot be empty; expected one of {allowed_values_string}")
        elif in_args[0][0] == "-":
            raise MacheteException(f"Option `{in_args[0]}` not recognized")
        else:
            return in_args[0]

    try:
        cmd = None
        # Let's first extract the common options like `--help` or `--verbose` that might appear BEFORE the command,
        # as in e.g. `git machete --verbose status`.
        cmd_and_args = parse_options(orig_args, allow_intermixing_options_and_params=False)
        # Subsequent calls to `parse_options` will, in turn, extract the options appearing AFTER the command.
        if not cmd_and_args:
            usage()
            sys.exit(2)
        cmd = cmd_and_args[0]
        args = cmd_and_args[1:]

        if cmd != "help":
            if cmd != "discover":
                if not os.path.exists(machete_client.definition_file_path):
                    # We're opening in "append" and not "write" mode to avoid a race condition:
                    # if other process writes to the file between we check the result of `os.path.exists` and call `open`,
                    # then open(..., "w") would result in us clearing up the file contents, while open(..., "a") has no effect.
                    with open(machete_client.definition_file_path, "a"):
                        pass
                elif os.path.isdir(machete_client.definition_file_path):
                    # Extremely unlikely case, basically checking if anybody tampered with the repository.
                    raise MacheteException(
                        f"{machete_client.definition_file_path} is a directory rather than a regular file, aborting")

        if cmd == "add":
            param = check_optional_param(parse_options(args, "o:Ry", ["onto=", "as-root", "yes"]))
            machete_client.read_definition_file()
            machete_client.add(param or git.current_branch())
        elif cmd == "advance":
            args1 = parse_options(args, "y", ["yes"])
            expect_no_param(args1)
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            cb = git.current_branch()
            machete_client.expect_in_managed_branches(cb)
            machete_client.advance(cb)
        elif cmd == "anno":
            params = parse_options(args, "b:H", ["branch=", "sync-github-prs"])
            machete_client.read_definition_file(verify_branches=False)
            if cli_opts.opt_sync_github_prs:
                machete_client.sync_annotations_to_github_prs()
            else:
                b = cli_opts.opt_branch or git.current_branch()
                machete_client.expect_in_managed_branches(b)
                if params:
                    machete_client.annotate(b, params)
                else:
                    machete_client.print_annotation(b)
        elif cmd == "delete-unmanaged":
            expect_no_param(parse_options(args, "y", ["yes"]))
            machete_client.read_definition_file()
            machete_client.delete_unmanaged()
        elif cmd in ("d", "diff"):
            param = check_optional_param(parse_options(args, "s", ["stat"]))
            machete_client.read_definition_file()
            machete_client.diff(param)  # passing None if not specified
        elif cmd == "discover":
            expect_no_param(parse_options(args, "C:lr:y", ["checked-out-since=", "list-commits", "roots=", "yes"]))
            # No need to read definition file.
            machete_client.discover_tree()
        elif cmd in ("e", "edit"):
            expect_no_param(parse_options(args))
            # No need to read definition file.
            machete_client.edit()
        elif cmd == "file":
            expect_no_param(parse_options(args))
            # No need to read definition file.
            print(os.path.abspath(machete_client.definition_file_path))
        elif cmd == "fork-point":
            long_options = ["inferred", "override-to=", "override-to-inferred", "override-to-parent", "unset-override"]
            param = check_optional_param(parse_options(args, "", long_options))
            machete_client.read_definition_file()
            b = param or git.current_branch()
            if len(list(filter(None, [cli_opts.opt_inferred, cli_opts.opt_override_to, cli_opts.opt_override_to_inferred, cli_opts.opt_override_to_parent, cli_opts.opt_unset_override]))) > 1:
                long_options_string = ", ".join(map(lambda x: x.replace("=", ""), long_options))
                raise MacheteException(f"At most one of {long_options_string} options may be present")
            if cli_opts.opt_inferred:
                print(machete_client.fork_point(b, use_overrides=False))
            elif cli_opts.opt_override_to:
                machete_client.set_fork_point_override(b, cli_opts.opt_override_to)
            elif cli_opts.opt_override_to_inferred:
                machete_client.set_fork_point_override(b, machete_client.fork_point(b, use_overrides=False))
            elif cli_opts.opt_override_to_parent:
                u = machete_client.up_branch.get(b)
                if u:
                    machete_client.set_fork_point_override(b, u)
                else:
                    raise MacheteException(f"Branch {b} does not have upstream (parent) branch")
            elif cli_opts.opt_unset_override:
                machete_client.unset_fork_point_override(b)
            else:
                print(machete_client.fork_point(b, use_overrides=True))
        elif cmd in ("g", "go"):
            param = check_required_param(parse_options(args), allowed_directions(allow_current=False))
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            cb = git.current_branch()
            dest = machete_client.parse_direction(param, cb, allow_current=False, down_pick_mode=True)
            if dest != cb:
                git.checkout(dest)
        elif cmd == "help":
            param = check_optional_param(parse_options(args))
            # No need to read definition file.
            usage(param)
        elif cmd == "is-managed":
            param = check_optional_param(parse_options(args))
            machete_client.read_definition_file()
            b = param or git.current_branch_or_none()
            if b is None or b not in machete_client.managed_branches:
                sys.exit(1)
        elif cmd == "list":
            list_allowed_values = "addable|managed|slidable|slidable-after <branch>|unmanaged|with-overridden-fork-point"
            list_args = parse_options(args)
            if not list_args:
                raise MacheteException(f"`git machete list` expects argument(s): {list_allowed_values}")
            elif not list_args[0]:
                raise MacheteException(
                    f"Argument to `git machete list` cannot be empty; expected {list_allowed_values}")
            elif list_args[0][0] == "-":
                raise MacheteException(f"Option `{list_args[0]}` not recognized")
            elif list_args[0] not in ("addable", "managed", "slidable", "slidable-after", "unmanaged", "with-overridden-fork-point"):
                raise MacheteException(f"Usage: git machete list {list_allowed_values}")
            elif len(list_args) > 2:
                raise MacheteException(f"Too many arguments to `git machete list {list_args[0]}` ")
            elif list_args[0] in ("addable", "managed", "slidable", "unmanaged", "with-overridden-fork-point") and len(list_args) > 1:
                raise MacheteException(f"`git machete list {list_args[0]}` does not expect extra arguments")
            elif list_args[0] == "slidable-after" and len(list_args) != 2:
                raise MacheteException(f"`git machete list {list_args[0]}` requires an extra <branch> argument")

            param = list_args[0]
            machete_client.read_definition_file()
            res = []
            if param == "addable":
                def strip_first_fragment(rb: str) -> str:
                    return re.sub("^[^/]+/", "", rb)

                remote_counterparts_of_local_branches = utils.map_truthy_only(lambda b: git.combined_counterpart_for_fetching_of_branch(b), git.local_branches())
                qualifying_remote_branches = excluding(git.remote_branches(), remote_counterparts_of_local_branches)
                res = excluding(git.local_branches(), machete_client.managed_branches) + list(map(strip_first_fragment, qualifying_remote_branches))
            elif param == "managed":
                res = machete_client.managed_branches
            elif param == "slidable":
                res = machete_client.slidable()
            elif param == "slidable-after":
                b_arg = list_args[1]
                machete_client.expect_in_managed_branches(b_arg)
                res = machete_client.slidable_after(b_arg)
            elif param == "unmanaged":
                res = excluding(git.local_branches(), machete_client.managed_branches)
            elif param == "with-overridden-fork-point":
                res = list(filter(lambda b: machete_client.has_any_fork_point_override_config(b), git.local_branches()))

            if res:
                print("\n".join(res))
        elif cmd in ("l", "log"):
            param = check_optional_param(parse_options(args))
            machete_client.read_definition_file()
            machete_client.log(param or git.current_branch())
        elif cmd == "reapply":
            args1 = parse_options(args, "f:", ["fork-point="])
            expect_no_param(args1, ". Use `-f` or `--fork-point` to specify the fork point commit")
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            cb = git.current_branch()
            git.rebase_onto_ancestor_commit(cb, cli_opts.opt_fork_point or machete_client.fork_point(cb, use_overrides=True))
        elif cmd == "show":
            args1 = parse_options(args)
            param = check_required_param(args1[:1], allowed_directions(allow_current=True))
            branch = check_optional_param(args1[1:])
            if param == "current" and branch is not None:
                raise MacheteException(f'`show current` with a branch (`{branch}`) does not make sense')
            machete_client.read_definition_file(verify_branches=False)
            print(machete_client.parse_direction(param, branch or git.current_branch(), allow_current=True, down_pick_mode=False))
        elif cmd == "slide-out":
            params = parse_options(args, "d:Mn", ["down-fork-point=", "merge", "no-edit-merge", "no-interactive-rebase"])
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            machete_client.slide_out(params or [git.current_branch()])
        elif cmd == "squash":
            args1 = parse_options(args, "f:", ["fork-point="])
            expect_no_param(args1, ". Use `-f` or `--fork-point` to specify the fork point commit")
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            cb = git.current_branch()
            machete_client.squash(cb, cli_opts.opt_fork_point or machete_client.fork_point(cb, use_overrides=True))
        elif cmd in ("s", "status"):
            expect_no_param(parse_options(args, "Ll", ["color=", "list-commits-with-hashes", "list-commits", "no-detect-squash-merges"]))
            machete_client.read_definition_file()
            machete_client.expect_at_least_one_managed_branch()
            machete_client.status(warn_on_yellow_edges=True)
        elif cmd == "traverse":
            traverse_long_opts = ["fetch", "list-commits", "merge",
                                  "no-detect-squash-merges", "no-edit-merge", "no-interactive-rebase",
                                  "no-push", "no-push-untracked", "push", "push-untracked",
                                  "return-to=", "start-from=", "whole", "yes"]
            expect_no_param(parse_options(args, "FlMnWwy", traverse_long_opts))
            if cli_opts.opt_start_from not in ("here", "root", "first-root"):
                raise MacheteException("Invalid argument for `--start-from`. Valid arguments: `here|root|first-root`.")
            if cli_opts.opt_return_to not in ("here", "nearest-remaining", "stay"):
                raise MacheteException("Invalid argument for `--return-to`. Valid arguments: here|nearest-remaining|stay.")
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            machete_client.traverse()
        elif cmd == "update":
            args1 = parse_options(args, "f:Mn", ["fork-point=", "merge", "no-edit-merge", "no-interactive-rebase"])
            expect_no_param(args1, ". Use `-f` or `--fork-point` to specify the fork point commit")
            machete_client.read_definition_file()
            git.expect_no_operation_in_progress()
            machete_client.update()
        elif cmd == "version":
            version()
            sys.exit()
        else:
            short_usage()
            raise MacheteException(f"\nUnknown command: `{cmd}`. Use `git machete help` to list possible commands")

    except getopt.GetoptError as e:
        short_usage()
        sys.stderr.write(str(e) + "\n")
        sys.exit(2)
    except MacheteException as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted by the user")
        sys.exit(1)
    except StopTraversal:
        pass
    finally:
        if initial_current_directory and not utils.directory_exists(initial_current_directory):
            nearest_existing_parent_directory = initial_current_directory
            while not utils.directory_exists(nearest_existing_parent_directory):
                nearest_existing_parent_directory = os.path.join(nearest_existing_parent_directory, os.path.pardir)
            warn(f"current directory {initial_current_directory} no longer exists, "
                 f"the nearest existing parent directory is {os.path.abspath(nearest_existing_parent_directory)}")


if __name__ == "__main__":
    main()
