#!/usr/bin/env python

from typing import Any, Callable, Dict, Generator, Iterable, Iterator, List, Match, Optional, Set, Tuple, TypeVar

from git_machete import __version__
import datetime
import getopt
import io
import itertools
import os
import re
import shutil
import subprocess
import sys
import textwrap


# Core utils

T = TypeVar('T')


class MacheteException(Exception):
    def __init__(self, msg: str, apply_fmt: bool = True) -> None:
        self.parameter = fmt(msg) if apply_fmt else msg

    def __str__(self) -> str:
        return str(self.parameter)


def excluding(iterable: Iterable[T], s: Iterable[T]) -> List[T]:
    return list(filter(lambda x: x not in s, iterable))


def flat_map(func: Callable[[T], List[T]], iterable: Iterable[T]) -> List[T]:
    return sum(map(func, iterable), [])


def map_truthy_only(func: Callable[[T], Optional[T]], iterable: Iterable[T]) -> List[T]:
    return list(filter(None, map(func, iterable)))


def non_empty_lines(s: str) -> List[str]:
    return list(filter(None, s.split("\n")))


# Converts a lambda accepting N arguments to a lambda accepting one argument, an N-element tuple.
# Name matching Scala's `tupled` on `FunctionX`.
def tupled(f: Callable[..., T]) -> Callable[[Any], T]:
    return lambda tple: f(*tple)


def get_second(pair: Tuple[str, str]) -> str:
    a, b = pair
    return b


ENDC = '\033[0m'
BOLD = '\033[1m'
# `GIT_MACHETE_DIM_AS_GRAY` remains undocumented as for now,
# was just needed for animated gifs to render correctly (`[2m`-style dimmed text was invisible)
DIM = '\033[38;2;128;128;128m' if os.environ.get('GIT_MACHETE_DIM_AS_GRAY') == 'true' else '\033[2m'
UNDERLINE = '\033[4m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[00;38;5;208m'
RED = '\033[91m'


ascii_only: bool = False


def bold(s: str) -> str:
    return s if ascii_only or not s else BOLD + s + ENDC


def dim(s: str) -> str:
    return s if ascii_only or not s else DIM + s + ENDC


def underline(s: str, star_if_ascii_only: bool = False) -> str:
    if s and not ascii_only:
        return UNDERLINE + s + ENDC
    elif s and star_if_ascii_only:
        return s + " *"
    else:
        return s


def colored(s: str, color: str) -> str:
    return s if ascii_only or not s else color + s + ENDC


