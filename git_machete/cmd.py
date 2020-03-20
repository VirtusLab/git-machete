#!/usr/bin/env python
# -*- coding: utf-8 -*-

from git_machete import __version__
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

class MacheteException(Exception):
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return str(self.parameter)


ENDC = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'
UNDERLINE = '\033[4m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[00;38;5;208m'
RED = '\033[91m'


ascii_only = False


def bold(s):
    return BOLD + s + ENDC if not ascii_only else s


def dim(s):
    return DIM + s + ENDC if not ascii_only else s


def underline(s):
    return UNDERLINE + s + ENDC if not ascii_only else s + " *"


def colored(s, color):
    return color + s + ENDC if not ascii_only else s


def vertical_bar():
    return u"│" if not ascii_only else "|"


def right_arrow():
    return u"➔" if not ascii_only else "->"


def star(f):  # tuple unpacking in lambdas
    return lambda args: f(*args)


def flat_map(func, l):
    return sum(map(func, l), [])


def map_non_null(func, l):
    return list(filter(None, map(func, l)))


def non_empty_lines(s):
    return list(filter(None, s.split("\n")))


def excluding(l, s):
    return list(filter(lambda x: x not in s, l))


def join_branch_names(bs, sep):
    return sep.join("'%s'" % x for x in bs)


def safe_input(msg):
    if sys.version_info[0] == 2:  # Python 2
        return raw_input(msg)  # noqa: F821
    else:  # Python 3
        return input(msg)


def ask_if(msg, opt_yes_msg):
    if opt_yes:
        print(opt_yes_msg)
        return 'y'
    return safe_input(msg).lower()


def pick(choices, name):
    xs = "".join("[%i] %s\n" % (idx + 1, x) for idx, x in enumerate(choices))
    msg = xs + "Specify " + name + " or hit <return> to skip: "
    try:
        idx = int(safe_input(msg)) - 1
    except ValueError:
        sys.exit(1)
    if idx not in range(len(choices)):
        raise MacheteException("Invalid index: %i" % (idx + 1))
    return choices[idx]


def debug(hdr, msg):
    if opt_debug:
        sys.stderr.write("%s: %s\n" % (bold(hdr), dim(msg)))


# To avoid displaying the same warning multiple times during a single run.
displayed_warnings = set()


def warn(msg):
    global displayed_warnings
    if msg not in displayed_warnings:
        sys.stderr.write("%s: %s\n" % (colored("Warn", RED), msg))
        displayed_warnings.add(msg)


def run_cmd(cmd, *args, **kwargs):
    return subprocess.call([cmd] + list(args), **kwargs)


