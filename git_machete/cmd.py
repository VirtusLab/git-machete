#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

import getopt
import itertools
import os
import subprocess
import sys
import textwrap

VERSION = '2.8.5'


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
YELLOW = '\033[00;38;5;220m'
ORANGE = '\033[00;38;5;208m'
RED = '\033[91m'


def bold(s):
    return BOLD + s + ENDC


def dim(s):
    return DIM + s + ENDC


def underline(s):
    return UNDERLINE + s + ENDC


def flat_map(func, l):
    return sum(map(func, l), [])


def non_empty_lines(s):
    return filter(None, s.split("\n"))


def excluding(l, s):
    return filter(lambda x: x not in s, l)


def join_branch_names(bs, sep):
    return sep.join("'%s'" % x for x in bs)


def ask_if(msg):
    return raw_input(msg).lower() in ('y', 'yes')


def pick(choices, name):
    xs = "".join("[%i] %s\n" % (idx + 1, x) for idx, x in enumerate(choices))
    msg = xs + "Specify " + name + " or hit <return> to skip: "
    try:
        idx = int(raw_input(msg)) - 1
    except ValueError:
        sys.exit(1)
    if idx not in range(len(choices)):
        raise MacheteException("Invalid index: %i" % (idx + 1))
    return choices[idx]


def debug(hdr, msg):
    if opt_debug:
        print >> sys.stderr, "%s: %s" % (bold(hdr), dim(msg))


def run_cmd(cmd, *args):
    return subprocess.call([cmd] + list(args))