fmt_transformations: List[Callable[[str], str]] = [
    lambda x: re.sub('<b>(.*?)</b>', bold(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<u>(.*?)</u>', underline(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<dim>(.*?)</dim>', dim(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<red>(.*?)</red>', colored(r"\1", RED), x, flags=re.DOTALL),
    lambda x: re.sub('<yellow>(.*?)</yellow>', colored(r"\1", YELLOW), x, flags=re.DOTALL),
    lambda x: re.sub('<green>(.*?)</green>', colored(r"\1", GREEN), x, flags=re.DOTALL),
    lambda x: re.sub('`(.*?)`', r"`\1`" if ascii_only else UNDERLINE + r"\1" + ENDC, x),
]


def fmt(*parts: str) -> str:
    result = ''.join(parts)
    for f in fmt_transformations:
        result = f(result)
    return result


def vertical_bar() -> str:
    return "|" if ascii_only else u"│"


def right_arrow() -> str:
    return "->" if ascii_only else u"➔"


class CommandLineContext:
    def __init__(self) -> None:
        self.opt_as_root: bool = False
        self.opt_branch: Optional[str] = None
        self.opt_checked_out_since: Optional[str] = None
        self.opt_color: str = "auto"
        self.opt_debug: bool = False
        self.opt_down_fork_point: Optional[str] = None
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
        self.opt_verbose: bool = False
        self.opt_yes: bool = False


def ask_if(
    cli_ctxt: CommandLineContext,
    msg: str,
    opt_yes_msg: Optional[str],
    override_answer: Optional[str] = None,
    apply_fmt: bool = True
) -> str:
    if override_answer:
        return override_answer
    if cli_ctxt.opt_yes and opt_yes_msg:
        print(fmt(opt_yes_msg) if apply_fmt else opt_yes_msg)
        return 'y'
    return input(fmt(msg) if apply_fmt else msg).lower()


def pretty_choices(*choices: str) -> str:
    def format_choice(c: str) -> str:
        if not c:
            return ''
        elif c.lower() == 'y':
            return colored(c, GREEN)
        elif c.lower() == 'yq':
            return colored(c[0], GREEN) + colored(c[1], RED)
        elif c.lower() in ('n', 'q'):
            return colored(c, RED)
        else:
            return colored(c, ORANGE)
    return f" ({', '.join(map_truthy_only(format_choice, choices))}) "


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


def debug(cli_ctxt: CommandLineContext, hdr: str, msg: str) -> None:
    if cli_ctxt.opt_debug:
        sys.stderr.write(f"{bold(hdr)}: {dim(msg)}\n")


# To avoid displaying the same warning multiple times during a single run.
displayed_warnings: Set[str] = set()


def warn(msg: str, apply_fmt: bool = True) -> None:
    global displayed_warnings
    if msg not in displayed_warnings:
        sys.stderr.write(colored("Warn: ", RED) + (fmt(msg) if apply_fmt else msg) + "\n")
        displayed_warnings.add(msg)


def directory_exists(path: str) -> bool:
    try:
        # Note that os.path.isdir itself (without os.path.abspath) isn't reliable
        # since it returns a false positive (True) for the current directory when if it doesn't exist
        return os.path.isdir(os.path.abspath(path))
    except OSError:
        return False


def current_directory_or_none() -> Optional[str]:
    try:
        return os.getcwd()
    except OSError:
        # This happens when current directory does not exist (typically: has been deleted)
        return None


# Let's keep the flag to avoid checking for current directory's existence
# every time any command is being popened or run.
current_directory_confirmed_to_exist: bool = False
initial_current_directory: Optional[str] = current_directory_or_none() or os.getenv('PWD')


def mark_current_directory_as_possibly_non_existent() -> None:
    global current_directory_confirmed_to_exist
    current_directory_confirmed_to_exist = False


def chdir_upwards_until_current_directory_exists(cli_ctxt: CommandLineContext) -> None:
    global current_directory_confirmed_to_exist
    if not current_directory_confirmed_to_exist:
        current_directory: Optional[str] = current_directory_or_none()
        if not current_directory:
            while not current_directory:
                # Note: 'os.chdir' only affects the current process and its subprocesses;
                # it doesn't propagate to the parent process (which is typically a shell).
                os.chdir(os.path.pardir)
                current_directory = current_directory_or_none()
            debug(cli_ctxt,
                  "chdir_upwards_until_current_directory_exists()",
                  f"current directory did not exist, chdired up into {current_directory}")
        current_directory_confirmed_to_exist = True


def run_cmd(cli_ctxt: CommandLineContext, cmd: str, *args: str, **kwargs: Any) -> int:
    chdir_upwards_until_current_directory_exists(cli_ctxt)

    flat_cmd: str = cmd_shell_repr(cmd, *args, **kwargs)
    if cli_ctxt.opt_debug:
        sys.stderr.write(bold(f">>> {flat_cmd}") + "\n")
    elif cli_ctxt.opt_verbose:
        sys.stderr.write(flat_cmd + "\n")

    exit_code: int = subprocess.call([cmd] + list(args), **kwargs)

    # Let's defensively assume that every command executed via run_cmd
    # (but not via popen_cmd) can make the current directory disappear.
    # In practice, it's mostly 'git checkout' that carries such risk.
    mark_current_directory_as_possibly_non_existent()

    if cli_ctxt.opt_debug and exit_code != 0:
        sys.stderr.write(dim(f"<exit code: {exit_code}>\n\n"))
    return exit_code


def popen_cmd(cli_ctxt: CommandLineContext, cmd: str, *args: str, **kwargs: Any) -> Tuple[int, str, str]:
    chdir_upwards_until_current_directory_exists(cli_ctxt)

    flat_cmd = cmd_shell_repr(cmd, *args, **kwargs)
    if cli_ctxt.opt_debug:
        sys.stderr.write(bold(f">>> {flat_cmd}") + "\n")
    elif cli_ctxt.opt_verbose:
        sys.stderr.write(flat_cmd + "\n")

    process = subprocess.Popen([cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    stdout_bytes, stderr_bytes = process.communicate()
    stdout: str = stdout_bytes.decode('utf-8')
    stderr: str = stderr_bytes.decode('utf-8')
    exit_code: int = process.returncode

    if cli_ctxt.opt_debug:
        if exit_code != 0:
            sys.stderr.write(colored(f"<exit code: {exit_code}>\n\n", RED))
        if stdout:
            sys.stderr.write(f"{dim('<stdout>:')}\n{dim(stdout)}\n")
        if stderr:
            sys.stderr.write(f"{dim('<stderr>:')}\n{colored(stderr, RED)}\n")

    return exit_code, stdout, stderr

# Git core


def cmd_shell_repr(cmd: str, *args: str, **kwargs: Dict[str, str]) -> str:
    def shell_escape(arg: str) -> str:
        return arg.replace("(", "\\(") \
            .replace(")", "\\)") \
            .replace(" ", "\\ ") \
            .replace("\t", "$'\\t'") \
            .replace("\n", "$'\\n'")

    env: Dict[str, str] = kwargs.get("env", {})
    # We don't want to include the env vars that are inherited from the environment of git-machete process
    env_repr = [k + "=" + shell_escape(v) for k, v in env.items() if k not in os.environ]
    return " ".join(env_repr + [cmd] + list(map(shell_escape, args)))


def run_git(cli_ctxt: CommandLineContext, git_cmd: str, *args: str, **kwargs: Dict[str, str]) -> int:
    exit_code = run_cmd(cli_ctxt, "git", git_cmd, *args, **kwargs)
    if not kwargs.get("allow_non_zero") and exit_code != 0:
        raise MacheteException(f"`{cmd_shell_repr('git', git_cmd, *args, **kwargs)}` returned {exit_code}")
    return exit_code


def popen_git(cli_ctxt: CommandLineContext, git_cmd: str, *args: str, **kwargs: Dict[str, str]) -> str:
    exit_code, stdout, stderr = popen_cmd(cli_ctxt, "git", git_cmd, *args, **kwargs)
    if not kwargs.get("allow_non_zero") and exit_code != 0:
        exit_code_msg: str = fmt(f"`{cmd_shell_repr('git', git_cmd, *args, **kwargs)}` returned {exit_code}\n")
        stdout_msg: str = f"\n{bold('stdout')}:\n{dim(stdout)}" if stdout else ""
        stderr_msg: str = f"\n{bold('stderr')}:\n{dim(stderr)}" if stderr else ""
        # Not applying the formatter to avoid transforming whatever characters might be in the output of the command.
        raise MacheteException(exit_code_msg + stdout_msg + stderr_msg, apply_fmt=False)
    return stdout


# Manipulation on definition file/tree of branches

BRANCH_DEF = Tuple[str, str]


class MacheteClient:

    DISCOVER_DEFAULT_FRESH_BRANCH_COUNT = 10
    PICK_FIRST_ROOT: int = 0
    PICK_LAST_ROOT: int = -1

    branch_defs_by_sha_in_reflog: Optional[Dict[str, Optional[List[Tuple[str, str]]]]] = None

    def __init__(self, cli_ctxt: CommandLineContext) -> None:
        self.cli_ctxt = cli_ctxt
        self.definition_file_path: str = get_git_subpath(self.cli_ctxt, "machete")
        self.managed_branches: List[str] = []
        self.down_branches: Dict[str, List[str]] = {}  # TODO (#110): default dict with []
        self.up_branch: Dict[str, str] = {}  # TODO (#110): default dict with None
        self.indent: Optional[str] = None
        self.roots: List[str] = []
        self.annotations: Dict[str, str] = {}
        self.empty_line_status: Optional[bool] = None

    def expect_in_managed_branches(self, b: str) -> None:
        if b not in self.managed_branches:
            raise MacheteException(
                f"Branch `{b}` not found in the tree of branch dependencies.\nUse `git machete add {b}` or `git machete edit`")

    def expect_at_least_one_managed_branch(self) -> None:
        if not self.roots:
            self.raise_no_branches_error()

    def raise_no_branches_error(self) -> None:
        raise MacheteException(
            f"No branches listed in {self.definition_file_path}; use `git machete discover` or `git machete edit`, or edit {self.definition_file_path} manually.")

    def read_definition_file(self, verify_branches: bool = True) -> None:
        with open(self.definition_file_path) as f:
            lines: List[str] = [line.rstrip() for line in f.readlines() if not line.isspace()]

        at_depth = {}
        last_depth = -1

        hint = "Edit the definition file manually with `git machete edit`"

        invalid_branches: List[str] = []
        for index, line in enumerate(lines):
            prefix = "".join(itertools.takewhile(str.isspace, line))
            if prefix and not self.indent:
                self.indent = prefix

            b_a: List[str] = line.strip().split(" ", 1)
            b = b_a[0]
            if len(b_a) > 1:
                self.annotations[b] = b_a[1]
            if b in self.managed_branches:
                raise MacheteException(
                    f"{self.definition_file_path}, line {index + 1}: branch `{b}` re-appears in the tree definition. {hint}")
            if verify_branches and b not in local_branches(self.cli_ctxt):
                invalid_branches += [b]
            self.managed_branches += [b]

            if prefix:
                depth: int = len(prefix) // len(self.indent)
                if prefix != self.indent * depth:
                    mapping: Dict[str, str] = {" ": "<SPACE>", "\t": "<TAB>"}
                    prefix_expanded: str = "".join(mapping[c] for c in prefix)
                    indent_expanded: str = "".join(mapping[c] for c in self.indent)
                    raise MacheteException(
                        f"{self.definition_file_path}, line {index + 1}: invalid indent `{prefix_expanded}`, expected a multiply of `{indent_expanded}`. {hint}")
            else:
                depth = 0

            if depth > last_depth + 1:
                raise MacheteException(
                    f"{self.definition_file_path}, line {index + 1}: too much indent (level {depth}, expected at most {last_depth + 1}) for the branch `{b}`. {hint}")
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
                self.roots += [b]

        if not invalid_branches:
            return

        if len(invalid_branches) == 1:
            ans: str = ask_if(self.cli_ctxt,
                              f"Skipping `{invalid_branches[0]}` " +
                              "which is not a local branch (perhaps it has been deleted?).\n" +
                              "Slide it out from the definition file?" +
                              pretty_choices("y", "e[dit]", "N"), opt_yes_msg=None)
        else:
            ans = ask_if(self.cli_ctxt,
                         f"Skipping {', '.join(f'`{b}`' for b in invalid_branches)} " +
                         "which are not local branches (perhaps they have been deleted?).\n" +
                         "Slide them out from the definition file?" +
                         pretty_choices("y", "e[dit]", "N"), opt_yes_msg=None)

        def recursive_slide_out_invalid_branches(b: str) -> List[str]:
            new_down_branches = flat_map(recursive_slide_out_invalid_branches, self.down_branches.get(b, []))
            if b in invalid_branches:
                if b in self.down_branches:
                    del self.down_branches[b]
                if b in self.annotations:
                    del self.annotations[b]
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

        self.roots = flat_map(recursive_slide_out_invalid_branches, self.roots)
        self.managed_branches = excluding(self.managed_branches, invalid_branches)
        if ans in ('y', 'yes'):
            self.save_definition_file()
        elif ans in ('e', 'edit'):
            self.edit()
            self.read_definition_file(verify_branches)

    def render_tree(self) -> List[str]:
        if not self.indent:
            self.indent = "\t"

        def render_dfs(b: str, depth: int) -> List[str]:
            self.annotation = f" {self.annotations[b]}" if b in self.annotations else ""
            res: List[str] = [depth * self.indent + b + self.annotation]
            for d in self.down_branches.get(b, []):
                res += render_dfs(d, depth + 1)
            return res

        total: List[str] = []
        for r in self.roots:
            total += render_dfs(r, depth=0)
        return total

    def back_up_definition_file(self) -> None:
        shutil.copyfile(self.definition_file_path, self.definition_file_path + "~")

    def save_definition_file(self) -> None:
        with open(self.definition_file_path, "w") as f:
            f.write("\n".join(self.render_tree()) + "\n")

    def add(self, b: str) -> None:
        if b in self.managed_branches:
            raise MacheteException(f"Branch `{b}` already exists in the tree of branch dependencies")

        onto: Optional[str] = self.cli_ctxt.opt_onto
        if onto:
            self.expect_in_managed_branches(onto)

        if b not in local_branches(self.cli_ctxt):
            rb: Optional[str] = get_sole_remote_branch(self.cli_ctxt, b)
            if rb:
                common_line = f"A local branch `{b}` does not exist, but a remote branch `{rb}` exists.\n"
                msg = common_line + f"Check out `{b}` locally?" + pretty_choices('y', 'N')
                opt_yes_msg = common_line + f"Checking out `{b}` locally..."
                if ask_if(self.cli_ctxt, msg, opt_yes_msg) in ('y', 'yes'):
                    create_branch(self.cli_ctxt, b, f"refs/remotes/{rb}")
                else:
                    return
                # Not dealing with `onto` here. If it hasn't been explicitly specified via `--onto`, we'll try to infer it now.
            else:
                out_of = f"refs/heads/{onto}" if onto else "HEAD"
                out_of_str = f"`{onto}`" if onto else "the current HEAD"
                msg = f"A local branch `{b}` does not exist. Create (out of {out_of_str})?" + pretty_choices('y', 'N')
                opt_yes_msg = f"A local branch `{b}` does not exist. Creating out of {out_of_str}"
                if ask_if(self.cli_ctxt, msg, opt_yes_msg) in ('y', 'yes'):
                    # If `--onto` hasn't been explicitly specified, let's try to assess if the current branch would be a good `onto`.
                    if self.roots and not onto:
                        cb = current_branch_or_none(self.cli_ctxt)
                        if cb and cb in self.managed_branches:
                            onto = cb
                    create_branch(self.cli_ctxt, b, out_of)
                else:
                    return

        if self.cli_ctxt.opt_as_root or not self.roots:
            self.roots += [b]
            print(fmt(f"Added branch `{b}` as a new root"))
        else:
            if not onto:
                u = self.infer_upstream(b, condition=lambda x: x in self.managed_branches, reject_reason_message="this candidate is not a managed branch")
                if not u:
                    raise MacheteException(f"Could not automatically infer upstream (parent) branch for `{b}`.\n"
                                           "You can either:\n"
                                           "1) specify the desired upstream branch with `--onto` or\n"
                                           f"2) pass `--as-root` to attach `{b}` as a new root or\n"
                                           "3) edit the definition file manually with `git machete edit`")
                else:
                    msg = f"Add `{b}` onto the inferred upstream (parent) branch `{u}`?" + pretty_choices('y', 'N')
                    opt_yes_msg = f"Adding `{b}` onto the inferred upstream (parent) branch `{u}`"
                    if ask_if(self.cli_ctxt, msg, opt_yes_msg) in ('y', 'yes'):
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

        if b in self.annotations and words == ['']:
            del self.annotations[b]
        else:
            self.annotations[b] = " ".join(words)
        self.save_definition_file()

    def print_annotation(self, b: str) -> None:
        if b in self.annotations:
            print(self.annotations[b])

    def update(self) -> None:
        cb = current_branch(self.cli_ctxt)
        if self.cli_ctxt.opt_merge:
            with_branch = self.up(cb,
                                  prompt_if_inferred_msg="Branch `%s` not found in the tree of branch dependencies. Merge with the inferred upstream `%s`?" + pretty_choices('y', 'N'),
                                  prompt_if_inferred_yes_opt_msg="Branch `%s` not found in the tree of branch dependencies. Merging with the inferred upstream `%s`...")
            merge(self.cli_ctxt, with_branch, cb)
        else:
            onto_branch = self.up(cb,
                                  prompt_if_inferred_msg="Branch `%s` not found in the tree of branch dependencies. Rebase onto the inferred upstream `%s`?" + pretty_choices('y', 'N'),
                                  prompt_if_inferred_yes_opt_msg="Branch `%s` not found in the tree of branch dependencies. Rebasing onto the inferred upstream `%s`...")
            rebase(self.cli_ctxt, f"refs/heads/{onto_branch}",
                   self.cli_ctxt.opt_fork_point or self.fork_point(cb, use_overrides=True), cb)

    def discover_tree(self) -> None:
        all_local_branches = local_branches(self.cli_ctxt)
        if not all_local_branches:
            raise MacheteException("No local branches found")
        for r in self.cli_ctxt.opt_roots:
            if r not in local_branches(self.cli_ctxt):
                raise MacheteException(f"`{r}` is not a local branch")
        if self.cli_ctxt.opt_roots:
            self.roots = list(self.cli_ctxt.opt_roots)
        else:
            self.roots = []
            if "master" in local_branches(self.cli_ctxt):
                self.roots += ["master"]
            elif "main" in local_branches(self.cli_ctxt):
                # See https://github.com/github/renaming
                self.roots += ["main"]
            if "develop" in local_branches(self.cli_ctxt):
                self.roots += ["develop"]
        self.down_branches = {}
        self.up_branch = {}
        self.indent = "\t"
        self.annotations = {}

        root_of = dict((b, b) for b in all_local_branches)

        def get_root_of(b: str) -> str:
            if b != root_of[b]:
                root_of[b] = get_root_of(root_of[b])
            return root_of[b]

        non_root_fixed_branches = excluding(all_local_branches, self.roots)
        last_checkout_timestamps = get_latest_checkout_timestamps(self.cli_ctxt)
        non_root_fixed_branches_by_last_checkout_timestamps = sorted(
            (last_checkout_timestamps.get(b, 0), b) for b in non_root_fixed_branches)
        if self.cli_ctxt.opt_checked_out_since:
            threshold = parse_git_timespec_to_unix_timestamp(self.cli_ctxt, self.cli_ctxt.opt_checked_out_since)
            stale_non_root_fixed_branches = [b for (timestamp, b) in itertools.takewhile(
                tupled(lambda timestamp, b: timestamp < threshold),
                non_root_fixed_branches_by_last_checkout_timestamps
            )]
        else:
            c = MacheteClient.DISCOVER_DEFAULT_FRESH_BRANCH_COUNT
            stale, fresh = non_root_fixed_branches_by_last_checkout_timestamps[:-c], non_root_fixed_branches_by_last_checkout_timestamps[-c:]
            stale_non_root_fixed_branches = [b for (timestamp, b) in stale]
            if stale:
                threshold_date = datetime.datetime.utcfromtimestamp(fresh[0][0]).strftime("%Y-%m-%d")
                warn(f"to keep the size of the discovered tree reasonable (ca. {c} branches), "
                     f"only branches checked out at or after ca. <b>{threshold_date}</b> are included.\n"
                     "Use `git machete discover --checked-out-since=<date>` (where <date> can be e.g. `'2 weeks ago'` or `2020-06-01`) "
                     "to change this threshold so that less or more branches are included.\n")
        self.managed_branches = excluding(all_local_branches, stale_non_root_fixed_branches)
        if self.cli_ctxt.opt_checked_out_since and not self.managed_branches:
            warn(
                "no branches satisfying the criteria. Try moving the value of `--checked-out-since` further to the past.")
            return

        for b in excluding(non_root_fixed_branches, stale_non_root_fixed_branches):
            u = self.infer_upstream(b, condition=lambda candidate: get_root_of(candidate) != b and candidate not in stale_non_root_fixed_branches, reject_reason_message="choosing this candidate would form a cycle in the resulting graph or the candidate is a stale branch")
            if u:
                debug(self.cli_ctxt, "discover_tree()",
                      f"inferred upstream of {b} is {u}, attaching {b} as a child of {u}\n")
                self.up_branch[b] = u
                root_of[b] = u
                if u in self.down_branches:
                    self.down_branches[u].append(b)
                else:
                    self.down_branches[u] = [b]
            else:
                debug(self.cli_ctxt, "discover_tree()", f"inferred no upstream for {b}, attaching {b} as a new root\n")
                self.roots += [b]

        # Let's remove merged branches for which no downstream branch have been found.
        merged_branches_to_skip = []
        for b in self.managed_branches:
            if b in self.up_branch and not self.down_branches.get(b):
                u = self.up_branch[b]
                if is_merged_to(self, self.cli_ctxt, b, u):
                    debug(self.cli_ctxt,
                          "discover_tree()",
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
        do_backup = os.path.isfile(self.definition_file_path)
        backup_msg = f"\nThe existing definition file will be backed up as {self.definition_file_path}~" if do_backup else ""
        msg = f"Save the above tree to {self.definition_file_path}?{backup_msg}" + pretty_choices('y', 'e[dit]', 'N')
        opt_yes_msg = f"Saving the above tree to {self.definition_file_path}... {backup_msg}"
        ans = ask_if(self.cli_ctxt, msg, opt_yes_msg)
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
        self.run_post_slide_out_hook(new_upstream, branches_to_slide_out[-1], new_downstreams)

        go(self.cli_ctxt, new_upstream)
        for new_downstream in new_downstreams:
            go(self.cli_ctxt, new_downstream)
            if self.cli_ctxt.opt_merge:
                print(f"Merging {bold(new_upstream)} into {bold(new_downstream)}...")
                merge(self.cli_ctxt, new_upstream, new_downstream)
            else:
                print(f"Rebasing {bold(new_downstream)} onto {bold(new_upstream)}...")
                rebase(self.cli_ctxt, f"refs/heads/{new_upstream}",
                       self.cli_ctxt.opt_down_fork_point or self.fork_point(new_downstream, use_overrides=True),
                       new_downstream)

    def advance(self, b: str) -> None:
        if not self.down_branches.get(b):
            raise MacheteException(f"`{b}` does not have any downstream (child) branches to advance towards")

        def connected_with_green_edge(bd: str) -> bool:
            return bool(
                not self.is_merged_to_upstream(bd) and
                is_ancestor_or_equal(self.cli_ctxt, b, bd) and
                (self.get_overridden_fork_point(bd) or commit_sha_by_revision(self.cli_ctxt, b) == self.fork_point(bd, use_overrides=False)))

        candidate_downstreams = list(filter(connected_with_green_edge, self.down_branches[b]))
        if not candidate_downstreams:
            raise MacheteException(f"No downstream (child) branch of `{b}` is connected to `{b}` with a green edge")
        if len(candidate_downstreams) > 1:
            if self.cli_ctxt.opt_yes:
                raise MacheteException(
                    f"More than one downstream (child) branch of `{b}` is connected to `{b}` with a green edge "
                    "and `-y/--yes` option is specified")
            else:
                d = pick(candidate_downstreams, f"downstream branch towards which `{b}` is to be fast-forwarded")
                merge_fast_forward_only(self.cli_ctxt, d)
        else:
            d = candidate_downstreams[0]
            ans = ask_if(
                self.cli_ctxt,
                f"Fast-forward {bold(b)} to match {bold(d)}?" + pretty_choices('y', 'N'),
                f"Fast-forwarding {bold(b)} to match {bold(d)}..."
            )
            if ans in ('y', 'yes'):
                merge_fast_forward_only(self.cli_ctxt, d)
            else:
                return

        ans = ask_if(
            self.cli_ctxt,
            f"\nBranch {bold(d)} is now merged into {bold(b)}. Slide {bold(d)} out of the tree of branch dependencies?" + pretty_choices(
                'y', 'N'),
            f"\nBranch {bold(d)} is now merged into {bold(b)}. Sliding {bold(d)} out of the tree of branch dependencies..."
        )
        if ans in ('y', 'yes'):
            dds = self.down_branches.get(d, [])
            for dd in dds:
                self.up_branch[dd] = b
            self.down_branches[b] = flat_map(
                lambda bd: dds if bd == d else [bd],
                self.down_branches[b])
            self.save_definition_file()
            self.run_post_slide_out_hook(b, d, dds)

    def traverse(self) -> None:

        self.expect_at_least_one_managed_branch()

        self.empty_line_status = True

        def print_new_line(new_status: bool) -> None:
            if not self.empty_line_status:
                print("")
            self.empty_line_status = new_status

        if self.cli_ctxt.opt_fetch:
            for r in remotes(self.cli_ctxt):
                print(f"Fetching {r}...")
                fetch_remote(self.cli_ctxt, r)
            if remotes(self.cli_ctxt):
                flush_caches()
                print("")

        initial_branch = nearest_remaining_branch = current_branch(self.cli_ctxt)

        if self.cli_ctxt.opt_start_from == "root":
            dest = self.root_branch(current_branch(self.cli_ctxt), if_unmanaged=MacheteClient.PICK_FIRST_ROOT)
            print_new_line(False)
            print(f"Checking out the root branch ({bold(dest)})")
            go(self.cli_ctxt, dest)
            cb = dest
        elif self.cli_ctxt.opt_start_from == "first-root":
            # Note that we already ensured that there is at least one managed branch.
            dest = self.managed_branches[0]
            print_new_line(False)
            print(f"Checking out the first root branch ({bold(dest)})")
            go(self.cli_ctxt, dest)
            cb = dest
        else:  # cli_ctxt.opt_start_from == "here"
            cb = current_branch(self.cli_ctxt)
            self.expect_in_managed_branches(cb)

        b: str
        for b in itertools.dropwhile(lambda x: x != cb, self.managed_branches):
            u = self.up_branch.get(b)

            needs_slide_out: bool = self.is_merged_to_upstream(b)
            s, remote = get_strict_remote_sync_status(self.cli_ctxt, b)
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
            elif self.cli_ctxt.opt_merge:
                needs_parent_sync = bool(u and not is_ancestor_or_equal(self.cli_ctxt, u, b))
            else:  # using rebase
                needs_parent_sync = bool(u and not (
                                         is_ancestor_or_equal(self.cli_ctxt, u, b) and commit_sha_by_revision(self.cli_ctxt, u) == self.fork_point(b, use_overrides=True)))

            if b != cb and (needs_slide_out or needs_parent_sync or needs_remote_sync):
                print_new_line(False)
                sys.stdout.write(f"Checking out {bold(b)}\n")
                go(self.cli_ctxt, b)
                cb = b
                print_new_line(False)
                self.status(warn_on_yellow_edges=True)
                print_new_line(True)
            if needs_slide_out:
                print_new_line(False)
                ans: str = ask_if(
                    self.cli_ctxt,
                    f"Branch {bold(b)} is merged into {bold(u)}. Slide {bold(b)} out of the tree of branch dependencies?" + pretty_choices(
                        'y', 'N', 'q', 'yq'),
                    f"Branch {bold(b)} is merged into {bold(u)}. Sliding {bold(b)} out of the tree of branch dependencies..."
                )
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
                    if b in self.annotations:
                        del self.annotations[b]
                    self.save_definition_file()
                    self.run_post_slide_out_hook(u, b, self.down_branches.get(b) or [])
                    if ans == 'yq':
                        return
                    # No need to flush caches since nothing changed in commit/branch structure (only machete-specific changes happened).
                    continue  # No need to sync branch 'b' with remote since it just got removed from the tree of dependencies.
                elif ans in ('q', 'quit'):
                    return
                # If user answered 'no', we don't try to rebase/merge but still suggest to sync with remote (if needed; very rare in practice).
            elif needs_parent_sync:
                print_new_line(False)
                if self.cli_ctxt.opt_merge:
                    ans = ask_if(
                        self.cli_ctxt,
                        f"Merge {bold(u)} into {bold(b)}?" + pretty_choices('y', 'N', 'q', 'yq'),
                        f"Merging {bold(u)} into {bold(b)}..."
                    )
                else:
                    ans = ask_if(
                        self.cli_ctxt,
                        f"Rebase {bold(b)} onto {bold(u)}?" + pretty_choices('y', 'N', 'q', 'yq'),
                        f"Rebasing {bold(b)} onto {bold(u)}..."
                    )
                if ans in ('y', 'yes', 'yq'):
                    if self.cli_ctxt.opt_merge:
                        merge(self.cli_ctxt, u, b)
                        # It's clearly possible that merge can be in progress after 'git merge' returned non-zero exit code;
                        # this happens most commonly in case of conflicts.
                        # As for now, we're not aware of any case when merge can be still in progress after 'git merge' returns zero,
                        # at least not with the options that git-machete passes to merge; this happens though in case of 'git merge --no-commit' (which we don't ever invoke).
                        # It's still better, however, to be on the safe side.
                        if is_merge_in_progress(self.cli_ctxt):
                            sys.stdout.write("\nMerge in progress; stopping the traversal\n")
                            return
                    else:
                        rebase(self.cli_ctxt, f"refs/heads/{u}", self.fork_point(b, use_overrides=True), b)
                        # It's clearly possible that rebase can be in progress after 'git rebase' returned non-zero exit code;
                        # this happens most commonly in case of conflicts, regardless of whether the rebase is interactive or not.
                        # But for interactive rebases, it's still possible that even if 'git rebase' returned zero,
                        # the rebase is still in progress; e.g. when interactive rebase gets to 'edit' command, it will exit returning zero,
                        # but the rebase will be still in progress, waiting for user edits and a subsequent 'git rebase --continue'.
                        rb = currently_rebased_branch_or_none(self.cli_ctxt)
                        if rb:  # 'rb' should be equal to 'b' at this point anyway
                            sys.stdout.write(fmt(f"\nRebase of `{rb}` in progress; stopping the traversal\n"))
                            return
                    if ans == 'yq':
                        return

                    flush_caches()
                    s, remote = get_strict_remote_sync_status(self.cli_ctxt, b)
                    needs_remote_sync = s in statuses_to_sync
                elif ans in ('q', 'quit'):
                    return

            if needs_remote_sync:
                if s == BEHIND_REMOTE:
                    rb = strict_counterpart_for_fetching_of_branch(self.cli_ctxt, b)
                    ans = ask_if(
                        self.cli_ctxt,
                        f"Branch {bold(b)} is behind its remote counterpart {bold(rb)}.\n"
                        f"Pull {bold(b)} (fast-forward only) from {bold(remote)}?" + pretty_choices('y', 'N', 'q',
                                                                                                    'yq'),
                        f"Branch {bold(b)} is behind its remote counterpart {bold(rb)}.\n"
                        f"Pulling {bold(b)} (fast-forward only) from {bold(remote)}..."
                    )
                    if ans in ('y', 'yes', 'yq'):
                        pull_ff_only(self.cli_ctxt, remote, rb)
                        if ans == 'yq':
                            return
                        flush_caches()
                        print("")
                    elif ans in ('q', 'quit'):
                        return

                elif s == AHEAD_OF_REMOTE:
                    print_new_line(False)
                    ans = ask_if(
                        self.cli_ctxt,
                        f"Push {bold(b)} to {bold(remote)}?" + pretty_choices('y', 'N', 'q', 'yq'),
                        f"Pushing {bold(b)} to {bold(remote)}...",
                        override_answer=None if self.cli_ctxt.opt_push_tracked else "N"
                    )
                    if ans in ('y', 'yes', 'yq'):
                        push(self.cli_ctxt, remote, b)
                        if ans == 'yq':
                            return
                        flush_caches()
                    elif ans in ('q', 'quit'):
                        return

                elif s == DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                    print_new_line(False)
                    rb = strict_counterpart_for_fetching_of_branch(self.cli_ctxt, b)
                    ans = ask_if(
                        self.cli_ctxt,
                        f"Branch {bold(b)} diverged from (and has older commits than) its remote counterpart {bold(rb)}.\n"
                        f"Reset branch {bold(b)} to the commit pointed by {bold(rb)}?" + pretty_choices('y', 'N', 'q',
                                                                                                        'yq'),
                        f"Branch {bold(b)} diverged from (and has older commits than) its remote counterpart {bold(rb)}.\n"
                        f"Resetting branch {bold(b)} to the commit pointed by {bold(rb)}..."
                    )
                    if ans in ('y', 'yes', 'yq'):
                        reset_keep(self.cli_ctxt, rb)
                        if ans == 'yq':
                            return
                        flush_caches()
                    elif ans in ('q', 'quit'):
                        return

                elif s == DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                    print_new_line(False)
                    rb = strict_counterpart_for_fetching_of_branch(self.cli_ctxt, b)
                    ans = ask_if(
                        self.cli_ctxt,
                        f"Branch {bold(b)} diverged from (and has newer commits than) its remote counterpart {bold(rb)}.\n"
                        f"Push {bold(b)} with force-with-lease to {bold(remote)}?" + pretty_choices('y', 'N', 'q', 'yq'),
                        f"Branch {bold(b)} diverged from (and has newer commits than) its remote counterpart {bold(rb)}.\n"
                        f"Pushing {bold(b)} with force-with-lease to {bold(remote)}...",
                        override_answer=None if self.cli_ctxt.opt_push_tracked else "N"
                    )
                    if ans in ('y', 'yes', 'yq'):
                        push(self.cli_ctxt, remote, b, force_with_lease=True)
                        if ans == 'yq':
                            return
                        flush_caches()
                    elif ans in ('q', 'quit'):
                        return

                elif s == UNTRACKED:
                    rems: List[str] = remotes(self.cli_ctxt)
                    rmt: Optional[str] = inferred_remote_for_fetching_of_branch(self.cli_ctxt, b)
                    print_new_line(False)
                    if rmt:
                        handle_untracked_branch(self.cli_ctxt, rmt, b)
                    elif len(rems) == 1:
                        handle_untracked_branch(self.cli_ctxt, rems[0], b)
                    elif "origin" in rems:
                        handle_untracked_branch(self.cli_ctxt, "origin", b)
                    else:
                        # We know that there is at least 1 remote, otherwise 's' would be 'NO_REMOTES'
                        print(fmt(f"Branch `{bold(b)}` is untracked and there's no `{bold('origin')}` repository."))
                        pick_remote(self.cli_ctxt, b)

        if self.cli_ctxt.opt_return_to == "here":
            go(self.cli_ctxt, initial_branch)
        elif self.cli_ctxt.opt_return_to == "nearest-remaining":
            go(self.cli_ctxt, nearest_remaining_branch)
        # otherwise cli_ctxt.opt_return_to == "stay", so no action is needed

        print_new_line(False)
        self.status(warn_on_yellow_edges=True)
        print("")
        if cb == self.managed_branches[-1]:
            msg: str = f"Reached branch {bold(cb)} which has no successor"
        else:
            msg = f"No successor of {bold(cb)} needs to be slid out or synced with upstream branch or remote"
        sys.stdout.write(f"{msg}; nothing left to update\n")

        if self.cli_ctxt.opt_return_to == "here" or (
                self.cli_ctxt.opt_return_to == "nearest-remaining" and nearest_remaining_branch == initial_branch):
            print(f"Returned to the initial branch {bold(initial_branch)}")
        elif self.cli_ctxt.opt_return_to == "nearest-remaining" and nearest_remaining_branch != initial_branch:
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

        for u in self.roots:
            prefix_dfs(u, accumulated_path=[])

        out = io.StringIO()
        edge_color: Dict[str, str] = {}
        fp_sha_cached: Dict[str, Optional[str]] = {}  # TODO (#110): default dict with None
        fp_branches_cached: Dict[str, List[BRANCH_DEF]] = {}

        def fp_sha(b: str) -> Optional[str]:
            if b not in fp_sha_cached:
                try:
                    # We're always using fork point overrides, even when status is launched from discover().
                    fp_sha_cached[b], fp_branches_cached[b] = self.fork_point_and_containing_branch_defs(b, use_overrides=True)
                except MacheteException:
                    fp_sha_cached[b], fp_branches_cached[b] = None, []
            return fp_sha_cached[b]

        # Edge colors need to be precomputed
        # in order to render the leading parts of lines properly.
        for b in self.up_branch:
            u = self.up_branch[b]
            if is_merged_to(self, self.cli_ctxt, b, u):
                edge_color[b] = DIM
            elif not is_ancestor_or_equal(self.cli_ctxt, u, b):
                edge_color[b] = RED
            elif self.get_overridden_fork_point(b) or commit_sha_by_revision(self.cli_ctxt, u) == fp_sha(b):
                edge_color[b] = GREEN
            else:
                edge_color[b] = YELLOW

        crb = currently_rebased_branch_or_none(self.cli_ctxt)
        ccob = currently_checked_out_branch_or_none(self.cli_ctxt)

        hook_path = get_hook_path(self.cli_ctxt, "machete-status-branch")
        hook_executable = check_hook_executable(self.cli_ctxt, hook_path)

        def print_line_prefix(b_: str, suffix: str) -> None:
            out.write("  ")
            for p in accumulated_path[:-1]:
                if not p:
                    out.write("  ")
                else:
                    out.write(colored(f"{vertical_bar()} ", edge_color[p]))
            out.write(colored(suffix, edge_color[b_]))

        for b, accumulated_path in dfs_res:
            if b in self.up_branch:
                print_line_prefix(b, f"{vertical_bar()} \n")
                if self.cli_ctxt.opt_list_commits:
                    if edge_color[b] in (RED, DIM):
                        commits: List[Hash_ShortHash_Message] = commits_between(self.cli_ctxt, fp_sha(b),
                                                                                f"refs/heads/{b}") if fp_sha(b) else []
                    elif edge_color[b] == YELLOW:
                        commits = commits_between(self.cli_ctxt, f"refs/heads/{self.up_branch[b]}", f"refs/heads/{b}")
                    else:  # edge_color == GREEN
                        commits = commits_between(self.cli_ctxt, fp_sha(b), f"refs/heads/{b}")

                    for sha, short_sha, subject in commits:
                        if sha == fp_sha(b):
                            # fp_branches_cached will already be there thanks to the above call to 'fp_sha'.
                            fp_branches_formatted: str = " and ".join(
                                sorted(underline(lb_or_rb) for lb, lb_or_rb in fp_branches_cached[b]))
                            fp_suffix: str = " %s %s %s seems to be a part of the unique history of %s" % \
                                             (colored(right_arrow(), RED), colored("fork point ???", RED),
                                              "this commit" if self.cli_ctxt.opt_list_commits_with_hashes else f"commit {short_sha}",
                                              fp_branches_formatted)
                        else:
                            fp_suffix = ''
                        print_line_prefix(b, vertical_bar())
                        out.write(" %s%s%s\n" % (
                                  f"{dim(short_sha)}  " if self.cli_ctxt.opt_list_commits_with_hashes else "", dim(subject),
                                  fp_suffix))
                elbow_ascii_only: Dict[str, str] = {DIM: "m-", RED: "x-", GREEN: "o-", YELLOW: "?-"}
                elbow: str = u"└─" if not ascii_only else elbow_ascii_only[edge_color[b]]
                print_line_prefix(b, elbow)
            else:
                if b != dfs_res[0][0]:
                    out.write("\n")
                out.write("  ")

            if b in (ccob, crb):  # i.e. if b is the current branch (checked out or being rebased)
                if b == crb:
                    prefix = "REBASING "
                elif is_am_in_progress(self.cli_ctxt):
                    prefix = "GIT AM IN PROGRESS "
                elif is_cherry_pick_in_progress(self.cli_ctxt):
                    prefix = "CHERRY-PICKING "
                elif is_merge_in_progress(self.cli_ctxt):
                    prefix = "MERGING "
                elif is_revert_in_progress(self.cli_ctxt):
                    prefix = "REVERTING "
                else:
                    prefix = ""
                current = "%s%s" % (bold(colored(prefix, RED)), bold(underline(b, star_if_ascii_only=True)))
            else:
                current = bold(b)

            anno: str = f"  {dim(self.annotations[b])}" if b in self.annotations else ""

            s, remote = get_combined_remote_sync_status(self.cli_ctxt, b)
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
                debug(self.cli_ctxt, "status()", f"running machete-status-branch hook ({hook_path}) for branch {b}")
                hook_env = dict(os.environ, ASCII_ONLY=str(ascii_only).lower())
                status_code, stdout, stderr = popen_cmd(self.cli_ctxt, hook_path, b, cwd=get_root_dir(self.cli_ctxt),
                                                        env=hook_env)
                if status_code == 0:
                    if not stdout.isspace():
                        hook_output = f"  {stdout.rstrip()}"
                else:
                    debug(self.cli_ctxt,
                          "status()",
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

            if not self.cli_ctxt.opt_list_commits:
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
        branches_to_delete = excluding(local_branches(self.cli_ctxt), self.managed_branches)
        cb = current_branch_or_none(self.cli_ctxt)
        if cb and cb in branches_to_delete:
            branches_to_delete = excluding(branches_to_delete, [cb])
            print(fmt(f"Skipping current branch `{cb}`"))
        if branches_to_delete:
            branches_merged_to_head = merged_local_branches(self.cli_ctxt)

            branches_to_delete_merged_to_head = [b for b in branches_to_delete if b in branches_merged_to_head]
            for b in branches_to_delete_merged_to_head:
                rb = strict_counterpart_for_fetching_of_branch(self.cli_ctxt, b)
                is_merged_to_remote = is_ancestor_or_equal(self.cli_ctxt, b, rb,
                                                           later_prefix="refs/remotes/") if rb else True
                msg_core = f"{bold(b)} (merged to HEAD{'' if is_merged_to_remote else f', but not merged to {rb}'})"
                msg = f"Delete branch {msg_core}?" + pretty_choices('y', 'N', 'q')
                opt_yes_msg = f"Deleting branch {msg_core}"
                ans = ask_if(self.cli_ctxt, msg, opt_yes_msg)
                if ans in ('y', 'yes'):
                    run_git(self.cli_ctxt, "branch", "-d" if is_merged_to_remote else "-D", b)
                elif ans in ('q', 'quit'):
                    return

            branches_to_delete_unmerged_to_head = [b for b in branches_to_delete if b not in branches_merged_to_head]
            for b in branches_to_delete_unmerged_to_head:
                msg_core = f"{bold(b)} (unmerged to HEAD)"
                msg = f"Delete branch {msg_core}?" + pretty_choices('y', 'N', 'q')
                opt_yes_msg = f"Deleting branch {msg_core}"
                ans = ask_if(self.cli_ctxt, msg, opt_yes_msg)
                if ans in ('y', 'yes'):
                    run_git(self.cli_ctxt, "branch", "-D", b)
                elif ans in ('q', 'quit'):
                    return
        else:
            print("No branches to delete")

    def edit(self) -> int:
        default_editor_name: Optional[str] = get_default_editor(self.cli_ctxt)
        if default_editor_name is None:
            raise MacheteException(f"Cannot determine editor. Set `GIT_MACHETE_EDITOR` environment variable or edit {self.definition_file_path} directly.")
        return run_cmd(self.cli_ctxt, default_editor_name, self.definition_file_path)

    def fork_point_and_containing_branch_defs(self, b: str, use_overrides: bool) -> Tuple[Optional[str], List[BRANCH_DEF]]:
        u = self.up_branch.get(b)

        if self.is_merged_to_upstream(b):
            fp_sha = commit_sha_by_revision(self.cli_ctxt, b)
            debug(self.cli_ctxt, f"fork_point_and_containing_branch_defs({b})",
                  f"{b} is merged to {u}; skipping inference, using tip of {b} ({fp_sha}) as fork point")
            return fp_sha, []

        if use_overrides:
            overridden_fp_sha = self.get_overridden_fork_point(b)
            if overridden_fp_sha:
                if u and is_ancestor_or_equal(self.cli_ctxt, u, b) and not is_ancestor_or_equal(self.cli_ctxt,
                                                                                                u,
                                                                                                overridden_fp_sha,
                                                                                                later_prefix=""):
                    # We need to handle the case when b is a descendant of u,
                    # but the fork point of b is overridden to a commit that is NOT a descendant of u.
                    # In this case it's more reasonable to assume that u (and not overridden_fp_sha) is the fork point.
                    debug(self.cli_ctxt, f"fork_point_and_containing_branch_defs({b})",
                          f"{b} is descendant of its upstream {u}, but overridden fork point commit {overridden_fp_sha} is NOT a descendant of {u}; falling back to {u} as fork point")
                    return commit_sha_by_revision(self.cli_ctxt, u), []
                else:
                    debug(self.cli_ctxt, f"fork_point_and_containing_branch_defs({b})",
                          f"fork point of {b} is overridden to {overridden_fp_sha}; skipping inference")
                    return overridden_fp_sha, []

        try:
            fp_sha, containing_branch_defs = next(self.match_log_to_filtered_reflogs(b))
        except StopIteration:
            if u and is_ancestor_or_equal(self.cli_ctxt, u, b):
                debug(self.cli_ctxt, f"fork_point_and_containing_branch_defs({b})",
                      f"cannot find fork point, but {b} is descendant of its upstream {u}; falling back to {u} as fork point")
                return commit_sha_by_revision(self.cli_ctxt, u), []
            else:
                raise MacheteException(f"Cannot find fork point for branch `{b}`")
        else:
            debug(self.cli_ctxt,
                  "fork_point_and_containing_branch_defs({b})",
                  f"commit {fp_sha} is the most recent point in history of {b} to occur on "
                  "filtered reflog of any other branch or its remote counterpart "
                  f"(specifically: {' and '.join(map(get_second, containing_branch_defs))})")

            if u and is_ancestor_or_equal(self.cli_ctxt, u, b) and not is_ancestor_or_equal(self.cli_ctxt, u, fp_sha,
                                                                                            later_prefix=""):
                # That happens very rarely in practice (typically current head of any branch, including u, should occur on the reflog of this
                # branch, thus is_ancestor(u, b) should imply is_ancestor(u, FP(b)), but it's still possible in case reflog of
                # u is incomplete for whatever reason.
                debug(self.cli_ctxt,
                      f"fork_point_and_containing_branch_defs({b})",
                      f"{u} is descendant of its upstream {b}, but inferred fork point commit {fp_sha} is NOT a descendant of {u}; falling back to {u} as fork point")
                return commit_sha_by_revision(self.cli_ctxt, u), []
            else:
                debug(self.cli_ctxt,
                      f"fork_point_and_containing_branch_defs({b})",
                      f"choosing commit {fp_sha} as fork point")
                return fp_sha, containing_branch_defs

    def fork_point(self, b: str, use_overrides: bool) -> Optional[str]:
        sha, containing_branch_defs = self.fork_point_and_containing_branch_defs(b, use_overrides)
        return sha

    def diff(self, branch: Optional[str]) -> None:
        fp: str = self.fork_point(branch if branch else current_branch(self.cli_ctxt), use_overrides=True)
        params = \
            (["--stat"] if self.cli_ctxt.opt_stat else []) + \
            [fp] + \
            ([f"refs/heads/{branch}"] if branch else []) + \
            ["--"]
        run_git(self.cli_ctxt, "diff", *params)

    def log(self, branch: str) -> None:
        run_git(self.cli_ctxt, "log", "^" + self.fork_point(branch, use_overrides=True), f"refs/heads/{branch}")

    def down(self, b: str, pick_mode: bool) -> str:
        self.expect_in_managed_branches(b)
        dbs = self.down_branches.get(b)
        if not dbs:
            raise MacheteException(f"Branch `{b}` has no downstream branch")
        elif len(dbs) == 1:
            return dbs[0]
        elif pick_mode:
            return pick(dbs, "downstream branch")
        else:
            return "\n".join(dbs)

    def first_branch(self, b: str) -> str:
        root = self.root_branch(b, if_unmanaged=MacheteClient.PICK_FIRST_ROOT)
        root_dbs = self.down_branches.get(root)
        return root_dbs[0] if root_dbs else root

    def last_branch(self, b: str) -> str:
        destination = self.root_branch(b, if_unmanaged=MacheteClient.PICK_LAST_ROOT)
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
            if self.roots:
                if if_unmanaged == MacheteClient.PICK_FIRST_ROOT:
                    warn(
                        f"{b} is not a managed branch, assuming {self.roots[0]} (the first root) instead as root")
                    return self.roots[0]
                else:  # if_unmanaged == MacheteContext.PICK_LAST_ROOT
                    warn(
                        f"{b} is not a managed branch, assuming {self.roots[-1]} (the last root) instead as root")
                    return self.roots[-1]
            else:
                self.raise_no_branches_error()
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
            u = self.infer_upstream(b)
            if u:
                if prompt_if_inferred_msg:
                    if ask_if(
                            self.cli_ctxt,
                            prompt_if_inferred_msg % (b, u),
                            prompt_if_inferred_yes_opt_msg % (b, u)
                    ) in ('y', 'yes'):
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

    def is_merged_to_upstream(self, b: str) -> bool:
        if b not in self.up_branch:
            return False
        return is_merged_to(self, self.cli_ctxt, b, self.up_branch[b])

    def run_post_slide_out_hook(self, new_upstream: str, slid_out_branch: str,
                                new_downstreams: List[str]) -> None:
        hook_path = get_hook_path(self.cli_ctxt, "machete-post-slide-out")
        if check_hook_executable(self.cli_ctxt, hook_path):
            debug(self.cli_ctxt,
                  f"run_post_slide_out_hook({new_upstream}, {slid_out_branch}, {new_downstreams})",
                  f"running machete-post-slide-out hook ({hook_path})")
            exit_code = run_cmd(self.cli_ctxt, hook_path, new_upstream, slid_out_branch, *new_downstreams,
                                cwd=get_root_dir(self.cli_ctxt))
            if exit_code != 0:
                sys.stderr.write(f"The machete-post-slide-out hook exited with {exit_code}, aborting.\n")
                sys.exit(exit_code)

    def squash(self, cb: str, fork_commit: str) -> None:
        commits: List[Hash_ShortHash_Message] = commits_between(self.cli_ctxt, fork_commit, cb)
        if not commits:
            raise MacheteException(
                "No commits to squash. Use `-f` or `--fork-point` to specify the start of range of commits to squash.")
        if len(commits) == 1:
            sha, short_sha, subject = commits[0]
            print(f"Exactly one commit ({short_sha}) to squash, ignoring.\n")
            print("Tip: use `-f` or `--fork-point` to specify where the range of commits to squash starts.")
            return

        earliest_sha, earliest_short_sha, earliest_subject = commits[0]
        earliest_full_body = popen_git(self.cli_ctxt, "log", "-1", "--format=%B", earliest_sha).strip()
        # %ai for ISO-8601 format; %aE/%aN for respecting .mailmap; see `git rev-list --help`
        earliest_author_date = popen_git(self.cli_ctxt, "log", "-1", "--format=%ai", earliest_sha).strip()
        earliest_author_email = popen_git(self.cli_ctxt, "log", "-1", "--format=%aE", earliest_sha).strip()
        earliest_author_name = popen_git(self.cli_ctxt, "log", "-1", "--format=%aN", earliest_sha).strip()

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
        squashed_sha = popen_git(self.cli_ctxt, "commit-tree", "HEAD^{tree}", "-p", fork_commit, "-m", earliest_full_body,
                                 env=author_env).strip()

        # This can't be done with `git reset` since it doesn't allow for a custom reflog message.
        # Even worse, reset's reflog message would be filtered out in our fork point algorithm,
        # so the squashed commit would not even be considered to "belong"
        # (in the FP sense) to the current branch's history.
        run_git(self.cli_ctxt, "update-ref", "HEAD", squashed_sha, "-m", f"squash: {earliest_subject}")

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
                debug(self.cli_ctxt, f"filtered_reflog({b}, {prefix}) -> is_excluded_reflog_subject({sha_}, <<<{gs_}>>>)",
                      "skipping reflog entry")
            return is_excluded

        b_reflog = reflog(self.cli_ctxt, prefix + b)
        if not b_reflog:
            return []

        earliest_sha, earliest_gs = b_reflog[-1]  # Note that the reflog is returned from latest to earliest entries.
        shas_to_exclude = set()
        if earliest_gs.startswith("branch: Created from"):
            debug(self.cli_ctxt,
                  f"filtered_reflog({b}, {prefix})",
                  f"skipping any reflog entry with the hash equal to the hash of the earliest (branch creation) entry: {earliest_sha}")
            shas_to_exclude.add(earliest_sha)

        result = [sha for (sha, gs) in b_reflog if
                  sha not in shas_to_exclude and not is_excluded_reflog_subject(sha, gs)]
        debug(self.cli_ctxt,
              f"filtered_reflog({b}, {prefix})",
              "computed filtered reflog (= reflog without branch creation "
              "and branch reset events irrelevant for fork point/upstream inference): %s\n" % (", ".join(result) or "<empty>"))
        return result

    def sync_annotations_to_github_prs(self) -> None:
        from git_machete.github import derive_current_user_login, derive_pull_requests, GitHubPullRequest, \
            parse_github_remote_url

        url_for_remote: Dict[str, str] = {r: get_url_of_remote(self.cli_ctxt, r) for r in
                                          remotes(self.cli_ctxt)}
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
        debug(self.cli_ctxt, 'sync_annotations_to_github_prs()',
              'Current GitHub user is ' + (current_user or '<none>'))
        pr: GitHubPullRequest
        for pr in derive_pull_requests(org, repo):
            if pr.head in self.managed_branches:
                debug(self.cli_ctxt, 'sync_annotations_to_github_prs()',
                      f'{pr} corresponds to a managed branch')
                anno: str = f'PR #{pr.number}'
                if pr.user != current_user:
                    anno += f' ({pr.user})'
                u: Optional[str] = self.up_branch.get(pr.head)
                if pr.base != u:
                    warn(f'branch `{pr.head}` has a different base in PR #{pr.number} (`{pr.base}`) '
                         f'than in machete file (`{u or "<none, is a root>"}`)')
                    anno += f" WRONG PR BASE or MACHETE PARENT? PR has '{pr.base}'"
                if self.annotations.get(pr.head) != anno:
                    print(fmt(f'Annotating <b>{pr.head}</b> as `{anno}`'))
                    self.annotations[pr.head] = anno
            else:
                debug(self.cli_ctxt, 'sync_annotations_to_github_prs()',
                      f'{pr} does NOT correspond to a managed branch')
        self.save_definition_file()

    # Parse and evaluate direction against current branch for show/go commands
    def parse_direction(self, param: str, b: str, allow_current: bool, down_pick_mode: bool) -> str:
        if param in ("c", "current") and allow_current:
            return current_branch(self.cli_ctxt)  # throws in case of detached HEAD, as in the spec
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
            return self.root_branch(b, if_unmanaged=MacheteClient.PICK_FIRST_ROOT)
        elif param in ("u", "up"):
            return self.up(b, prompt_if_inferred_msg=None, prompt_if_inferred_yes_opt_msg=None)
        else:
            raise MacheteException(f"Invalid direction: `{param}` expected: {allowed_directions(allow_current)}")

    def match_log_to_filtered_reflogs(self, b: str) -> Generator[Tuple[str, List[BRANCH_DEF]], None, None]:

        if b not in local_branches(self.cli_ctxt):
            raise MacheteException(f"`{b}` is not a local branch")

        if self.branch_defs_by_sha_in_reflog is None:
            def generate_entries() -> Generator[Tuple[str, BRANCH_DEF], None, None]:
                for lb in local_branches(self.cli_ctxt):
                    lb_shas = set()
                    for sha_ in self.filtered_reflog(lb, prefix="refs/heads/"):
                        lb_shas.add(sha_)
                        yield sha_, (lb, lb)
                    rb = combined_counterpart_for_fetching_of_branch(self.cli_ctxt, lb)
                    if rb:
                        for sha_ in self.filtered_reflog(rb, prefix="refs/remotes/"):
                            if sha_ not in lb_shas:
                                yield sha_, (lb, rb)

            self.branch_defs_by_sha_in_reflog = {}
            for sha, branch_def in generate_entries():
                if sha in self.branch_defs_by_sha_in_reflog:
                    # The practice shows that it's rather unlikely for a given commit to appear on filtered reflogs of two unrelated branches
                    # ("unrelated" as in, not a local branch and its remote counterpart) but we need to handle this case anyway.
                    self.branch_defs_by_sha_in_reflog[sha] += [branch_def]
                else:
                    self.branch_defs_by_sha_in_reflog[sha] = [branch_def]

            def log_result() -> Generator[str, None, None]:
                branch_defs: List[BRANCH_DEF]
                sha_: str
                for sha_, branch_defs in self.branch_defs_by_sha_in_reflog.items():
                    def branch_def_to_str(lb: str, lb_or_rb: str) -> str:
                        return lb if lb == lb_or_rb else f"{lb_or_rb} (remote counterpart of {lb})"

                    joined_branch_defs = ", ".join(map(tupled(branch_def_to_str), branch_defs))
                    yield dim(f"{sha_} => {joined_branch_defs}")

            debug(self.cli_ctxt, f"match_log_to_filtered_reflogs({b})",
                  "branches containing the given SHA in their filtered reflog: \n%s\n" % "\n".join(log_result()))

        for sha in spoonfeed_log_shas(self.cli_ctxt, b):
            if sha in self.branch_defs_by_sha_in_reflog:
                # The entries must be sorted by lb_or_rb to make sure the upstream inference is deterministic
                # (and does not depend on the order in which `generate_entries` iterated through the local branches).
                branch_defs: List[BRANCH_DEF] = self.branch_defs_by_sha_in_reflog[sha]

                def lb_is_not_b(lb: str, lb_or_rb: str) -> bool:
                    return lb != b

                containing_branch_defs = sorted(filter(tupled(lb_is_not_b), branch_defs), key=get_second)
                if containing_branch_defs:
                    debug(self.cli_ctxt,
                          f"match_log_to_filtered_reflogs({b})",
                          f"commit {sha} found in filtered reflog of {' and '.join(map(get_second, branch_defs))}")
                    yield sha, containing_branch_defs
                else:
                    debug(self.cli_ctxt,
                          f"match_log_to_filtered_reflogs({b})",
                          f"commit {sha} found only in filtered reflog of {' and '.join(map(get_second, branch_defs))}; ignoring")
            else:
                debug(self.cli_ctxt, f"match_log_to_filtered_reflogs({b})", f"commit {sha} not found in any filtered reflog")

    def infer_upstream(self, b: str, condition: Callable[[str], bool] = lambda u: True, reject_reason_message: str = "") -> Optional[str]:
        for sha, containing_branch_defs in self.match_log_to_filtered_reflogs(b):
            debug(self.cli_ctxt,
                  f"infer_upstream({b})",
                  f"commit {sha} found in filtered reflog of {' and '.join(map(get_second, containing_branch_defs))}")

            for candidate, original_matched_branch in containing_branch_defs:
                if candidate != original_matched_branch:
                    debug(self.cli_ctxt,
                          f"infer_upstream({b})",
                          f"upstream candidate is {candidate}, which is the local counterpart of {original_matched_branch}")

                if condition(candidate):
                    debug(self.cli_ctxt, f"infer_upstream({b})", f"upstream candidate {candidate} accepted")
                    return candidate
                else:
                    debug(self.cli_ctxt, f"infer_upstream({b})",
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
        return (get_config_or_none(self.cli_ctxt, self.config_key_for_override_fork_point_to(b)) or
                get_config_or_none(self.cli_ctxt, self.config_key_for_override_fork_point_while_descendant_of(b))) is not None

    def get_fork_point_override_data(self, b: str) -> Optional[Tuple[str, str]]:
        to_key = self.config_key_for_override_fork_point_to(b)
        to = get_config_or_none(self.cli_ctxt, to_key)
        while_descendant_of_key = self.config_key_for_override_fork_point_while_descendant_of(b)
        while_descendant_of = get_config_or_none(self.cli_ctxt, while_descendant_of_key)
        if not to and not while_descendant_of:
            return None
        if to and not while_descendant_of:
            warn(f"{to_key} config is set but {while_descendant_of_key} config is missing")
            return None
        if not to and while_descendant_of:
            warn(f"{while_descendant_of_key} config is set but {to_key} config is missing")
            return None

        to_sha: Optional[str] = commit_sha_by_revision(self.cli_ctxt, to, prefix="")
        while_descendant_of_sha: Optional[str] = commit_sha_by_revision(self.cli_ctxt, while_descendant_of, prefix="")
        if not to_sha or not while_descendant_of_sha:
            if not to_sha:
                warn(f"{to_key} config value `{to}` does not point to a valid commit")
            if not while_descendant_of_sha:
                warn(f"{while_descendant_of_key} config value `{while_descendant_of}` does not point to a valid commit")
            return None
        # This check needs to be performed every time the config is retrieved.
        # We can't rely on the values being validated in set_fork_point_override(), since the config could have been modified outside of git-machete.
        if not is_ancestor_or_equal(self.cli_ctxt, to_sha, while_descendant_of_sha, earlier_prefix="", later_prefix=""):
            warn(
                f"commit {short_commit_sha_by_revision(self.cli_ctxt, to)} pointed by {to_key} config "
                f"is not an ancestor of commit {short_commit_sha_by_revision(self.cli_ctxt, while_descendant_of)} "
                f"pointed by {while_descendant_of_key} config")
            return None
        return to_sha, while_descendant_of_sha

    def get_overridden_fork_point(self, b: str) -> Optional[str]:
        override_data = self.get_fork_point_override_data(b)
        if not override_data:
            return None

        to, while_descendant_of = override_data
        # Note that this check is distinct from the is_ancestor check performed in get_fork_point_override_data.
        # While the latter checks the sanity of fork point override configuration,
        # the former checks if the override still applies to wherever the given branch currently points.
        if not is_ancestor_or_equal(self.cli_ctxt, while_descendant_of, b, earlier_prefix=""):
            warn(fmt(
                f"since branch <b>{b}</b> is no longer a descendant of commit {short_commit_sha_by_revision(self.cli_ctxt, while_descendant_of)}, ",
                f"the fork point override to commit {short_commit_sha_by_revision(self.cli_ctxt, to)} no longer applies.\n",
                "Consider running:\n",
                f"  `git machete fork-point --unset-override {b}`\n"))
            return None
        debug(self.cli_ctxt,
              f"get_overridden_fork_point({b})",
              f"since branch {b} is descendant of while_descendant_of={while_descendant_of}, fork point of {b} is overridden to {to}")
        return to

    def unset_fork_point_override(self, b: str) -> None:
        unset_config(self.cli_ctxt, self.config_key_for_override_fork_point_to(b))
        unset_config(self.cli_ctxt, self.config_key_for_override_fork_point_while_descendant_of(b))

    def set_fork_point_override(self, b: str, to_revision: str) -> None:
        if b not in local_branches(self.cli_ctxt):
            raise MacheteException(f"`{b}` is not a local branch")
        to_sha = commit_sha_by_revision(self.cli_ctxt, to_revision, prefix="")
        if not to_sha:
            raise MacheteException(f"Cannot find revision {to_revision}")
        if not is_ancestor_or_equal(self.cli_ctxt, to_sha, b, earlier_prefix=""):
            raise MacheteException(
                f"Cannot override fork point: {get_revision_repr(self.cli_ctxt, to_revision)} is not an ancestor of {b}")

        to_key = self.config_key_for_override_fork_point_to(b)
        set_config(self.cli_ctxt, to_key, to_sha)

        while_descendant_of_key = self.config_key_for_override_fork_point_while_descendant_of(b)
        b_sha = commit_sha_by_revision(self.cli_ctxt, b, prefix="refs/heads/")
        set_config(self.cli_ctxt, while_descendant_of_key, b_sha)

        sys.stdout.write(
            fmt(f"Fork point for <b>{b}</b> is overridden to <b>{get_revision_repr(self.cli_ctxt, to_revision)}</b>.\n",
                f"This applies as long as {b} points to (or is descendant of) its current head (commit {short_commit_sha_by_revision(self.cli_ctxt, b_sha)}).\n\n",
                f"This information is stored under git config keys:\n  * `{to_key}`\n  * `{while_descendant_of_key}`\n\n",
                f"To unset this override, use:\n  `git machete fork-point --unset-override {b}`\n"))


# Allowed parameter values for show/go command
def allowed_directions(allow_current: bool) -> str:
    current = "c[urrent]|" if allow_current else ""
    return current + "d[own]|f[irst]|l[ast]|n[ext]|p[rev]|r[oot]|u[p]"


# Implementation of basic git or git-related commands
def is_executable(path: str) -> bool:
    return os.access(path, os.X_OK)


def find_executable(cli_ctxt: CommandLineContext, executable: str) -> Optional[str]:
    base, ext = os.path.splitext(executable)

    if (sys.platform == 'win32' or os.name == 'os2') and (ext != '.exe'):
        executable = f"{executable}.exe"

    if os.path.isfile(executable):
        return executable

    path = os.environ.get('PATH', os.defpath)
    paths = path.split(os.pathsep)
    for p in paths:
        f = os.path.join(p, executable)
        if os.path.isfile(f) and is_executable(f):
            debug(cli_ctxt, f"find_executable({executable})", f"found {executable} at {f}")
            return f
    return None


def get_default_editor(cli_ctxt: CommandLineContext) -> Optional[str]:
    # Based on the git's own algorithm for identifying the editor.
    # '$GIT_MACHETE_EDITOR', 'editor' (to please Debian-based systems) and 'nano' have been added.
    git_machete_editor_var = "GIT_MACHETE_EDITOR"
    proposed_editor_funs: List[Tuple[str, Callable[[], Optional[str]]]] = [
        ("$" + git_machete_editor_var, lambda: os.environ.get(git_machete_editor_var)),
        ("$GIT_EDITOR", lambda: os.environ.get("GIT_EDITOR")),
        ("git config core.editor", lambda: get_config_or_none(cli_ctxt, "core.editor")),
        ("$VISUAL", lambda: os.environ.get("VISUAL")),
        ("$EDITOR", lambda: os.environ.get("EDITOR")),
        ("editor", lambda: "editor"),
        ("nano", lambda: "nano"),
        ("vi", lambda: "vi"),
    ]

    for name, fun in proposed_editor_funs:
        editor = fun()
        if not editor:
            debug(cli_ctxt, "get_default_editor()", f"'{name}' is undefined")
        else:
            editor_repr = f"'{name}'{(' (' + editor + ')') if editor != name else ''}"
            if not find_executable(cli_ctxt, editor):
                debug(cli_ctxt, "get_default_editor()", f"{editor_repr} is not available")
                if name == "$" + git_machete_editor_var:
                    # In this specific case, when GIT_MACHETE_EDITOR is defined but doesn't point to a valid executable,
                    # it's more reasonable/less confusing to raise an error and exit without opening anything.
                    raise MacheteException(f"<b>{editor_repr}</b> is not available")
            else:
                debug(cli_ctxt, "get_default_editor()", f"{editor_repr} is available")
                if name != "$" + git_machete_editor_var and get_config_or_none(cli_ctxt, 'advice.macheteEditorSelection') != 'false':
                    sample_alternative = 'nano' if editor.startswith('vi') else 'vi'
                    sys.stderr.write(
                        fmt(f"Opening <b>{editor_repr}</b>.\n",
                            f"To override this choice, use <b>{git_machete_editor_var}</b> env var, e.g. `export {git_machete_editor_var}={sample_alternative}`.\n\n",
                            "See `git machete help edit` and `git machete edit --debug` for more details.\n\n"
                            "Use `git config --global advice.macheteEditorSelection false` to suppress this message.\n"))
                return editor

    # This case is extremely unlikely on a modern Unix-like system.
    return None


git_version = None


def get_git_version(cli_ctxt: CommandLineContext) -> Tuple[int, int, int]:
    global git_version
    if not git_version:
        # We need to cut out the x.y.z part and not just take the result of 'git version' as is,
        # because the version string in certain distributions of git (esp. on OS X) has an extra suffix,
        # which is irrelevant for our purpose (checking whether certain git CLI features are available/bugs are fixed).
        raw = re.search(r"\d+.\d+.\d+", popen_git(cli_ctxt, "version")).group(0)
        git_version = tuple(map(int, raw.split(".")))
    return git_version  # type: ignore


root_dir = None


def get_root_dir(cli_ctxt: CommandLineContext) -> str:
    global root_dir
    if not root_dir:
        try:
            root_dir = popen_git(cli_ctxt, "rev-parse", "--show-toplevel").strip()
        except MacheteException:
            raise MacheteException("Not a git repository")
    return root_dir


git_dir = None


def get_git_dir(cli_ctxt: CommandLineContext) -> str:
    global git_dir
    if not git_dir:
        try:
            git_dir = popen_git(cli_ctxt, "rev-parse", "--git-dir").strip()
        except MacheteException:
            raise MacheteException("Not a git repository")
    return git_dir


def get_git_subpath(cli_ctxt: CommandLineContext, *fragments: str) -> str:
    return os.path.join(get_git_dir(cli_ctxt), *fragments)


def parse_git_timespec_to_unix_timestamp(cli_ctxt: CommandLineContext, date: str) -> int:
    try:
        return int(popen_git(cli_ctxt, "rev-parse", "--since=" + date).replace("--max-age=", "").strip())
    except (MacheteException, ValueError):
        raise MacheteException(f"Cannot parse timespec: `{date}`")


config_cached: Optional[Dict[str, str]] = None


def ensure_config_loaded(cli_ctxt: CommandLineContext) -> None:
    global config_cached
    if config_cached is None:
        config_cached = {}
        for config_line in non_empty_lines(popen_git(cli_ctxt, "config", "--list")):
            k_v = config_line.split("=", 1)
            if len(k_v) == 2:
                k, v = k_v
                config_cached[k.lower()] = v


def get_config_or_none(cli_ctxt: CommandLineContext, key: str) -> Optional[str]:
    ensure_config_loaded(cli_ctxt)
    return config_cached.get(key.lower())


def set_config(cli_ctxt: CommandLineContext, key: str, value: str) -> None:
    run_git(cli_ctxt, "config", "--", key, value)
    ensure_config_loaded(cli_ctxt)
    config_cached[key.lower()] = value


def unset_config(cli_ctxt: CommandLineContext, key: str) -> None:
    ensure_config_loaded(cli_ctxt)
    if get_config_or_none(cli_ctxt, key):
        run_git(cli_ctxt, "config", "--unset", key)
        del config_cached[key.lower()]


remotes_cached = None


def remotes(cli_ctxt: CommandLineContext) -> List[str]:
    global remotes_cached
    if remotes_cached is None:
        remotes_cached = non_empty_lines(popen_git(cli_ctxt, "remote"))
    return remotes_cached


def get_url_of_remote(cli_ctxt: CommandLineContext, remote: str) -> str:
    return popen_git(cli_ctxt, "remote", "get-url", "--", remote).strip()


fetch_done_for = set()


def fetch_remote(cli_ctxt: CommandLineContext, remote: str) -> None:
    global fetch_done_for
    if remote not in fetch_done_for:
        run_git(cli_ctxt, "fetch", remote)
        fetch_done_for.add(remote)


def set_upstream_to(cli_ctxt: CommandLineContext, rb: str) -> None:
    run_git(cli_ctxt, "branch", "--set-upstream-to", rb)


def reset_keep(cli_ctxt: CommandLineContext, to_revision: str) -> None:
    try:
        run_git(cli_ctxt, "reset", "--keep", to_revision)
    except MacheteException:
        raise MacheteException(
            f"Cannot perform `git reset --keep {to_revision}`. This is most likely caused by local uncommitted changes.")


def push(cli_ctxt: CommandLineContext, remote: str, b: str, force_with_lease: bool = False) -> None:
    if not force_with_lease:
        opt_force = []
    elif get_git_version(cli_ctxt) >= (1, 8, 5):  # earliest version of git to support 'push --force-with-lease'
        opt_force = ["--force-with-lease"]
    else:
        opt_force = ["--force"]
    args = [remote, b]
    run_git(cli_ctxt, "push", "--set-upstream", *(opt_force + args))


def pull_ff_only(cli_ctxt: CommandLineContext, remote: str, rb: str) -> None:
    fetch_remote(cli_ctxt, remote)
    run_git(cli_ctxt, "merge", "--ff-only", rb)
    # There's apparently no way to set remote automatically when doing 'git pull' (as opposed to 'git push'),
    # so a separate 'git branch --set-upstream-to' is needed.
    set_upstream_to(cli_ctxt, rb)


def find_short_commit_sha_by_revision(cli_ctxt: CommandLineContext, revision: str) -> str:
    return popen_git(cli_ctxt, "rev-parse", "--short", revision + "^{commit}").rstrip()


short_commit_sha_by_revision_cached: Dict[str, str] = {}


def short_commit_sha_by_revision(cli_ctxt: CommandLineContext, revision: str) -> str:
    if revision not in short_commit_sha_by_revision_cached:
        short_commit_sha_by_revision_cached[revision] = find_short_commit_sha_by_revision(cli_ctxt, revision)
    return short_commit_sha_by_revision_cached[revision]


def find_commit_sha_by_revision(cli_ctxt: CommandLineContext, revision: str) -> Optional[str]:
    # Without ^{commit}, 'git rev-parse --verify' will not only accept references to other kinds of objects (like trees and blobs),
    # but just echo the argument (and exit successfully) even if the argument doesn't match anything in the object store.
    try:
        return popen_git(cli_ctxt, "rev-parse", "--verify", "--quiet", revision + "^{commit}").rstrip()
    except MacheteException:
        return None


commit_sha_by_revision_cached: Optional[Dict[str, Optional[str]]] = None  # TODO (#110): default dict with None


def commit_sha_by_revision(cli_ctxt: CommandLineContext, revision: str, prefix: str = "refs/heads/") -> Optional[str]:
    global commit_sha_by_revision_cached
    if commit_sha_by_revision_cached is None:
        load_branches(cli_ctxt)
    full_revision: str = prefix + revision
    if full_revision not in commit_sha_by_revision_cached:
        commit_sha_by_revision_cached[full_revision] = find_commit_sha_by_revision(cli_ctxt, full_revision)
    return commit_sha_by_revision_cached[full_revision]


def find_tree_sha_by_revision(cli_ctxt: CommandLineContext, revision: str) -> Optional[str]:
    try:
        return popen_git(cli_ctxt, "rev-parse", "--verify", "--quiet", revision + "^{tree}").rstrip()
    except MacheteException:
        return None


tree_sha_by_commit_sha_cached: Optional[Dict[str, Optional[str]]] = None  # TODO (#110): default dict with None


def tree_sha_by_commit_sha(cli_ctxt: CommandLineContext, commit_sha: str) -> Optional[str]:
    global tree_sha_by_commit_sha_cached
    if tree_sha_by_commit_sha_cached is None:
        load_branches(cli_ctxt)
    if commit_sha not in tree_sha_by_commit_sha_cached:
        tree_sha_by_commit_sha_cached[commit_sha] = find_tree_sha_by_revision(cli_ctxt, commit_sha)
    return tree_sha_by_commit_sha_cached[commit_sha]


def is_full_sha(revision: str) -> Optional[Match[str]]:
    return re.match("^[0-9a-f]{40}$", revision)


# Resolve a revision identifier to a full sha
def full_sha(cli_ctxt: CommandLineContext, revision: str, prefix: str = "refs/heads/") -> Optional[str]:
    if prefix == "" and is_full_sha(revision):
        return revision
    else:
        return commit_sha_by_revision(cli_ctxt, revision, prefix)


committer_unix_timestamp_by_revision_cached: Optional[Dict[str, int]] = None  # TODO (#110): default dict with 0


def committer_unix_timestamp_by_revision(cli_ctxt: CommandLineContext, revision: str, prefix: str = "refs/heads/") -> int:
    global committer_unix_timestamp_by_revision_cached
    if committer_unix_timestamp_by_revision_cached is None:
        load_branches(cli_ctxt)
    return committer_unix_timestamp_by_revision_cached.get(prefix + revision, 0)


def inferred_remote_for_fetching_of_branch(cli_ctxt: CommandLineContext, b: str) -> Optional[str]:
    # Since many people don't use '--set-upstream' flag of 'push', we try to infer the remote instead.
    for r in remotes(cli_ctxt):
        if f"{r}/{b}" in remote_branches(cli_ctxt):
            return r
    return None


def strict_remote_for_fetching_of_branch(cli_ctxt: CommandLineContext, b: str) -> Optional[str]:
    remote = get_config_or_none(cli_ctxt, f"branch.{b}.remote")
    return remote.rstrip() if remote else None


def combined_remote_for_fetching_of_branch(cli_ctxt: CommandLineContext, b: str) -> Optional[str]:
    return strict_remote_for_fetching_of_branch(cli_ctxt, b) or inferred_remote_for_fetching_of_branch(cli_ctxt, b)


def inferred_counterpart_for_fetching_of_branch(cli_ctxt: CommandLineContext, b: str) -> Optional[str]:
    for r in remotes(cli_ctxt):
        if f"{r}/{b}" in remote_branches(cli_ctxt):
            return f"{r}/{b}"
    return None


counterparts_for_fetching_cached: Optional[Dict[str, Optional[str]]] = None  # TODO (#110): default dict with None


def strict_counterpart_for_fetching_of_branch(cli_ctxt: CommandLineContext, b: str) -> Optional[str]:
    global counterparts_for_fetching_cached
    if counterparts_for_fetching_cached is None:
        load_branches(cli_ctxt)
    return counterparts_for_fetching_cached.get(b)


def combined_counterpart_for_fetching_of_branch(cli_ctxt: CommandLineContext, b: str) -> Optional[str]:
    # Since many people don't use '--set-upstream' flag of 'push' or 'branch', we try to infer the remote if the tracking data is missing.
    return strict_counterpart_for_fetching_of_branch(cli_ctxt, b) or inferred_counterpart_for_fetching_of_branch(cli_ctxt, b)


def is_am_in_progress(cli_ctxt: CommandLineContext) -> bool:
    # As of git 2.24.1, this is how 'cmd_rebase()' in builtin/rebase.c checks whether am is in progress.
    return os.path.isfile(get_git_subpath(cli_ctxt, "rebase-apply", "applying"))


def is_cherry_pick_in_progress(cli_ctxt: CommandLineContext) -> bool:
    return os.path.isfile(get_git_subpath(cli_ctxt, "CHERRY_PICK_HEAD"))


def is_merge_in_progress(cli_ctxt: CommandLineContext) -> bool:
    return os.path.isfile(get_git_subpath(cli_ctxt, "MERGE_HEAD"))


def is_revert_in_progress(cli_ctxt: CommandLineContext) -> bool:
    return os.path.isfile(get_git_subpath(cli_ctxt, "REVERT_HEAD"))


# Note: while rebase is ongoing, the repository is always in a detached HEAD state,
# so we need to extract the name of the currently rebased branch from the rebase-specific internals
# rather than rely on 'git symbolic-ref HEAD' (i.e. the contents of .git/HEAD).
def currently_rebased_branch_or_none(cli_ctxt: CommandLineContext) -> Optional[str]:  # utils/private
    # https://stackoverflow.com/questions/3921409

    head_name_file = None

    # .git/rebase-merge directory exists during cherry-pick-powered rebases,
    # e.g. all interactive ones and the ones where '--strategy=' or '--keep-empty' option has been passed
    rebase_merge_head_name_file = get_git_subpath(cli_ctxt, "rebase-merge", "head-name")
    if os.path.isfile(rebase_merge_head_name_file):
        head_name_file = rebase_merge_head_name_file

    # .git/rebase-apply directory exists during the remaining, i.e. am-powered rebases, but also during am sessions.
    rebase_apply_head_name_file = get_git_subpath(cli_ctxt, "rebase-apply", "head-name")
    # Most likely .git/rebase-apply/head-name can't exist during am sessions, but it's better to be safe.
    if not is_am_in_progress(cli_ctxt) and os.path.isfile(rebase_apply_head_name_file):
        head_name_file = rebase_apply_head_name_file

    if not head_name_file:
        return None
    with open(head_name_file) as f:
        raw = f.read().strip()
        return re.sub("^refs/heads/", "", raw)


def currently_checked_out_branch_or_none(cli_ctxt: CommandLineContext) -> Optional[str]:
    try:
        raw = popen_git(cli_ctxt, "symbolic-ref", "--quiet", "HEAD").strip()
        return re.sub("^refs/heads/", "", raw)
    except MacheteException:
        return None


def expect_no_operation_in_progress(cli_ctxt: CommandLineContext) -> None:
    rb = currently_rebased_branch_or_none(cli_ctxt)
    if rb:
        raise MacheteException(
            f"Rebase of `{rb}` in progress. Conclude the rebase first with `git rebase --continue` or `git rebase --abort`.")
    if is_am_in_progress(cli_ctxt):
        raise MacheteException("`git am` session in progress. Conclude `git am` first with `git am --continue` or `git am --abort`.")
    if is_cherry_pick_in_progress(cli_ctxt):
        raise MacheteException("Cherry pick in progress. Conclude the cherry pick first with `git cherry-pick --continue` or `git cherry-pick --abort`.")
    if is_merge_in_progress(cli_ctxt):
        raise MacheteException("Merge in progress. Conclude the merge first with `git merge --continue` or `git merge --abort`.")
    if is_revert_in_progress(cli_ctxt):
        raise MacheteException("Revert in progress. Conclude the revert first with `git revert --continue` or `git revert --abort`.")


def current_branch_or_none(cli_ctxt: CommandLineContext) -> Optional[str]:
    return currently_checked_out_branch_or_none(cli_ctxt) or currently_rebased_branch_or_none(cli_ctxt)


def current_branch(cli_ctxt: CommandLineContext) -> str:
    result = current_branch_or_none(cli_ctxt)
    if not result:
        raise MacheteException("Not currently on any branch")
    return result


merge_base_cached: Dict[Tuple[str, str], str] = {}


def merge_base(cli_ctxt: CommandLineContext, sha1: str, sha2: str) -> str:
    if sha1 > sha2:
        sha1, sha2 = sha2, sha1
    if not (sha1, sha2) in merge_base_cached:
        # Note that we don't pass '--all' flag to 'merge-base', so we'll get only one merge-base
        # even if there is more than one (in the rare case of criss-cross histories).
        # This is still okay from the perspective of is-ancestor checks that are our sole use of merge-base:
        # * if any of sha1, sha2 is an ancestor of another,
        #   then there is exactly one merge-base - the ancestor,
        # * if neither of sha1, sha2 is an ancestor of another,
        #   then none of the (possibly more than one) merge-bases is equal to either of sha1/sha2 anyway.
        merge_base_cached[sha1, sha2] = popen_git(cli_ctxt, "merge-base", sha1, sha2).rstrip()
    return merge_base_cached[sha1, sha2]


# Note: the 'git rev-parse --verify' validation is not performed in case for either of earlier/later
# if the corresponding prefix is empty AND the revision is a 40 hex digit hash.
def is_ancestor_or_equal(
    cli_ctxt: CommandLineContext,
    earlier_revision: str,
    later_revision: str,
    earlier_prefix: str = "refs/heads/",
    later_prefix: str = "refs/heads/",
) -> bool:
    earlier_sha = full_sha(cli_ctxt, earlier_revision, earlier_prefix)
    later_sha = full_sha(cli_ctxt, later_revision, later_prefix)

    if earlier_sha == later_sha:
        return True
    return merge_base(cli_ctxt, earlier_sha, later_sha) == earlier_sha


contains_equivalent_tree_cached: Dict[Tuple[str, str], bool] = {}


# Determine if later_revision, or any ancestors of later_revision that are NOT ancestors of earlier_revision,
# contain a tree with identical contents to earlier_revision, indicating that
# later_revision contains a rebase or squash merge of earlier_revision.
def contains_equivalent_tree(
    cli_ctxt: CommandLineContext,
    earlier_revision: str,
    later_revision: str,
    earlier_prefix: str = "refs/heads/",
    later_prefix: str = "refs/heads/",
) -> bool:
    earlier_commit_sha = full_sha(cli_ctxt, earlier_revision, earlier_prefix)
    later_commit_sha = full_sha(cli_ctxt, later_revision, later_prefix)

    if earlier_commit_sha == later_commit_sha:
        return True

    if (earlier_commit_sha, later_commit_sha) in contains_equivalent_tree_cached:
        return contains_equivalent_tree_cached[earlier_commit_sha, later_commit_sha]

    debug(
        cli_ctxt,
        "contains_equivalent_tree",
        f"earlier_revision={earlier_revision} later_revision={later_revision}",
    )

    earlier_tree_sha = tree_sha_by_commit_sha(cli_ctxt, earlier_commit_sha)

    # `git log later_commit_sha ^earlier_commit_sha`
    # shows all commits reachable from later_commit_sha but NOT from earlier_commit_sha
    intermediate_tree_shas = non_empty_lines(
        popen_git(
            cli_ctxt,
            "log",
            "--format=%T",  # full commit's tree hash
            "^" + earlier_commit_sha,
            later_commit_sha
        )
    )

    result = earlier_tree_sha in intermediate_tree_shas
    contains_equivalent_tree_cached[earlier_commit_sha, later_commit_sha] = result
    return result


def create_branch(cli_ctxt: CommandLineContext, b: str, out_of_revision: str) -> None:
    run_git(cli_ctxt, "checkout", "-b", b, out_of_revision)
    flush_caches()  # the repository state has changed b/c of a successful branch creation, let's defensively flush all the caches


def log_shas(cli_ctxt: CommandLineContext, revision: str, max_count: Optional[int]) -> List[str]:
    opts = ([f"--max-count={str(max_count)}"] if max_count else []) + ["--format=%H", f"refs/heads/{revision}"]
    return non_empty_lines(popen_git(cli_ctxt, "log", *opts))


MAX_COUNT_FOR_INITIAL_LOG = 10

initial_log_shas_cached: Dict[str, List[str]] = {}
remaining_log_shas_cached: Dict[str, List[str]] = {}


# Since getting the full history of a branch can be an expensive operation for large repositories (compared to all other underlying git operations),
# there's a simple optimization in place: we first fetch only a couple of first commits in the history,
# and only fetch the rest if none of them occurs on reflog of any other branch.
def spoonfeed_log_shas(cli_ctxt: CommandLineContext, b: str) -> Generator[str, None, None]:
    if b not in initial_log_shas_cached:
        initial_log_shas_cached[b] = log_shas(cli_ctxt, b, max_count=MAX_COUNT_FOR_INITIAL_LOG)
    for sha in initial_log_shas_cached[b]:
        yield sha

    if b not in remaining_log_shas_cached:
        remaining_log_shas_cached[b] = log_shas(cli_ctxt, b, max_count=None)[MAX_COUNT_FOR_INITIAL_LOG:]
    for sha in remaining_log_shas_cached[b]:
        yield sha


local_branches_cached: Optional[List[str]] = None
remote_branches_cached: Optional[List[str]] = None


def local_branches(cli_ctxt: CommandLineContext) -> List[str]:
    global local_branches_cached, remote_branches_cached
    if local_branches_cached is None:
        load_branches(cli_ctxt)
    return local_branches_cached


def remote_branches(cli_ctxt: CommandLineContext) -> List[str]:
    global local_branches_cached, remote_branches_cached
    if remote_branches_cached is None:
        load_branches(cli_ctxt)
    return remote_branches_cached


def load_branches(cli_ctxt: CommandLineContext) -> None:
    global commit_sha_by_revision_cached, committer_unix_timestamp_by_revision_cached, counterparts_for_fetching_cached
    global local_branches_cached, remote_branches_cached, tree_sha_by_commit_sha_cached
    commit_sha_by_revision_cached = {}
    committer_unix_timestamp_by_revision_cached = {}
    counterparts_for_fetching_cached = {}
    local_branches_cached = []
    remote_branches_cached = []
    tree_sha_by_commit_sha_cached = {}

    # Using 'committerdate:raw' instead of 'committerdate:unix' since the latter isn't supported by some older versions of git.
    raw_remote = non_empty_lines(popen_git(cli_ctxt, "for-each-ref", "--format=%(refname)\t%(objectname)\t%(tree)\t%(committerdate:raw)", "refs/remotes"))
    for line in raw_remote:
        values = line.split("\t")
        if len(values) != 4:
            continue  # invalid, shouldn't happen
        b, commit_sha, tree_sha, committer_unix_timestamp_and_time_zone = values
        b_stripped = re.sub("^refs/remotes/", "", b)
        remote_branches_cached += [b_stripped]
        commit_sha_by_revision_cached[b] = commit_sha
        tree_sha_by_commit_sha_cached[commit_sha] = tree_sha
        committer_unix_timestamp_by_revision_cached[b] = int(committer_unix_timestamp_and_time_zone.split(' ')[0])

    raw_local = non_empty_lines(popen_git(cli_ctxt, "for-each-ref", "--format=%(refname)\t%(objectname)\t%(tree)\t%(committerdate:raw)\t%(upstream)", "refs/heads"))

    for line in raw_local:
        values = line.split("\t")
        if len(values) != 5:
            continue  # invalid, shouldn't happen
        b, commit_sha, tree_sha, committer_unix_timestamp_and_time_zone, fetch_counterpart = values
        b_stripped = re.sub("^refs/heads/", "", b)
        fetch_counterpart_stripped = re.sub("^refs/remotes/", "", fetch_counterpart)
        local_branches_cached += [b_stripped]
        commit_sha_by_revision_cached[b] = commit_sha
        tree_sha_by_commit_sha_cached[commit_sha] = tree_sha
        committer_unix_timestamp_by_revision_cached[b] = int(committer_unix_timestamp_and_time_zone.split(' ')[0])
        if fetch_counterpart_stripped in remote_branches_cached:
            counterparts_for_fetching_cached[b_stripped] = fetch_counterpart_stripped


def get_sole_remote_branch(cli_ctxt: CommandLineContext, b: str) -> Optional[str]:
    def matches(rb: str) -> bool:
        # Note that this matcher is defensively too inclusive:
        # if there is both origin/foo and origin/feature/foo,
        # then both are matched for 'foo';
        # this is to reduce risk wrt. which '/'-separated fragments belong to remote and which to branch name.
        # FIXME (#116): this is still likely to deliver incorrect results in rare corner cases with compound remote names.
        return rb.endswith(f"/{b}")
    matching_remote_branches = list(filter(matches, remote_branches(cli_ctxt)))
    return matching_remote_branches[0] if len(matching_remote_branches) == 1 else None


def merged_local_branches(cli_ctxt: CommandLineContext) -> List[str]:
    return list(map(
        lambda b: re.sub("^refs/heads/", "", b),
        non_empty_lines(popen_git(cli_ctxt, "for-each-ref", "--format=%(refname)", "--merged", "HEAD", "refs/heads"))
    ))


def go(cli_ctxt: CommandLineContext, branch: str) -> None:
    run_git(cli_ctxt, "checkout", "--quiet", branch, "--")


def get_hook_path(cli_ctxt: CommandLineContext, hook_name: str) -> str:
    hook_dir: str = get_config_or_none(cli_ctxt, "core.hooksPath") or get_git_subpath(cli_ctxt, "hooks")
    return os.path.join(hook_dir, hook_name)


def check_hook_executable(cli_ctxt: CommandLineContext, hook_path: str) -> bool:
    if not os.path.isfile(hook_path):
        return False
    elif not is_executable(hook_path):
        advice_ignored_hook = get_config_or_none(cli_ctxt, "advice.ignoredHook")
        if advice_ignored_hook != 'false':  # both empty and "true" is okay
            # The [33m color must be used to keep consistent with how git colors this advice for its built-in hooks.
            sys.stderr.write(colored(f"hint: The '{hook_path}' hook was ignored because it's not set as executable.", YELLOW) + "\n")
            sys.stderr.write(colored("hint: You can disable this warning with `git config advice.ignoredHook false`.", YELLOW) + "\n")
        return False
    else:
        return True


def merge(cli_ctxt: CommandLineContext, branch: str, into: str) -> None:  # refs/heads/ prefix is assumed for 'branch'
    extra_params = ["--no-edit"] if cli_ctxt.opt_no_edit_merge else ["--edit"]
    # We need to specify the message explicitly to avoid 'refs/heads/' prefix getting into the message...
    commit_message = f"Merge branch '{branch}' into {into}"
    # ...since we prepend 'refs/heads/' to the merged branch name for unambiguity.
    run_git(cli_ctxt, "merge", "-m", commit_message, f"refs/heads/{branch}", *extra_params)


def merge_fast_forward_only(cli_ctxt: CommandLineContext, branch: str) -> None:  # refs/heads/ prefix is assumed for 'branch'
    run_git(cli_ctxt, "merge", "--ff-only", f"refs/heads/{branch}")


def rebase(cli_ctxt: CommandLineContext, onto: str, fork_commit: str, branch: str) -> None:
    def do_rebase() -> None:
        try:
            if cli_ctxt.opt_no_interactive_rebase:
                run_git(cli_ctxt, "rebase", "--onto", onto, fork_commit, branch)
            else:
                run_git(cli_ctxt, "rebase", "--interactive", "--onto", onto, fork_commit, branch)
        finally:
            # https://public-inbox.org/git/317468c6-40cc-9f26-8ee3-3392c3908efb@talktalk.net/T
            # In our case, this can happen when git version invoked by git-machete to start the rebase
            # is different than git version used (outside of git-machete) to continue the rebase.
            # This used to be the case when git-machete was installed via a strict-confinement snap
            # with its own version of git baked in as a dependency.
            # Currently we're using classic-confinement snaps which no longer have this problem
            # (snapped git-machete uses whatever git is available in the host system),
            # but it still doesn't harm to patch the author script.

            # No need to fix <git-dir>/rebase-apply/author-script,
            # only <git-dir>/rebase-merge/author-script (i.e. interactive rebases, for the most part) is affected.
            author_script = get_git_subpath(cli_ctxt, "rebase-merge", "author-script")
            if os.path.isfile(author_script):
                faulty_line_regex = re.compile("[A-Z0-9_]+='[^']*")

                def fix_if_needed(line: str) -> str:
                    return f"{line.rstrip()}'\n" if faulty_line_regex.fullmatch(line) else line

                def get_all_lines_fixed() -> Iterator[str]:
                    with open(author_script) as f_read:
                        return map(fix_if_needed, f_read.readlines())

                fixed_lines = get_all_lines_fixed()  # must happen before the 'with' clause where we open for writing
                with open(author_script, "w") as f_write:
                    f_write.write("".join(fixed_lines))

    hook_path = get_hook_path(cli_ctxt, "machete-pre-rebase")
    if check_hook_executable(cli_ctxt, hook_path):
        debug(cli_ctxt, f"rebase({onto}, {fork_commit}, {branch})", f"running machete-pre-rebase hook ({hook_path})")
        exit_code = run_cmd(cli_ctxt, hook_path, onto, fork_commit, branch, cwd=get_root_dir(cli_ctxt))
        if exit_code == 0:
            do_rebase()
        else:
            sys.stderr.write("The machete-pre-rebase hook refused to rebase.\n")
            sys.exit(exit_code)
    else:
        do_rebase()


def rebase_onto_ancestor_commit(cli_ctxt: CommandLineContext, branch: str, ancestor_commit: str) -> None:
    rebase(cli_ctxt, ancestor_commit, ancestor_commit, branch)


Hash_ShortHash_Message = Tuple[str, str, str]


def commits_between(cli_ctxt: CommandLineContext, earliest_exclusive: str, latest_inclusive: str) -> List[Hash_ShortHash_Message]:
    # Reverse the list, since `git log` by default returns the commits from the latest to earliest.
    return list(reversed(list(map(
        lambda x: tuple(x.split(":", 2)),  # type: ignore
        non_empty_lines(popen_git(cli_ctxt, "log", "--format=%H:%h:%s", f"^{earliest_exclusive}", latest_inclusive, "--"))
    ))))


# TODO (#117): extract to namespace, use mypy
NO_REMOTES = 0
UNTRACKED = 1
IN_SYNC_WITH_REMOTE = 2
BEHIND_REMOTE = 3
AHEAD_OF_REMOTE = 4
DIVERGED_FROM_AND_OLDER_THAN_REMOTE = 5
DIVERGED_FROM_AND_NEWER_THAN_REMOTE = 6


def get_relation_to_remote_counterpart(cli_ctxt: CommandLineContext, b: str, rb: str) -> int:
    b_is_anc_of_rb = is_ancestor_or_equal(cli_ctxt, b, rb, later_prefix="refs/remotes/")
    rb_is_anc_of_b = is_ancestor_or_equal(cli_ctxt, rb, b, earlier_prefix="refs/remotes/")
    if b_is_anc_of_rb:
        return IN_SYNC_WITH_REMOTE if rb_is_anc_of_b else BEHIND_REMOTE
    elif rb_is_anc_of_b:
        return AHEAD_OF_REMOTE
    else:
        b_t = committer_unix_timestamp_by_revision(cli_ctxt, b, "refs/heads/")
        rb_t = committer_unix_timestamp_by_revision(cli_ctxt, rb, "refs/remotes/")
        return DIVERGED_FROM_AND_OLDER_THAN_REMOTE if b_t < rb_t else DIVERGED_FROM_AND_NEWER_THAN_REMOTE


def get_strict_remote_sync_status(cli_ctxt: CommandLineContext, b: str) -> Tuple[int, Optional[str]]:
    if not remotes(cli_ctxt):
        return NO_REMOTES, None
    rb = strict_counterpart_for_fetching_of_branch(cli_ctxt, b)
    if not rb:
        return UNTRACKED, None
    return get_relation_to_remote_counterpart(cli_ctxt, b, rb), strict_remote_for_fetching_of_branch(cli_ctxt, b)


def get_combined_remote_sync_status(cli_ctxt: CommandLineContext, b: str) -> Tuple[int, Optional[str]]:
    if not remotes(cli_ctxt):
        return NO_REMOTES, None
    rb = combined_counterpart_for_fetching_of_branch(cli_ctxt, b)
    if not rb:
        return UNTRACKED, None
    return get_relation_to_remote_counterpart(cli_ctxt, b, rb), combined_remote_for_fetching_of_branch(cli_ctxt, b)


# Reflog magic


REFLOG_ENTRY = Tuple[str, str]

reflogs_cached: Optional[Dict[str, Optional[List[REFLOG_ENTRY]]]] = None


def load_all_reflogs(cli_ctxt: CommandLineContext) -> None:
    global reflogs_cached
    # %gd - reflog selector (refname@{num})
    # %H - full hash
    # %gs - reflog subject
    all_branches = [f"refs/heads/{b}" for b in local_branches(cli_ctxt)] + \
                   [f"refs/remotes/{combined_counterpart_for_fetching_of_branch(cli_ctxt, b)}" for b in local_branches(cli_ctxt) if combined_counterpart_for_fetching_of_branch(cli_ctxt, b)]
    # The trailing '--' is necessary to avoid ambiguity in case there is a file called just exactly like one of the branches.
    entries = non_empty_lines(popen_git(cli_ctxt, "reflog", "show", "--format=%gD\t%H\t%gs", *(all_branches + ["--"])))
    reflogs_cached = {}
    for entry in entries:
        values = entry.split("\t")
        if len(values) != 3:  # invalid, shouldn't happen
            continue
        selector, sha, subject = values
        branch_and_pos = selector.split("@")
        if len(branch_and_pos) != 2:  # invalid, shouldn't happen
            continue
        b, pos = branch_and_pos
        if b not in reflogs_cached:
            reflogs_cached[b] = []
        reflogs_cached[b] += [(sha, subject)]


def reflog(cli_ctxt: CommandLineContext, b: str) -> List[REFLOG_ENTRY]:
    global reflogs_cached
    # git version 2.14.2 fixed a bug that caused fetching reflog of more than
    # one branch at the same time unreliable in certain cases
    if get_git_version(cli_ctxt) >= (2, 14, 2):
        if reflogs_cached is None:
            load_all_reflogs(cli_ctxt)
        return reflogs_cached.get(b, [])
    else:
        if reflogs_cached is None:
            reflogs_cached = {}
        if b not in reflogs_cached:
            # %H - full hash
            # %gs - reflog subject
            reflogs_cached[b] = [
                tuple(entry.split(":", 1)) for entry in non_empty_lines(  # type: ignore
                    # The trailing '--' is necessary to avoid ambiguity in case there is a file called just exactly like the branch 'b'.
                    popen_git(cli_ctxt, "reflog", "show", "--format=%H:%gs", b, "--"))
            ]
        return reflogs_cached[b]


def get_latest_checkout_timestamps(cli_ctxt: CommandLineContext) -> Dict[str, int]:  # TODO (#110): default dict with 0
    # Entries are in the format '<branch_name>@{<unix_timestamp> <time-zone>}'
    result = {}
    # %gd - reflog selector (HEAD@{<unix-timestamp> <time-zone>} for `--date=raw`;
    #   `--date=unix` is not available on some older versions of git)
    # %gs - reflog subject
    output = popen_git(cli_ctxt, "reflog", "show", "--format=%gd:%gs", "--date=raw")
    for entry in non_empty_lines(output):
        pattern = "^HEAD@\\{([0-9]+) .+\\}:checkout: moving from (.+) to (.+)$"
        match = re.search(pattern, entry)
        if match:
            from_branch = match.group(2)
            to_branch = match.group(3)
            # Only the latest occurrence for any given branch is interesting
            # (i.e. the first one to occur in reflog)
            if from_branch not in result:
                result[from_branch] = int(match.group(1))
            if to_branch not in result:
                result[to_branch] = int(match.group(1))
    return result


# Complex routines/commands

def is_merged_to(machete_client: MacheteClient, cli_ctxt: CommandLineContext, b: str, target: str) -> bool:
    if is_ancestor_or_equal(cli_ctxt, b, target):
        # If branch is ancestor of or equal to the target, we need to distinguish between the
        # case of branch being "recently" created from the target and the case of
        # branch being fast-forward-merged to the target.
        # The applied heuristics is to check if the filtered reflog of the branch
        # (reflog stripped of trivial events like branch creation, reset etc.)
        # is non-empty.
        return bool(machete_client.filtered_reflog(b, prefix="refs/heads/"))
    elif cli_ctxt.opt_no_detect_squash_merges:
        return False
    else:
        # In the default mode.
        # If there is a commit in target with an identical tree state to b,
        # then b may be squash or rebase merged into target.
        return contains_equivalent_tree(cli_ctxt, b, target)


def get_revision_repr(cli_ctxt: CommandLineContext, revision: str) -> str:
    short_sha = short_commit_sha_by_revision(cli_ctxt, revision)
    if is_full_sha(revision) or revision == short_sha:
        return f"commit {revision}"
    else:
        return f"{revision} (commit {short_commit_sha_by_revision(cli_ctxt, revision)})"


class StopTraversal(Exception):
    def __init__(self) -> None:
        pass


def flush_caches() -> None:
    global commit_sha_by_revision_cached, config_cached, counterparts_for_fetching_cached, initial_log_shas_cached
    global local_branches_cached, reflogs_cached, remaining_log_shas_cached, remote_branches_cached
    MacheteClient.branch_defs_by_sha_in_reflog = None
    commit_sha_by_revision_cached = None
    config_cached = None
    counterparts_for_fetching_cached = None
    initial_log_shas_cached = {}
    local_branches_cached = None
    reflogs_cached = None
    remaining_log_shas_cached = {}
    remote_branches_cached = None


def pick_remote(cli_ctxt: CommandLineContext, b: str) -> None:
    rems = remotes(cli_ctxt)
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
        handle_untracked_branch(cli_ctxt, rems[index], b)
    except ValueError:
        pass


def handle_untracked_branch(cli_ctxt: CommandLineContext, new_remote: str, b: str) -> None:
    rems: List[str] = remotes(cli_ctxt)
    can_pick_other_remote = len(rems) > 1
    other_remote_choice = "o[ther-remote]" if can_pick_other_remote else ""
    rb = f"{new_remote}/{b}"
    if not commit_sha_by_revision(cli_ctxt, rb, prefix="refs/remotes/"):
        ask_message = f"Push untracked branch {bold(b)} to {bold(new_remote)}?" + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice)
        ask_opt_yes_message = f"Pushing untracked branch {bold(b)} to {bold(new_remote)}..."
        ans = ask_if(cli_ctxt, ask_message, ask_opt_yes_message,
                     override_answer=None if cli_ctxt.opt_push_untracked else "N")
        if ans in ('y', 'yes', 'yq'):
            push(cli_ctxt, new_remote, b)
            if ans == 'yq':
                raise StopTraversal
            flush_caches()
        elif can_pick_other_remote and ans in ('o', 'other'):
            pick_remote(cli_ctxt, b)
        elif ans in ('q', 'quit'):
            raise StopTraversal
        return

    relation: int = get_relation_to_remote_counterpart(cli_ctxt, b, rb)

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
            f"Push branch {bold(b)} to {bold(new_remote)}?" + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
            f"Pushing branch {bold(b)} to {bold(new_remote)}..."
        ),
        DIVERGED_FROM_AND_OLDER_THAN_REMOTE: (
            f"Reset branch {bold(b)} to the commit pointed by {bold(rb)}?" + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
            f"Resetting branch {bold(b)} to the commit pointed by {bold(rb)}..."
        ),
        DIVERGED_FROM_AND_NEWER_THAN_REMOTE: (
            f"Push branch {bold(b)} with force-with-lease to {bold(new_remote)}?" + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
            f"Pushing branch {bold(b)} with force-with-lease to {bold(new_remote)}..."
        )
    }[relation]

    override_answer: Optional[str] = {
        IN_SYNC_WITH_REMOTE: None,
        BEHIND_REMOTE: None,
        AHEAD_OF_REMOTE: None if cli_ctxt.opt_push_tracked else "N",
        DIVERGED_FROM_AND_OLDER_THAN_REMOTE: None,
        DIVERGED_FROM_AND_NEWER_THAN_REMOTE: None if cli_ctxt.opt_push_tracked else "N",
    }[relation]

    yes_action: Callable[[], None] = {
        IN_SYNC_WITH_REMOTE: lambda: set_upstream_to(cli_ctxt, rb),
        BEHIND_REMOTE: lambda: pull_ff_only(cli_ctxt, new_remote, rb),
        AHEAD_OF_REMOTE: lambda: push(cli_ctxt, new_remote, b),
        DIVERGED_FROM_AND_OLDER_THAN_REMOTE: lambda: reset_keep(cli_ctxt, rb),
        DIVERGED_FROM_AND_NEWER_THAN_REMOTE: lambda: push(cli_ctxt, new_remote, b, force_with_lease=True)
    }[relation]

    print(message)
    ans = ask_if(cli_ctxt, ask_message, ask_opt_yes_message, override_answer=override_answer)
    if ans in ('y', 'yes', 'yq'):
        yes_action()
        if ans == 'yq':
            raise StopTraversal
        flush_caches()
    elif can_pick_other_remote and ans in ('o', 'other'):
        pick_remote(cli_ctxt, b)
    elif ans in ('q', 'quit'):
        raise StopTraversal


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

short_docs: Dict[str, str] = {
    "add": "Add a branch to the tree of branch dependencies",
    "advance": "Fast-forward merge one of children to the current branch and then slide out this child",
    "anno": "Manage custom annotations",
    "delete-unmanaged": "Delete local branches that are not present in the definition file",
    "diff": "Diff current working directory or a given branch against its computed fork point",
    "discover": "Automatically discover tree of branch dependencies",
    "edit": "Edit the definition file",
    "file": "Display the location of the definition file",
    "fork-point": "Display or override fork point for a branch",
    "format": "Display docs for the format of the definition file",
    "go": "Check out the branch relative to the position of the current branch, accepts down/first/last/next/root/prev/up argument",
    "help": "Display this overview, or detailed help for a specified command",
    "hooks": "Display docs for the extra hooks added by git machete",
    "is-managed": "Check if the current branch is managed by git machete (mostly for scripts)",
    "list": "List all branches that fall into one of pre-defined categories (mostly for internal use)",
    "log": "Log the part of history specific to the given branch",
    "reapply": "Rebase the current branch onto its computed fork point",
    "show": "Show name(s) of the branch(es) relative to the position of a branch, accepts down/first/last/next/root/prev/up argument",
    "slide-out": "Slide out the current branch and sync its downstream (child) branches with its upstream (parent) branch via rebase or merge",
    "squash": "Squash the unique history of the current branch into a single commit",
    "status": "Display formatted tree of branch dependencies, including info on their sync with upstream branch and with remote",
    "traverse": "Walk through the tree of branch dependencies and rebase, merge, slide out, push and/or pull each branch one by one",
    "update": "Sync the current branch with its upstream (parent) branch via rebase or merge",
    "version": "Display the version and exit"
}

long_docs: Dict[str, str] = {
    "add": """
        <b>Usage: git machete add [-o|--onto=<target-upstream-branch>] [-R|--as-root] [-y|--yes] [<branch>]</b>

        Adds the provided <branch> (or the current branch, if none specified) to the definition file.
        If <branch> is provided but no local branch with the given name exists:
        * if a remote branch of the same name exists in exactly one remote, then user is asked whether to check out this branch locally (as in `git checkout`),
        * otherwise, user is asked whether it should be created as a new local branch.

        If the definition file is empty or `-R`/`--as-root` is provided, the branch will be added as a root of the tree of branch dependencies.
        Otherwise, the desired upstream (parent) branch can be specified with `-o`/`--onto`.
        Neither of these options is mandatory, however; if both are skipped, git machete will try to automatically infer the target upstream.
        If the upstream branch can be inferred, the user will be presented with inferred branch and asked to confirm.

        Note: all the effects of `add` (except git branch creation) can as well be achieved by manually editing the definition file.

        <b>Options:</b>
          <b>-o, --onto=<target-upstream-branch></b>    Specifies the target parent branch to add the given branch onto.
                                                 Cannot be specified together with `-R`/`--as-root`.

          <b>-R, --as-root</b>                          Add the given branch as a new root (and not onto any other branch).
                                                 Cannot be specified together with `-o`/`--onto`.

          <b>-y, --yes</b>                              Don't ask for confirmation whether to create the branch or whether to add onto the inferred upstream.
    """,
    "advance": """
        <b>Usage: git machete advance [-y|--yes]</b>

        Fast forwards (as in `git merge --ff-only`) the current branch `C` to match its downstream `D`,
        and subsequently slides out `D`. Both steps require manual confirmation unless `-y`/`--yes` is provided.

        The downstream `C` is selected according to the following criteria:
        * if `C` has exactly one downstream branch `d` whose tip is a descendant of `C`, and whose fork point is equal to `C` or is overridden
          (basically: there's a green edge between `C` and `d`), then `d` is selected as `D`,
        * if `C` has no downstream branches connected with a green edge to `C`, then `advance` fails,
        * if `C` has more than one downstream branch connected with a green edge to `C`,
          then user is asked to pick the branch to fast-forward merge into (similarly to what happens in `git machete go down`).
          If `--yes` is specified, then `advance` fails.

        As an example, if `git machete status --color=never --list-commits` is as follows:
        <dim>
          master
          |
          m-develop *
            |
            | Enable adding remote branch in the manner similar to git checkout
            o-feature/add-from-remote
            | |
            | | Add support and sample for machete-post-slide-out hook
            | o-feature/post-slide-out-hook
            |
            | Remove support for Python 2
            | Remove support for Python 2 - 1st round of fixes
            ?-chore/v3
            |
            | Apply Python2-compatible static typing
            x-feature/types
        </dim>
        then running `git machete advance` will fast-forward the current branch `develop` to match `feature/add-from-remote`, and subsequently slide out the latter.
        After `advance` completes, `status` will show:
        <dim>
          master
          |
          | Enable adding remote branch in the manner similar to git checkout
          o-develop *
            |
            | Add support and sample for machete-post-slide-out hook
            o-feature/post-slide-out-hook
            |
            | Remove support for Python 2
            | Remove support for Python 2 - 1st round of fixes
            ?-chore/v3
            |
            | Apply Python2-compatible static typing
            x-feature/types
        </dim>
        Note that the current branch after the operation is still `develop`, just pointing to `feature/add-from-remote`'s tip now.

        <b>Options:</b>
          <b>-y, --yes</b>         Don't ask for confirmation whether to fast-forward the current branch or whether to slide-out the downstream.
                            Fails if the current branch has more than one green-edge downstream branch.
    """,
    "anno": """
        <b>Usage:
          git machete anno [-b|--branch=<branch>] [<annotation text>]
          git machete anno -H|--sync-github-prs</b>

        If invoked without any argument, prints out the custom annotation for the given branch (or current branch, if none specified with `-b/--branch`).

        If invoked with a single empty string argument, like:
        <dim>$ git machete anno ''</dim>
        then clears the annotation for the current branch (or a branch specified with `-b/--branch`).

        If invoked with `-H` or `--sync-github-prs`, annotates the branches based on their corresponding GitHub PR numbers and authors.
        Any existing annotations are overwritten for the branches that have an opened PR; annotations for the other branches remain untouched.

        To allow GitHub API access for private repositories (and also to correctly identify the current user, even in case of public repositories),
        a GitHub API token with `repo` scope is required, see `https://github.com/settings/tokens`. This will be resolved from the first of:
        1. `GITHUB_TOKEN` env var,
        2. current auth token from the `gh` GitHub CLI,
        3. current auth token from the `hub` GitHub CLI.

        In any other case, sets the annotation for the given/current branch to the given argument.
        If multiple arguments are passed to the command, they are concatenated with a single space.

        Note: all the effects of `anno` can be always achieved by manually editing the definition file.

        <b>Options:</b>
          <b>-b, --branch=<branch></b>      Branch to set the annotation for.
          <b>-H, --sync-github-prs</b>      Annotate with GitHub PR numbers and authors where applicable.
    """,
    "delete-unmanaged": """
        <b>Usage: git machete delete-unmanaged [-y|--yes]</b>

        Goes one-by-one through all the local git branches that don't exist in the definition file,
        and ask to delete each of them (with `git branch -d` or `git branch -D`) if confirmed by user.
        No branch will be deleted unless explicitly confirmed by the user (or unless `-y/--yes` option is passed).

        Note: this should be used with care since deleting local branches can sometimes make it impossible for `git machete` to properly figure out fork points.
        See `git machete help fork-point` for more details.

        <b>Options:</b>
          <b>-y, --yes</b>          Don't ask for confirmation.
    """,
    "diff": """
        <b>Usage: git machete d[iff] [-s|--stat] [<branch>]</b>

        Runs `git diff` of the given branch tip against its fork point or, if none specified, of the current working tree against the fork point of the currently checked out branch.
        See `git machete help fork-point` for more details on meaning of the "fork point".

        Note: the branch in question does not need to occur in the definition file.

        Options:
          <b>-s, --stat</b>    Makes `git machete diff` pass `--stat` option to `git diff`, so that only summary (diffstat) is printed.
    """,
    "discover": """
        <b>Usage: git machete discover [-C|--checked-out-since=<date>] [-l|--list-commits] [-r|--roots=<branch1>,<branch2>,...] [-y|--yes]</b>

        Discovers and displays tree of branch dependencies using a heuristic based on reflogs and asks whether to overwrite the existing definition file with the new discovered tree.
        If confirmed with a `y[es]` or `e[dit]` reply, backs up the current definition file (if it exists) as `$GIT_DIR/machete~` and saves the new tree under the usual `$GIT_DIR/machete` path.
        If the reply was `e[dit]`, additionally an editor is opened (as in `git machete edit`) after saving the new definition file.

        Options:
          <b>-C, --checked-out-since=<date></b>   Only consider branches checked out at least once since the given date. <date> can be e.g. `2 weeks ago` or `2020-06-01`, as in `git log --since=<date>`.
                                           If not present, the date is selected automatically so that around """ + str(MacheteClient.DISCOVER_DEFAULT_FRESH_BRANCH_COUNT) + """ branches are included.

          <b>-l, --list-commits</b>               When printing the discovered tree, additionally lists the messages of commits introduced on each branch (as for `git machete status`).

          <b>-r, --roots=<branch1,...></b>        Comma-separated list of branches that should be considered roots of trees of branch dependencies.
                                           If not present, `master` is assumed to be a root.
                                           Note that in the process of discovery, certain other branches can also be additionally deemed to be roots as well.

          <b>-y, --yes</b>                        Don't ask for confirmation before saving the newly-discovered tree.
                                           Mostly useful in scripts; not recommended for manual use.
    """,
    "edit": """
        <b>Usage: git machete e[dit]</b>

        Opens an editor and lets you edit the definition file manually.

        The editor is determined by checking up the following locations:
        * `$GIT_MACHETE_EDITOR`
        * `$GIT_EDITOR`
        * `$(git config core.editor)`
        * `$VISUAL`
        * `$EDITOR`
        * `editor`
        * `nano`
        * `vi`
        and selecting the first one that is defined and points to an executable file accessible on `PATH`.

        Note that the above editor selection only applies for editing the definition file,
        but not for any other actions that may be indirectly triggered by git-machete, including editing of rebase TODO list, commit messages etc.

        The definition file can be always accessed and edited directly under path returned by `git machete file` (currently fixed to <git-directory>/machete).
    """,
    "file": """
        <b>Usage: git machete file</b>

        Outputs the absolute path of the machete definition file. Currently fixed to `<git-directory>/machete`.
        Note: this won't always be just `<repo-root>/.git/machete` since e.g. submodules and worktrees have their git directories in different location.
    """,
    "fork-point": """
        <b>Usage:
          git machete fork-point [--inferred] [<branch>]
          git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent [<branch>]
          git machete fork-point --unset-override [<branch>]</b>

        Note: in all three forms, if no <branch> is specified, the currently checked out branch is assumed.
        The branch in question does not need to occur in the definition file.


        Without any option, displays full SHA of the fork point commit for the <branch>.
        Fork point of the given <branch> is the commit at which the history of the <branch> diverges from history of any other branch.

        Fork point is assumed by many `git machete` commands as the place where the unique history of the <branch> starts.
        The range of commits between the fork point and the tip of the given branch is, for instance:
        * listed for each branch by `git machete status --list-commits`
        * passed to `git rebase` by `git machete reapply`/`slide-out`/`traverse`/`update`
        * provided to `git diff`/`log` by `git machete diff`/`log`.

        `git machete` assumes fork point of <branch> is the most recent commit in the log of <branch> that has NOT been introduced on that very branch,
        but instead occurs on a reflog (see help for `git reflog`) of some other, usually chronologically earlier, branch.
        This yields a correct result in typical cases, but there are some situations
        (esp. when some local branches have been deleted) where the fork point might not be determined correctly.
        Thus, all rebase-involving operations (`reapply`, `slide-out`, `traverse` and `update`) run `git rebase` in the interactive mode,
        unless told explicitly not to do so by `--no-interactive-rebase` flag, so that the suggested commit range can be inspected before the rebase commences.
        Also, `reapply`, `slide-out`, `squash`, and `update` allow to specify the fork point explicitly by a command-line option.

        `git machete fork-point` is different (and more powerful) than `git merge-base --fork-point`,
        since the latter takes into account only the reflog of the one provided upstream branch,
        while the former scans reflogs of all local branches and their remote tracking branches.
        This makes git-machete's `fork-point` more resilient to modifications of the tree definition which change the upstreams of branches.


        With `--override-to=<revision>`, sets up a fork point override for <branch>.
        Fork point for <branch> will be overridden to the provided <revision> (commit) as long as the <branch> still points to (or is descendant of) the commit X
        that <branch> pointed to at the moment the override is set up.
        Even if revision is a symbolic name (e.g. other branch name or `HEAD~3`) and not explicit commit hash (like `a1b2c3ff`),
        it's still resolved to a specific commit hash at the moment the override is set up (and not later when the override is actually used).
        The override data is stored under `machete.overrideForkPoint.<branch>.to` and `machete.overrideForkPoint.<branch>.whileDescendantOf` git config keys.
        Note: the provided fork point <revision> must be an ancestor of the current <branch> commit X.

        With `--override-to-parent`, overrides fork point of the <branch> to the commit currently pointed by <branch>'s parent in the branch dependency tree.
        Note: this will only work if <branch> has a parent at all (i.e. is not a root) and parent of <branch> is an ancestor of current <branch> commit X.

        With `--inferred`, displays the commit that `git machete fork-point` infers to be the fork point of <branch>.
        If there is NO fork point override for <branch>, this is identical to the output of `git machete fork-point`.
        If there is a fork point override for <branch>, this is identical to the what the output of `git machete fork-point` would be if the override was NOT present.

        With `--override-to-inferred` option, overrides fork point of the <branch> to the commit that `git machete fork-point` infers to be the fork point of <branch>.
        Note: this piece of information is also displayed by `git machete status --list-commits` in case a yellow edge occurs.

        With `--unset-override`, the fork point override for <branch> is unset.
        This is simply done by removing the corresponding `machete.overrideForkPoint.<branch>.*` config entries.


        <b>Note:</b> if an overridden fork point applies to a branch `B`, then it's considered to be <green>connected with a green edge</green> to its upstream (parent) `U`,
        even if the overridden fork point of `B` is NOT equal to the commit pointed by `U`.
    """,
    "format": """
        Note: there is no 'git machete format' command as such; 'format' is just a topic of 'git machete help'.

        The format of the definition file should be as follows:
        <dim>
          develop
              adjust-reads-prec PR #234
                  block-cancel-order PR #235
                      change-table
                          drop-location-type
              edit-margin-not-allowed
                  full-load-gatling
              grep-errors-script
          master
              hotfix/receipt-trigger PR #236
        </dim>
        In the above example `develop` and `master` are roots of the tree of branch dependencies.
        Branches `adjust-reads-prec`, `edit-margin-not-allowed` and `grep-errors-script` are direct downstream branches for `develop`.
        `block-cancel-order` is a downstream branch of `adjust-reads-prec`, `change-table` is a downstream branch of `block-cancel-order` and so on.

        Every branch name can be followed (after a single space as a delimiter) by a custom annotation - a PR number in the above example.
        The annotations don't influence the way `git machete` operates other than that they are displayed in the output of the `status` command.
        Also see help for the `anno` command.

        Tabs or any number of spaces can be used as indentation.
        It's only important to be consistent wrt. the sequence of characters used for indentation between all lines.
    """,
    "go": """
        <b>Usage: git machete g[o] <direction></b>
        where <direction> is one of: `d[own]`, `f[irst]`, `l[ast]`, `n[ext]`, `p[rev]`, `r[oot]`, `u[p]`

        Checks out the branch specified by the given direction relative to the currently checked out branch.
        Roughly equivalent to `git checkout $(git machete show <direction>)`.
        See `git machete help show` on more details on meaning of each direction.
    """,
    "help": """
        <b>Usage: git machete help [<command>]</b>

        Prints a summary of this tool, or a detailed info on a command if defined.
    """,
    "hooks": """
        As with the standard git hooks, git-machete looks for its own specific hooks in `$GIT_DIR/hooks/*` (or `$(git config core.hooksPath)/*`, if set).

        Note: `hooks` is not a command as such, just a help topic (there is no `git machete hooks` command).

        * <b>machete-post-slide-out <new-upstream> <lowest-slid-out-branch> [<new-downstreams>...]</b>
            The hook that is executed after a branch (or possibly multiple branches, in case of `slide-out`)
            is slid out by `advance`, `slide-out` or `traverse`.

            At least two parameters (branch names) are passed to the hook:
            * <b><new-upstream></b> is the upstream of the branch that has been slid out,
              or in case of multiple branches being slid out - the upstream of the highest slid out branch;
            * <b><lowest-slid-out-branch></b> is the branch that has been slid out,
              or in case of multiple branches being slid out - the lowest slid out branch;
            * <b><new-downstreams></b> are all the following (possibly zero) parameters,
              which correspond to all original downstreams of <lowest-slid-out-branch>, now reattached as the downstreams of <new-upstream>.
              Note that this may be zero, one, or multiple branches.

            Note: the hook, if present, is executed:
            * zero or once during a `advance` execution (depending on whether the slide-out has been confirmed or not),
            * exactly once during a `slide-out` execution (even if multiple branches are slid out),
            * zero or more times during `traverse` (every time a slide-out operation is confirmed).

            If the hook returns a non-zero exit code, then the execution of the command is aborted,
            i.e. `slide-out` won't attempt rebase of the new downstream branches and `traverse` won't continue the traversal.
            In case of `advance` there is no difference (other than exit code of the entire `advance` command being non-zero),
            since slide-out is the last operation that happens within `advance`.
            Note that non-zero exit code of the hook doesn't cancel the effects of slide-out itself, only the subsequent operations.
            The hook is executed only once the slide-out is complete and can in fact rely on .git/machete file being updated to the new branch layout.

        * <b>machete-pre-rebase <new-base> <fork-point-hash> <branch-being-rebased></b>
            The hook that is executed before rebase is run during `reapply`, `slide-out`, `traverse` and `update`.
            Note that it is NOT executed by `squash` (despite its similarity to `reapply`), since no rebase is involved in `squash`.

            The parameters are exactly the three revisions that are passed to `git rebase --onto`:
            1. what is going to be the new base for the rebased commits,
            2. what is the fork point - the place where the rebased history diverges from the upstream history,
            3. what branch is rebased.
            If the hook returns a non-zero exit code, the entire rebase is aborted.

            Note: this hook is independent from git's standard `pre-rebase` hook.
            If machete-pre-rebase returns zero, the execution flow continues to `git rebase`, which may also run `pre-rebase` hook if present.
            `machete-pre-rebase` is thus always launched before `pre-rebase`.

        * <b>machete-status-branch <branch-name></b>
            The hook that is executed for each branch displayed during `discover`, `status` and `traverse`.

            The standard output of this hook is displayed at the end of the line, after branch name, (optionally) custom annotation and (optionally) remote sync-ness status.
            Standard error is ignored. If the hook returns a non-zero exit code, both stdout and stderr are ignored, and printing the status continues as usual.

            Note: the hook is always invoked with `ASCII_ONLY` variable passed into the environment.
            If `status` runs in ASCII-only mode (i.e. if `--color=auto` and stdout is not a terminal, or if `--color=never`), then `ASCII_ONLY=true`, otherwise `ASCII_ONLY=false`.

        Please see hook_samples/ directory of git-machete project for examples.
        An example of using the standard git `post-commit` hook to `git machete add` branches automatically is also included.
    """,
    "is-managed": """
        <b>Usage: git machete is-managed [<branch>]</b>

        Returns with zero exit code if the given branch (or current branch, if none specified) is managed by git-machete (i.e. listed in .git/machete).

        Returns with a non-zero exit code in case:
        * the <branch> is provided but isn't managed, or
        * the <branch> isn't provided and the current branch isn't managed, or
        * the <branch> isn't provided and there's no current branch (detached HEAD).
    """,
    "list": """
        <b>Usage: git machete list <category></b>
        where <category> is one of: `addable`, `managed`, `slidable`, `slidable-after <branch>`, `unmanaged`, `with-overridden-fork-point`.

        Lists all branches that fall into one of the specified categories:
        * `addable`: all branches (local or remote) than can be added to the definition file,
        * `managed`: all branches that appear in the definition file,
        * `slidable`: all managed branches that have an upstream and can be slid out with `slide-out` command
        * `slidable-after <branch>`: the downstream branch of the <branch>, if it exists and is the only downstream of <branch> (i.e. the one that can be slid out immediately following <branch>),
        * `unmanaged`: all local branches that don't appear in the definition file,
        * `with-overridden-fork-point`: all local branches that have a fork point override set up (even if this override does not affect the location of their fork point anymore).

        This command is generally not meant for a day-to-day use, it's mostly needed for the sake of branch name completion in shell.
    """,
    "log": """
        <b>Usage: git machete l[og] [<branch>]</b>

        Runs `git log` for the range of commits from tip of the given branch (or current branch, if none specified) back to its fork point.
        See `git machete help fork-point` for more details on meaning of the "fork point".

        Note: the branch in question does not need to occur in the definition file.
    """,
    "reapply": """
        <b>Usage: git machete reapply [-f|--fork-point=<fork-point-commit>]</b>

        Interactively rebase the current branch on the top of its computed fork point.
        The chunk of the history to be rebased starts at the automatically computed fork point of the current branch by default, but can also be set explicitly by `--fork-point`.
        See `git machete help fork-point` for more details on meaning of the "fork point".

        Note: the current reapplied branch does not need to occur in the definition file.

        Tip: `reapply` can be used for squashing the commits on the current branch to make history more condensed before push to the remote,
        but there is also dedicated `squash` command that achieves the same goal without running `git rebase`.

        <b>Options:</b>
          <b>-f, --fork-point=<fork-point-commit></b>    Specifies the alternative fork point commit after which the rebased part of history is meant to start.
    """,
    "show": """
        <b>Usage: git machete show <direction> [<branch>]</b>
        where <direction> is one of: `c[urrent]`, `d[own]`, `f[irst]`, `l[ast]`, `n[ext]`, `p[rev]`, `r[oot]`, `u[p]`
        displayed relative to target <branch>, or the current checked out branch if <branch> is unspecified.

        Outputs name of the branch (or possibly multiple branches, in case of `down`) that is:

        * `current`: the current branch; exits with a non-zero status if none (detached HEAD)
        * `down`:    the direct children/downstream branch of the target branch.
        * `first`:   the first downstream of the root branch of the target branch (like `root` followed by `next`), or the root branch itself if the root has no downstream branches.
        * `last`:    the last branch in the definition file that has the same root as the target branch; can be the root branch itself if the root has no downstream branches.
        * `next`:    the direct successor of the target branch in the definition file.
        * `prev`:    the direct predecessor of the target branch in the definition file.
        * `root`:    the root of the tree where the target branch is located. Note: this will typically be something like `develop` or `master`, since all branches are usually meant to be ultimately merged to one of those.
        * `up`:      the direct parent/upstream branch of the target branch.
    """,
    "slide-out": """
        <b>Usage: git machete slide-out [-d|--down-fork-point=<down-fork-point-commit>] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase] <branch> [<branch> [<branch> ...]]</b>

        Removes the given branch (or multiple branches) from the branch tree definition.
        Then synchronizes the downstream (child) branches of the last specified branch on the top of the upstream (parent) branch of the first specified branch.
        Sync is performed either by rebase (default) or by merge (if `--merge` option passed).

        The most common use is to slide out a single branch whose upstream was a `develop`/`master` branch and that has been recently merged.

        Since this tool is designed to perform only one single rebase/merge at the end, provided branches must form a chain, i.e. all of the following conditions must be met:
        * for i=1..N-1, (i+1)-th branch must be the only downstream (child) branch of the i-th branch,
        * all provided branches must have an upstream branch (so, in other words, roots of branch dependency tree cannot be slid out).

        For example, let's assume the following dependency tree:
        <dim>
          develop
              adjust-reads-prec
                  block-cancel-order
                      change-table
                          drop-location-type
                      add-notification
        </dim>
        And now let's assume that `adjust-reads-prec` and later `block-cancel-order` were merged to develop.
        After running `git machete slide-out adjust-reads-prec block-cancel-order` the tree will be reduced to:
        <dim>
          develop
              change-table
                  drop-location-type
              add-notification
        </dim>
        and `change-table` and `add-notification` will be rebased onto develop (fork point for this rebase is configurable, see `-d` option below).

        Note: This command doesn't delete any branches from git, just removes them from the tree of branch dependencies.

        <b>Options:</b>
          <b>-d, --down-fork-point=<down-fork-point-commit></b>    If updating by rebase, specifies the alternative fork point for downstream branches for the operation.
                                                            `git machete fork-point` overrides for downstream branches are recommended over use of this option.
                                                            See also doc for `--fork-point` option in `git machete help reapply` and `git machete help update`.
                                                            Not allowed if updating by merge.

          <b>-M, --merge</b>                                       Update the downstream branch by merge rather than by rebase.

          <b>-n</b>                                                If updating by rebase, equivalent to `--no-interactive-rebase`. If updating by merge, equivalent to `--no-edit-merge`.

          <b>--no-edit-merge</b>                                   If updating by merge, skip opening the editor for merge commit message while doing `git merge` (i.e. pass `--no-edit` flag to underlying `git merge`).
                                                            Not allowed if updating by rebase.

          <b>--no-interactive-rebase</b>                           If updating by rebase, run `git rebase` in non-interactive mode (without `-i/--interactive` flag).
                                                            Not allowed if updating by merge.
    """,
    "squash": """
        <b>Usage: git machete squash [-f|--fork-point=<fork-point-commit>]</b>

        Squashes the commits belonging uniquely to the current branch into a single commit.
        The chunk of the history to be squashed starts at the automatically computed fork point of the current branch by default, but can also be set explicitly by `--fork-point`.
        See `git machete help fork-point` for more details on meaning of the "fork point".
        The message for the squashed is taken from the earliest squashed commit, i.e. the commit directly following the fork point.

        Note: the current reapplied branch does not need to occur in the definition file.

        Tip: for more complex scenarios that require rewriting the history of current branch, see `reapply` and `update`.

        <b>Options:</b>
          <b>-f, --fork-point=<fork-point-commit></b>    Specifies the alternative fork point commit after which the squashed part of history is meant to start.
    """,
    "status": """
        <b>Usage: git machete s[tatus] [--color=WHEN] [-l|--list-commits] [-L|--list-commits-with-hashes] [--no-detect-squash-merges]</b>

        Displays a tree-shaped status of the branches listed in the definition file.

        Apart from simply ASCII-formatting the definition file, this also:

        * colors the edges between upstream (parent) and downstream (children) branches:

          - <b><red>red edge</red></b> means that the downstream branch tip is <b>not a direct descendant</b> of the upstream branch tip,

          - <b><yellow>yellow edge</yellow></b> means that the downstream branch tip is a <b>direct descendant</b> of the upstream branch tip,
            but the fork point (see help on `fork-point`) of the downstream branch is <b>not equal</b> to the upstream branch tip,

          - <b><green>green edge</green></b> means that the downstream branch tip is a <b>direct descendant</b> of the upstream branch tip
            and the fork point of the downstream branch is <b>equal</b> to the upstream branch tip,

          - <b><dim>grey/dimmed edge</dim></b> means that the downstream branch has been <b>merged</b> to the upstream branch,
            detected by commit equivalency (default), or by strict detection of merge commits (if `--no-detect-squash-merges` passed).


        * prints `(untracked/ahead of <remote>/behind <remote>/diverged from [& older than] <remote>)` message if the branch is not in sync with its remote counterpart;

        * displays the custom annotations (see help on `format` and `anno`) next to each branch, if present;

        * displays the output of `machete-status-branch` hook (see help on `hooks`), if present;

        * optionally lists commits introduced on each branch if `-l`/`--list-commits` or `-L`/`--list-commits-with-hashes` is supplied.

        The currently checked-out branch is underlined.

        In case of yellow edge, use `-l` flag to show the exact location of the inferred fork point
        (which indicates e.g. what range of commits is going to be rebased when the branch is updated).
        The inferred fork point can be always overridden manually, see help on `fork-point`.

        Grey/dimmed edge suggests that the downstream branch can be slid out (see help on `slide-out` and `traverse`).

        Using colors can be disabled with a `--color` flag set to `never`.
        With `--color=always`, git machete always emits colors and with `--color=auto`, it emits colors only when standard output is connected to a terminal.
        `--color=auto` is the default. When colors are disabled, relation between branches is represented in the following way:
        <dim>
          <branch0>
          |
          o-<branch1> # green (in sync with parent)
          | |
          | x-<branch2> # red (not in sync with parent)
          |   |
          |   ?-<branch3> # yellow (in sync with parent, but parent is not the fork point)
          |
          m-<branch4> # grey (merged to parent)
        </dim>
        <b>Options:</b>
          <b>--color=WHEN</b>                      Colorize the output; WHEN can be `always`, `auto` (default; i.e. only if stdout is a terminal), or `never`.

          <b>-l, --list-commits</b>                Additionally list the commits introduced on each branch.

          <b>-L, --list-commits-with-hashes</b>    Additionally list the short hashes and messages of commits introduced on each branch.

          <b>--no-detect-squash-merges</b>         Only consider "strict" (fast-forward or 2-parent) merges, rather than rebase/squash merges,
                                            when detecting if a branch is merged into its upstream (parent).
    """,
    "traverse": """
        <b>Usage: git machete traverse [-F|--fetch] [-l|--list-commits] [-M|--merge]
                                       [-n|--no-edit-merge|--no-interactive-rebase] [--no-detect-squash-merges]
                                       [--[no-]push] [--[no-]push-untracked]
                                       [--return-to=WHERE] [--start-from=WHERE] [-w|--whole] [-W] [-y|--yes]</b>

        Traverses the branch dependency tree in pre-order (i.e. simply in the order as they occur in the definition file) and for each branch:
        * detects if the branch is merged to its parent/upstream
          - by commit equivalency (default), or by strict detection of merge commits (if `--no-detect-squash-merges` passed),
          - if so, asks the user whether to slide out the branch from the dependency tree (typically branches are longer needed after they're merged);
        * otherwise, if the branch is not in "green" sync with its parent/upstream (see help for `status`):
          - asks the user whether to rebase (default) or merge (if `--merge` passed) the branch onto into its upstream branch - equivalent to `git machete update` with no `--fork-point` option passed;

        * if the branch is not tracked on a remote, is ahead of its remote counterpart, or diverged from the counterpart & has newer head commit than the counterpart:
          - asks the user whether to push the branch (possibly with `--force-with-lease` if the branches diverged);
        * otherwise, if the branch diverged from the remote counterpart & has older head commit than the counterpart:
          - asks the user whether to `git reset --keep` the branch to its remote counterpart
        * otherwise, if the branch is behind its remote counterpart:
          - asks the user whether to pull the branch;

        * and finally, if any of the above operations has been successfully completed:
          - prints the updated `status`.

        Note that even if the traverse flow is stopped (typically due to merge/rebase conflicts), running `git machete traverse` after the merge/rebase is finished will pick up the walk where it stopped.
        In other words, there is no need to explicitly ask to "continue" as it is the case with e.g. `git rebase`.

        <b>Options:</b>
          <b>-F, --fetch</b>                  Fetch the remotes of all managed branches at the beginning of traversal (no `git pull` involved, only `git fetch`).

          <b>-l, --list-commits</b>           When printing the status, additionally list the messages of commits introduced on each branch.

          <b>-M, --merge</b>                  Update by merge rather than by rebase.

          <b>-n</b>                           If updating by rebase, equivalent to `--no-interactive-rebase`. If updating by merge, equivalent to `--no-edit-merge`.

          <b>--no-detect-squash-merges</b>    Only consider "strict" (fast-forward or 2-parent) merges, rather than rebase/squash merges,
                                       when detecting if a branch is merged into its upstream (parent).

          <b>--no-edit-merge</b>              If updating by merge, skip opening the editor for merge commit message while doing `git merge` (i.e. pass `--no-edit` flag to underlying `git merge`).
                                       Not allowed if updating by rebase.

          <b>--no-interactive-rebase</b>      If updating by rebase, run `git rebase` in non-interactive mode (without `-i/--interactive` flag).
                                       Not allowed if updating by merge.

          <b>--no-push</b>                    Do not push any (neither tracked nor untracked) branches to remote, re-enable via `--push`.

          <b>--no-push-untracked</b>          Do not push untracked branches to remote, re-enable via `--push-untracked`.

          <b>--push</b>                       Push all (both tracked and untracked) branches to remote - default behavior.

          <b>--push-untracked</b>             Push untracked branches to remote - default behavior.

          <b>--return-to=WHERE</b>            Specifies the branch to return after traversal is successfully completed; WHERE can be `here` (the current branch at the moment when traversal starts),
                                       `nearest-remaining` (nearest remaining branch in case the `here` branch has been slid out by the traversal)
                                       or `stay` (the default - just stay wherever the traversal stops).
                                       Note: when user quits by `q/yq` or when traversal is stopped because one of git actions fails, the behavior is always `stay`.

          <b>--start-from=WHERE</b>           Specifies the branch to start the traversal from; WHERE can be `here` (the default - current branch, must be managed by git-machete),
                                       `root` (root branch of the current branch, as in `git machete show root`) or `first-root` (first listed managed branch).

          <b>-w, --whole</b>                  Equivalent to `-n --start-from=first-root --return-to=nearest-remaining`;
                                       useful for quickly traversing & syncing all branches (rather than doing more fine-grained operations on the local section of the branch tree).

          <b>-W</b>                           Equivalent to `--fetch --whole`; useful for even more automated traversal of all branches.

          <b>-y, --yes</b>                    Don't ask for any interactive input, including confirmation of rebase/push/pull. Implies `-n`.
    """,
    "update": """
        <b>Usage: git machete update [-f|--fork-point=<fork-point-commit>] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase]</b>

        Synchronizes the current branch with its upstream (parent) branch either by rebase (default) or by merge (if `--merge` option passed).

        If updating by rebase, interactively rebases the current branch on the top of its upstream (parent) branch.
        The chunk of the history to be rebased starts at the fork point of the current branch, which by default is inferred automatically, but can also be set explicitly by `--fork-point`.
        See `git machete help fork-point` for more details on meaning of the "fork point".

        If updating by merge, merges the upstream (parent) branch into the current branch.

        <b>Options:</b>
          <b>-f, --fork-point=<fork-point-commit></b>    If updating by rebase, specifies the alternative fork point commit after which the rebased part of history is meant to start.
                                                  Not allowed if updating by merge.

          <b>-M, --merge</b>                             Update by merge rather than by rebase.

          <b>-n</b>                                      If updating by rebase, equivalent to `--no-interactive-rebase`. If updating by merge, equivalent to `--no-edit-merge`.

          <b>--no-edit-merge</b>                         If updating by merge, skip opening the editor for merge commit message while doing `git merge` (i.e. pass `--no-edit` flag to underlying `git merge`).
                                                  Not allowed if updating by rebase.

          <b>--no-interactive-rebase</b>                 If updating by rebase, run `git rebase` in non-interactive mode (without `-i/--interactive` flag).
                                                  Not allowed if updating by merge.
    """,
    "version": """
        <b>Usage: git machete version</b>

        Prints the version and exits.
    """
}


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

    cli_ctxt = CommandLineContext()
    machete_client = MacheteClient(cli_ctxt)

    if sys.version_info.major == 2 or (sys.version_info.major == 3 and sys.version_info.minor < 6):
        version_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        sys.stderr.write(f"Python {version_str} is no longer supported. Please switch to Python 3.6 or higher.\n")
        sys.exit(1)

    def parse_options(in_args: List[str], short_opts: str = "", long_opts: List[str] = [], gnu: bool = True) -> List[str]:
        global ascii_only

        fun = getopt.gnu_getopt if gnu else getopt.getopt
        opts, rest = fun(in_args, short_opts + "hv", long_opts + ['debug', 'help', 'verbose', 'version'])

        for opt, arg in opts:
            if opt in ("-b", "--branch"):
                cli_ctxt.opt_branch = arg
            elif opt in ("-C", "--checked-out-since"):
                cli_ctxt.opt_checked_out_since = arg
            elif opt == "--color":
                cli_ctxt.opt_color = arg
            elif opt in ("-d", "--down-fork-point"):
                cli_ctxt.opt_down_fork_point = arg
            elif opt == "--debug":
                cli_ctxt.opt_debug = True
            elif opt in ("-F", "--fetch"):
                cli_ctxt.opt_fetch = True
            elif opt in ("-f", "--fork-point"):
                cli_ctxt.opt_fork_point = arg
            elif opt in ("-H", "--sync-github-prs"):
                cli_ctxt.opt_sync_github_prs = True
            elif opt in ("-h", "--help"):
                usage(cmd)
                sys.exit()
            elif opt == "--inferred":
                cli_ctxt.opt_inferred = True
            elif opt in ("-L", "--list-commits-with-hashes"):
                cli_ctxt.opt_list_commits = cli_ctxt.opt_list_commits_with_hashes = True
            elif opt in ("-l", "--list-commits"):
                cli_ctxt.opt_list_commits = True
            elif opt in ("-M", "--merge"):
                cli_ctxt.opt_merge = True
            elif opt == "-n":
                cli_ctxt.opt_n = True
            elif opt == "--no-detect-squash-merges":
                cli_ctxt.opt_no_detect_squash_merges = True
            elif opt == "--no-edit-merge":
                cli_ctxt.opt_no_edit_merge = True
            elif opt == "--no-interactive-rebase":
                cli_ctxt.opt_no_interactive_rebase = True
            elif opt == "--no-push":
                cli_ctxt.opt_push_tracked = False
                cli_ctxt.opt_push_untracked = False
            elif opt == "--no-push-untracked":
                cli_ctxt.opt_push_untracked = False
            elif opt in ("-o", "--onto"):
                cli_ctxt.opt_onto = arg
            elif opt == "--override-to":
                cli_ctxt.opt_override_to = arg
            elif opt == "--override-to-inferred":
                cli_ctxt.opt_override_to_inferred = True
            elif opt == "--override-to-parent":
                cli_ctxt.opt_override_to_parent = True
            elif opt == "--push":
                cli_ctxt.opt_push_tracked = True
                cli_ctxt.opt_push_untracked = True
            elif opt == "--push-untracked":
                cli_ctxt.opt_push_untracked = True
            elif opt in ("-R", "--as-root"):
                cli_ctxt.opt_as_root = True
            elif opt in ("-r", "--roots"):
                cli_ctxt.opt_roots = arg.split(",")
            elif opt == "--return-to":
                cli_ctxt.opt_return_to = arg
            elif opt in ("-s", "--stat"):
                cli_ctxt.opt_stat = True
            elif opt == "--start-from":
                cli_ctxt.opt_start_from = arg
            elif opt == "--unset-override":
                cli_ctxt.opt_unset_override = True
            elif opt in ("-v", "--verbose"):
                cli_ctxt.opt_verbose = True
            elif opt == "--version":
                version()
                sys.exit()
            elif opt == "-W":
                cli_ctxt.opt_fetch = True
                cli_ctxt.opt_start_from = "first-root"
                cli_ctxt.opt_n = True
                cli_ctxt.opt_return_to = "nearest-remaining"
            elif opt in ("-w", "--whole"):
                cli_ctxt.opt_start_from = "first-root"
                cli_ctxt.opt_n = True
                cli_ctxt.opt_return_to = "nearest-remaining"
            elif opt in ("-y", "--yes"):
                cli_ctxt.opt_yes = cli_ctxt.opt_no_interactive_rebase = True

        if cli_ctxt.opt_color not in ("always", "auto", "never"):
            raise MacheteException("Invalid argument for `--color`. Valid arguments: `always|auto|never`.")
        else:
            ascii_only = cli_ctxt.opt_color == "never" or (cli_ctxt.opt_color == "auto" and not sys.stdout.isatty())

        if cli_ctxt.opt_as_root and cli_ctxt.opt_onto:
            raise MacheteException("Option `-R/--as-root` cannot be specified together with `-o/--onto`.")

        if cli_ctxt.opt_no_edit_merge and not cli_ctxt.opt_merge:
            raise MacheteException("Option `--no-edit-merge` only makes sense when using merge and must be specified together with `-M/--merge`.")
        if cli_ctxt.opt_no_interactive_rebase and cli_ctxt.opt_merge:
            raise MacheteException("Option `--no-interactive-rebase` only makes sense when using rebase and cannot be specified together with `-M/--merge`.")
        if cli_ctxt.opt_down_fork_point and cli_ctxt.opt_merge:
            raise MacheteException("Option `-d/--down-fork-point` only makes sense when using rebase and cannot be specified together with `-M/--merge`.")
        if cli_ctxt.opt_fork_point and cli_ctxt.opt_merge:
            raise MacheteException("Option `-f/--fork-point` only makes sense when using rebase and cannot be specified together with `-M/--merge`.")

        if cli_ctxt.opt_n and cli_ctxt.opt_merge:
            cli_ctxt.opt_no_edit_merge = True
        if cli_ctxt.opt_n and not cli_ctxt.opt_merge:
            cli_ctxt.opt_no_interactive_rebase = True

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
        cmd_and_args = parse_options(orig_args, gnu=False)
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
            machete_client.add(param or current_branch(cli_ctxt))
        elif cmd == "advance":
            args1 = parse_options(args, "y", ["yes"])
            expect_no_param(args1)
            machete_client.read_definition_file()
            expect_no_operation_in_progress(cli_ctxt)
            cb = current_branch(cli_ctxt)
            machete_client.expect_in_managed_branches(cb)
            machete_client.advance(cb)
        elif cmd == "anno":
            params = parse_options(args, "b:H", ["branch=", "sync-github-prs"])
            machete_client.read_definition_file(verify_branches=False)
            if cli_ctxt.opt_sync_github_prs:
                machete_client.sync_annotations_to_github_prs()
            else:
                b = cli_ctxt.opt_branch or current_branch(cli_ctxt)
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
            b = param or current_branch(cli_ctxt)
            if len(list(filter(None, [cli_ctxt.opt_inferred, cli_ctxt.opt_override_to, cli_ctxt.opt_override_to_inferred, cli_ctxt.opt_override_to_parent, cli_ctxt.opt_unset_override]))) > 1:
                long_options_string = ", ".join(map(lambda x: x.replace("=", ""), long_options))
                raise MacheteException(f"At most one of {long_options_string} options may be present")
            if cli_ctxt.opt_inferred:
                print(machete_client.fork_point(b, use_overrides=False))
            elif cli_ctxt.opt_override_to:
                machete_client.set_fork_point_override(b, cli_ctxt.opt_override_to)
            elif cli_ctxt.opt_override_to_inferred:
                machete_client.set_fork_point_override(b, machete_client.fork_point(b, use_overrides=False))
            elif cli_ctxt.opt_override_to_parent:
                u = machete_client.up_branch.get(b)
                if u:
                    machete_client.set_fork_point_override(b, u)
                else:
                    raise MacheteException(f"Branch {b} does not have upstream (parent) branch")
            elif cli_ctxt.opt_unset_override:
                machete_client.unset_fork_point_override(b)
            else:
                print(machete_client.fork_point(b, use_overrides=True))
        elif cmd in ("g", "go"):
            param = check_required_param(parse_options(args), allowed_directions(allow_current=False))
            machete_client.read_definition_file()
            expect_no_operation_in_progress(cli_ctxt)
            cb = current_branch(cli_ctxt)
            dest = machete_client.parse_direction(param, cb, allow_current=False, down_pick_mode=True)
            if dest != cb:
                go(cli_ctxt, dest)
        elif cmd == "help":
            param = check_optional_param(parse_options(args))
            # No need to read definition file.
            usage(param)
        elif cmd == "is-managed":
            param = check_optional_param(parse_options(args))
            machete_client.read_definition_file()
            b = param or current_branch_or_none(cli_ctxt)
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

                remote_counterparts_of_local_branches = map_truthy_only(lambda b: combined_counterpart_for_fetching_of_branch(cli_ctxt, b), local_branches(cli_ctxt))
                qualifying_remote_branches = excluding(remote_branches(cli_ctxt), remote_counterparts_of_local_branches)
                res = excluding(local_branches(cli_ctxt), machete_client.managed_branches) + list(map(strip_first_fragment, qualifying_remote_branches))
            elif param == "managed":
                res = machete_client.managed_branches
            elif param == "slidable":
                res = machete_client.slidable()
            elif param == "slidable-after":
                b_arg = list_args[1]
                machete_client.expect_in_managed_branches(b_arg)
                res = machete_client.slidable_after(b_arg)
            elif param == "unmanaged":
                res = excluding(local_branches(cli_ctxt), machete_client.managed_branches)
            elif param == "with-overridden-fork-point":
                res = list(filter(lambda b: machete_client.has_any_fork_point_override_config(b), local_branches(cli_ctxt)))

            if res:
                print("\n".join(res))
        elif cmd in ("l", "log"):
            param = check_optional_param(parse_options(args))
            machete_client.read_definition_file()
            machete_client.log(param or current_branch(cli_ctxt))
        elif cmd == "reapply":
            args1 = parse_options(args, "f:", ["fork-point="])
            expect_no_param(args1, ". Use `-f` or `--fork-point` to specify the fork point commit")
            machete_client.read_definition_file()
            expect_no_operation_in_progress(cli_ctxt)
            cb = current_branch(cli_ctxt)
            rebase_onto_ancestor_commit(cli_ctxt, cb, cli_ctxt.opt_fork_point or machete_client.fork_point(cb, use_overrides=True))
        elif cmd == "show":
            param = check_required_param(args[:1], allowed_directions(allow_current=True))
            branch = check_optional_param(args[1:])
            if param == "current" and branch is not None:
                raise MacheteException(f'`show current` with a branch (`{branch}`) does not make sense')
            machete_client.read_definition_file(verify_branches=False)
            print(machete_client.parse_direction(param, branch or current_branch(cli_ctxt), allow_current=True, down_pick_mode=False))
        elif cmd == "slide-out":
            params = parse_options(args, "d:Mn", ["down-fork-point=", "merge", "no-edit-merge", "no-interactive-rebase"])
            machete_client.read_definition_file()
            expect_no_operation_in_progress(cli_ctxt)
            machete_client.slide_out(params or [current_branch(cli_ctxt)])
        elif cmd == "squash":
            args1 = parse_options(args, "f:", ["fork-point="])
            expect_no_param(args1, ". Use `-f` or `--fork-point` to specify the fork point commit")
            machete_client.read_definition_file()
            expect_no_operation_in_progress(cli_ctxt)
            cb = current_branch(cli_ctxt)
            machete_client.squash(cb, cli_ctxt.opt_fork_point or machete_client.fork_point(cb, use_overrides=True))
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
            if cli_ctxt.opt_start_from not in ("here", "root", "first-root"):
                raise MacheteException("Invalid argument for `--start-from`. Valid arguments: `here|root|first-root`.")
            if cli_ctxt.opt_return_to not in ("here", "nearest-remaining", "stay"):
                raise MacheteException("Invalid argument for `--return-to`. Valid arguments: here|nearest-remaining|stay.")
            machete_client.read_definition_file()
            expect_no_operation_in_progress(cli_ctxt)
            machete_client.traverse()
        elif cmd == "update":
            args1 = parse_options(args, "f:Mn", ["fork-point=", "merge", "no-edit-merge", "no-interactive-rebase"])
            expect_no_param(args1, ". Use `-f` or `--fork-point` to specify the fork point commit")
            machete_client.read_definition_file()
            expect_no_operation_in_progress(cli_ctxt)
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
        if initial_current_directory and not directory_exists(initial_current_directory):
            nearest_existing_parent_directory = initial_current_directory
            while not directory_exists(nearest_existing_parent_directory):
                nearest_existing_parent_directory = os.path.join(nearest_existing_parent_directory, os.path.pardir)
            warn(f"current directory {initial_current_directory} no longer exists, "
                 f"the nearest existing parent directory is {os.path.abspath(nearest_existing_parent_directory)}")


if __name__ == "__main__":
    main()