def popen_cmd(cmd, *args, **kwargs):
    process = subprocess.Popen([cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    stdout, stderr = process.communicate()
    return process.returncode, stdout.decode('utf-8'), stderr.decode('utf-8')


# Git core


def cmd_shell_repr(git_cmd, args):
    def shell_escape(arg):
        return arg.replace("(", "\\(") \
            .replace(")", "\\)") \
            .replace(" ", "\\ ") \
            .replace("\t", "$'\\t'")

    return " ".join(["git", git_cmd] + list(map(shell_escape, args)))


def run_git(git_cmd, *args, **kwargs):
    flat_cmd = cmd_shell_repr(git_cmd, args)
    if opt_debug:
        sys.stderr.write(underline(flat_cmd) + "\n")
    elif opt_verbose:
        sys.stderr.write(flat_cmd + "\n")
    exit_code = run_cmd("git", git_cmd, *args)
    if not kwargs.get("allow_non_zero") and exit_code != 0:
        raise MacheteException("'%s' returned %i" % (flat_cmd, exit_code))
    if opt_debug:
        sys.stderr.write(dim("<exit code: %i>\n\n" % exit_code))
    return exit_code


def popen_git(git_cmd, *args, **kwargs):
    flat_cmd = cmd_shell_repr(git_cmd, args)
    if opt_debug:
        sys.stderr.write(underline(flat_cmd) + "\n")
    elif opt_verbose:
        sys.stderr.write(flat_cmd + "\n")
    exit_code, stdout, stderr = popen_cmd("git", git_cmd, *args)
    if opt_debug:
        if exit_code != 0:
            sys.stderr.write(colored("<exit code: %i>\n\n" % exit_code, RED))
        sys.stderr.write(dim(stdout) + "\n")
        if stderr:
            sys.stderr.write(dim("\n<stderr>:\n"))
            sys.stderr.write(colored(stderr, RED) + "\n")
    if not kwargs.get("allow_non_zero") and exit_code != 0:
        raise MacheteException("'%s' returned %i" % (flat_cmd, exit_code))
    return stdout


# Manipulation on definition file/tree of branches

def expect_in_managed_branches(b):
    if b not in managed_branches:
        raise MacheteException("Branch '%s' not found in the tree of branch dependencies. "
                               "Use 'git machete add %s' or 'git machete edit'" % (b, b))


def expect_at_least_one_managed_branch():
    if not roots:
        raise_no_branches_error()


def raise_no_branches_error():
    raise MacheteException(
        "No branches listed in %s; use 'git machete discover' or 'git machete edit', or edit %s manually." % (
            definition_file, definition_file))


def read_definition_file():
    global indent, managed_branches, down_branches, up_branch, roots, annotations

    with open(definition_file) as f:
        lines = [l.rstrip() for l in f.readlines() if not l.isspace()]

    managed_branches = []
    down_branches = {}
    up_branch = {}
    indent = None
    roots = []
    annotations = {}
    at_depth = {}
    last_depth = -1
    hint = "Edit the definition file manually with 'git machete edit'"

    for idx, l in enumerate(lines):
        pfx = "".join(itertools.takewhile(str.isspace, l))
        if pfx and not indent:
            indent = pfx

        b_a = l.strip().split(" ", 1)
        b = b_a[0]
        if len(b_a) > 1:
            annotations[b] = b_a[1]
        if b in managed_branches:
            raise MacheteException("%s, line %i: branch '%s' re-appears in the tree definition. %s" %
                                   (definition_file, idx + 1, b, hint))
        if b not in local_branches():
            raise MacheteException("%s, line %i: '%s' is not a local branch. %s" %
                                   (definition_file, idx + 1, b, hint))
        managed_branches += [b]

        if pfx:
            depth = len(pfx) // len(indent)
            if pfx != indent * depth:
                mapping = {" ": "<SPACE>", "\t": "<TAB>"}
                pfx_expanded = "".join(mapping[c] for c in pfx)
                indent_expanded = "".join(mapping[c] for c in indent)
                raise MacheteException("%s, line %i: invalid indent '%s', expected a multiply of '%s'. %s" %
                                       (definition_file, idx + 1, pfx_expanded, indent_expanded, hint))
        else:
            depth = 0

        if depth > last_depth + 1:
            raise MacheteException("%s, line %i: too much indent (level %s, expected at most %s) for the branch '%s'. %s" %
                                   (definition_file, idx + 1, depth, last_depth + 1, b, hint))
        last_depth = depth

        at_depth[depth] = b
        if depth:
            p = at_depth[depth - 1]
            up_branch[b] = p
            if p in down_branches:
                down_branches[p] += [b]
            else:
                down_branches[p] = [b]
        else:
            roots += [b]


def render_tree():
    global roots, down_branches, indent, annotations
    if not indent:
        indent = "\t"

    def render_dfs(b, depth):
        annotation = (" " + annotations[b]) if b in annotations else ""
        res = [depth * indent + b + annotation]
        for d in down_branches.get(b) or []:
            res += render_dfs(d, depth + 1)
        return res

    total = []
    for r in roots:
        total += render_dfs(r, depth=0)
    return total


def back_up_definition_file():
    shutil.copyfile(definition_file, definition_file + "~")


def save_definition_file():
    with open(definition_file, "w") as f:
        f.write("\n".join(render_tree()) + "\n")


def down(b, pick_mode):
    expect_in_managed_branches(b)
    dbs = down_branches.get(b)
    if not dbs:
        raise MacheteException("Branch '%s' has no downstream branch" % b)
    elif len(dbs) == 1:
        return dbs[0]
    elif pick_mode:
        return pick(dbs, "downstream branch")
    else:
        return "\n".join(dbs)


def first_branch(b):
    root = root_branch(b, accept_self=True, if_unmanaged=PICK_FIRST_ROOT)
    root_dbs = down_branches.get(root)
    return root_dbs[0] if root_dbs else root


def last_branch(b):
    d = root_branch(b, accept_self=True, if_unmanaged=PICK_LAST_ROOT)
    while down_branches.get(d):
        d = down_branches[d][-1]
    return d


def next_branch(b):
    expect_in_managed_branches(b)
    idx = managed_branches.index(b) + 1
    if idx == len(managed_branches):
        raise MacheteException("Branch '%s' has no successor" % b)
    return managed_branches[idx]


def prev_branch(b):
    expect_in_managed_branches(b)
    idx = managed_branches.index(b) - 1
    if idx == -1:
        raise MacheteException("Branch '%s' has no predecessor" % b)
    return managed_branches[idx]


PICK_FIRST_ROOT = 0
PICK_LAST_ROOT = -1


def root_branch(b, accept_self, if_unmanaged):
    if b not in managed_branches:
        if roots:
            if if_unmanaged == PICK_FIRST_ROOT:
                warn("%s is not a managed branch, assuming %s (the first root) instead as root" % (b, roots[0]))
                return roots[0]
            else:  # if_unmanaged == PICK_LAST_ROOT
                warn("%s is not a managed branch, assuming %s (the last root) instead as root" % (b, roots[-1]))
                return roots[-1]
        else:
            raise_no_branches_error()
    u = up_branch.get(b)
    if not u and not accept_self:
        raise MacheteException("Branch '%s' is already a root" % b)
    while u:
        b = u
        u = up_branch.get(b)
    return b


def up(b, prompt_if_inferred_msg, prompt_if_inferred_yes_opt_msg):
    if b in managed_branches:
        u = up_branch.get(b)
        if u:
            return u
        else:
            raise MacheteException("Branch '%s' has no upstream branch" % b)
    else:
        u = infer_upstream(b)
        if u:
            if prompt_if_inferred_msg:
                if ask_if(prompt_if_inferred_msg % (b, u), prompt_if_inferred_yes_opt_msg % (b, u)) in ('y', 'yes'):
                    return u
                else:
                    sys.exit(1)
            else:
                warn("branch '%s' not found in the tree of branch dependencies; the upstream has been inferred to '%s'" % (b, u))
                return u
        else:
            raise MacheteException("Branch '%s' not found in the tree of branch dependencies and its upstream could not be inferred" % b)


def add(b):
    global roots

    if b in managed_branches:
        raise MacheteException("Branch '%s' already exists in the tree of branch dependencies" % b)

    onto = opt_onto
    if onto:
        expect_in_managed_branches(onto)

    if b not in local_branches():
        out_of = ("'" + onto + "'") if onto else "the current HEAD"
        msg = "A local branch '%s' does not exist. Create (out of %s)? [y/N] " % (b, out_of)
        opt_yes_msg = "A local branch '%s' does not exist. Creating out of %s" % (b, out_of)
        if ask_if(msg, opt_yes_msg) in ('y', 'yes'):
            if roots and not onto:
                cb = current_branch_or_none()
                if cb and cb in managed_branches:
                    onto = cb
            create_branch(b, onto)
        else:
            return

    if not roots:
        roots = [b]
        print("Added branch '%s' as a new root" % b)
    else:
        if not onto:
            u = infer_upstream(b, condition=lambda x: x in managed_branches, reject_reason_message="this candidate is not a managed branch")
            if not u:
                raise MacheteException("Could not automatically infer upstream (parent) branch for '%s'.\n"
                                       "Specify the desired upstream branch with '--onto' or edit the definition file manually with 'git machete edit'" % b)
            elif u not in managed_branches:
                raise MacheteException("Inferred upstream (parent) branch for '%s' is '%s', but '%s' does not exist in the tree of branch dependencies.\n"
                                       "Specify other upstream branch with '--onto' or edit the definition file manually with 'git machete edit'" % (b, u, u))
            else:
                msg = "Add '%s' onto the inferred upstream (parent) branch '%s'? [y/N] " % (b, u)
                opt_yes_msg = "Adding '%s' onto the inferred upstream (parent) branch '%s'" % (b, u)
                if ask_if(msg, opt_yes_msg) in ('y', 'yes'):
                    onto = u
                else:
                    return

        up_branch[b] = onto
        if onto in down_branches:
            down_branches[onto].append(b)
        else:
            down_branches[onto] = [b]
        print("Added branch '%s' onto '%s'" % (b, onto))

    save_definition_file()


def annotate(b, words):
    global annotations
    if b in annotations and words == ['']:
        del annotations[b]
    else:
        annotations[b] = " ".join(words)
    save_definition_file()


def print_annotation(b):
    global annotations
    if b in annotations:
        print(annotations[b])


# Implementation of basic git or git-related commands

def is_executable(path):
    return os.access(path, os.X_OK)


def find_executable(executable):
    base, ext = os.path.splitext(executable)

    if (sys.platform == 'win32' or os.name == 'os2') and (ext != '.exe'):
        executable = executable + '.exe'

    if os.path.isfile(executable):
        return executable

    path = os.environ.get('PATH', os.defpath)
    paths = path.split(os.pathsep)
    for p in paths:
        f = os.path.join(p, executable)
        if os.path.isfile(f) and is_executable(f):
            debug("find_executable(%s)" % executable, "found %s at %s" % (executable, f))
            return f
    return None


def get_default_editor():
    # Based on the git's own algorithm for identifying the editor.
    # 'editor' (to please Debian-based systems) and 'nano' have been added.
    proposed_editor_funs = [
        ("$GIT_EDITOR", lambda: os.environ.get("GIT_EDITOR")),
        ("git config core.editor", lambda: get_config_or_none("core.editor")),
        ("editor", lambda: "editor"),
        ("$VISUAL", lambda: os.environ.get("VISUAL")),
        ("$EDITOR", lambda: os.environ.get("EDITOR")),
        ("nano", lambda: "nano"),
        ("vi", lambda: "vi")
    ]

    for name, fun in proposed_editor_funs:
        editor = fun()
        if not editor:
            debug("get_default_editor()", "'%s' is undefined" % name)
        elif not find_executable(editor):
            debug("get_default_editor()", "'%s'%s is not available" % (name, (" (" + editor + ")") if editor != name else ""))
        else:
            debug("get_default_editor()", "'%s'%s is available" % (name, (" (" + editor + ")") if editor != name else ""))
            return editor
    raise MacheteException("Cannot determine editor. Set EDITOR environment variable or edit %s directly." % definition_file)


def edit():
    return run_cmd(get_default_editor(), definition_file)


git_version = None


def get_git_version():
    global git_version
    if not git_version:
        raw = re.search(r"\d+.\d+.\d+", popen_git("version")).group(0)
        git_version = tuple(map(int, raw.split(".")))
    return git_version


root_dir = None


def get_root_dir():
    global root_dir
    if not root_dir:
        root_dir = popen_git("rev-parse", "--show-toplevel").strip()
    return root_dir


abs_git_dir = None


def get_abs_git_dir():
    global abs_git_dir
    if not abs_git_dir:
        try:
            git_dir = popen_git("rev-parse", "--git-dir").strip()
            abs_git_dir = os.path.abspath(git_dir)
        except MacheteException:
            raise MacheteException("Not a git repository")
    return abs_git_dir


def get_abs_git_subpath(*fragments):
    return os.path.join(get_abs_git_dir(), *fragments)


def parse_git_timespec_to_unix_timestamp(date):
    try:
        return int(popen_git("rev-parse", "--since=" + date).replace("--max-age=", "").strip())
    except (MacheteException, ValueError):
        raise MacheteException("Cannot parse timespec: '%s'" % date)


config_cached = None


def ensure_config_loaded():
    global config_cached
    if config_cached is None:
        config_cached = {}
        for config_line in non_empty_lines(popen_git("config", "--list")):
            k_v = config_line.split("=", 1)
            if len(k_v) == 2:
                k, v = k_v
                config_cached[k.lower()] = v


def get_config_or_none(key):
    ensure_config_loaded()
    return config_cached.get(key.lower())


def set_config(key, value):
    run_git("config", "--", key, value)
    ensure_config_loaded()
    config_cached[key.lower()] = value


def unset_config(key):
    ensure_config_loaded()
    if get_config_or_none(key):
        run_git("config", "--unset", key)
        del config_cached[key.lower()]


remotes_cached = None


def remotes():
    global remotes_cached
    if remotes_cached is None:
        remotes_cached = non_empty_lines(popen_git("remote"))
    return remotes_cached


fetch_done_for = set()


def fetch_remote(remote):
    global fetch_done_for
    if remote not in fetch_done_for:
        run_git("fetch", remote)
        fetch_done_for.add(remote)


def set_upstream_to(rb):
    run_git("branch", "--set-upstream-to", rb)


def reset_keep(to_revision):
    try:
        run_git("reset", "--keep", to_revision)
    except MacheteException:
        raise MacheteException("Cannot perform 'git reset --keep %s'. This is most likely caused by local uncommitted changes." % to_revision)


def push(remote, b, force_with_lease=False):
    if not force_with_lease:
        opt_force = []
    elif get_git_version() >= (1, 8, 5):  # earliest version of git to support 'push --force-with-lease'
        opt_force = ["--force-with-lease"]
    else:
        opt_force = ["--force"]
    args = [remote, b]
    run_git("push", "--set-upstream", *(opt_force + args))


def pull_ff_only(remote, rb):
    fetch_remote(remote)
    run_git("merge", "--ff-only", rb)
    # There's apparently no way to set remote automatically when doing 'git pull' (as opposed to 'git push'),
    # so a separate 'git branch --set-upstream-to' is needed.
    set_upstream_to(rb)


def find_short_commit_sha_by_revision(revision):
    return popen_git("rev-parse", "--short", revision + "^{commit}").rstrip()


def find_commit_sha_by_revision(revision):
    # Without ^{commit}, 'git rev-parse --verify' will not only accept references to other kinds of objects (like trees and blobs),
    # but just echo the argument (and exit successfully) even if the argument doesn't match anything in the object store.
    try:
        return popen_git("rev-parse", "--verify", "--quiet", revision + "^{commit}").rstrip()
    except MacheteException:
        return None


commit_sha_by_revision_cached = None


def commit_sha_by_revision(revision, prefix="refs/heads/"):
    global commit_sha_by_revision_cached
    if commit_sha_by_revision_cached is None:
        load_branches()
    full_revision = prefix + revision
    if full_revision not in commit_sha_by_revision_cached:
        commit_sha_by_revision_cached[full_revision] = find_commit_sha_by_revision(full_revision)
    return commit_sha_by_revision_cached[full_revision]


committer_unix_timestamp_by_revision_cached = None


def committer_unix_timestamp_by_revision(revision, prefix="refs/heads/"):
    global committer_unix_timestamp_by_revision_cached
    if committer_unix_timestamp_by_revision_cached is None:
        load_branches()
    return committer_unix_timestamp_by_revision_cached.get(prefix + revision) or 0


def inferred_remote_for_fetching_of_branch(b):
    # Since many people don't use '--set-upstream' flag of 'push', we try to infer the remote instead.
    for r in remotes():
        if r + "/" + b in remote_branches():
            return r
    return None


def strict_remote_for_fetching_of_branch(b):
    remote = get_config_or_none("branch." + b + ".remote")
    return remote.rstrip() if remote else None


def combined_remote_for_fetching_of_branch(b):
    return strict_remote_for_fetching_of_branch(b) or inferred_remote_for_fetching_of_branch(b)


def inferred_counterpart_for_fetching_of_branch(b):
    for r in remotes():
        if r + "/" + b in remote_branches():
            return r + "/" + b
    return None


counterparts_for_fetching_cached = None


def strict_counterpart_for_fetching_of_branch(b):
    global counterparts_for_fetching_cached
    if counterparts_for_fetching_cached is None:
        load_branches()
    return counterparts_for_fetching_cached.get(b)


def combined_counterpart_for_fetching_of_branch(b):
    # Since many people don't use '--set-upstream' flag of 'push' or 'branch', we try to infer the remote if the tracking data is missing.
    return strict_counterpart_for_fetching_of_branch(b) or inferred_counterpart_for_fetching_of_branch(b)


def is_am_in_progress():
    # As of git 2.24.1, this is how 'cmd_rebase()' in builtin/rebase.c checks whether am is in progress.
    return os.path.isfile(get_abs_git_subpath("rebase-apply", "applying"))


def is_cherry_pick_in_progress():
    return os.path.isfile(get_abs_git_subpath("CHERRY_PICK_HEAD"))


def is_merge_in_progress():
    return os.path.isfile(get_abs_git_subpath("MERGE_HEAD"))


def is_revert_in_progress():
    return os.path.isfile(get_abs_git_subpath("REVERT_HEAD"))


# Note: while rebase is ongoing, the repository is always in a detached HEAD state,
# so we need to extract the name of the currently rebased branch from the rebase-specific internals
# rather than rely on 'git symbolic-ref HEAD` (i.e. .git/HEAD).
def currently_rebased_branch_or_none():
    # https://stackoverflow.com/questions/3921409

    head_name_file = None

    # .git/rebase-merge directory exists during cherry-pick-powered rebases,
    # e.g. all interactive ones and the ones where '--strategy=' or '--keep-empty' option has been passed
    rebase_merge_head_name_file = get_abs_git_subpath("rebase-merge", "head-name")
    if os.path.isfile(rebase_merge_head_name_file):
        head_name_file = rebase_merge_head_name_file

    # .git/rebase-apply directory exists during the remaining, i.e. am-powered rebases, but also during am sessions.
    rebase_apply_head_name_file = get_abs_git_subpath("rebase-apply", "head-name")
    # Most likely .git/rebase-apply/head-name can't exist during am sessions, but it's better to be safe.
    if not is_am_in_progress() and os.path.isfile(rebase_apply_head_name_file):
        head_name_file = rebase_apply_head_name_file

    if not head_name_file:
        return None
    with open(head_name_file) as f:
        raw = f.read().strip()
        return re.sub("^refs/heads/", "", raw)


def currently_checked_out_branch_or_none():
    try:
        raw = popen_git("symbolic-ref", "--quiet", "HEAD").strip()
        return re.sub("^refs/heads/", "", raw)
    except MacheteException:
        return None


def expect_no_operation_in_progress():
    rb = currently_rebased_branch_or_none()
    if rb:
        raise MacheteException("Rebase of '%s' in progress. Conclude the rebase first with 'git rebase --continue' or 'git rebase --abort'." % rb)
    if is_am_in_progress():
        raise MacheteException("'git am' session in progress. Conclude 'git am' first with 'git am --continue' or 'git am --abort'.")
    if is_cherry_pick_in_progress():
        raise MacheteException("Cherry pick in progress. Conclude the cherry pick first with 'git cherry-pick --continue' or 'git cherry-pick --abort'.")
    if is_merge_in_progress():
        raise MacheteException("Merge in progress. Conclude the merge first with 'git merge --continue' or 'git merge --abort'.")
    if is_revert_in_progress():
        raise MacheteException("Revert in progress. Conclude the revert first with 'git revert --continue' or 'git revert --abort'.")


def current_branch_or_none():
    return currently_checked_out_branch_or_none() or currently_rebased_branch_or_none()


def current_branch():
    result = current_branch_or_none()
    if not result:
        raise MacheteException("Not currently on any branch")
    return result


merge_base_cached = {}


def merge_base(sha1, sha2):
    if sha1 > sha2:
        sha1, sha2 = sha2, sha1
    if not (sha1, sha2) in merge_base_cached:
        merge_base_cached[sha1, sha2] = popen_git("merge-base", sha1, sha2).rstrip()
    return merge_base_cached[sha1, sha2]


# Note: the 'git rev-parse --verify' validation is not performed in case for either of earlier/later
# if the corresponding prefix is empty AND the revision is a 40 hex digit hash.
def is_ancestor(earlier_revision, later_revision, earlier_prefix="refs/heads/", later_prefix="refs/heads/"):
    if earlier_prefix == "" and re.match("^[0-9a-f]{40}$", earlier_revision):
        earlier_sha = earlier_revision
    else:
        earlier_sha = commit_sha_by_revision(earlier_revision, earlier_prefix)
    if later_prefix == "" and re.match("^[0-9a-f]{40}$", later_revision):
        later_sha = later_revision
    else:
        later_sha = commit_sha_by_revision(later_revision, later_prefix)
    if earlier_sha == later_sha:
        return True
    return merge_base(earlier_sha, later_sha) == earlier_sha


def create_branch(b, out_of):
    return run_git("checkout", "-b", b, *(["refs/heads/" + out_of] if out_of else []))


def log_shas(revision, max_count):
    opts = (["--max-count=" + str(max_count)] if max_count else []) + ["--format=%H", "refs/heads/" + revision]
    return non_empty_lines(popen_git("log", *opts))


MAX_COUNT_FOR_INITIAL_LOG = 10

initial_log_shas_cached = {}
remaining_log_shas_cached = {}


# Since getting the full history of a branch can be an expensive operation for large repositories (compared to all other underlying git operations),
# there's a simple optimization in place: we first fetch only a couple of first commits in the history,
# and only fetch the rest if none of them occurs on reflog of any other branch.
def spoonfeed_log_shas(b):
    if b not in initial_log_shas_cached:
        initial_log_shas_cached[b] = log_shas(b, max_count=MAX_COUNT_FOR_INITIAL_LOG)
    for sha in initial_log_shas_cached[b]:
        yield sha

    if b not in remaining_log_shas_cached:
        remaining_log_shas_cached[b] = log_shas(b, max_count=None)[MAX_COUNT_FOR_INITIAL_LOG:]
    for sha in remaining_log_shas_cached[b]:
        yield sha


local_branches_cached = None
remote_branches_cached = None


def local_branches():
    global local_branches_cached, remote_branches_cached
    if local_branches_cached is None:
        load_branches()
    return local_branches_cached


def remote_branches():
    global local_branches_cached, remote_branches_cached
    if remote_branches_cached is None:
        load_branches()
    return remote_branches_cached


def load_branches():
    global commit_sha_by_revision_cached, committer_unix_timestamp_by_revision_cached, counterparts_for_fetching_cached, local_branches_cached, remote_branches_cached
    commit_sha_by_revision_cached = {}
    committer_unix_timestamp_by_revision_cached = {}
    counterparts_for_fetching_cached = {}
    local_branches_cached = []
    remote_branches_cached = []

    # Using 'committerdate:raw' instead of 'committerdate:unix' since the latter isn't supported by some older versions of git.
    raw_remote = non_empty_lines(popen_git("for-each-ref", "--format=%(refname)\t%(objectname)\t%(committerdate:raw)", "refs/remotes"))
    for line in raw_remote:
        values = line.split("\t")
        if len(values) != 3:  # invalid, shouldn't happen
            continue
        b, sha, committer_unix_timestamp = values
        b_stripped = re.sub("^refs/remotes/", "", b)
        remote_branches_cached += [b_stripped]
        commit_sha_by_revision_cached[b] = sha
        committer_unix_timestamp_by_revision_cached[b] = int(committer_unix_timestamp.split(' ')[0])

    raw_local = non_empty_lines(popen_git("for-each-ref", "--format=%(refname)\t%(objectname)\t%(committerdate:raw)\t%(upstream)", "refs/heads"))

    for line in raw_local:
        values = line.split("\t")
        if len(values) != 4:  # invalid, shouldn't happen
            continue
        b, sha, committer_unix_timestamp, fetch_counterpart = values
        b_stripped = re.sub("^refs/heads/", "", b)
        fetch_counterpart_stripped = re.sub("^refs/remotes/", "", fetch_counterpart)
        local_branches_cached += [b_stripped]
        commit_sha_by_revision_cached[b] = sha
        committer_unix_timestamp_by_revision_cached[b] = int(committer_unix_timestamp.split(' ')[0])
        if fetch_counterpart_stripped in remote_branches_cached:
            counterparts_for_fetching_cached[b_stripped] = fetch_counterpart_stripped


def merged_local_branches():
    return list(map(
        lambda b: re.sub("^refs/heads/", "", b),
        non_empty_lines(popen_git("for-each-ref", "--format=%(refname)", "--merged", "HEAD", "refs/heads"))
    ))


def go(branch):
    run_git("checkout", "--quiet", branch, "--")


def get_hook_path(hook_name):
    hook_dir = get_config_or_none("core.hooksPath") or get_abs_git_subpath("hooks")
    return os.path.join(hook_dir, hook_name)


def check_hook_executable(hook_path):
    if not os.path.isfile(hook_path):
        return False
    elif not is_executable(hook_path):
        advice_ignored_hook = get_config_or_none("advice.ignoredHook")
        if advice_ignored_hook != 'false':  # both empty and "true" is okay
            # The [33m color must be used to keep consistent with how git colors this advice for its built-in hooks.
            sys.stderr.write(colored("hint: The '%s' hook was ignored because it's not set as executable." % hook_path, YELLOW) + "\n")
            sys.stderr.write(colored("hint: You can disable this warning with `git config advice.ignoredHook false`.", YELLOW) + "\n")
        return False
    else:
        return True


def merge(branch, into):  # refs/heads/ prefix is assumed for 'branch'
    extra_params = ["--no-edit"] if opt_no_edit_merge else ["--edit"]
    # We need to specify the message explicitly to avoid 'refs/heads/' prefix getting into the message...
    commit_message = "Merge branch '%s' into %s" % (branch, into)
    # ...since we prepend 'refs/heads/' to the merged branch name for unambiguity.
    run_git("merge", "-m", commit_message, "refs/heads/" + branch, *extra_params)


def rebase(onto, fork_commit, branch):
    def do_rebase():
        try:
            if opt_no_interactive_rebase:
                run_git("rebase", "--onto", onto, fork_commit, branch)
            else:
                run_git("rebase", "--interactive", "--onto", onto, fork_commit, branch)
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
            # only <git-dir>/rebase-merge/author-script (i.e. interactive rebases, for the most part) are affected.
            author_script = get_abs_git_subpath("rebase-merge", "author-script")
            if os.path.isfile(author_script):
                faulty_line_regex = re.compile("[A-Z0-9_]+='[^']*")

                def fix_if_needed(line):
                    return (line.rstrip() + "'\n") if faulty_line_regex.fullmatch(line) else line

                def get_all_lines_fixed():
                    with open(author_script) as f_read:
                        return map(fix_if_needed, f_read.readlines())

                fixed_lines = get_all_lines_fixed()  # must happen before the `with` clause where we open for writing
                with open(author_script, "w") as f_write:
                    f_write.write("".join(fixed_lines))

    hook_path = get_hook_path("machete-pre-rebase")
    if check_hook_executable(hook_path):
        debug("rebase(%s, %s, %s)" % (onto, fork_commit, branch), "running machete-pre-rebase hook (%s)" % hook_path)
        exit_code = run_cmd(hook_path, onto, fork_commit, branch, cwd=get_root_dir())
        if exit_code == 0:
            do_rebase()
        else:
            sys.stderr.write("The machete-pre-rebase hook refused to rebase.\n")
            sys.exit(exit_code)
    else:
        do_rebase()


def rebase_onto_ancestor_commit(branch, ancestor_commit):
    rebase(ancestor_commit, ancestor_commit, branch)


def update():
    cb = current_branch()
    if opt_merge:
        with_branch = up(cb,
                         prompt_if_inferred_msg="Branch '%s' not found in the tree of branch dependencies. Merge with the inferred upstream '%s'? [y/N] ",
                         prompt_if_inferred_yes_opt_msg="Branch '%s' not found in the tree of branch dependencies. Merging with the inferred upstream '%s'...")
        merge(with_branch, cb)
    else:
        onto_branch = up(cb,
                         prompt_if_inferred_msg="Branch '%s' not found in the tree of branch dependencies. Rebase onto the inferred upstream '%s'? [y/N] ",
                         prompt_if_inferred_yes_opt_msg="Branch '%s' not found in the tree of branch dependencies. Rebasing onto the inferred upstream '%s'...")
        rebase("refs/heads/" + onto_branch, opt_fork_point or fork_point(cb, use_overrides=True), cb)


def diff(branch):
    params = \
        (["--stat"] if opt_stat else []) + \
        [fork_point(branch if branch else current_branch(), use_overrides=True)] + \
        (["refs/heads/" + branch] if branch else []) + \
        ["--"]
    run_git("diff", *params)


def log(branch):
    run_git("log", "^" + fork_point(branch, use_overrides=True), "refs/heads/" + branch)


def commits_between(earlier, later):
    return list(map(lambda x: x.split(":", 2), non_empty_lines(popen_git("log", "--format=%H:%h:%s", "^" + earlier, later, "--"))))


NO_REMOTES = 0
UNTRACKED = 1
IN_SYNC_WITH_REMOTE = 2
BEHIND_REMOTE = 3
AHEAD_OF_REMOTE = 4
DIVERGED_FROM_AND_OLDER_THAN_REMOTE = 5
DIVERGED_FROM_AND_NEWER_THAN_REMOTE = 6


def get_relation_to_remote_counterpart(b, rb):
    b_is_anc_of_rb = is_ancestor(b, rb, later_prefix="refs/remotes/")
    rb_is_anc_of_b = is_ancestor(rb, b, earlier_prefix="refs/remotes/")
    if b_is_anc_of_rb:
        return IN_SYNC_WITH_REMOTE if rb_is_anc_of_b else BEHIND_REMOTE
    elif rb_is_anc_of_b:
        return AHEAD_OF_REMOTE
    else:
        b_t = committer_unix_timestamp_by_revision(b, "refs/heads/")
        rb_t = committer_unix_timestamp_by_revision(rb, "refs/remotes/")
        return DIVERGED_FROM_AND_OLDER_THAN_REMOTE if b_t < rb_t else DIVERGED_FROM_AND_NEWER_THAN_REMOTE


def get_strict_remote_sync_status(b):
    if not remotes():
        return NO_REMOTES, None
    rb = strict_counterpart_for_fetching_of_branch(b)
    if not rb:
        return UNTRACKED, None
    return get_relation_to_remote_counterpart(b, rb), strict_remote_for_fetching_of_branch(b)


def get_combined_remote_sync_status(b):
    if not remotes():
        return NO_REMOTES, None
    rb = combined_counterpart_for_fetching_of_branch(b)
    if not rb:
        return UNTRACKED, None
    return get_relation_to_remote_counterpart(b, rb), combined_remote_for_fetching_of_branch(b)


# Reflog magic


reflogs_cached = None


def load_all_reflogs():
    global reflogs_cached
    # %gd - reflog selector (refname@{num})
    # %H - full hash
    # %gs - reflog subject
    all_branches = ["refs/heads/" + b for b in local_branches()] + \
                   ["refs/remotes/" + combined_counterpart_for_fetching_of_branch(b) for b in local_branches() if combined_counterpart_for_fetching_of_branch(b)]
    # The trailing '--' is necessary to avoid ambiguity in case there is a file called just exactly like one of the branches.
    entries = non_empty_lines(popen_git("reflog", "show", "--format=%gD\t%H\t%gs", *(all_branches + ["--"])))
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


def reflog(b):
    global reflogs_cached
    # git version 2.14.2 fixed a bug that caused fetching reflog of more than
    # one branch at the same time unreliable in certain cases
    if get_git_version() >= (2, 14, 2):
        if reflogs_cached is None:
            load_all_reflogs()
        return reflogs_cached.get(b) or []
    else:
        if reflogs_cached is None:
            reflogs_cached = {}
        if b not in reflogs_cached:
            # %H - full hash
            # %gs - reflog subject
            reflogs_cached[b] = [
                entry.split(":", 1) for entry in non_empty_lines(
                    # The trailing '--' is necessary to avoid ambiguity in case there is a file called just exactly like the branch 'b'.
                    popen_git("reflog", "show", "--format=%H:%gs", b, "--"))
            ]
        return reflogs_cached[b]


def adjusted_reflog(b, prefix):
    def is_excluded_reflog_subject(sha_, gs_):
        is_excluded = (
            gs_.startswith("branch: Created from") or
            gs_ == "branch: Reset to " + b or
            gs_ == "branch: Reset to HEAD" or
            gs_.startswith("reset: moving to ") or
            gs_ == "rebase finished: %s/%s onto %s" % (prefix, b, sha_)  # the rare case of a no-op rebase
        )
        if is_excluded:
            debug("adjusted_reflog(%s, %s) -> is_excluded_reflog_subject(%s, <<<%s>>>)" % (b, prefix, sha_, gs_), "skipping reflog entry")
        return is_excluded

    b_reflog = reflog(prefix + b)
    if not b_reflog:
        return []

    earliest_sha, earliest_gs = b_reflog[-1]  # Note that the reflog is returned from latest to earliest entries.
    shas_to_exclude = set()
    if earliest_gs.startswith("branch: Created from"):
        shas_to_exclude.add(earliest_sha)
    debug("adjusted_reflog(%s, %s)" % (b, prefix), "also, skipping any reflog entry with the hash in %s" % shas_to_exclude)

    result = [sha for (sha, gs) in reflog(prefix + b) if sha not in shas_to_exclude and not is_excluded_reflog_subject(sha, gs)]
    debug("adjusted_reflog(%s, %s)" % (b, prefix), "computed adjusted reflog (= reflog without branch creation and branch reset events irrelevant for fork point/upstream inference): %s\n" %
          (", ".join(result) or "<empty>"))
    return result


def get_latest_checkout_timestamps():
    # Entries are in the format '<branch_name>@{unix_timestamp}'
    result = {}
    # %gd - reflog selector (HEAD@{unix timestamp})
    # %gs - reflog subject
    output = popen_git("reflog", "show", "--format=%gd:%gs", "--date=unix")
    for entry in non_empty_lines(output):
        pattern = "^HEAD@\\{([0-9]+)\\}:checkout: moving from (.+) to (.+)$"
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


branch_defs_by_sha_in_reflog = None


def match_log_to_adjusted_reflogs(b):
    global branch_defs_by_sha_in_reflog

    if b not in local_branches():
        raise MacheteException("'%s' is not a local branch" % b)

    if branch_defs_by_sha_in_reflog is None:
        def generate_entries():
            for lb in local_branches():
                lb_shas = set()
                for sha_ in adjusted_reflog(lb, "refs/heads/"):
                    lb_shas.add(sha_)
                    yield sha_, (lb, lb)
                rb = combined_counterpart_for_fetching_of_branch(lb)
                if rb:
                    for sha_ in adjusted_reflog(rb, "refs/remotes/"):
                        if sha_ not in lb_shas:
                            yield sha_, (lb, rb)

        branch_defs_by_sha_in_reflog = {}
        for sha, branch_def in generate_entries():
            if sha in branch_defs_by_sha_in_reflog:
                # The practice shows that it's rather unlikely for a given commit to appear on adjusted reflogs of two unrelated branches
                # ("unrelated" as in, not a local branch and its remote counterpart) but we need to handle this case anyway.
                branch_defs_by_sha_in_reflog[sha] += [branch_def]
            else:
                branch_defs_by_sha_in_reflog[sha] = [branch_def]

        def log_result():
            for sha_, branch_defs in branch_defs_by_sha_in_reflog.items():
                yield dim("%s => %s" %
                          (sha_, ", ".join(map(star(lambda lb, lb_or_rb: lb if lb == lb_or_rb else "%s (remote counterpart of %s)" % (lb_or_rb, lb)), branch_defs))))

        debug("match_log_to_adjusted_reflogs(%s)" % b, "branches containing the given SHA in their adjusted reflog: \n%s\n" % "\n".join(log_result()))

    for sha in spoonfeed_log_shas(b):
        if sha in branch_defs_by_sha_in_reflog:
            containing_branch_defs = list(filter(star(lambda lb, lb_or_rb: lb != b), branch_defs_by_sha_in_reflog[sha]))
            if containing_branch_defs:
                debug("match_log_to_adjusted_reflogs(%s)" % b, "commit %s found in adjusted reflog of %s" % (sha, " and ".join(map(star(lambda lb, lb_or_rb: lb_or_rb), branch_defs_by_sha_in_reflog[sha]))))
                yield sha, containing_branch_defs
            else:
                debug("match_log_to_adjusted_reflogs(%s)" % b, "commit %s found only in adjusted reflog of %s; ignoring" % (sha, " and ".join(map(star(lambda lb, lb_or_rb: lb_or_rb), branch_defs_by_sha_in_reflog[sha]))))
        else:
            debug("match_log_to_adjusted_reflogs(%s)" % b, "commit %s not found in any adjusted reflog" % sha)


# Complex routines/commands

def is_merged_to_parent(b):
    if b not in up_branch:
        return False
    u = up_branch[b]
    equal_to_parent = commit_sha_by_revision(u) == commit_sha_by_revision(b)

    # If a branch is NOT equal to parent, it's just enough to check if the
    # parent is reachable from the branch.
    # If branch is equal to parent, then we need to distinguish between the
    # case of branch being "recently" created from the parent and the case of
    # branch being fast-forward merged to the parent.
    # The applied heuristics is to check if the adjusted reflog of the branch
    # (reflog stripped of trivial events like branch creation, reset etc.)
    # is non-empty.
    return (not equal_to_parent and is_ancestor(b, u)) or \
        (equal_to_parent and adjusted_reflog(b, prefix="refs/heads/"))


def infer_upstream(b, condition=lambda u: True, reject_reason_message=""):
    for sha, containing_branch_defs in match_log_to_adjusted_reflogs(b):
        debug("infer_upstream(%s)" % b, "commit %s found in adjusted reflog of %s" % (sha, " and ".join(map(star(lambda x, y: y), containing_branch_defs))))

        for candidate, original_matched_branch in containing_branch_defs:
            if candidate != original_matched_branch:
                debug("infer_upstream(%s)" % b, "upstream candidate is %s, which is the local counterpart of %s" % (candidate, original_matched_branch))

            if condition(candidate):
                debug("infer_upstream(%s)" % b, "upstream candidate %s accepted" % candidate)
                return candidate
            else:
                debug("infer_upstream(%s)" % b, "upstream candidate %s rejected (%s)" % (candidate, reject_reason_message))
    return None


def discover_tree():
    global managed_branches, roots, down_branches, up_branch, indent, annotations, opt_checked_out_since, opt_roots
    all_local_branches = local_branches()
    if not all_local_branches:
        raise MacheteException("No local branches found")
    for r in opt_roots:
        if r not in local_branches():
            raise MacheteException("'%s' is not a local branch" % r)
    roots = list(opt_roots)
    down_branches = {}
    up_branch = {}
    indent = "\t"
    annotations = {}

    root_of = dict((b, b) for b in all_local_branches)

    def get_root_of(b):
        if b != root_of[b]:
            root_of[b] = get_root_of(root_of[b])
        return root_of[b]

    non_root_fixed_branches = excluding(all_local_branches, opt_roots)
    if opt_checked_out_since:
        threshold = parse_git_timespec_to_unix_timestamp(opt_checked_out_since)
        last_checkout_timestamps = get_latest_checkout_timestamps()
        stale_branches = [b for b in non_root_fixed_branches if
                          b not in last_checkout_timestamps or
                          last_checkout_timestamps[b] < threshold]
    else:
        stale_branches = []
    managed_branches = excluding(all_local_branches, stale_branches)
    if not managed_branches:
        warn("no branches satisfying the criteria. Try moving the value of '--checked-out-since' further to the past.")
        return

    for b in excluding(non_root_fixed_branches, stale_branches):
        u = infer_upstream(b,
                           condition=lambda x: get_root_of(x) != b and x not in stale_branches,
                           reject_reason_message="choosing this candidate would form a cycle in the resulting graph or the candidate is a stale branch"
                           )
        if u:
            debug("discover_tree()", "inferred upstream of %s is %s, attaching %s as a child of %s\n" % (b, u, b, u))
            up_branch[b] = u
            root_of[b] = u
            if u in down_branches:
                down_branches[u].append(b)
            else:
                down_branches[u] = [b]
        else:
            debug("discover_tree()", "inferred no upstream for %s, attaching %s as a new root\n" % (b, b))
            roots += [b]

    print(bold('Discovered tree of branch dependencies:\n'))
    status(warn_on_yellow_edges=False)
    print("")
    do_backup = os.path.isfile(definition_file)
    backup_msg = ("The existing definition file will be backed up as '%s~' " % definition_file) if do_backup else ""
    msg = "Save the above tree to '%s'? %s([y]es/[e]dit/[N]o) " % (definition_file, backup_msg)
    opt_yes_msg = "Saving the above tree to '%s'... %s" % (definition_file, backup_msg)
    ans = ask_if(msg, opt_yes_msg)
    if ans in ('y', 'yes'):
        if do_backup:
            back_up_definition_file()
        save_definition_file()
    elif ans in ('e', 'edit'):
        if do_backup:
            back_up_definition_file()
        save_definition_file()
        edit()


def fork_point_and_containing_branch_defs(b, use_overrides):
    global up_branch
    u = up_branch.get(b)

    if use_overrides:
        overridden_fp_sha = get_overridden_fork_point(b)
        if overridden_fp_sha:
            if u and is_ancestor(u, b) and not is_ancestor(u, overridden_fp_sha, later_prefix=""):
                # We need to handle the case when b is a descendant of u,
                # but the fork point of is overridden to a commit that is NOT a descendant of u.
                # In this case it's more reasonable to assume that u (and not overridden_fp_sha) is the fork point.
                debug("fork_point_and_containing_branch_defs(%s)" % b,
                      "%s is descendant of its upstream %s, but overridden fork point commit %s is NOT a descendant of %s; falling back to %s as fork point" % (u, b, overridden_fp_sha, u, u))
                return commit_sha_by_revision(u), []
            else:
                debug("fork_point_and_containing_branch_defs(%s)" % b,
                      "fork point of %s is overridden to %s; skipping inference" % (b, overridden_fp_sha))
                return overridden_fp_sha, []

    try:
        fp_sha, containing_branch_defs = next(match_log_to_adjusted_reflogs(b))
    except StopIteration:
        if u and is_ancestor(u, b):
            debug("fork_point_and_containing_branch_defs(%s)" % b,
                  "cannot find fork point, but %s is descendant of its upstream %s; falling back to %s as fork point" % (b, u, u))
            return commit_sha_by_revision(u), []
        else:
            raise MacheteException("Cannot find fork point for branch '%s'" % b)
    else:
        debug("fork_point_and_containing_branch_defs(%s)" % b,
              "commit %s is the most recent point in history of %s to occur on "
              "adjusted reflog of any other branch or its remote counterpart "
              "(specifically: %s)" % (fp_sha, b, " and ".join(map(star(lambda lb, lb_or_rb: lb_or_rb), containing_branch_defs))))

        if u and is_ancestor(u, b) and not is_ancestor(u, fp_sha, later_prefix=""):
            # That happens very rarely in practice (typically current head of any branch, including u, should occur on the reflog of this
            # branch, thus is_ancestor(u, b) should implicate is_ancestor(u, FP(b)), but it's still possible in case reflog of
            # u is incomplete for whatever reason.
            debug("fork_point_and_containing_branch_defs(%s)" % b,
                  "%s is descendant of its upstream %s, but inferred fork point commit %s is NOT a descendant of %s; falling back to %s as fork point" % (u, b, fp_sha, u, u))
            return commit_sha_by_revision(u), []
        else:
            debug("fork_point_and_containing_branch_defs(%s)" % b,
                  "choosing commit %s as fork point" % fp_sha)
            return fp_sha, containing_branch_defs


def fork_point(b, use_overrides):
    sha, containing_branch_defs = fork_point_and_containing_branch_defs(b, use_overrides)
    return sha


def config_key_for_override_fork_point_to(b):
    return "machete.overrideForkPoint." + b + ".to"


def config_key_for_override_fork_point_while_descendant_of(b):
    return "machete.overrideForkPoint." + b + ".whileDescendantOf"


# Also includes config that is incomplete (only one entry out of two) or otherwise invalid.
def has_any_fork_point_override_config(b):
    return (get_config_or_none(config_key_for_override_fork_point_to(b)) or
            get_config_or_none(config_key_for_override_fork_point_while_descendant_of(b))) is not None


def get_fork_point_override_data(b):
    to_key = config_key_for_override_fork_point_to(b)
    to = get_config_or_none(to_key)
    while_descendant_of_key = config_key_for_override_fork_point_while_descendant_of(b)
    while_descendant_of = get_config_or_none(while_descendant_of_key)
    if not to and not while_descendant_of:
        return None
    if to and not while_descendant_of:
        warn("%s config is set but %s config is missing" % (to_key, while_descendant_of_key))
        return None
    if not to and while_descendant_of:
        warn("%s config is set but %s config is missing" % (while_descendant_of_key, to_key))
        return None

    to_sha = commit_sha_by_revision(to, prefix="")
    while_descendant_of_sha = commit_sha_by_revision(while_descendant_of, prefix="")
    if not to_sha or not while_descendant_of_sha:
        if not to_sha:
            warn("%s config's value '%s' does not point to a valid commit" % (to_key, to))
        if not while_descendant_of_sha:
            warn("%s config's value '%s' does not point to a valid commit" % (while_descendant_of_key, while_descendant_of))
        return None
    # This check needs to be performed every time the config is retrieved.
    # We can't rely on the values being validated in set_fork_point_override(), since the config could have been modified outside of git-machete.
    if not is_ancestor(to_sha, while_descendant_of_sha, earlier_prefix="", later_prefix=""):
        warn("commit %s pointed by %s config is not an ancestor of commit %s pointed by %s config" % (to, to_key, while_descendant_of, while_descendant_of_key))
        return None
    return to_sha, while_descendant_of_sha


def get_overridden_fork_point(b):
    override_data = get_fork_point_override_data(b)
    if not override_data:
        return None

    to, while_descendant_of = override_data
    # Note that this check is distinct from the is_ancestor check performed in get_fork_point_override_data.
    # While the latter checks the sanity of fork point override configuration,
    # the former checks if the override still applies to wherever the given branch currently points.
    if not is_ancestor(while_descendant_of, b, earlier_prefix=""):
        warn("since branch %s is no longer a descendant of commit %s, the fork point override to commit %s no longer applies.\n"
             "Consider running 'git machete fork-point --unset-override %s'." % (b, while_descendant_of, to, b))
        return None
    debug("get_overridden_fork_point(%s)" % b,
          "since branch %s is descendant of while_descendant_of=%s, fork point of %s is overridden to %s" % (b, while_descendant_of, b, to))
    return to


def set_fork_point_override(b, to_revision):
    if b not in local_branches():
        raise MacheteException("'%s' is not a local branch" % b)
    to_sha = commit_sha_by_revision(to_revision, prefix="")
    if not to_sha:
        raise MacheteException("Cannot find revision %s" % to_revision)
    if not is_ancestor(to_sha, b, earlier_prefix=""):
        raise MacheteException("Cannot override fork point: %s (commit %s) is not an ancestor of %s" % (to_revision, find_short_commit_sha_by_revision(to_sha), b))

    to_key = config_key_for_override_fork_point_to(b)
    set_config(to_key, to_sha)

    while_descendant_of_key = config_key_for_override_fork_point_while_descendant_of(b)
    b_sha = commit_sha_by_revision(b, prefix="refs/heads/")
    set_config(while_descendant_of_key, b_sha)

    sys.stdout.write("Fork point for %s is overridden to %s (commit %s).\nThis is going to apply as long as %s points to (or is descendant of) its current head (commit %s).\n\n"
                     % (bold(b), bold(to_revision), find_short_commit_sha_by_revision(to_sha), b, find_short_commit_sha_by_revision(b_sha)))
    sys.stdout.write("This information is stored under git config keys:\n  * %s\n  * %s\n\n" % (to_key, while_descendant_of_key))
    sys.stdout.write("To unset this override, use:\n  git machete fork-point --unset-override %s\n" % b)


def unset_fork_point_override(b):
    unset_config(config_key_for_override_fork_point_to(b))
    unset_config(config_key_for_override_fork_point_while_descendant_of(b))


def delete_unmanaged():
    branches_to_delete = excluding(local_branches(), managed_branches)
    cb = current_branch_or_none()
    if cb and cb in branches_to_delete:
        branches_to_delete = excluding(branches_to_delete, [cb])
        print("Skipping current branch '%s'" % cb)
    if branches_to_delete:
        branches_merged_to_head = merged_local_branches()

        branches_to_delete_merged_to_head = [b for b in branches_to_delete if b in branches_merged_to_head]
        for b in branches_to_delete_merged_to_head:
            rb = strict_counterpart_for_fetching_of_branch(b)
            is_merged_to_remote = is_ancestor(b, rb, later_prefix="refs/remotes/") if rb else True
            msg_core = "%s (merged to HEAD%s)" % (bold(b), "" if is_merged_to_remote else (", but not merged to " + rb))
            msg = "Delete branch %s? [y/N/q] " % msg_core
            opt_yes_msg = "Deleting branch %s" % msg_core
            ans = ask_if(msg, opt_yes_msg)
            if ans in ('y', 'yes'):
                run_git("branch", "-d" if is_merged_to_remote else "-D", b)
            elif ans in ('q', 'quit'):
                return

        branches_to_delete_unmerged_to_head = [b for b in branches_to_delete if b not in branches_merged_to_head]
        for b in branches_to_delete_unmerged_to_head:
            msg_core = "%s (unmerged to HEAD)" % bold(b)
            msg = "Delete branch %s? [y/N/q] " % msg_core
            opt_yes_msg = "Deleting branch %s" % msg_core
            ans = ask_if(msg, opt_yes_msg)
            if ans in ('y', 'yes'):
                run_git("branch", "-D", b)
            elif ans in ('q', 'quit'):
                return
    else:
        print("No branches to delete")


def slide_out(bs):
    for b in bs:
        expect_in_managed_branches(b)
        u = up_branch.get(b)
        if not u:
            raise MacheteException("No upstream branch defined for '%s', cannot slide out" % b)
        dbs = down_branches.get(b)
        if not dbs or len(dbs) == 0:
            raise MacheteException("No downstream branch defined for '%s', cannot slide out" % b)
        elif len(dbs) > 1:
            flat_dbs = join_branch_names(dbs, ", ")
            raise MacheteException("Multiple downstream branches defined for '%s': %s; cannot slide out" % (b, flat_dbs))

    for bu, bd in zip(bs[:-1], bs[1:]):
        if up_branch[bd] != bu:
            raise MacheteException("'%s' is not upstream of '%s', cannot slide out" % (bu, bd))

    u = up_branch[bs[0]]
    d = down_branches[bs[-1]][0]
    for b in bs:
        up_branch[b] = None
        down_branches[b] = None

    go(d)
    up_branch[d] = u
    down_branches[u] = [(d if x == bs[0] else x) for x in down_branches[u]]
    save_definition_file()
    if opt_merge:
        print("Merging %s into %s..." % (bold(u), bold(d)))
        merge(u, d)
    else:
        print("Rebasing %s onto %s..." % (bold(d), bold(u)))
        rebase("refs/heads/" + u, opt_down_fork_point or fork_point(d, use_overrides=True), d)


def slidable():
    return [b for b in managed_branches if b in up_branch and b in down_branches and len(down_branches[b]) == 1]


def slidable_after(b):
    if b in up_branch:
        dbs = down_branches.get(b)
        if dbs and len(dbs) == 1:
            d = dbs[0]
            ddbs = down_branches.get(d)
            if ddbs and len(ddbs) == 1:
                return [d]
    return []


class StopTraversal(Exception):
    def __init__(self):
        pass


def flush():
    global branch_defs_by_sha_in_reflog, commit_sha_by_revision_cached, config_cached, counterparts_for_fetching_cached, initial_log_shas_cached
    global local_branches_cached, reflogs_cached, remaining_log_shas_cached, remote_branches_cached
    branch_defs_by_sha_in_reflog = None
    commit_sha_by_revision_cached = None
    config_cached = None
    counterparts_for_fetching_cached = None
    initial_log_shas_cached = {}
    local_branches_cached = None
    reflogs_cached = None
    remaining_log_shas_cached = {}
    remote_branches_cached = None


def pick_remote(b):
    rems = remotes()
    print("\n".join("[%i] %s" % (idx + 1, r) for idx, r in enumerate(rems)))
    msg = "Select number 1..%i to specify the destination remote " \
          "repository, or 'n' to skip this branch, or " \
          "'q' to quit the traverse: " % len(rems)
    ans = safe_input(msg).lower()
    if ans in ('q', 'quit'):
        raise StopTraversal
    try:
        idx = int(ans) - 1
        if idx not in range(len(rems)):
            raise MacheteException("Invalid index: %i" % (idx + 1))
        handle_untracked_branch(rems[idx], b)
    except ValueError:
        pass


def handle_untracked_branch(new_remote, b):
    rems = remotes()
    can_pick_other_remote = len(rems) > 1
    other_remote_suffix = "/[o]ther remote" if can_pick_other_remote else ""
    rb = new_remote + "/" + b
    if not commit_sha_by_revision(rb, prefix="refs/remotes/"):
        msg = "Push untracked branch %s to %s? (y/N/q/yq%s) " % (bold(b), bold(new_remote), other_remote_suffix)
        opt_yes_msg = "Pushing untracked branch %s to %s..." % (bold(b), bold(new_remote))
        ans = ask_if(msg, opt_yes_msg)
        if ans in ('y', 'yes', 'yq'):
            push(new_remote, b)
            if msg == 'yq':
                raise StopTraversal
            flush()
        elif can_pick_other_remote and ans in ('o', 'other'):
            pick_remote(b)
        elif ans in ('q', 'quit'):
            raise StopTraversal
        return

    message = {
        IN_SYNC_WITH_REMOTE:
            "Branch %s is untracked, but its remote counterpart candidate %s already exists and both branches point to the same commit." % (bold(b), bold(rb)),
        BEHIND_REMOTE:
            "Branch %s is untracked, but its remote counterpart candidate %s already exists and is ahead of %s." % (bold(b), bold(rb), bold(b)),
        AHEAD_OF_REMOTE:
            "Branch %s is untracked, but its remote counterpart candidate %s already exists and is behind %s." % (bold(b), bold(rb), bold(b)),
        DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
            "Branch %s is untracked, it diverged from its remote counterpart candidate %s, and has %s commits than %s." % (bold(b), bold(rb), bold("older"), bold(rb)),
        DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
            "Branch %s is untracked, it diverged from its remote counterpart candidate %s, and has %s commits than %s." % (bold(b), bold(rb), bold("newer"), bold(rb))
    }

    prompt = {
        IN_SYNC_WITH_REMOTE: (
            "Set the remote of %s to %s without pushing or pulling? (y/N/q/yq%s) " % (bold(b), bold(new_remote), other_remote_suffix),
            "Setting the remote of %s to %s..." % (bold(b), bold(new_remote))
        ),
        BEHIND_REMOTE: (
            "Pull %s (fast-forward only) from %s? (y/N/q/yq%s) " % (bold(b), bold(new_remote), other_remote_suffix),
            "Pulling %s (fast-forward only) from %s..." % (bold(b), bold(new_remote))
        ),
        AHEAD_OF_REMOTE: (
            "Push branch %s to %s? (y/N/q/yq%s) " % (bold(b), bold(new_remote), other_remote_suffix),
            "Pushing branch %s to %s..." % (bold(b), bold(new_remote))
        ),
        DIVERGED_FROM_AND_OLDER_THAN_REMOTE: (
            "Reset branch %s to the commit pointed by %s? (y/N/q/yq%s) " % (bold(b), bold(rb), other_remote_suffix),
            "Resetting branch %s to the commit pointed by %s..." % (bold(b), bold(rb))
        ),
        DIVERGED_FROM_AND_NEWER_THAN_REMOTE: (
            "Push branch %s with force-with-lease to %s? (y/N/q/yq%s) " % (bold(b), bold(new_remote), other_remote_suffix),
            "Pushing branch %s with force-with-lease to %s..." % (bold(b), bold(new_remote))
        )
    }

    yes_actions = {
        IN_SYNC_WITH_REMOTE: lambda: set_upstream_to(rb),
        BEHIND_REMOTE: lambda: pull_ff_only(new_remote, rb),
        AHEAD_OF_REMOTE: lambda: push(new_remote, b),
        DIVERGED_FROM_AND_OLDER_THAN_REMOTE: lambda: reset_keep(rb),
        DIVERGED_FROM_AND_NEWER_THAN_REMOTE: lambda: push(new_remote, b, force_with_lease=True)
    }

    relation = get_relation_to_remote_counterpart(b, rb)
    print(message[relation])
    msg, opt_yes_msg = prompt[relation]
    ans = ask_if(msg, opt_yes_msg)
    if ans in ('y', 'yes', 'yq'):
        yes_actions[relation]()
        if msg == 'yq':
            raise StopTraversal
        flush()
    elif can_pick_other_remote and ans in ('o', 'other'):
        pick_remote(b)
    elif ans in ('q', 'quit'):
        raise StopTraversal


def traverse():
    global down_branches, up_branch, empty_line_status, managed_branches

    expect_at_least_one_managed_branch()

    empty_line_status = True

    def print_new_line(new_status):
        global empty_line_status
        if not empty_line_status:
            print("")
        empty_line_status = new_status

    if opt_fetch:
        for r in remotes():
            print("Fetching %s..." % r)
            fetch_remote(r)
        if remotes():
            flush()
            print("")

    initial_branch = nearest_remaining_branch = current_branch()

    if opt_start_from == "root":
        dest = root_branch(current_branch(), accept_self=True, if_unmanaged=PICK_FIRST_ROOT)
        print_new_line(False)
        print("Checking out the root branch (%s)" % bold(dest))
        go(dest)
        cb = dest
    elif opt_start_from == "first-root":
        # Note that we already ensured that there is at least one managed branch.
        dest = managed_branches[0]
        print_new_line(False)
        print("Checking out the first root branch (%s)" % bold(dest))
        go(dest)
        cb = dest
    else:  # opt_start_from == "here"
        cb = current_branch()
        expect_in_managed_branches(cb)

    for b in itertools.dropwhile(lambda x: x != cb, managed_branches):
        u = up_branch.get(b)

        needs_slide_out = is_merged_to_parent(b)
        s, remote = get_strict_remote_sync_status(b)
        statuses_to_sync = (UNTRACKED,
                            AHEAD_OF_REMOTE,
                            BEHIND_REMOTE,
                            DIVERGED_FROM_AND_OLDER_THAN_REMOTE,
                            DIVERGED_FROM_AND_NEWER_THAN_REMOTE)
        needs_remote_sync = s in statuses_to_sync

        if needs_slide_out:
            # Avoid unnecessary fork point check if we already know that the branch qualifies for slide out;
            # neither rebase nor merge will be suggested in such case anyway.
            needs_parent_sync = False
        elif s == DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
            # Avoid unnecessary fork point check if we already know that the branch qualifies for resetting to remote counterpart;
            # neither rebase nor merge will be suggested in such case anyway.
            needs_parent_sync = False
        elif opt_merge:
            needs_parent_sync = u and not is_ancestor(u, b)
        else:  # using rebase
            needs_parent_sync = u and not (is_ancestor(u, b) and commit_sha_by_revision(u) == fork_point(b, use_overrides=True))

        if b != cb and (needs_slide_out or needs_parent_sync or needs_remote_sync):
            print_new_line(False)
            sys.stdout.write("Checking out %s\n" % bold(b))
            go(b)
            cb = b
            print_new_line(False)
            status(warn_on_yellow_edges=True)
            print_new_line(True)
        if needs_slide_out:
            print_new_line(False)
            ans = ask_if(
                "Branch %s is merged into %s. Slide %s out of the tree of branch dependencies? [y/N/q/yq] " % (bold(b), bold(u), bold(b)),
                "Branch %s is merged into %s. Sliding %s out of the tree of branch dependencies..." % (bold(b), bold(u), bold(b))
            )
            if ans in ('y', 'yes', 'yq'):
                if nearest_remaining_branch == b:
                    if down_branches.get(b):
                        nearest_remaining_branch = down_branches[b][0]
                    else:
                        nearest_remaining_branch = u
                for d in down_branches.get(b) or []:
                    up_branch[d] = u
                down_branches[u] = flat_map(
                    lambda ud: (down_branches.get(b) or [])
                    if ud == b else [ud],
                    down_branches[u])
                if b in annotations:
                    del annotations[b]
                save_definition_file()
                if ans == 'yq':
                    return
                # No need to flush caches since nothing changed in commit/branch structure (only machete-specific changes happened).
                continue  # No need to sync branch 'b' with remote since it just got removed from the tree of dependencies.
            elif ans in ('q', 'quit'):
                return
            # If user answered 'no', we don't try to rebase/merge but still suggest to sync with remote (if needed; very rare in practice).
        elif needs_parent_sync:
            print_new_line(False)
            if opt_merge:
                ans = ask_if("Merge %s into %s? [y/N/q/yq] " % (bold(u), bold(b)), "Merging %s into %s..." % (bold(u), bold(b)))
            else:
                ans = ask_if("Rebase %s onto %s? [y/N/q/yq] " % (bold(b), bold(u)), "Rebasing %s onto %s..." % (bold(b), bold(u)))
            if ans in ('y', 'yes', 'yq'):
                if opt_merge:
                    merge(u, b)
                    # It's clearly possible that merge can be in progress after 'git merge' returned non-zero exit code;
                    # this happens most commonly in case of conflicts.
                    # As for now, we're not aware of any case when merge can be still in progress after 'git merge' returns zero,
                    # at least not with the options that git-machete passes to merge; this happens though in case of 'git merge --no-commit' (which we don't ever invoke).
                    # It's still better, however, to be on the safe side.
                    if is_merge_in_progress():
                        sys.stdout.write("\nMerge in progress; stopping the traversal\n")
                        return
                else:
                    rebase("refs/heads/" + u, fork_point(b, use_overrides=True), b)
                    # It's clearly possible that rebase can be in progress after 'git rebase' returned non-zero exit code;
                    # this happens most commonly in case of conflicts, regardless of whether the rebase is interactive or not.
                    # But for interactive rebases, it's still possible that even if 'git rebase' returned zero,
                    # the rebase is still in progress; e.g. when interactive rebase gets to 'edit' command, it will exit returning zero,
                    # but the rebase will be still in progress, waiting for user edits and a subsequent 'git rebase --continue'.
                    rb = currently_rebased_branch_or_none()
                    if rb:  # 'rb' should be equal to 'b' at this point anyway
                        sys.stdout.write("\nRebase of '%s' in progress; stopping the traversal\n" % rb)
                        return
                if ans == 'yq':
                    return

                flush()
                s, remote = get_strict_remote_sync_status(b)
                needs_remote_sync = s in statuses_to_sync
            elif ans in ('q', 'quit'):
                return

        if needs_remote_sync:
            if s == BEHIND_REMOTE:
                rb = strict_counterpart_for_fetching_of_branch(b)
                ans = ask_if(
                    "Branch %s is behind its remote counterpart %s.\nPull %s (fast-forward only) from %s? [y/N/q/yq] " % (bold(b), bold(rb), bold(b), bold(remote)),
                    "Branch %s is behind its remote counterpart %s.\nPulling %s (fast-forward only) from %s..." % (bold(b), bold(rb), bold(b), bold(remote))
                )
                if ans in ('y', 'yes', 'yq'):
                    pull_ff_only(remote, rb)
                    if ans == 'yq':
                        return
                    flush()
                    print("")
                elif ans in ('q', 'quit'):
                    return

            elif s == AHEAD_OF_REMOTE:
                print_new_line(False)
                ans = ask_if(
                    "Push %s to %s? [y/N/q/yq] " % (bold(b), bold(remote)),
                    "Pushing %s to %s..." % (bold(b), bold(remote))
                )
                if ans in ('y', 'yes', 'yq'):
                    push(remote, b)
                    if ans == 'yq':
                        return
                    flush()
                elif ans in ('q', 'quit'):
                    return

            elif s == DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                print_new_line(False)
                rb = strict_counterpart_for_fetching_of_branch(b)
                ans = ask_if(
                    "Branch %s diverged from (and has older commits than) its remote counterpart %s.\nReset branch %s to the commit pointed by %s? [y/N/q/yq] " % (bold(b), bold(rb), bold(b), bold(rb)),
                    "Branch %s diverged from (and has older commits than) its remote counterpart %s.\nResetting branch %s to the commit pointed by %s..." % (bold(b), bold(rb), bold(b), bold(rb))
                )
                if ans in ('y', 'yes', 'yq'):
                    reset_keep(rb)
                    if ans == 'yq':
                        return
                    flush()
                elif ans in ('q', 'quit'):
                    return

            elif s == DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                print_new_line(False)
                rb = strict_counterpart_for_fetching_of_branch(b)
                ans = ask_if(
                    "Branch %s diverged from (and has newer commits than) its remote counterpart %s.\nPush %s with force-with-lease to %s? [y/N/q/yq] " % (bold(b), bold(rb), bold(b), bold(remote)),
                    "Branch %s diverged from (and has newer commits than) its remote counterpart %s.\nPushing %s with force-with-lease to %s..." % (bold(b), bold(rb), bold(b), bold(remote))
                )
                if ans in ('y', 'yes', 'yq'):
                    push(remote, b, force_with_lease=True)
                    if ans == 'yq':
                        return
                    flush()
                elif ans in ('q', 'quit'):
                    return

            elif s == UNTRACKED:
                rems = remotes()
                r = inferred_remote_for_fetching_of_branch(b)
                print_new_line(False)
                if r:
                    handle_untracked_branch(r, b)
                elif len(rems) == 1:
                    handle_untracked_branch(rems[0], b)
                elif "origin" in rems:
                    handle_untracked_branch("origin", b)
                else:
                    # We know that there is at least 1 remote, otherwise 's' would be 'NO_REMOTES'
                    print("Branch %s is untracked and there's no %s repository." % (bold(b), bold("origin")))
                    pick_remote(b)

    if opt_return_to == "here":
        go(initial_branch)
    elif opt_return_to == "nearest-remaining":
        go(nearest_remaining_branch)
    # otherwise opt_return_to == "stay", so no action is needed

    print_new_line(False)
    status(warn_on_yellow_edges=True)
    print("")
    msg = "Reached branch %s which has no successor" \
        if cb == managed_branches[-1] else \
        "No successor of %s needs to be slid out or synced with upstream branch or remote"
    sys.stdout.write(msg % bold(cb) + "; nothing left to update\n")

    if opt_return_to == "here" or (opt_return_to == "nearest-remaining" and nearest_remaining_branch == initial_branch):
        print("Returned to the initial branch %s" % bold(initial_branch))
    elif opt_return_to == "nearest-remaining" and nearest_remaining_branch != initial_branch:
        print("The initial branch %s has been slid out. Returned to nearest remaining managed branch %s" % (bold(initial_branch), bold(nearest_remaining_branch)))


def status(warn_on_yellow_edges):
    dfs_res = []

    def prefix_dfs(u_, prefix):
        dfs_res.append((u_, prefix))
        if down_branches.get(u_):
            for (v, nv) in zip(down_branches[u_][:-1], down_branches[u_][1:]):
                prefix_dfs(v, prefix + [nv])
            prefix_dfs(down_branches[u_][-1], prefix + [None])

    for u in roots:
        prefix_dfs(u, prefix=[])

    out = io.StringIO()
    edge_color = {}
    fp_sha_cached = {}
    fp_branches_cached = {}

    def fp_sha(b):
        if b not in fp_sha_cached:
            try:
                # We're always using fork point overrides, even when status is launched from discover().
                fp_sha_cached[b], fp_branches_cached[b] = fork_point_and_containing_branch_defs(b, use_overrides=True)
            except MacheteException:
                fp_sha_cached[b], fp_branches_cached[b] = None, []
        return fp_sha_cached[b]

    # Edge colors need to be precomputed
    # in order to render the leading parts of lines properly.
    for b in up_branch:
        u = up_branch[b]
        if is_merged_to_parent(b):
            edge_color[b] = DIM
        elif not is_ancestor(u, b):
            edge_color[b] = RED
        elif get_overridden_fork_point(b) or commit_sha_by_revision(u) == fp_sha(b):
            edge_color[b] = GREEN
        else:
            edge_color[b] = YELLOW

    crb = currently_rebased_branch_or_none()
    ccob = currently_checked_out_branch_or_none()

    hook_path = get_hook_path("machete-status-branch")
    hook_executable = check_hook_executable(hook_path)

    def write_unicode(x):
        if sys.version_info[0] == 2:  # Python 2
            out.write(unicode(x))  # noqa: F821
        else:  # Python 3
            out.write(x)

    def print_line_prefix(b_, suffix):
        write_unicode("  ")
        for p in pfx[:-1]:
            if not p:
                write_unicode("  ")
            else:
                write_unicode(colored(vertical_bar() + " ", edge_color[p]))
        write_unicode(colored(suffix, edge_color[b_]))

    for b, pfx in dfs_res:
        if b in up_branch:
            print_line_prefix(b, vertical_bar() + " \n")
            if opt_list_commits:
                if edge_color[b] in (RED, DIM):
                    commits = commits_between(fp_sha(b), "refs/heads/" + b) if fp_sha(b) else []
                elif edge_color[b] == YELLOW:
                    commits = commits_between("refs/heads/" + up_branch[b], "refs/heads/" + b)
                else:  # edge_color == GREEN
                    commits = commits_between(fp_sha(b), "refs/heads/" + b)

                for sha, short_sha, msg in reversed(commits):
                    if sha == fp_sha(b):
                        # fp_branches_cached will already be there thanks to the above call to 'fp_sha'.
                        fp_branches_formatted = " and ".join(map(star(lambda lb, lb_or_rb: lb_or_rb), fp_branches_cached[b]))
                        fp_suffix = " %s %s %s has been found in reflog of %s" %\
                            (colored(right_arrow(), RED), colored("fork point ???", RED), "this commit" if opt_list_commits_with_hashes else "commit " + short_sha, fp_branches_formatted)
                    else:
                        fp_suffix = ''
                    print_line_prefix(b, vertical_bar())
                    write_unicode(" %s%s%s\n" % (dim(short_sha) + "  " if opt_list_commits_with_hashes else "", dim(msg), fp_suffix))
            elbow_ascii_only = {DIM: "m-", RED: "x-", GREEN: "o-", YELLOW: "?-"}
            elbow = u"└─" if not ascii_only else elbow_ascii_only[edge_color[b]]
            print_line_prefix(b, elbow)
        else:
            if b != dfs_res[0][0]:
                write_unicode("\n")
            write_unicode("  ")

        if b in (ccob, crb):  # i.e. if b is the current branch (checked out or being rebased)
            if b == crb:
                prefix = "REBASING "
            elif is_am_in_progress():
                prefix = "GIT AM IN PROGRESS "
            elif is_cherry_pick_in_progress():
                prefix = "CHERRY-PICKING "
            elif is_merge_in_progress():
                prefix = "MERGING "
            elif is_revert_in_progress():
                prefix = "REVERTING "
            else:
                prefix = ""
            current = "%s%s" % (bold(colored(prefix, RED)) if prefix else "", bold(underline(b)))
        else:
            current = bold(b)

        anno = "  " + dim(annotations[b]) if b in annotations else ""

        s, remote = get_combined_remote_sync_status(b)
        sync_status = {
            NO_REMOTES: "",
            UNTRACKED: colored(" (untracked)", ORANGE),
            IN_SYNC_WITH_REMOTE: "",
            BEHIND_REMOTE: colored(" (behind %s)" % remote, RED),
            AHEAD_OF_REMOTE: colored(" (ahead of %s)" % remote, RED),
            DIVERGED_FROM_AND_OLDER_THAN_REMOTE: colored(" (diverged from & older than %s)" % remote, RED),
            DIVERGED_FROM_AND_NEWER_THAN_REMOTE: colored(" (diverged from %s)" % remote, RED)
        }[s]

        hook_output = ""
        if hook_executable:
            debug("status()", "running machete-status-branch hook (%s) for branch %s" % (hook_path, b))
            hook_env = dict(os.environ, ASCII_ONLY=str(ascii_only).lower())
            status_code, stdout, stderr = popen_cmd(hook_path, b, cwd=get_root_dir(), env=hook_env)
            if status_code == 0:
                if not stdout.isspace():
                    hook_output = "  " + stdout.rstrip()
            else:
                debug("status()", "machete-status-branch hook (%s) for branch %s returned %i; stdout: '%s'; stderr: '%s'" % (hook_path, b, status_code, stdout, stderr))

        write_unicode(current + anno + sync_status + hook_output + "\n")

    sys.stdout.write(out.getvalue())
    out.close()

    yellow_edge_branches = [k for k, v in edge_color.items() if v == YELLOW]
    if yellow_edge_branches and warn_on_yellow_edges:
        if len(yellow_edge_branches) == 1:
            first_line = "yellow edge indicates that fork point for '%s' is probably incorrectly inferred" % yellow_edge_branches[0]
        else:
            affected_branches = ", ".join(map(lambda x: "'%s'" % x, yellow_edge_branches))
            first_line = "yellow edges indicate that fork points for %s are probably incorrectly inferred" % affected_branches

        if not opt_list_commits:
            second_line = "Run 'git machete status --list-commits' or 'git machete status --list-commits-with-hashes' to see more details"
        elif len(yellow_edge_branches) == 1:
            second_line = "Consider using 'git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent %s'" % yellow_edge_branches[0]
        else:
            second_line = "Consider using 'git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent <branch>' for each affected branch"

        sys.stderr.write("\n")
        warn("%s.\n%s." % (first_line, second_line))


# Main


def usage(c=None):
    short_docs = {
        "add": "Add a branch to the tree of branch dependencies",
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
        "list": "List all branches that fall into one of pre-defined categories (mostly for internal use)",
        "log": "Log the part of history specific to the given branch",
        "reapply": "Rebase the current branch onto its computed fork point",
        "show": "Show name(s) of the branch(es) relative to the position of the current branch, accepts down/first/last/next/root/prev/up argument",
        "slide-out": "Slide out the current branch and sync its downstream (child) branch with its upstream (parent) branch via rebase or merge",
        "status": "Display formatted tree of branch dependencies, including info on their sync with upstream branch and with remote",
        "traverse": "Walk through the tree of branch dependencies and rebase, merge, slide out, push and/or pull each branch one by one",
        "update": "Sync the current branch with its upstream (parent) branch via rebase or merge",
        "version": "Display the version and exit"
    }
    long_docs = {
        "add": """
            Usage: git machete add [-o|--onto=<target-upstream-branch>] [-y|--yes] [<branch>]

            Adds the given branch (or the current branch, if none specified) to the definition file.
            If the definition file is empty, the branch will be added as the first root of the tree of branch dependencies.
            Otherwise, the desired upstream (parent) branch can be specified with '--onto'.
            This option is not mandatory, however; if skipped, git machete will try to automatically infer the target upstream.
            If the upstream branch can be inferred, the user will be presented with inferred branch and asked to confirm.
            Also, if the given branch does not exist, user will be asked whether it should be created.

            Note: the same effect (except branch creation) can be always achieved by manually editing the definition file.

            Options:
              -o, --onto=<target-upstream-branch>    Specifies the target parent branch to add the given branch onto.

              -y, --yes                              Don't ask for confirmation whether to create the branch or whether to add onto the inferred upstream.
        """,
        "anno": """
            Usage: git machete anno [<annotation text>]

            If invoked without any argument, prints out the custom annotation for the current branch.

            If invoked with a single empty string argument, like:
            $ git machete anno ''
            clears the annotation set the current branch.

            In any other case, sets the annotation for the current branch to the given argument.
            If multiple arguments are passed to the command, they are concatenated with single spaces.

            Note: the same effect can be always achieved by manually editing the definition file.
        """,
        "delete-unmanaged": """
            Usage: git machete delete-unmanaged [-y|--yes]

            Goes one-by-one through all the local git branches that don't exist in the definition file, and ask to delete each of them (with 'git branch -d' or 'git branch -D') if confirmed by user.
            No branch will be deleted unless explicitly confirmed by the user.

            Note: this should be used with care since deleting local branches can sometimes make it impossible for 'git machete' to properly compute fork points.
            See 'git machete help fork-point' for more details.

            Options:
              -y, --yes          Don't ask for confirmation.
        """,
        "diff": """
            Usage: git machete d[iff] [-s|--stat] [<branch>]

            Runs 'git diff' of the given branch tip against its fork point or, if none specified, of the current working tree against the fork point of the currently checked out branch.
            See 'git machete help fork-point' for more details on meaning of the "fork point".

            Note: the branch in question does not need to occur in the definition file.

            Options:
              -s, --stat    Makes 'git machete diff' pass '--stat' option to 'git diff', so that only summary (diffstat) is printed.
        """,
        "discover": """
            Usage: git machete discover [-C|--checked-out-since=<date>] [-l|--list-commits] [-r|--roots=<branch1>,<branch2>,...] [-y|--yes]

            Discovers and displays tree of branch dependencies using a heuristic based on reflogs and asks whether to overwrite the existing definition file with the new discovered tree.
            If confirmed with a '[y]es' or '[e]dit' reply, backs up the current definition file as '.git/machete~' (if exists) and saves the new tree under the usual '.git/machete' path.
            If the reply was '[e]dit', additionally an editor is opened (as in 'git machete edit') after saving the new definition file.

            Options:
              -C, --checked-out-since=<date>  Only consider branches checked out at least once since the given date. <date> can be e.g. '2 weeks ago', as in 'git log --since=<date>'.

              -l, --list-commits              When printing the discovered tree, additionally lists the messages of commits introduced on each branch (as for 'git machete status').

              -r, --roots=<branch1,...>       Comma-separated list of branches that should be considered roots of trees of branch dependencies, typically 'develop' and/or 'master'.

              -y, --yes                       Don't ask for confirmation.
        """,
        "edit": """
            Usage: git machete e[dit]

            Opens the editor (as defined by the 'EDITOR' environment variable, or 'vim' if undefined) and lets you edit the definition file manually.
            The definition file can be always accessed under path returned by 'git machete file' (currently fixed to <repo-root>/.git/machete).
        """,
        "file": """
            Usage: git machete file

            Outputs the path of the machete definition file. Currently fixed to '<git-directory>/machete'.
            Note: this won't always be just '.git/machete' since e.g. submodules have their git directory in different location by default.
        """,
        "fork-point": """
            Usage:
              git machete fork-point [--inferred] [<branch>]
              git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent [<branch>]
              git machete fork-point --unset-override [<branch>]

            Note: in all three forms, if no <branch> is specified, the currently checked out branch is assumed. The branch in question does not need to occur in the definition file.


            Without any option, displays full SHA of the fork point commit for the <branch> (the commit at which the history of the <branch> diverges from history of any other branch).

            The returned fork point is assumed by the commands 'diff', 'reapply', 'slide-out', 'traverse' and 'update' as the default place where the unique history of the <branch> starts.
            In other words, 'git machete' treats the fork point as the most recent commit in the log of the given branch that has NOT been introduced on that very branch,
            but on some other (usually chronologically earlier) branch.

            To determine this place in history, 'git machete' uses a heuristics based on reflogs of local branches.
            This yields a correct result in typical cases, but there are some situations (esp. when some local branches have been deleted) where the fork point might not be determined correctly.
            Thus, all rebase-involving operations ('reapply', 'slide-out', 'traverse' and 'update') run 'git rebase' in the interactive mode,
            unless told explicitly not to do so by '--no-interactive-rebase' flag.
            Also, 'reapply', 'slide-out' and 'update' allow to specify the fork point explictly by a command-line option.

            'git machete fork-point' is different (and more powerful) than 'git merge-base --fork-point', since the latter takes into account only the reflog of the one provided upstream branch,
            while the former scans reflogs of all local branches and their remote tracking branches.
            This makes machete's 'fork-point' work correctly even when the tree definition has been modified and thus one or more of the branches changed their corresponding upstream branch.


            With '--override-to=<revision>', sets up a fork point override for <branch>.
            Fork point for <branch> will be overridden to the provided <revision> (commit) as long as the <branch> still points to (or is descendant of) the commit X
            that <branch> pointed to at the moment the override is set up.
            Note that even if revision is a symbolic name (e.g. other branch name or 'HEAD~3') and not explicit commit hash (like 'a1b2c3ff'), it's still resolved to a specific commit at the moment the override is set up.
            The override data is stored under 'machete.overrideForkPoint.<branch>.to' and 'machete.overrideForkPoint.<branch>.whileDescendantOf' git config keys.
            Note: the provided fork point <revision> must be an ancestor of the current <branch> commit X.

            With '--override-to-parent', overrides fork point of the <branch> to the commit currently pointed by <branch>'s parent in the branch dependency tree.
            Note: this will only work if <branch> has a parent at all (i.e. is not a root) and parent of <branch> is an ancestor of current <branch> commit X.

            With '--inferred', displays the commit that 'git machete fork-point' infers to be the fork point of <branch>.
            If there is NO fork point override for <branch>, this is identical to the output of 'git machete fork-point'.
            If there is a fork point override for <branch>, this is identical to the what the output of 'git machete fork-point' would be if the override was NOT present.

            With '--override-to-inferred' option, overrides fork point of the <branch> to the commit that 'git machete fork-point' infers to be the fork point of <branch>.
            Note: this piece of information is also displayed by 'git machete status --list-commits' in case a yellow edge occurs.

            With '--unset-override', the fork point override for <branch> is unset.
            Note: this is simply done by removing the corresponding 'machete.overrideForkPoint.<branch>.*' config entries.
        """,
        "format": """
            The format of the definition file should be as follows:

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

            In the above example 'develop' and 'master' are roots of the tree of branch dependencies.
            Branches 'adjust-reads-prec', 'edit-margin-not-allowed' and 'grep-errors-script' are direct downstream branches for 'develop'.
            'block-cancel-order' is a downstream branch of 'adjust-reads-prec', 'change-table' is a downstream branch of 'block-cancel-order' and so on.

            Every branch name can be followed (after a single space as a delimiter) by a custom annotation - a PR number in the above example.
            The annotations don't influence the way 'git machete' operates other than that they are displayed in the output of the 'status' command.
            Also see help for the 'anno' command.

            Tabs or any number of spaces can be used as indentation.
            It's only important to be consistent wrt. the sequence of characters used for indentation between all lines.
        """,
        "go": """
            Usage: git machete g[o] <direction>
            where <direction> is one of: d[own], f[irst], l[ast], n[ext], p[rev], r[oot], u[p]

            Checks out the branch specified by the given direction relative to the currently checked out branch.
            Roughly equivalent to 'git checkout $(git machete show <direction>)'.
            See 'git machete help show' on more details on meaning of each direction.
        """,
        "infer": """
            Usage: git machete infer [-l|--list-commits]

            A deprecated alias for 'discover'. Retained for compatibility, to be removed in the next major release.

            Options:
              -l, --list-commits            When printing the discovered tree, additionally lists the messages of commits introduced on each branch (as for 'git machete status').
        """,
        "help": """
            Usage: git machete help [<command>]

            Prints a summary of this tool, or a detailed info on a command if defined.
        """,
        "hooks": """
            As for standard git hooks, git-machete looks for its own specific hooks in $GIT_DIR/hooks/* (or $(git config core.hooksPath)/*, if set).

            Note: 'hooks' is not a command as such, just a help topic (there is no 'git machete hooks' command).

            * machete-pre-rebase <new-base> <fork-point-hash> <branch-being-rebased>
                The hook that is executed before rebase is run during 'reapply', 'slide-out', 'traverse' and 'update'.
                The parameters are exactly the three revisions that are passed to 'git rebase --onto':
                1. what is going to be the new base for the rebased commits,
                2. what is the fork point - the place where the rebased history diverges from the upstream history,
                3. what branch is rebased.
                If the hook returns a non-zero status, the entire command is aborted.

                Note: this hook is independent from git's standard 'pre-rebase' hook.
                If machete-pre-rebase returns zero, the execution flow continues to 'git rebase', which will run 'pre-rebase' hook if present.
                'machete-pre-rebase' is thus always run before 'pre-rebase'.

            * machete-status-branch <branch-name>
                The hook that is executed for each branch displayed during 'discover', 'status' and 'traverse'.
                The standard output of this hook is displayed at the end of the line, after branch name, (optionally) custom annotation and (optionally) remote sync-ness status.
                Standard error is ignored. If the hook returns a non-zero status, both stdout and stderr are ignored, and printing the status continues as usual.

                Note: the hook is always invoked with 'ASCII_ONLY' variable passed into the environment.
                If 'status' runs in ASCII-only mode (i.e. if '--color=auto' and stdout is not a terminal, or if '--color=never'), then 'ASCII_ONLY=true', otherwise 'ASCII_ONLY=false'.

            Please see hook_samples/ directory for examples (also includes an example of using the standard git post-commit hook to 'git machete add' branches automatically).
        """,
        "list": """
            Usage: git machete list <category>
            where <category> is one of: managed, slidable, slidable-after <branch>, unmanaged, with-overridden-fork-point

            Lists all branches that fall into one of the specified categories:
            - 'managed': all branches that appear in the definition file,
            - 'slidable': all managed branches that have exactly one upstream and one downstream (i.e. the ones that can be slid out with 'slide-out' command),
            - 'slidable-after <branch>': the downstream branch of the <branch>, if it exists and is the only downstream of <branch> (i.e. the one that can be slid out immediately following <branch>),
            - 'unmanaged': all local branches that don't appear in the definition file,
            - 'with-overridden-fork-point': all local branches that have a fork point override set up (even if this override does not affect the location of their fork point anymore).

            This command is generally not meant for a day-to-day use, it's mostly needed for the sake of branch name completion in shell.
        """,
        "log": """
            Usage: git machete l[og] [<branch>]

            Runs 'git log' for the range of commits from tip of the given branch (or current branch, if none specified) back to its fork point.
            See 'git machete help fork-point' for more details on meaning of the "fork point".

            Note: the branch in question does not need to occur in the definition file.
        """,
        "prune-branches": """
            Usage: git machete prune-branches

            A deprecated alias for 'delete-unmanaged'. Retained for compatibility, to be removed in the next major release.
        """,
        "reapply": """
            Usage: git machete reapply [-f|--fork-point=<fork-point-commit>]

            Interactively rebase the current branch on the top of its computed fork point.
            This is useful e.g. for squashing the commits on the current branch to make history more condensed before push to the remote.
            The chunk of the history to be rebased starts at the automatically computed fork point of the current branch by default, but can also be set explicitly by '--fork-point'.
            See 'git machete help fork-point' for more details on meaning of the "fork point".

            Note: the current reapplied branch does not need to occur in the definition file.

            Options:
              -f, --fork-point=<fork-point-commit>    Specifies the alternative fork point commit after which the rebased part of history is meant to start.
        """,
        "show": """
            Usage: git machete show [<direction>]
            where <direction> is one of: d[own], f[irst], l[ast], n[ext], p[rev], r[oot], u[p]

            Outputs name of the branch (or possibly multiple branches, in case of 'down') that is:

            * 'down':  the direct children/downstream branch of the current branch.
            * 'first': the first downstream of the root branch of the current branch (like 'root' followed by 'next'), or the root branch itself if the root has no downstream branches.
            * 'last':  the last branch in the definition file that has the same root as the current branch; can be the root branch itself if the root has no downstream branches.
            * 'next':  the direct successor of the current branch in the definition file.
            * 'prev':  the direct predecessor of the current branch in the definition file.
            * 'root':  the root of the tree where the current branch is located. Note: this will typically be something like 'develop' or 'master', since all branches are usually meant to be ultimately merged to one of those.
            * 'up':    the direct parent/upstream branch of the current branch.
        """,
        "slide-out": """
            Usage: git machete slide-out [-d|--down-fork-point=<down-fork-point-commit>] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase] <branch> [<branch> [<branch> ...]]

            Removes the given branch (or multiple branches) from the branch tree definition.
            Then synchronizes the downstream (child) branch of the last specified branch on the top of the upstream (parent) branch of the first specified branch.
            Sync is performed either by rebase (default) or by merge (if '--merge' option passed).

            The most common use is to slide out a single branch whose upstream was a 'develop'/'master' branch and that has been recently merged.

            Since this tool is designed to perform only one single rebase/merge at the end, provided branches must form a chain, i.e. all of the following conditions must be met:
            * for i=1..N-1, (i+1)-th branch must be a downstream (child) branch of the i-th branch,
            * all provided branches (including N-th branch) must have exactly one downstream branch,
            * all provided branches must have an upstream branch (so, in other words, roots of branch dependency tree cannot be slid out).

            For example, let's assume the following dependency tree:

              develop
                  adjust-reads-prec
                      block-cancel-order
                          change-table
                              drop-location-type

            And now let's assume that 'adjust-reads-prec' and later 'block-cancel-order' were merged to develop.
            After running 'git machete slide-out adjust-reads-prec block-cancel-order' the tree will be reduced to:

              develop
                  change-table
                      drop-location-type

            and 'change-table' will be rebased onto develop (fork point for this rebase is configurable, see '-d' option below).

            Note: This command doesn't delete any branches from git, just removes them from the tree of branch dependencies.

            Options:
              -d, --down-fork-point=<down-fork-point-commit>    If updating by rebase, specifies the alternative fork point commit after which the rebased part of history of the downstream branch is meant to start.
                                                                Not allowed if updating by merge. See also doc for '--fork-point' option in 'git machete help reapply' and 'git machete help update'.

              -M, --merge                                       Update the downstream branch by merge rather than by rebase.

              -n                                                If updating by rebase, equivalent to '--no-interactive-rebase'. If updating by merge, equivalent to '--no-edit-merge'.

              --no-edit-merge                                   If updating by merge, skip opening the editor for merge commit message while doing 'git merge' (i.e. pass '--no-edit' flag to underlying 'git merge').
                                                                Not allowed if updating by rebase.

              --no-interactive-rebase                           If updating by rebase, run 'git rebase' in non-interactive mode (without '-i/--interactive' flag).
                                                                Not allowed if updating by merge.
        """,
        "status": """
            Usage: git machete s[tatus] [--color=WHEN] [-l|--list-commits] [-L|--list-commits-with-hashes]

            Displays a tree-shaped status of the branches listed in the definition file.

            Apart from simply ASCII-formatting the definition file, this also:
            * prints '(untracked [on <remote>]/ahead of <remote>/behind <remote>/diverged from <remote>)' message for each branch that is not in sync with its remote counterpart;
            * colors the edges between upstream (parent) and downstream (children) branches depending on whether downstream branch commit is a direct descendant of the upstream branch commit:
              - grey edge indicates the downstream branch has been merged to the upstream branch
              - red edge means that the downstream branch commit is NOT a direct descendant of the upstream branch commit (basically, the downstream branch is out of sync with its upstream branch),
              - yellow means that the opposite holds true, i.e. the downstream branch is in sync with its upstream branch, but the fork point of the downstream branch is a different commit than upstream branch tip,
              - green means that downstream branch is in sync with its upstream branch (so just like for yellow edge) and the fork point of downstream branch is EQUAL to the upstream branch tip.
            * displays the custom annotations (see help on 'format' and 'anno') next to each branch, if present;
            * displays the output of 'machete-status-branch' hook (see help on 'hooks'), if present;
            * optionally lists commits introduced on each branch if '-l'/'--list-commits' is supplied.

            Note: in practice, both yellow and red edges suggest that the downstream branch should be updated against its upstream.
            Yellow typically indicates that there are/were commits from some other branches on the path between upstream and downstream and that a closer look at the log of the downstream branch might be necessary.
            Grey edge suggests that the downstream branch can be slid out.

            Using colors can be disabled with a '--color' flag set to 'never'. With '--color=always' git machete always emits colors and with '--color=auto' it emits colors only when standard output
            is connected to a terminal. '--color=auto' is the default. When colors are disabled, relation between branches is represented in the following way:

              <branch0>
              |
              o-<branch1> # green (in sync with parent)
              | |
              | x-<branch2> # red (not in sync with parent)
              |   |
              |   ?-<branch3> # yellow (in sync with parent, but parent is not the fork point)
              |
              m-<branch4> # grey (merged to parent)

            Options:
              --color=WHEN                      Colorize the output; WHEN can be 'always', 'auto' (default; i.e. only if stdout is a terminal), or 'never'.

              -l, --list-commits                Additionally list the commits introduced on each branch.

              -L, --list-commits-with-hashes    Additionally list the short hashes and messages of commits introduced on each branch.
        """,
        "traverse": """
            Usage: git machete traverse [-F|--fetch] [-l|--list-commits] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase] [--return-to=WHERE] [--start-from=WHERE] [-w|--whole] [-W] [-y|--yes]

            Traverses the branch dependency in pre-order (i.e. simply in the order as they occur in the definition file) and for each branch:
            * if the branch is merged to its parent/upstream:
              - asks the user whether to slide out the branch from the dependency tree (typically branches are longer needed after they're merged);
            * otherwise, if the branch is not in "green" sync with its parent/upstream (see help for 'status'):
              - asks the user whether to rebase (default) or merge (if '--merge' passed) the branch onto into its upstream branch - equivalent to 'git machete update' with no '--fork-point' option passed;

            * if the branch is not tracked on a remote, is ahead of its remote counterpart, or diverged from the counterpart & has newer head commit than the counterpart:
              - asks the user whether to push the branch (possibly with '--force-with-lease' if the branches diverged);
            * otherwise, if the branch diverged from the remote counterpart & has older head commit than the counterpart:
              - asks the user whether to 'git reset --keep' the branch to its remote counterpart
            * otherwise, if the branch is behind its remote counterpart:
              - asks the user whether to pull the branch;

            * and finally, if any of the above operations has been successfully completed:
              - prints the updated 'status'.

            Note that even if the traverse flow is stopped (typically due to merge/rebase conflicts), running 'git machete traverse' after the merge/rebase is finished will pick up the walk where it stopped.
            In other words, there is no need to explicitly ask to "continue" as it is the case with e.g. 'git rebase'.

            Options:
              -F, --fetch                  Fetch the remotes of all managed branches at the beginning of traversal (no 'git pull' involved, only 'git fetch').

              -l, --list-commits           When printing the status, additionally list the messages of commits introduced on each branch.

              -M, --merge                  Update by merge rather than by rebase.

              -n                           If updating by rebase, equivalent to '--no-interactive-rebase'. If updating by merge, equivalent to '--no-edit-merge'.

              --no-edit-merge              If updating by merge, skip opening the editor for merge commit message while doing 'git merge' (i.e. pass '--no-edit' flag to underlying 'git merge').
                                           Not allowed if updating by rebase.

              --no-interactive-rebase      If updating by rebase, run 'git rebase' in non-interactive mode (without '-i/--interactive' flag).
                                           Not allowed if updating by merge.

              --return-to=WHERE            Specifies the branch to return after traversal is successfully completed; WHERE can be 'here' (the current branch at the moment when traversal starts),
                                           'nearest-remaining' (nearest remaining branch in case the 'here' branch has been slid out by the traversal)
                                           or 'stay' (the default - just stay wherever the traversal stops).
                                           Note: when user quits by 'q/yq' or when traversal is stopped because one of git actions fails, the behavior is always 'stay'.

              --start-from=WHERE           Specifies the branch to start the traversal from; WHERE can be 'here' (the default - current branch, must be managed by git-machete),
                                           'root' (root branch of the current branch, as in 'git machete show root') or 'first-root' (first listed managed branch).

              -w, --whole                  Equivalent to '-n --start-from=first-root --return-to=nearest-remaining';
                                           useful for quickly traversing & syncing all branches (rather than doing more fine-grained operations on the local section of the branch tree).

              -W                           Equivalent to '--fetch --whole'; useful for even more automated traversal of all branches.

              -y, --yes                    Don't ask for any interactive input, including confirmation of rebase/push/pull. Implicates '-n'.
        """,
        "update": """
            Usage: git machete update [-f|--fork-point=<fork-point-commit>] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase]

            Synchronizes the current branch with its upstream (parent) branch either by rebase (default) or by merge (if '--merge' option passed).

            If updating by rebase, interactively rebases the current branch on the top of its upstream (parent) branch.
            The chunk of the history to be rebased starts at the fork point of the current branch, which by default is inferred automatically, but can also be set explicitly by '--fork-point'.
            See 'git machete help fork-point' for more details on meaning of the "fork point".

            If updating by merge, merges the upstream (parent) branch into the current branch.

            Options:
              -f, --fork-point=<fork-point-commit>    If updating by rebase, specifies the alternative fork point commit after which the rebased part of history is meant to start.
                                                      Not allowed if updating by merge.

              -M, --merge                             Update by merge rather than by rebase.

              -n                                      If updating by rebase, equivalent to '--no-interactive-rebase'. If updating by merge, equivalent to '--no-edit-merge'.

              --no-edit-merge                         If updating by merge, skip opening the editor for merge commit message while doing 'git merge' (i.e. pass '--no-edit' flag to underlying 'git merge').
                                                      Not allowed if updating by rebase.

              --no-interactive-rebase                 If updating by rebase, run 'git rebase' in non-interactive mode (without '-i/--interactive' flag).
                                                      Not allowed if updating by merge.
        """,
        "version": """
            Usage: git machete version

            Prints the version and exits.
        """
    }
    aliases = {
        "diff": "d",
        "edit": "e",
        "go": "g",
        "log": "l",
        "status": "s"
    }
    inv_aliases = {v: k for k, v in aliases.items()}
    groups = [
        ("General topics", ["file", "format", "help", "hooks", "version"]),
        ("Build, display and modify the tree of branch dependencies", ["add", "anno", "discover", "edit", "status"]),  # 'infer' is deprecated and therefore skipped
        ("List, check out and delete branches", ["delete-unmanaged", "go", "list", "show"]),  # 'prune-branches' is deprecated and therefore skipped
        ("Determine changes specific to the given branch", ["diff", "fork-point", "log"]),
        ("Update git history in accordance with the tree of branch dependencies", ["reapply", "slide-out", "traverse", "update"])
    ]
    if c and c in inv_aliases:
        c = inv_aliases[c]
    if c and c in long_docs:
        print(textwrap.dedent(long_docs[c]))
    else:
        short_usage()
        if c and c not in long_docs:
            print("\nUnknown command: '%s'" % c)
        print("\n%s\n\n    Get familiar with the help for %s, %s, %s and %s, in this order.\n" % (
            underline("TL;DR tip"), bold("format"), bold("edit"), bold("status"), bold("update"))
        )
        for hdr, cmds in groups:
            print(underline(hdr))
            print("")
            for cm in cmds:
                alias = (", " + aliases[cm]) if cm in aliases else ""
                print("    %s%-18s%s%s" % (BOLD, cm + alias, ENDC, short_docs[cm]))
            sys.stdout.write("\n")
        print(textwrap.dedent("""
            %s\n
                --debug           Log detailed diagnostic info, including outputs of the executed git commands.
                -h, --help        Print help and exit.
                -v, --verbose     Log the executed git commands.
                --version         Print version and exit.
        """[1:] % underline("General options")))


def short_usage():
    print("Usage: git machete [--debug] [-h] [-v|--verbose] [--version] <command> [command-specific options] [command-specific argument]")


def version():
    print('git-machete version ' + __version__)


def main():
    launch(sys.argv[1:])


def launch(orig_args):
    def parse_options(in_args, short_opts="", long_opts=[], gnu=True):
        global ascii_only
        global opt_checked_out_since, opt_color, opt_debug, opt_down_fork_point, opt_fetch, opt_fork_point, opt_inferred, opt_list_commits, opt_list_commits_with_hashes, opt_merge, opt_n, opt_no_edit_merge
        global opt_no_interactive_rebase, opt_onto, opt_override_to, opt_override_to_inferred, opt_override_to_parent, opt_return_to, opt_roots, opt_start_from, opt_stat, opt_unset_override, opt_verbose, opt_yes

        fun = getopt.gnu_getopt if gnu else getopt.getopt
        opts, rest = fun(in_args, short_opts + "hv", long_opts + ['debug', 'help', 'verbose', 'version'])

        for opt, arg in opts:
            if opt == "--color":
                opt_color = arg
            elif opt in ("-C", "--checked-out-since"):
                opt_checked_out_since = arg
            elif opt in ("-d", "--down-fork-point"):
                opt_down_fork_point = arg
            elif opt == "--debug":
                opt_debug = True
            elif opt in ("-f", "--fork-point"):
                opt_fork_point = arg
            elif opt in ("-F", "--fetch"):
                opt_fetch = True
            elif opt in ("-h", "--help"):
                usage(cmd)
                sys.exit()
            elif opt == "--inferred":
                opt_inferred = True
            elif opt in ("-L", "--list-commits-with-hashes"):
                opt_list_commits = opt_list_commits_with_hashes = True
            elif opt in ("-l", "--list-commits"):
                opt_list_commits = True
            elif opt in ("-M", "--merge"):
                opt_merge = True
            elif opt == "-n":
                opt_n = True
            elif opt == "--no-edit-merge":
                opt_no_edit_merge = True
            elif opt == "--no-interactive-rebase":
                opt_no_interactive_rebase = True
            elif opt in ("-o", "--onto"):
                opt_onto = arg
            elif opt == "--override-to":
                opt_override_to = arg
            elif opt == "--override-to-inferred":
                opt_override_to_inferred = True
            elif opt == "--override-to-parent":
                opt_override_to_parent = True
            elif opt in ("-r", "--roots"):
                opt_roots = arg.split(",")
            elif opt == "--return-to":
                opt_return_to = arg
            elif opt == "--start-from":
                opt_start_from = arg
            elif opt in ("-s", "--stat"):
                opt_stat = True
            elif opt == "--unset-override":
                opt_unset_override = True
            elif opt in ("-v", "--verbose"):
                opt_verbose = True
            elif opt == "--version":
                version()
                sys.exit()
            elif opt in ("-w", "--whole"):
                opt_start_from = "first-root"
                opt_n = True
                opt_return_to = "nearest-remaining"
            elif opt == "-W":
                opt_fetch = True
                opt_start_from = "first-root"
                opt_n = True
                opt_return_to = "nearest-remaining"
            elif opt in ("-y", "--yes"):
                opt_yes = opt_no_interactive_rebase = True

        if opt_color not in ("always", "auto", "never"):
            raise MacheteException("Invalid argument for '--color'. Valid arguments: always|auto|never.")
        else:
            ascii_only = opt_color == "never" or (opt_color == "auto" and not sys.stdout.isatty())

        if opt_no_edit_merge and not opt_merge:
            raise MacheteException("Option --no-edit-merge passed only makes sense when using merge and must be used together with -M/--merge")
        if opt_down_fork_point and opt_merge:
            raise MacheteException("Option -d/--down-fork-point passed only makes sense when using rebase and cannot be used together with -M/--merge.")
        if opt_fork_point and opt_merge:
            raise MacheteException("Option -f/--fork-point passed only makes sense when using rebase and cannot be used together with -M/--merge.")
        if opt_no_interactive_rebase and opt_merge:
            raise MacheteException("Option --no-interactive-rebase only makes sense when using rebase and cannot be used together with -M/--merge.")

        if opt_n and opt_merge:
            opt_no_edit_merge = True
        if opt_n and not opt_merge:
            opt_no_interactive_rebase = True

        return rest

    def expect_no_param(in_args, extra_explanation=''):
        if len(in_args) > 0:
            raise MacheteException("No argument expected for '%s'%s" % (cmd, extra_explanation))

    def check_optional_param(in_args):
        if not in_args:
            return None
        elif len(in_args) > 1:
            raise MacheteException("'%s' accepts at most one argument" % cmd)
        elif not in_args[0]:
            raise MacheteException("Argument to '%s' cannot be empty" % cmd)
        elif in_args[0][0] == "-":
            raise MacheteException("option '%s' not recognized" % in_args[0])
        else:
            return in_args[0]

    def check_required_param(in_args, allowed_values):
        if not in_args or len(in_args) > 1:
            raise MacheteException("'%s' expects exactly one argument: one of %s" % (cmd, allowed_values))
        elif not in_args[0]:
            raise MacheteException("Argument to '%s' cannot be empty; expected one of %s" % (cmd, allowed_values))
        elif in_args[0][0] == "-":
            raise MacheteException("option '%s' not recognized" % in_args[0])
        else:
            return in_args[0]

    global definition_file, up_branch
    global opt_checked_out_since, opt_color, opt_debug, opt_down_fork_point, opt_fetch, opt_fork_point, opt_inferred, opt_list_commits, opt_list_commits_with_hashes, opt_merge, opt_n, opt_no_edit_merge
    global opt_no_interactive_rebase, opt_onto, opt_override_to, opt_override_to_inferred, opt_override_to_parent, opt_return_to, opt_roots, opt_start_from, opt_stat, opt_unset_override, opt_verbose, opt_yes
    try:
        cmd = None
        opt_checked_out_since = None
        opt_color = "auto"
        opt_debug = False
        opt_down_fork_point = None
        opt_fetch = False
        opt_fork_point = None
        opt_inferred = False
        opt_list_commits = False
        opt_list_commits_with_hashes = False
        opt_merge = False
        opt_n = False
        opt_no_edit_merge = False
        opt_no_interactive_rebase = False
        opt_onto = None
        opt_override_to = None
        opt_override_to_inferred = False
        opt_override_to_parent = False
        opt_return_to = "stay"
        opt_roots = list()
        opt_start_from = "here"
        opt_stat = False
        opt_unset_override = False
        opt_verbose = False
        opt_yes = False

        cmd_and_args = parse_options(orig_args, gnu=False)
        if not cmd_and_args:
            usage()
            sys.exit(2)
        cmd = cmd_and_args[0]
        args = cmd_and_args[1:]

        if cmd not in ("format", "help"):
            definition_file = get_abs_git_subpath("machete")
            if cmd not in ("discover", "infer") and not os.path.isfile(definition_file):
                open(definition_file, 'w').close()

        directions = "d[own]|f[irst]|l[ast]|n[ext]|p[rev]|r[oot]|u[p]"

        def parse_direction(b, down_pick_mode):
            if param in ("d", "down"):
                return down(b, pick_mode=down_pick_mode)
            elif param in ("f", "first"):
                return first_branch(b)
            elif param in ("l", "last"):
                return last_branch(b)
            elif param in ("n", "next"):
                return next_branch(b)
            elif param in ("p", "prev"):
                return prev_branch(b)
            elif param in ("r", "root"):
                return root_branch(b, accept_self=False, if_unmanaged=PICK_FIRST_ROOT)
            elif param in ("u", "up"):
                return up(b, prompt_if_inferred_msg=None, prompt_if_inferred_yes_opt_msg=None)
            else:
                raise MacheteException("Usage: git machete %s %s" % (cmd, directions))

        if cmd == "add":
            param = check_optional_param(parse_options(args, "o:y", ["onto=", "yes"]))
            read_definition_file()
            add(param or current_branch())
        elif cmd == "anno":
            params = parse_options(args)
            read_definition_file()
            b = current_branch()
            expect_in_managed_branches(b)
            if params:
                annotate(b, params)
            else:
                print_annotation(b)
        elif cmd == "delete-unmanaged":
            expect_no_param(parse_options(args, "y", ["yes"]))
            read_definition_file()
            delete_unmanaged()
        elif cmd in ("d", "diff"):
            param = check_optional_param(parse_options(args, "s", ["stat"]))
            read_definition_file()
            diff(param)  # passing None if not specified
        elif cmd == "discover":
            expect_no_param(parse_options(args, "C:lr:y", ["checked-out-since=", "list-commits", "roots=", "yes"]))
            # No need to read definition file.
            discover_tree()
        elif cmd in ("e", "edit"):
            expect_no_param(parse_options(args))
            # No need to read definition file.
            edit()
        elif cmd == "file":
            expect_no_param(parse_options(args))
            # No need to read definition file.
            print(definition_file)
        elif cmd == "fork-point":
            long_options = ["inferred", "override-to=", "override-to-inferred", "override-to-parent", "unset-override"]
            param = check_optional_param(parse_options(args, "", long_options))
            read_definition_file()
            b = param or current_branch()
            if len(list(filter(None, [opt_inferred, opt_override_to, opt_override_to_inferred, opt_override_to_parent, opt_unset_override]))) > 1:
                long_options_string = ", ".join(map(lambda x: x.replace("=", ""), long_options))
                raise MacheteException("At most one of %s options may be present" % long_options_string)
            if opt_inferred:
                print(fork_point(b, use_overrides=False))
            elif opt_override_to:
                set_fork_point_override(b, opt_override_to)
            elif opt_override_to_inferred:
                set_fork_point_override(b, fork_point(b, use_overrides=False))
            elif opt_override_to_parent:
                u = up_branch.get(b)
                if u:
                    set_fork_point_override(b, u)
                else:
                    raise MacheteException("Branch %s does not have upstream (parent) branch" % b)
            elif opt_unset_override:
                unset_fork_point_override(b)
            else:
                print(fork_point(b, use_overrides=True))
        elif cmd == "format":
            # No need to read definition file.
            usage("format")
        elif cmd in ("g", "go"):
            param = check_required_param(parse_options(args), directions)
            read_definition_file()
            expect_no_operation_in_progress()
            cb = current_branch()
            dest = parse_direction(cb, down_pick_mode=True)
            if dest != cb:
                go(dest)
        elif cmd == "help":
            param = check_optional_param(parse_options(args))
            # No need to read definition file.
            usage(param)
        elif cmd == "infer":  # TODO: deprecated in favor of 'discover'
            expect_no_param(parse_options(args, "l", ["list-commits"]))
            # No need to read definition file.
            discover_tree()
        elif cmd == "list":
            list_allowed_values = "managed|slidable|slidable-after <branch>|unmanaged|with-overridden-fork-point"
            list_args = parse_options(args)
            if not list_args:
                raise MacheteException("'git machete list' expects argument(s): %s" % list_allowed_values)
            elif not list_args[0]:
                raise MacheteException("Argument to 'git machete list' cannot be empty; expected %s" % list_allowed_values)
            elif list_args[0][0] == "-":
                raise MacheteException("option '%s' not recognized" % list_args[0])
            elif list_args[0] not in ("managed", "slidable", "slidable-after", "unmanaged", "with-overridden-fork-point"):
                raise MacheteException("Usage: git machete list %s" % list_allowed_values)
            elif len(list_args) > 2:
                raise MacheteException("Too many arguments to 'git machete list %s' " % list_args[0])
            elif list_args[0] in ("managed", "slidable", "unmanaged", "with-overridden-fork-point") and len(list_args) > 1:
                raise MacheteException("'git machete list %s' does not expect extra arguments" % list_args[0])
            elif list_args[0] == "slidable-after" and len(list_args) != 2:
                raise MacheteException("'git machete list %s' requires an extra <branch> argument" % list_args[0])

            param = list_args[0]
            read_definition_file()
            res = []
            if param == "managed":
                res = managed_branches
            elif param == "slidable":
                res = slidable()
            elif param == "slidable-after":
                b_arg = list_args[1]
                expect_in_managed_branches(b_arg)
                res = slidable_after(b_arg)
            elif param == "unmanaged":
                res = excluding(local_branches(), managed_branches)
            elif param == "with-overridden-fork-point":
                res = list(filter(has_any_fork_point_override_config, local_branches()))

            if res:
                print("\n".join(res))
        elif cmd in ("l", "log"):
            param = check_optional_param(parse_options(args))
            read_definition_file()
            log(param or current_branch())
        elif cmd == "prune-branches":  # TODO: deprecated in favor of 'delete-unmanaged'
            expect_no_param(parse_options(args, "y", ["yes"]))
            read_definition_file()
            delete_unmanaged()
        elif cmd == "reapply":
            args1 = parse_options(args, "f:", ["fork-point="])
            expect_no_param(args1, ". Use '-f' or '--fork-point' to specify the fork point commit")
            read_definition_file()
            expect_no_operation_in_progress()
            cb = current_branch()
            rebase_onto_ancestor_commit(cb, opt_fork_point or fork_point(cb, use_overrides=True))
        elif cmd == "show":
            param = check_required_param(parse_options(args), directions)
            read_definition_file()
            print(parse_direction(current_branch(), down_pick_mode=False))
        elif cmd == "slide-out":
            params = parse_options(args, "d:Mn", ["down-fork-point=", "merge", "no-edit-merge", "no-interactive-rebase"])
            read_definition_file()
            expect_no_operation_in_progress()
            slide_out(params or [current_branch()])
        elif cmd in ("s", "status"):
            expect_no_param(parse_options(args, "Ll", ["color=", "list-commits-with-hashes", "list-commits"]))
            read_definition_file()
            expect_at_least_one_managed_branch()
            status(warn_on_yellow_edges=True)
        elif cmd == "traverse":
            traverse_long_opts = ["fetch", "list-commits", "merge", "no-edit-merge", "no-interactive-rebase", "return-to=", "start-from=", "whole", "yes"]
            expect_no_param(parse_options(args, "FlMnWwy", traverse_long_opts))
            if opt_start_from not in ("here", "root", "first-root"):
                raise MacheteException("Invalid argument for '--start-from'. Valid arguments: here|root|first-root.")
            if opt_return_to not in ("here", "nearest-remaining", "stay"):
                raise MacheteException("Invalid argument for '--return-to'. Valid arguments: here|nearest-remaining|stay.")
            read_definition_file()
            expect_no_operation_in_progress()
            traverse()
        elif cmd == "update":
            args1 = parse_options(args, "f:Mn", ["fork-point=", "merge", "no-edit-merge", "no-interactive-rebase"])
            expect_no_param(args1, ". Use '-f' or '--fork-point' to specify the fork point commit")
            read_definition_file()
            expect_no_operation_in_progress()
            update()
        elif cmd == "version":
            version()
            sys.exit()
        else:
            short_usage()
            raise MacheteException("\nUnknown command: '%s'. Use 'git machete help' to list possible commands" % cmd)

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


if __name__ == "__main__":
    main()