def popen_cmd(cmd, *args):
    process = subprocess.Popen([cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = process.communicate()
    return process.returncode, stdoutdata


# Git core

def run_git(git_cmd, *args, **kwargs):
    flat_cmd = " ".join(["git", git_cmd] + list(args))
    if opt_debug:
        print >> sys.stderr, underline(flat_cmd)
    elif opt_verbose:
        print >> sys.stderr, flat_cmd
    status = run_cmd("git", git_cmd, *args)
    if not kwargs.get("allow_non_zero") and status != 0:
        raise MacheteException("'%s' returned %i" % (flat_cmd, status))
    if opt_debug:
        print >> sys.stderr, dim("<status: %i>\n" % status)
    return status


def popen_git(git_cmd, *args):
    flat_cmd = " ".join(["git", git_cmd] + list(args))
    if opt_debug:
        print >> sys.stderr, underline(flat_cmd)
    elif opt_verbose:
        print >> sys.stderr, flat_cmd
    status, stdout = popen_cmd("git", git_cmd, *args)
    if status != 0:
        raise MacheteException("'%s' returned %i" % (flat_cmd, status))
    if opt_debug:
        print >> sys.stderr, dim(stdout)
    return stdout


# Manipulation on definition file/tree of branches

def expect_in_managed_branches(b):
    if b not in managed_branches:
        raise MacheteException("Branch '%s' not found in the tree of branch dependencies. "
                               "Use 'git machete add %s' or 'git machete edit'" % (b, b))


def read_definition_file():
    global definition_file, indent, managed_branches, down_branches, up_branch, roots, annotations

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
            depth = len(pfx) / len(indent)
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
    with open(definition_file + "~", "w") as backup:
        backup.write(open(definition_file).read())


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
    expect_in_managed_branches(b)
    root = root_branch(b, accept_self=True)
    root_dbs = down_branches.get(root)
    return root_dbs[0] if root_dbs else root


def last_branch(b):
    expect_in_managed_branches(b)
    d = root_branch(b, accept_self=True)
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


def root_branch(b, accept_self):
    expect_in_managed_branches(b)
    u = up_branch.get(b)
    if not u and not accept_self:
        raise MacheteException("Branch '%s' is already a root" % b)
    while u:
        b = u
        u = up_branch.get(b)
    return b


def up(b, prompt_if_inferred):
    if b in managed_branches:
        u = up_branch.get(b)
        if u:
            return u
        else:
            raise MacheteException("Branch '%s' has no upstream branch" % b)
    else:
        u = infer_upstream(b)
        if u:
            if prompt_if_inferred:
                if ask_if("Branch '%s' not found in the tree of branch dependencies; rebase onto the inferred upstream '%s'? [y/n] " % (b, u)):
                    return u
                else:
                    sys.exit(1)
            else:
                print >> sys.stderr, "Warn: branch '%s' not found in the tree of branch dependencies; the upstream has been inferred to '%s'" % (b, u)
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
        msg = "A local branch '%s' does not exist. Create (out of %s)? [y/n] " % (b, out_of)
        if ask_if(msg):
            if roots and not onto:
                cb = current_branch_or_none()
                if cb and cb in managed_branches:
                    onto = cb
            create_branch(b, onto)
        else:
            return

    if not roots:
        roots = [b]
        print "Added branch '%s' as a new root" % b
    else:
        if not onto:
            u = infer_upstream(b)
            if not u:
                raise MacheteException("Could not automatically infer upstream (parent) branch for '%s'.\n"
                                       "Specify the desired upstream branch with '--onto' or edit the definition file manually with 'git machete edit'" % b)
            elif u not in managed_branches:
                raise MacheteException("Inferred upstream (parent) branch for '%s' is '%s', but '%s' does not exist in the tree of branch dependencies.\n"
                                       "Specify other upstream branch with '--onto' or edit the definition file manually with 'git machete edit'" % (b, u, u))
            else:
                msg = "Add '%s' onto the inferred upstream (parent) branch '%s'? [y/n] " % (b, u)
                if ask_if(msg):
                    onto = u
                else:
                    return

        up_branch[b] = onto
        if onto in down_branches:
            down_branches[onto].append(b)
        else:
            down_branches[onto] = [b]
        print "Added branch '%s' onto '%s'" % (b, onto)

    save_definition_file()


def annotate(words):
    global annotations
    cb = current_branch()
    expect_in_managed_branches(cb)
    if cb in annotations and words == ['']:
        del annotations[cb]
    else:
        annotations[cb] = " ".join(words)
    save_definition_file()


def print_annotation():
    global annotations
    cb = current_branch()
    expect_in_managed_branches(cb)
    if cb in annotations:
        print annotations[cb]


# Implementation of basic git or git-related commands

def edit():
    return run_cmd(os.environ.get("EDITOR") or "vim", definition_file)


def get_git_dir():
    return popen_git("rev-parse", "--git-dir").strip()


remotes_cached = None


def remotes():
    global remotes_cached
    if remotes_cached is None:
        remotes_cached = non_empty_lines(popen_git("remote"))
    return remotes_cached


def remote_for_branch(b):
    try:
        return popen_git("config", "branch." + b + ".remote").rstrip()
    except MacheteException:
        return None


def compute_sha_by_refspec(refspec):
    try:
        return popen_git("rev-parse", "--verify", "--quiet", refspec).rstrip()
    except MacheteException:
        return None


sha_by_refspec_cached = {}


def sha_by_refspec(refspec, prefix="refs/heads"):
    global sha_by_refspec_cached
    full_refspec = prefix + "/" + refspec
    if full_refspec not in sha_by_refspec_cached:
        sha_by_refspec_cached[full_refspec] = compute_sha_by_refspec(full_refspec)
    return sha_by_refspec_cached[full_refspec]


remote_tracking_branches_cached = {}


def compute_remote_tracking_branch(b):
    try:
        # Note: no need to prefix `b` with `refs/heads/`, `@{upstream}` assumes local branch automatically.
        return popen_git("rev-parse", "--abbrev-ref", b + "@{upstream}").strip()
    except MacheteException:
        return None


def remote_tracking_branch(b):
    global remote_tracking_branches_cached
    if b not in remote_tracking_branches_cached:
        remote_tracking_branches_cached[b] = compute_remote_tracking_branch(b)
    return remote_tracking_branches_cached[b]


def current_branch_or_none():
    try:
        return popen_git("symbolic-ref", "--quiet", "HEAD").strip().replace("refs/heads/", "")
    except MacheteException:
        return None


def current_branch():
    res = current_branch_or_none()
    if res:
        return res
    else:
        raise MacheteException("Not currently on any branch")


def is_ancestor(earlier, later, earlier_prefix="refs/heads", later_prefix="refs/heads"):
    return run_git("merge-base", "--is-ancestor", earlier_prefix + "/" + earlier, later_prefix + "/" + later, allow_non_zero=True) == 0


def create_branch(b, out_of):
    return run_git("checkout", "-b", b, *(["refs/heads/" + out_of] if out_of else []))


def log_shas(refspec, max_count):
    opts = (["--max-count=" + str(max_count)] if max_count else []) + ["--format=%H", "refs/heads/" + refspec]
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


def local_branches():
    global local_branches_cached
    if local_branches_cached is None:
        local_branches_cached = get_local_branches()
    return local_branches_cached


def get_local_branches(extra_option=None):
    return non_empty_lines(popen_git("for-each-ref", "--format=%(refname:lstrip=2)", "refs/heads", *([extra_option] if extra_option else [])))


def go(branch):
    run_git("checkout", "--quiet", branch, "--")


def update(branch, fork_commit):
    run_git("rebase", "--interactive", "--onto", "refs/heads/" + up(branch, prompt_if_inferred=True), fork_commit, branch)


def reapply(branch, fork_commit):
    run_git("rebase", "--interactive", "--onto", fork_commit, fork_commit, branch)


def diff(branch):
    params = (["--stat"] if opt_stat else []) + [fork_point(branch if branch else current_branch())] + (["refs/heads/" + branch] if branch else []) + ["--"]
    run_git("diff", *params)


def log(branch):
    run_git("log", "^" + fork_point(branch), "refs/heads/" + branch)


def commits_between(earlier, later):
    return non_empty_lines(popen_git("log", "--format=%s", "^" + earlier, later, "--"))


NO_REMOTES = 0
UNTRACKED = 1
UNTRACKED_ON = 2
IN_SYNC_WITH_REMOTE = 3
BEHIND_REMOTE = 4
AHEAD_OF_REMOTE = 5
DIVERGED_FROM_REMOTE = 6


def get_relation_to_remote_counterpart(b, rb):
    b_is_anc_of_rb = is_ancestor(b, rb, later_prefix="refs/remotes")
    rb_is_anc_of_b = is_ancestor(rb, b, earlier_prefix="refs/remotes")
    if b_is_anc_of_rb:
        return IN_SYNC_WITH_REMOTE if rb_is_anc_of_b else BEHIND_REMOTE
    else:
        return AHEAD_OF_REMOTE if rb_is_anc_of_b else DIVERGED_FROM_REMOTE


def get_remote_sync_status(b):
    if not remotes():
        return NO_REMOTES, None
    remote = remote_for_branch(b)
    if not remote:
        return UNTRACKED, None
    rb = remote_tracking_branch(b)
    if not rb:
        return UNTRACKED_ON, remote
    return get_relation_to_remote_counterpart(b, rb), remote


# Reflog magic

def reflog(b):
    # %H - full hash
    # %gs - reflog subject
    return [entry.split(":", 1) for entry in non_empty_lines(popen_git("reflog", "show", "--format=%H:%gs", b, "--"))]


def adjusted_reflog(b, prefix):
    def is_relevant_reflog_subject(sha, gs):
        result = not (
            gs.startswith("branch: Created from") or
            gs == "branch: Reset to " + b or
            gs == "branch: Reset to HEAD" or
            gs.startswith("reset: moving to ") or
            gs == "rebase finished: %s/%s onto %s" % (prefix, b, sha)
        )
        if not result:
            debug("adjusted_reflog(%s, %s) -> is_relevant_reflog_subject(%s, <<<%s>>>)" % (b, prefix, sha, gs), "skipping reflog entry")
        return result

    result = [sha for (sha, gs) in reflog(prefix + "/" + b) if is_relevant_reflog_subject(sha, gs)]
    debug("adjusted_reflog(%s, %s)" % (b, prefix), "computed adjusted reflog (= reflog without branch creation and branch reset events irrelevant for fork point/upstream inference): %s\n" %
          (", ".join(result) or "<empty>"))
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
                for sha in adjusted_reflog(lb, "refs/heads"):
                    lb_shas.add(sha)
                    yield sha, (lb, lb)
                rb = remote_tracking_branch(lb)
                if rb:
                    for sha in adjusted_reflog(rb, "refs/remotes"):
                        if sha not in lb_shas:
                            yield sha, (lb, rb)

        branch_defs_by_sha_in_reflog = {}
        for sha, branch_def in generate_entries():
            if sha in branch_defs_by_sha_in_reflog:
                # The practice shows that it's rather unlikely for a given commit to appear on adjusted reflogs of two unrelated branches
                # ("unrelated" as in, not a local branch and its remote counterpart) but we need to handle this case anyway.
                branch_defs_by_sha_in_reflog[sha] += [branch_def]
            else:
                branch_defs_by_sha_in_reflog[sha] = [branch_def]

        def log_result():
            for sha, branch_defs in branch_defs_by_sha_in_reflog.items():
                yield dim("%s => %s" %
                          (sha, ", ".join(map(lambda (lb, lb_or_rb): lb if lb == lb_or_rb else "%s (remote counterpart of %s)" % (lb_or_rb, lb), branch_defs))))

        debug("match_log_to_adjusted_reflogs(%s)" % b, "branches containing the given SHA in their adjusted reflog: \n%s\n" % "\n".join(log_result()))

    for sha in spoonfeed_log_shas(b):
        if sha in branch_defs_by_sha_in_reflog:
            containing_branch_defs = filter(lambda (lb, lb_or_rb): lb != b, branch_defs_by_sha_in_reflog[sha])
            if containing_branch_defs:
                debug("match_log_to_adjusted_reflogs(%s)" % b, "commit %s found in adjusted reflog of %s" % (sha, " and ".join(map(lambda (lb, lb_or_rb): lb_or_rb, branch_defs_by_sha_in_reflog[sha]))))
                yield sha, containing_branch_defs
            else:
                debug("match_log_to_adjusted_reflogs(%s)" % b, "commit %s found only in adjusted reflog of %s; ignoring" % (sha, " and ".join(map(lambda (lb, lb_or_rb): lb_or_rb, branch_defs_by_sha_in_reflog[sha]))))
        else:
            debug("match_log_to_adjusted_reflogs(%s)" % b, "commit %s not found in any adjusted reflog" % sha)


# Complex subcommands

def infer_upstream(b, condition=lambda u: True, reject_reason_message=""):
    for sha, containing_branch_defs in match_log_to_adjusted_reflogs(b):
        debug("infer_upstream(%s)" % b, "commit %s found in adjusted reflog of %s" % (sha, " and ".join(map(lambda (x, y): y, containing_branch_defs))))

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
    global managed_branches, roots, down_branches, up_branch, indent, annotations
    managed_branches = local_branches()
    if not managed_branches:
        raise MacheteException("No local branches found")
    roots = []
    down_branches = {}
    up_branch = {}
    indent = "\t"
    annotations = {}

    root_of = dict((b, b) for b in managed_branches)

    def get_root_of(b):
        if b != root_of[b]:
            root_of[b] = get_root_of(root_of[b])
        return root_of[b]

    for b in managed_branches:
        u = infer_upstream(b, condition=lambda u: get_root_of(u) != b, reject_reason_message="choosing this candidate would form a cycle in the resulting graph")
        if u:
            debug("discover_tree()", "inferred upstream of %s "
                                     "is %s, attaching %s as a child of %s\n" % (b, u, b, u))
            up_branch[b] = u
            root_of[b] = u
            if u in down_branches:
                down_branches[u].append(b)
            else:
                down_branches[u] = [b]
        else:
            debug("discover_tree()", "inferred no upstream for %s, attaching %s as a new root\n" % (b, b))
            roots += [b]

    print bold('Discovered tree of branch dependencies:\n')
    status()
    print
    do_backup = os.path.exists(definition_file)
    backup_msg = ("The existing definition file will be backed up as '%s~' " % definition_file) if do_backup else ""
    msg = "Save the above tree to '%s'? %s(y[es]/e[dit]/n[o]) " % (definition_file, backup_msg)
    reply = raw_input(msg).lower()
    if reply in ('y', 'yes'):
        if do_backup:
            back_up_definition_file()
        save_definition_file()
    elif reply in ('e', 'edit'):
        if do_backup:
            back_up_definition_file()
        save_definition_file()
        edit()


def fork_point(b):
    try:
        sha, containing_branch_defs = next(match_log_to_adjusted_reflogs(b))
    except StopIteration:
        raise MacheteException("Cannot find fork point for branch '%s'" % b)

    debug("fork_point(%s)" % b,
          "commit %s is the most recent point in history of %s to occur on adjusted reflog of any other branch or its remote counterpart (specifically: %s)\n" %
          (sha, b, " and ".join(map(lambda (lb, lb_or_rb): lb_or_rb, containing_branch_defs))))
    return sha


def delete_unmanaged():
    branches_to_delete = excluding(local_branches(), managed_branches)
    cb = current_branch_or_none()
    if cb and cb in branches_to_delete:
        branches_to_delete = excluding(branches_to_delete, [cb])
        print "Skipping current branch '%s'" % cb
    if branches_to_delete:
        branches_merged_to_head = get_local_branches("--merged")

        branches_to_delete_merged_to_head = [b for b in branches_to_delete if b in branches_merged_to_head]
        for b in branches_to_delete_merged_to_head:
            rb = remote_tracking_branch(b)
            is_merged_to_remote = is_ancestor(b, rb, later_prefix="refs/remotes") if rb else True
            msg = "Delete branch %s (merged to HEAD%s)? [y/n/q] " % (
                bold(b), "" if is_merged_to_remote else (", but not merged to " + rb)
            )
            ans = raw_input(msg).lower()
            if ans in ('y', 'yes'):
                run_git("branch", "-d" if is_merged_to_remote else "-D", b)
            elif ans in ('q', 'quit'):
                return

        branches_to_delete_unmerged_to_head = [b for b in branches_to_delete if b not in branches_merged_to_head]
        for b in branches_to_delete_unmerged_to_head:
            msg = "Delete branch %s (unmerged to HEAD)? [y/n/q] " % bold(b)
            ans = raw_input(msg).lower()
            if ans in ('y', 'yes'):
                run_git("branch", "-D", b)
            elif ans in ('q', 'quit'):
                return
    else:
        print >> sys.stderr, "No branches to delete"


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
    update(d, opt_down_fork_point or fork_point(d))


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


class StopTraversal:
    def __init__(self):
        pass


def traverse():
    global down_branches, up_branch, empty_line_status, managed_branches

    def flush():
        global branch_defs_by_sha_in_reflog, initial_log_shas_cached, remaining_log_shas_cached, remote_tracking_branches_cached, sha_by_refspec_cached
        branch_defs_by_sha_in_reflog = None
        initial_log_shas_cached = {}
        remaining_log_shas_cached = {}
        remote_tracking_branches_cached = {}
        sha_by_refspec_cached = {}

    empty_line_status = True

    def print_new_line(new_status):
        global empty_line_status
        if not empty_line_status:
            print
        empty_line_status = new_status

    cb = current_branch()
    expect_in_managed_branches(cb)

    for b in itertools.dropwhile(lambda x: x != cb, managed_branches):
        u = up_branch.get(b)

        needs_slide_out = u and is_ancestor(b, u) and sha_by_refspec(u) != sha_by_refspec(b)
        if needs_slide_out:
            # Avoid unnecessary fork point check if we already now that the branch qualifies for slide out.
            needs_rebase = False
        else:
            needs_rebase = u and not (is_ancestor(u, b) and sha_by_refspec(u) == fork_point(b))
        s, remote = get_remote_sync_status(b)
        statuses_to_sync = (UNTRACKED, UNTRACKED_ON, AHEAD_OF_REMOTE, BEHIND_REMOTE, DIVERGED_FROM_REMOTE)
        needs_remote_sync = s in statuses_to_sync

        if b != cb and (needs_slide_out or needs_rebase or needs_remote_sync):
            print_new_line(False)
            print >> sys.stderr, "Checking out %s" % bold(b)
            go(b)
            cb = b
            print_new_line(False)
            status()
            print_new_line(True)
        if needs_slide_out:
            print_new_line(False)
            ans = raw_input("Branch %s is merged into %s. Slide %s out of the tree of branch dependencies? [y/n/q] " %
                            (bold(b), bold(u), bold(b))).lower()
            if ans in ('y', 'yes'):
                for d in down_branches.get(b) or []:
                    up_branch[d] = u
                down_branches[u] = flat_map(lambda ud: (down_branches.get(b) or []) if ud == b else [ud],
                                            down_branches[u])
                if b in annotations:
                    del annotations[b]
                save_definition_file()
                # No need to flush caches since nothing changed in commit/branch structure (only machete-specific changes happened).
                continue  # No need to sync branch `b` with remote since it just got removed from the tree of dependencies.
            elif ans in ('q', 'quit'):
                return
            # If user answered 'no', we don't try to rebase but still suggest to sync with remote (if needed).
        elif needs_rebase:
            print_new_line(False)
            ans = raw_input("Rebase %s onto %s? [y/n/q] " % (bold(b), bold(u))).lower()
            if ans in ('y', 'yes'):
                update(b, fork_point(b))
                flush()
                s, remote = get_remote_sync_status(b)
                needs_remote_sync = s in statuses_to_sync
            elif ans in ('q', 'quit'):
                return

        if needs_remote_sync:
            if s == BEHIND_REMOTE:
                rb = remote_tracking_branch(b)
                ans = raw_input("Branch %s is behind its remote counterpart %s.\nPull %s from %s? [y/n/q] " %
                                (bold(b), bold(rb), bold(b), bold(remote))).lower()
                if ans in ('y', 'yes'):
                    run_git("pull", "--ff-only", remote)
                    flush()
                    print
                elif ans in ('q', 'quit'):
                    raise StopTraversal

            elif s == UNTRACKED_ON or s == AHEAD_OF_REMOTE:
                print_new_line(False)
                # `remote` is defined for both cases we handle here, including UNTRACKED_ON
                ans = raw_input("Push %s to %s? [y/n/q] " % (bold(b), bold(remote))).lower()
                if ans in ('y', 'yes'):
                    run_git("push", remote)
                    flush()
                elif ans in ('q', 'quit'):
                    raise StopTraversal

            elif s == DIVERGED_FROM_REMOTE:
                print_new_line(False)
                rb = remote_tracking_branch(b)
                ans = raw_input("Branch %s diverged from its remote counterpart %s.\nPush %s with force to %s? [y/n/q] " %
                                (bold(b), bold(rb), bold(b), bold(remote))).lower()
                if ans in ('y', 'yes'):
                    run_git("push", "--force", remote)
                    flush()
                elif ans in ('q', 'quit'):
                    raise StopTraversal

            elif s == UNTRACKED:
                rems = remotes()

                def handle_untracked_branch(new_remote):
                    can_pick_other_remote = len(rems) > 1
                    other_remote_suffix = "/o[ther remote]" if can_pick_other_remote else ""
                    rb = new_remote + "/" + b
                    if not sha_by_refspec(rb, prefix="refs/remotes"):
                        ans = raw_input("Push untracked branch %s to %s? (y/n/q%s) " % (bold(b), bold(new_remote), other_remote_suffix)).lower()
                        if ans in ('y', 'yes'):
                            run_git("push", "--set-upstream", new_remote, b)
                            flush()
                        elif can_pick_other_remote and ans in ('o', 'other'):
                            pick_remote()
                        elif ans in ('q', 'quit'):
                            raise StopTraversal
                        return

                    new_s = get_relation_to_remote_counterpart(b, rb)
                    if new_s == IN_SYNC_WITH_REMOTE:
                        print "Branch %s is untracked, but its remote counterpart candidate %s already exists and the two branches point to the same commit." % (bold(b), bold(rb))
                        ans = raw_input("Set the remote of %s to %s without pushing or pulling? (y/n/q%s) " % (bold(b), bold(new_remote), other_remote_suffix)).lower()
                        if ans in ('y', 'yes'):
                            run_git("branch", "--set-upstream-to", rb)
                            flush()
                        elif can_pick_other_remote and ans in ('o', 'other'):
                            pick_remote()
                        elif ans in ('q', 'quit'):
                            raise StopTraversal
                    elif new_s == BEHIND_REMOTE:
                        print "Branch %s is untracked, but its remote counterpart candidate %s already exists and is ahead of %s." % (bold(b), bold(rb), bold(b))
                        ans = raw_input("Pull %s from %s? (y/n/q%s) " % (bold(b), bold(new_remote), other_remote_suffix)).lower()
                        if ans in ('y', 'yes'):
                            run_git("pull", "--ff-only", new_remote, b)
                            # There's apparently no way to set remote automatically when doing `git pull` (as it is with `git push`), so a separate `git branch --set-upstream-to` is needed.
                            run_git("branch", "--set-upstream-to", rb)
                            flush()
                        elif can_pick_other_remote and ans in ('o', 'other'):
                            pick_remote()
                        elif ans in ('q', 'quit'):
                            raise StopTraversal
                    elif new_s == AHEAD_OF_REMOTE:
                        print "Branch %s is untracked, but its remote counterpart candidate %s already exists and is behind %s." % (bold(b), bold(rb), bold(b))
                        ans = raw_input("Push branch %s to %s? (y/n/q%s) " % (bold(b), bold(new_remote), other_remote_suffix)).lower()
                        if ans in ('y', 'yes'):
                            run_git("push", "--set-upstream", new_remote, b)
                            flush()
                        elif can_pick_other_remote and ans in ('o', 'other'):
                            pick_remote()
                        elif ans in ('q', 'quit'):
                            raise StopTraversal
                    elif new_s == DIVERGED_FROM_REMOTE:
                        print "Branch %s is untracked, but its remote counterpart candidate %s already exists and the two branches are diverged." % (bold(b), bold(rb))
                        ans = raw_input("Push branch %s with force to %s? (y/n/q%s) " % (bold(b), bold(new_remote), other_remote_suffix)).lower()
                        if ans in ('y', 'yes'):
                            run_git("push", "--set-upstream", "--force", new_remote, b)
                            flush()
                        elif can_pick_other_remote and ans in ('o', 'other'):
                            pick_remote()
                        elif ans in ('q', 'quit'):
                            raise StopTraversal

                def pick_remote():
                    print "\n".join("[%i] %s" % (idx + 1, r) for idx, r in enumerate(rems))
                    msg = "Select number 1..%i to specify the destination remote repository, or 'n' to skip this branch, or 'q' to quit the traverse: " % len(rems)
                    ans = raw_input(msg).lower()
                    if ans in ('q', 'quit'):
                        raise StopTraversal
                    try:
                        idx = int(ans) - 1
                        if idx not in range(len(rems)):
                            raise MacheteException("Invalid index: %i" % (idx + 1))
                        handle_untracked_branch(rems[idx])
                    except ValueError:
                        pass

                print_new_line(False)
                if len(rems) == 1:
                    handle_untracked_branch(rems[0])
                elif "origin" in rems:
                    handle_untracked_branch("origin")
                else:
                    # We know that there is at least 1 remote, otherwise `s` would be `NO_REMOTES`
                    print "Branch %s is untracked and there's no %s repository." % (bold(b), bold("origin"))
                    pick_remote()

    print_new_line(False)
    status()
    print
    msg = "Reached branch %s which has no successor" if cb == managed_branches[-1] else "No successor of %s needs sync with upstream branch or remote"
    print >> sys.stderr, msg % bold(cb) + "; nothing left to update"


def status():
    global sha_by_refspec_cached

    dfs_res = []

    def prefix_dfs(u, prefix):
        dfs_res.append((u, prefix))
        if down_branches.get(u):
            for (v, nv) in zip(down_branches[u][:-1], down_branches[u][1:]):
                prefix_dfs(v, prefix + [nv])
            prefix_dfs(down_branches[u][-1], prefix + [None])

    for u in roots:
        prefix_dfs(u, prefix=[])

    needs_sync_with_up_branch = {}
    remote_sync_status = {}
    commits_cached = {}
    fork_points_cached = {}
    for b, pfx in dfs_res:
        if b in up_branch:
            needs_sync_with_up_branch[b] = not is_ancestor(up_branch[b], b)
            # Force computing all needed fork points to avoid later polluting the printed status in case of --verbose mode.
            try:
                fork_points_cached[b] = fork_point(b)
            except MacheteException:
                fork_points_cached[b] = None
            if opt_list_commits:
                commits_cached[b] = reversed(commits_between(fork_points_cached[b], "refs/heads/" + b)) if fork_points_cached[b] else []
        # Force computing all needed SHAs to avoid later polluting the printed status in case of --verbose mode.
        sha_by_refspec(b)
        remote_sync_status[b] = get_remote_sync_status(b)

    def edge_color(b):
        return RED if needs_sync_with_up_branch[b] else (GREEN if sha_by_refspec(up_branch[b]) == fork_points_cached[b] else YELLOW)

    def print_line_prefix(b, suffix):
        sys.stdout.write("  ")
        for p in pfx[:-1]:
            if not p:
                sys.stdout.write("  ")
            else:
                sys.stdout.write(edge_color(p) + "│ " + ENDC)
        sys.stdout.write(edge_color(b) + suffix + ENDC)

    cb = current_branch_or_none()

    for b, pfx in dfs_res:
        current = bold(b) + ("  " + dim(annotations[b]) if b in annotations else "")
        current_ul = underline(current) if b == cb else current
        if b in up_branch:
            print_line_prefix(b, "│ \n")
            if opt_list_commits:
                for msg in commits_cached[b]:
                    print_line_prefix(b, "│ " + ENDC + DIM + msg + "\n")
            print_line_prefix(b, "└─")
        else:
            if b != dfs_res[0][0]:
                print
            sys.stdout.write("  ")
        s, remote = remote_sync_status[b]
        sync_status_string = {
            NO_REMOTES: "",
            UNTRACKED: ORANGE + " (untracked)" + ENDC,
            UNTRACKED_ON: ORANGE + " (untracked on %s)" % remote + ENDC,
            IN_SYNC_WITH_REMOTE: "",
            BEHIND_REMOTE: RED + " (behind %s)" % remote + ENDC,
            AHEAD_OF_REMOTE: RED + " (ahead of %s)" % remote + ENDC,
            DIVERGED_FROM_REMOTE: RED + " (diverged from %s)" % remote + ENDC
        }
        print current_ul + sync_status_string[s]


# Main

def usage(c=None):
    short_docs = {
        "add": "Add a branch to the tree of branch dependencies",
        "anno": "Manage custom annotations",
        "delete-unmanaged": "Delete local branches that are not present in the definition file",
        "diff": "Diff current working directory or a given branch against its computed fork point",
        "discover": "Automatically discover tree of branch dependencies",
        "edit": "Edit the definition file",
        "file": "Print path of the definition file",
        "fork-point": "Print SHA of the computed fork point commit of a branch",
        "format": "Print information about the format of the definition file",
        "go": "Check out the branch relative to the position of the current branch, accepts down/first/last/next/root/prev/up argument",
        "help": "Print this overview, or print detailed help for a specified command",
        "list": "List all branches that fall into one of pre-defined categories (mostly for internal use)",
        "log": "Log the part of history specific to the given branch",
        "reapply": "Rebase the current branch onto its computed fork point",
        "show": "Print name(s) of the branch(es) relative to the position of the current branch, accepts down/first/last/next/root/prev/up argument",
        "slide-out": "Slide the current branch out and rebase its downstream (child) branch onto its upstream (parent) branch",
        "status": "Print formatted tree of branch dependencies, including info on their sync with upstream branch and with remote",
        "traverse": "Walk through the tree of branch dependencies and ask to rebase and/or push branches, one by one",
        "update": "Rebase the current branch onto its upstream (parent) branch"
    }
    long_docs = {
        "add": """
            Usage: git machete add [-o|--onto=<target-upstream-branch>] [<branch>]

            Adds the given branch (or the current branch, if none specified) to the definition file.
            If the definition file is empty, the branch will be added as the first root of the tree of branch dependencies.
            Otherwise, the desired upstream (parent) branch can be specified with '--onto'.
            This option is not mandatory, however; if skipped, git machete will try to automatically infer the target upstream.
            If the upstream branch can be inferred, the user will be presented with inferred branch and asked to confirm.
            Also, if the given branch does not exist, user will be asked whether it should be created.

            Note: the same effect (except branch creation) can be always achieved by manually editing the definition file.

            Options:
            -o, --onto=<target-upstream-branch>    Specifies the target parent branch to add the new branch onto.
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
            Usage: git machete delete-unmanaged

            Goes one-by-one through all the local git branches that don't exist in the definition file, and ask to delete each of them (with 'git branch -d' or 'git branch -D') if confirmed by user.
            No branch will be deleted unless explicitly confirmed by the user.

            Note: this should be used with care since deleting local branches can sometimes make it impossible for 'git machete' to properly compute fork points.
            See 'git machete help fork-point' for more details.
        """,
        "diff": """
            Usage: git machete d[iff] [-s|--stat] [<branch>]

            Runs 'git diff' of the given branch tip against its fork point or, if none specified, of the current working tree against the fork point of the currently checked out branch.
            See 'git machete help fork-point' for more details on meaning of the "fork point".

            Since the result of the command does not depend on the tree of branch dependencies, the branch in question does not need to occur in the definition file.

            Options:
            -s, --stat    Makes 'git machete diff' pass '--stat' option to 'git diff', so that only summary (diffstat) will be output.
        """,
        "discover": """
            Usage: git machete discover [-l|--list-commits]

            Discovers and prints tree of branch dependencies using a heuristic based on reflogs and asks whether to overwrite the existing definition file with the new discovered tree.
            If confirmed with a 'y[es]' or 'e[dit]' reply, backs up the current definition file as '.git/machete~' (if exists) and saves the new tree under the usual '.git/machete' path.
            If the reply was 'e[dit]', additionally an editor is opened (as in 'git machete edit') after saving the new definition file.

            Options:
            -l, --list-commits            When printing the discovered tree, additionally lists the messages of commits introduced on each branch (as for 'git machete status').
        """,
        "edit": """
            Usage: git machete e[dit]

            Opens the editor (as defined by the 'EDITOR' environment variable, or 'vim' if undefined) and lets you edit the definition file manually.
            The definition file can be always accessed under path returned by 'git machete file' (currently fixed to <repo-root>/.git/machete).
        """,
        "file": """
            Usage: git machete file

            Outputs the path of the machete definition file (currently fixed to <repo-root>/.git/machete).
        """,
        "fork-point": """
            Usage: git machete fork-point [<branch>]

            Outputs SHA of the fork point commit for the given branch (the commit at which the history of the branch actually diverges from history of any other branch).
            If no branch is specified, the currently checked out branch is assumed.

            The returned fork point will be assumed as the default place where the history of the branch starts in the commands 'diff', 'reapply', 'slide-out', and most notably 'update'.
            In other words, 'git machete' treats the fork point as the most recent commit in the log of the given branch that has NOT been introduced on that very branch, but on some other (usually earlier) branch.

            Since the result of the command does not depend on the tree of branch dependencies, the branch in question does not need to occur in the definition file.

            Note: to determine this place in history, 'git machete' uses a heuristics based on reflogs of local branches.
            This yields a correct result in typical cases, but there are some situations (esp. when some local branches have been deleted) where the fork point might not be determined correctly.
            Thus, all rebase-involving operations ('reapply', 'slide-out' and 'update') run 'git rebase' in the interactive mode and allow to specify the fork point explictly by a command-line option.

            Also, 'git machete fork-point' is different (and more powerful) than 'git merge-base --fork-point', since the latter takes into account only the reflog of the one provided upstream branch,
            while the former scans reflogs of all local branches.
            This makes machete's 'fork-point' work correctly even when the tree definition has been modified and one or more of the branches changed their corresponding upstream branch.
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
            The annotation doesn't influence the way 'git machete' operates other than that those annotation are displayed in the output of the 'status' subcommand.
            Also see help for the 'anno' subcommand.

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

            A deprecated alias for 'discover'. Retained for compatibility, to be removed in one of next major releases.

            Options:
            -l, --list-commits            When printing the discovered tree, additionally lists the messages of commits introduced on each branch (as for 'git machete status').
        """,
        "help": """
            Usage: git machete help [<command>]

            Prints a summary of this tool, or a detailed info on a command if defined.
        """,
        "list": """
            Usage: git machete list <category>
            where <category> is one of: managed, slidable, slidable-after <branch>, unmanaged

            Lists all branches that fall into one of the specified categories:
            - 'managed': all branches that appear in the definition file,
            - 'slidable': all managed branches that have exactly one upstream and one downstream (i.e. the ones that can be slid out with 'slide-out' subcommand),
            - 'slidable-after <branch>': the downstream branch of the <branch>, if it exists and is the only downstream of <branch> (i.e. the one that can be slid out immediately following <branch>),
            - 'unmanaged': all local branches that don't appear in the definition file.

            This command is generally not meant for a day-to-day use, it's mostly needed for the sake of branch name completion in shell.
        """,
        "log": """
            Usage: git machete l[og] [<branch>]

            Runs 'git log' for the range of commits from tip of the given branch (or current branch, if none specified) back to its fork point.
            See 'git machete help fork-point' for more details on meaning of the "fork point".

            Since the result of the command does not depend on the tree of branch dependencies, the branch in question does not need to occur in the definition file.
        """,
        "prune-branches": """
            Usage: git machete prune-branches

            A deprecated alias for 'delete-unmanaged'. Retained for compatibility, to be removed in one of next major releases.
        """,
        "reapply": """
            Usage: git machete reapply [-f|--fork-point=<fork-point-commit>]

            Interactively rebase the current branch on the top of its computed fork point.
            This is useful e.g. for squashing the commits on the current branch to make history more condensed before push to the remote.
            The chunk of the history to be rebased starts at the automatically computed fork point of the current branch by default, but can also be set explicitly by '--fork-point'.
            See 'git machete help fork-point' for more details on meaning of the "fork point".

            Since the result of the command does not depend on the tree of branch dependencies, the current reapplied branch does not need to occur in the definition file.

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
            * 'prev':  the direct predeccessor of the current branch in the definition file.
            * 'root':  the root of the tree where the current branch is located. Note: this will typically be something like 'develop' or 'master', since all branches are usually meant to be ultimately merged to one of those.
            * 'up':    the direct parent/upstream branch of the current branch.
        """,
        "slide-out": """
            Usage: git machete slide-out [-d|--down-fork-point=<down-fork-point-commit>] <branch> [<branch> [<branch> ...]]

            Removes the given branch (or multiple branches) from the branch tree definition.
            Then, rebases the downstream (child) branch of the last specified branch on the top of the upstream (parent) branch of the first specified branch.
            The most common use is to slide out a single branch whose upstream was a 'develop'/'master' branch and that has been recently merged.

            Since this tool is designed to perform only one rebase at the end, provided branches must form a chain, i.e the following conditions must be met:
            * (n+1)-th branch must be the ONLY downstream branch of the n-th branch.
            * all provided branches must have exactly one downstream branch (even if only one branch is to be slid out)
            * all provided branches must have an upstream branch (so, in other words, roots of branch dependency tree cannot be slid out - also applies if only one branch is specified).

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
            -d, --down-fork-point=<down-fork-point-commit>    Specifies the alternative fork-point commit after which the rebased part of history of the downstream branch should start.
                                                              See also doc for '--fork-point' option for 'git machete help reapply' and 'git machete help update'.
        """,
        "status": """
            Usage: git machete s[tatus] [-l|--list-commits]

            Outputs a tree-shaped status of the branches listed in the definition file.

            Apart from simply ASCII-formatting the definition file, this also:
            * if any remotes are defined for the repository:
              - prints '(untracked [on <remote>]/ahead of <remote>/behind <remote>/diverged from <remote>)' message for each branch that is not in sync with its remote counterpart;
            * colors the edges between upstream (parent) and downstream (children) branches depending on whether downstream branch commit is a direct descendant of the upstream branch commit:
              - red edge means that the downstream branch commit is NOT a direct descendant of the upstream branch commit (basically, the downstream branch is out of sync with its upstream branch),
              - yellow means that the opposite holds true, i.e. the downstream branch is in sync with its upstream branch, but the fork point of the downstream branch is a different commit than upstream branch tip,
              - green means that downstream branch is in sync with its upstream branch (so just like for yellow edge) and the fork point of downstream branch is EQUAL to the upstream branch tip.
            * displays the custom annotations (see help on 'format') next to each branch, if present;
            * optionally lists commits introduced on each branch if '--list-commits' is supplied.

            Note: in practice, both yellow and red edges suggest that the downstream branch should be updated against its upstream.
            Yellow typically indicates that there are/were commits from some other branches on the path between upstream and downstream and that a closer look at the log of the downstream branch might be necessary.

            Options:
            -l, --list-commits            Additionally lists the messages of commits introduced on each branch.
        """,
        "traverse": """
            Usage: git machete traverse [-l|--list-commits]

            Traverses the branch dependency in pre-order (i.e. simply in the order as they occur in the definition file) and for each branch:
            * if the branch is merged to its parent/upstream:
              - asks the user whether to slide out the branch from the dependency tree (typically branches are longer needed after they're merged);
            * otherwise, if the branch is not in "green" sync with its parent/upstream (see help for 'status'):
              - asks the user whether to rebase the branch onto into its upstream branch - equivalent to 'git machete update' with no options passed;

            * if the branch is not tracked on a remote, ahead its remote counterpart or diverged from the counterpart:
              - asks the user whether to push the branch (possibly with '--force' if the branches diverged);
            * otherwise, if the branch is behind its remote counterpart:
              - asks the user whether to pull the branch;

            * and finally, if user confirmed any of the above operations:
              - prints the updated 'status'.

            Note that even if the traverse flow is stopped (typically due to rebase conflicts), running 'git machete traverse' after the rebase is done will pick up the job where it stopped.
            In other words, there is no need to explicitly ask to "continue" as it is the case with e.g. 'git rebase'.

            Options:
            -l, --list-commits    Additionally lists the messages of commits introduced on each branch when printing the status.
        """,
        "update": """
            Usage: git machete update [-f|--fork-point=<fork-point-commit>]

            Interactively rebase the current branch on the top of its upstream (parent) branch.
            This is useful e.g. for syncing the current branch with changes introduced by an upstream branch like 'develop', or changes commited on the parent branches.
            The chunk of the history to be rebased starts at the automatically computed fork point of the current branch by default, but can also be set explicitly by '--fork-point'.
            See 'git machete help fork-point' for more details on meaning of the "fork point".

            Options:
            -f, --fork-point=<fork-point-commit>    Specifies the alternative fork point commit after which the rebased part of history is meant to start.
        """
    }
    aliases = {
        "diff": "d",
        "edit": "e",
        "go": "g",
        "log": "l",
        "status": "s"
    }
    inv_aliases = {v: k for k, v in aliases.iteritems()}
    groups = [
        ("General topics", ["file", "format", "help"]),
        ("Build, display and modify the tree of branch dependencies", ["add", "anno", "discover", "edit", "status"]),  # 'infer' is skipped from the main docs
        ("List, check out and delete branches", ["delete-unmanaged", "go", "list", "show"]),  # 'prune-branches' is skipped from the main docs
        ("Determine changes specific to the given branch", ["diff", "fork-point", "log"]),
        ("Update git history in accordance with the tree of branch dependencies", ["reapply", "slide-out", "traverse", "update"])
    ]
    if c and c in inv_aliases:
        c = inv_aliases[c]
    if c and c in long_docs:
        print textwrap.dedent(long_docs[c])
    else:
        short_usage()
        if c and c not in long_docs:
            print "\nUnknown command: '%s'" % c
        print "\n%s\n\n    Get familiar with the help for %s, %s, %s and %s, in this order.\n" % (
            underline("TL;DR tip"), bold("format"), bold("edit"), bold("status"), bold("update")
        )
        for hdr, cmds in groups:
            print underline(hdr)
            print
            for cm in cmds:
                alias = (", " + aliases[cm]) if cm in aliases else ""
                print "    %s%-18s%s%s" % (BOLD, cm + alias, ENDC, short_docs[cm])
            print >> sys.stderr
        print textwrap.dedent("""
            %s\n
                --debug           Logs detailed diagnostic info, including outputs of the executed git commands.
                -h, --help        Prints help and exits.
                -v, --verbose     Logs the executed git commands.
                --version         Prints version and exits.
        """[1:] % underline("General options"))


def short_usage():
    print "Usage: git machete [--help] [--verbose] [--version] <command> [command-specific options] [command-specific argument]"


def version():
    print 'git-machete version ' + VERSION


def parse_options(in_args, short_opts="", long_opts=[], gnu=True):
    global cmd, opt_debug, opt_down_fork_point, opt_fork_point, opt_list_commits, opt_onto, opt_stat, opt_verbose

    fun = getopt.gnu_getopt if gnu else getopt.getopt
    opts, rest = fun(in_args, short_opts + "hv", long_opts + ['debug', 'help', 'verbose', 'version'])

    for opt, arg in opts:
        if opt in ("-d", "--down-fork-point"):
            opt_down_fork_point = arg
        elif opt == "--debug":
            opt_debug = True
        elif opt in ("-f", "--fork-point"):
            opt_fork_point = arg
        elif opt in ("-h", "--help"):
            usage(cmd)
            sys.exit()
        elif opt in ("-l", "--list-commits"):
            opt_list_commits = True
        elif opt in ("-o", "--onto"):
            opt_onto = arg
        elif opt in ("-s", "--stat"):
            opt_stat = True
        elif opt in ("-v", "--verbose"):
            opt_verbose = True
        elif opt == "--version":
            version()
            sys.exit()
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


def main():
    try:
        cmd = None
        opt_debug = False  # noqa
        opt_down_fork_point = None  # noqa
        opt_fork_point = None
        opt_list_commits = False  # noqa
        opt_onto = None  # noqa
        opt_stat = False  # noqa
        opt_verbose = False  # noqa

        all_args = parse_options(sys.argv[1:], gnu=False)
        if not all_args:
            usage()
            sys.exit(2)
        cmd = all_args[0]
        args = all_args[1:]

        if cmd not in ("format", "help"):
            try:
                git_dir = get_git_dir()
            except MacheteException:
                raise MacheteException("Not a git repository")

            definition_file = os.path.join(git_dir, "machete")
            if cmd not in ("discover", "infer") and not os.path.exists(definition_file):
                open(definition_file, 'w').close()

        directions = "d[own]|f[irst]|l[ast]|n[ext]|p[rev]|r[oot]|u[p]"

        def parse_direction(cb, down_pick_mode):
            if param in ("d", "down"):
                return down(cb, pick_mode=down_pick_mode)
            elif param in ("f", "first"):
                return first_branch(cb)
            elif param in ("l", "last"):
                return last_branch(cb)
            elif param in ("n", "next"):
                return next_branch(cb)
            elif param in ("p", "prev"):
                return prev_branch(cb)
            elif param in ("r", "root"):
                return root_branch(cb, accept_self=False)
            elif param in ("u", "up"):
                return up(cb, prompt_if_inferred=False)
            else:
                raise MacheteException("Usage: git machete %s %s" % (cmd, directions))

        if cmd == "add":
            param = check_optional_param(parse_options(args, "o:", ["onto="]))
            read_definition_file()
            add(param or current_branch())
        elif cmd == "anno":
            params = parse_options(args)
            read_definition_file()
            if params:
                annotate(params)
            else:
                print_annotation()
        elif cmd == "delete-unmanaged":
            expect_no_param(parse_options(args))
            read_definition_file()
            delete_unmanaged()
        elif cmd in ("d", "diff"):
            param = check_optional_param(parse_options(args, "s", ["stat"]))
            # No need to read definition file.
            diff(param)  # passing None if not specified
        elif cmd == "discover":
            expect_no_param(parse_options(args, "l", ["list-commits"]))
            # No need to read definition file.
            discover_tree()
        elif cmd in ("e", "edit"):
            expect_no_param(parse_options(args))
            # No need to read definition file.
            edit()
        elif cmd == "file":
            expect_no_param(parse_options(args))
            # No need to read definition file.
            print definition_file
        elif cmd == "fork-point":
            param = check_optional_param(parse_options(args))
            # No need to read definition file.
            print fork_point(param or current_branch())
        elif cmd == "format":
            # No need to read definition file.
            usage("format")
        elif cmd in ("g", "go"):
            param = check_required_param(parse_options(args), directions)
            read_definition_file()
            cb = current_branch()
            dest = parse_direction(cb, down_pick_mode=True)
            if dest != cb:
                go(dest)
        elif cmd == "help":
            param = check_optional_param(parse_options(args))
            # No need to read definition file.
            usage(param)
        elif cmd == "infer":
            expect_no_param(parse_options(args, "l", ["list-commits"]))
            # No need to read definition file.
            discover_tree()
        elif cmd == "list":
            allowed_values = "managed|slidable|slidable-after <branch>|unmanaged"
            in_args = parse_options(args)
            if not in_args or len(in_args) > 2:
                raise MacheteException("'%s' expects argument(s): %s" % (cmd, allowed_values))
            elif not in_args[0]:
                raise MacheteException("Argument to '%s' cannot be empty; expected %s" % (cmd, allowed_values))
            elif in_args[0][0] == "-":
                raise MacheteException("option '%s' not recognized" % in_args[0])
            elif in_args[0] in ("managed", "slidable", "unmanaged") and len(in_args) == 2:
                raise MacheteException("'%s %s' doesn't expect an extra argument" % (cmd, in_args[0]))
            elif in_args[0] == "slidable-after" and len(in_args) == 1:
                raise MacheteException("'%s %s' requires an extra <branch> argument" % (cmd, in_args[0]))

            param = in_args[0]
            read_definition_file()
            if param == "managed":
                res = managed_branches
            elif param == "slidable":
                res = slidable()
            elif param == "slidable-after":
                b = in_args[1]
                expect_in_managed_branches(b)
                res = slidable_after(b)
            elif param == "unmanaged":
                res = excluding(local_branches(), managed_branches)
            else:
                raise MacheteException("Usage: git machete list " + allowed_values)
            print "\n".join(res),
        elif cmd in ("l", "log"):
            param = check_optional_param(parse_options(args))
            # No need to read definition file.
            log(param or current_branch())
        elif cmd == "prune-branches":
            expect_no_param(parse_options(args))
            read_definition_file()
            delete_unmanaged()
        elif cmd == "reapply":
            args1 = parse_options(args, "f:", ["fork-point="])
            expect_no_param(args1, ". Use '-f' or '--fork-point' to specify the fork point commit")
            # No need to read definition file.
            cb = current_branch()
            reapply(cb, opt_fork_point or fork_point(cb))
        elif cmd == "show":
            param = check_required_param(parse_options(args), directions)
            read_definition_file()
            print parse_direction(current_branch(), down_pick_mode=False)
        elif cmd == "slide-out":
            params = parse_options(args, "d:", ["down-fork-point="])
            read_definition_file()
            slide_out(params or [current_branch()])
        elif cmd in ("s", "status"):
            expect_no_param(parse_options(args, "lr:", ["list-commits", "remote="]))
            read_definition_file()
            status()
        elif cmd == "traverse":
            expect_no_param(parse_options(args, "lr:", ["list-commits", "remote="]))
            read_definition_file()
            traverse()
        elif cmd == "update":
            args1 = parse_options(args, "f:", ["fork-point="])
            expect_no_param(args1, ". Use '-f' or '--fork-point' to specify the fork point commit")
            read_definition_file()
            cb = current_branch()
            update(cb, opt_fork_point or fork_point(cb))
        else:
            short_usage()
            raise MacheteException("\nUnknown command: '%s'. Use 'git machete help' to list possible commands" % cmd)

    except getopt.GetoptError as e:
        short_usage()
        print >> sys.stderr, str(e)
        sys.exit(2)
    except MacheteException as e:
        print >> sys.stderr, str(e)
        sys.exit(1)
    except StopTraversal:
        pass


if __name__ == "__main__":
    main()
