#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

class MacheteException(Exception):
    def __init__(self, msg, apply_fmt=True):
        self.parameter = fmt(msg) if apply_fmt else msg

    def __str__(self):
        return str(self.parameter)


def excluding(iterable, s):
    return list(filter(lambda x: x not in s, iterable))


def flat_map(func, iterable):
    return sum(map(func, iterable), [])


def map_truthy_only(func, iterable):
    return list(filter(None, map(func, iterable)))


def non_empty_lines(s):
    return list(filter(None, s.split("\n")))


# Converts a lambda accepting N arguments to a lambda accepting one argument, an N-element tuple.
# Name matching Scala's `tupled` on `FunctionX`.
def tupled(f):
    return lambda tple: f(*tple)


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


ascii_only = False


def bold(s):
    return s if ascii_only or not s else BOLD + s + ENDC


def dim(s):
    return s if ascii_only or not s else DIM + s + ENDC


def underline(s, star_if_ascii_only=False):
    if s and not ascii_only:
        return UNDERLINE + s + ENDC
    elif s and star_if_ascii_only:
        return s + " *"
    else:
        return s


def colored(s, color):
    return s if ascii_only or not s else color + s + ENDC


fmt_transformations = [
    lambda x: re.sub('<b>(.*?)</b>', bold(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<u>(.*?)</u>', underline(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<dim>(.*?)</dim>', dim(r"\1"), x, flags=re.DOTALL),
    lambda x: re.sub('<red>(.*?)</red>', colored(r"\1", RED), x, flags=re.DOTALL),
    lambda x: re.sub('<yellow>(.*?)</yellow>', colored(r"\1", YELLOW), x, flags=re.DOTALL),
    lambda x: re.sub('<green>(.*?)</green>', colored(r"\1", GREEN), x, flags=re.DOTALL),
    lambda x: re.sub('`(.*?)`', r"`\1`" if ascii_only else UNDERLINE + r"\1" + ENDC, x),
]


def fmt(*parts):
    result = ''.join(parts)
    for f in fmt_transformations:
        result = f(result)
    return result


def vertical_bar():
    return "|" if ascii_only else u"│"


def right_arrow():
    return "->" if ascii_only else u"➔"


def safe_input(msg):
    if sys.version_info[0] == 2:  # Python 2
        return raw_input(msg)  # noqa: F821
    else:  # Python 3
        return input(msg)


def ask_if(msg, opt_yes_msg, apply_fmt=True):
    if opt_yes and opt_yes_msg:
        print(fmt(opt_yes_msg) if apply_fmt else opt_yes_msg)
        return 'y'
    return safe_input(fmt(msg) if apply_fmt else msg).lower()


def pretty_choices(*choices):
    def format_choice(c):
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
    return " (" + ", ".join(map_truthy_only(format_choice, choices)) + ") "


def pick(choices, name, apply_fmt=True):
    xs = "".join("[%i] %s\n" % (idx + 1, x) for idx, x in enumerate(choices))
    msg = xs + "Specify " + name + " or hit <return> to skip: "
    try:
        ans = safe_input(fmt(msg) if apply_fmt else msg)
        if not ans:
            sys.exit(0)
        idx = int(ans) - 1
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


def warn(msg, apply_fmt=True):
    global displayed_warnings
    if msg not in displayed_warnings:
        sys.stderr.write(colored("Warn: ", RED) + (fmt(msg) if apply_fmt else msg) + "\n")
        displayed_warnings.add(msg)


def directory_exists(path):
    try:
        # Note that os.path.isdir itself (without os.path.abspath) isn't reliable
        # since it returns a false positive (True) for the current directory when if it doesn't exist
        return os.path.isdir(os.path.abspath(path))
    except OSError:
        return False


def current_directory_or_none():
    try:
        return os.getcwd()
    except OSError:
        # This happens when current directory does not exist (typically: has been deleted)
        return None


# Let's keep the flag to avoid checking for current directory's existence
# every time any command is being popened or run.
current_directory_confirmed_to_exist = False
initial_current_directory = current_directory_or_none() or os.getenv('PWD')


def mark_current_directory_as_possibly_non_existent():
    global current_directory_confirmed_to_exist
    current_directory_confirmed_to_exist = False


def chdir_upwards_until_current_directory_exists():
    global current_directory_confirmed_to_exist
    if not current_directory_confirmed_to_exist:
        current_directory = current_directory_or_none()
        if not current_directory:
            while not current_directory:
                # Note: 'os.chdir' only affects the current process and its subprocesses;
                # it doesn't propagate to the parent process (which is typically a shell).
                os.chdir(os.path.pardir)
                current_directory = current_directory_or_none()
            debug("chdir_upwards_until_current_directory_exists()",
                  "current directory did not exist, chdired up into %s" % current_directory)
        current_directory_confirmed_to_exist = True


def run_cmd(cmd, *args, **kwargs):
    chdir_upwards_until_current_directory_exists()

    flat_cmd = cmd_shell_repr(cmd, *args)
    if opt_debug:
        sys.stderr.write(bold(">>> " + flat_cmd) + "\n")
    elif opt_verbose:
        sys.stderr.write(flat_cmd + "\n")

    exit_code = subprocess.call([cmd] + list(args), **kwargs)

    # Let's defensively assume that every command executed via run_cmd
    # (but not via popen_cmd) can make the current directory disappear.
    # In practice, it's mostly 'git checkout' that carries such risk.
    mark_current_directory_as_possibly_non_existent()

    if opt_debug and exit_code != 0:
        sys.stderr.write(dim("<exit code: %i>\n\n" % exit_code))
    return exit_code


def popen_cmd(cmd, *args, **kwargs):
    chdir_upwards_until_current_directory_exists()

    flat_cmd = cmd_shell_repr(cmd, *args)
    if opt_debug:
        sys.stderr.write(bold(">>> " + flat_cmd) + "\n")
    elif opt_verbose:
        sys.stderr.write(flat_cmd + "\n")

    process = subprocess.Popen([cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    stdout_bytes, stderr_bytes = process.communicate()
    stdout, stderr = stdout_bytes.decode('utf-8'), stderr_bytes.decode('utf-8')
    exit_code = process.returncode

    if opt_debug:
        if exit_code != 0:
            sys.stderr.write(colored("<exit code: %i>\n\n" % exit_code, RED))
        if stdout:
            sys.stderr.write("%s\n%s\n" % (dim("<stdout>:"), dim(stdout)))
        if stderr:
            sys.stderr.write("%s\n%s\n" % (dim("<stderr>:"), colored(stderr, RED)))

    return exit_code, stdout, stderr

# Git core


def cmd_shell_repr(cmd, *args):
    def shell_escape(arg):
        return arg.replace("(", "\\(") \
            .replace(")", "\\)") \
            .replace(" ", "\\ ") \
            .replace("\t", "$'\\t'")

    return " ".join([cmd] + list(map(shell_escape, args)))


def run_git(git_cmd, *args, **kwargs):
    exit_code = run_cmd("git", git_cmd, *args)
    if not kwargs.get("allow_non_zero") and exit_code != 0:
        raise MacheteException("`%s` returned %i" % (cmd_shell_repr("git", git_cmd, *args), exit_code))
    return exit_code


def popen_git(git_cmd, *args, **kwargs):
    exit_code, stdout, stderr = popen_cmd("git", git_cmd, *args)
    if not kwargs.get("allow_non_zero") and exit_code != 0:
        exit_code_msg = fmt("`%s` returned %i\n" % (cmd_shell_repr("git", git_cmd, *args), exit_code))
        stdout_msg = "\n%s:\n%s" % (bold("stdout"), dim(stdout)) if stdout else ""
        stderr_msg = "\n%s:\n%s" % (bold("stderr"), dim(stderr)) if stderr else ""
        # Not applying the formatter to avoid transforming whatever characters might be in the output of the command.
        raise MacheteException(exit_code_msg + stdout_msg + stderr_msg, apply_fmt=False)
    return stdout


# Manipulation on definition file/tree of branches

def expect_in_managed_branches(b):
    if b not in managed_branches:
        raise MacheteException("Branch `%s` not found in the tree of branch dependencies. "
                               "Use `git machete add %s` or `git machete edit`" % (b, b))


def expect_at_least_one_managed_branch():
    if not roots:
        raise_no_branches_error()


def raise_no_branches_error():
    raise MacheteException(
        "No branches listed in %s; use `git machete discover` or `git machete edit`, or edit %s manually." % (
            definition_file_path, definition_file_path))


def read_definition_file(verify_branches=True):
    global indent, managed_branches, down_branches, up_branch, roots, annotations

    with open(definition_file_path) as f:
        lines = [line.rstrip() for line in f.readlines() if not line.isspace()]

    managed_branches = []
    down_branches = {}
    up_branch = {}
    indent = None
    roots = []
    annotations = {}
    at_depth = {}
    last_depth = -1
    hint = "Edit the definition file manually with `git machete edit`"

    invalid_branches = []
    for idx, l in enumerate(lines):
        pfx = "".join(itertools.takewhile(str.isspace, l))
        if pfx and not indent:
            indent = pfx

        b_a = l.strip().split(" ", 1)
        b = b_a[0]
        if len(b_a) > 1:
            annotations[b] = b_a[1]
        if b in managed_branches:
            raise MacheteException("%s, line %i: branch `%s` re-appears in the tree definition. %s" %
                                   (definition_file_path, idx + 1, b, hint))
        if verify_branches and b not in local_branches():
            invalid_branches += [b]
        managed_branches += [b]

        if pfx:
            depth = len(pfx) // len(indent)
            if pfx != indent * depth:
                mapping = {" ": "<SPACE>", "\t": "<TAB>"}
                pfx_expanded = "".join(mapping[c] for c in pfx)
                indent_expanded = "".join(mapping[c] for c in indent)
                raise MacheteException("%s, line %i: invalid indent `%s`, expected a multiply of `%s`. %s" %
                                       (definition_file_path, idx + 1, pfx_expanded, indent_expanded, hint))
        else:
            depth = 0

        if depth > last_depth + 1:
            raise MacheteException("%s, line %i: too much indent (level %s, expected at most %s) for the branch `%s`. %s" %
                                   (definition_file_path, idx + 1, depth, last_depth + 1, b, hint))
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

    if not invalid_branches:
        return

    if len(invalid_branches) == 1:
        ans = ask_if("Skipping `" + invalid_branches[0] +
                     "` which is not a local branch (perhaps it has been deleted?).\n" +
                     "Slide it out from the definition file?" +
                     pretty_choices("y", "e[dit]", "N"), opt_yes_msg=None)
    else:
        ans = ask_if("Skipping " + ", ".join("`" + b + "`" for b in invalid_branches) +
                     " which are not local branches (perhaps they have been deleted?).\n" +
                     "Slide them out from the definition file?" +
                     pretty_choices("y", "e[dit]", "N"), opt_yes_msg=None)

    def recursive_slide_out_invalid_branches(b):
        new_down_branches = flat_map(recursive_slide_out_invalid_branches, down_branches.get(b) or [])
        if b in invalid_branches:
            if b in down_branches:
                del down_branches[b]
            if b in annotations:
                del annotations[b]
            if b in up_branch:
                for d in new_down_branches:
                    up_branch[d] = up_branch[b]
                del up_branch[b]
            else:
                for d in new_down_branches:
                    del up_branch[d]
            return new_down_branches
        else:
            down_branches[b] = new_down_branches
            return [b]

    roots = flat_map(recursive_slide_out_invalid_branches, roots)
    managed_branches = excluding(managed_branches, invalid_branches)
    if ans in ('y', 'yes'):
        save_definition_file()
    elif ans in ('e', 'edit'):
        edit()
        read_definition_file(verify_branches)


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
    shutil.copyfile(definition_file_path, definition_file_path + "~")


def save_definition_file():
    with open(definition_file_path, "w") as f:
        f.write("\n".join(render_tree()) + "\n")


def down(b, pick_mode):
    expect_in_managed_branches(b)
    dbs = down_branches.get(b)
    if not dbs:
        raise MacheteException("Branch `%s` has no downstream branch" % b)
    elif len(dbs) == 1:
        return dbs[0]
    elif pick_mode:
        return pick(dbs, "downstream branch")
    else:
        return "\n".join(dbs)


def first_branch(b):
    root = root_branch(b, if_unmanaged=PICK_FIRST_ROOT)
    root_dbs = down_branches.get(root)
    return root_dbs[0] if root_dbs else root


def last_branch(b):
    d = root_branch(b, if_unmanaged=PICK_LAST_ROOT)
    while down_branches.get(d):
        d = down_branches[d][-1]
    return d


def next_branch(b):
    expect_in_managed_branches(b)
    idx = managed_branches.index(b) + 1
    if idx == len(managed_branches):
        raise MacheteException("Branch `%s` has no successor" % b)
    return managed_branches[idx]


def prev_branch(b):
    expect_in_managed_branches(b)
    idx = managed_branches.index(b) - 1
    if idx == -1:
        raise MacheteException("Branch `%s` has no predecessor" % b)
    return managed_branches[idx]


PICK_FIRST_ROOT = 0
PICK_LAST_ROOT = -1


def root_branch(b, if_unmanaged):
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
            raise MacheteException("Branch `%s` has no upstream branch" % b)
    else:
        u = infer_upstream(b)
        if u:
            if prompt_if_inferred_msg:
                if ask_if(prompt_if_inferred_msg % (b, u), prompt_if_inferred_yes_opt_msg % (b, u)) in ('y', 'yes'):
                    return u
                else:
                    sys.exit(1)
            else:
                warn("branch `%s` not found in the tree of branch dependencies; the upstream has been inferred to `%s`" % (b, u))
                return u
        else:
            raise MacheteException("Branch `%s` not found in the tree of branch dependencies and its upstream could not be inferred" % b)


def add(b):
    global roots

    if b in managed_branches:
        raise MacheteException("Branch `%s` already exists in the tree of branch dependencies" % b)

    onto = opt_onto
    if onto:
        expect_in_managed_branches(onto)

    if b not in local_branches():
        rb = get_sole_remote_branch(b)
        if rb:
            common_line = "A local branch `%s` does not exist, but a remote branch `%s` exists.\n" % (b, rb)
            msg = common_line + "Check out `%s` locally?" % b + pretty_choices('y', 'N')
            opt_yes_msg = common_line + "Checking out `%s` locally..." % b
            if ask_if(msg, opt_yes_msg) in ('y', 'yes'):
                create_branch(b, "refs/remotes/" + rb)
            else:
                return
            # Not dealing with `onto` here. If it hasn't been explicitly specified via `--onto`, we'll try to infer it now.
        else:
            out_of = ("`" + onto + "`") if onto else "the current HEAD"
            msg = "A local branch `%s` does not exist. Create (out of %s)?" % (b, out_of) + pretty_choices('y', 'N')
            opt_yes_msg = "A local branch `%s` does not exist. Creating out of %s" % (b, out_of)
            if ask_if(msg, opt_yes_msg) in ('y', 'yes'):
                if roots and not onto:
                    cb = current_branch_or_none()
                    if cb and cb in managed_branches:
                        onto = cb
                create_branch(b, "refs/heads/" + onto)
            else:
                return

    if opt_as_root or not roots:
        roots += [b]
        print(fmt("Added branch `%s` as a new root" % b))
    else:
        if not onto:
            u = infer_upstream(b, condition=lambda x: x in managed_branches, reject_reason_message="this candidate is not a managed branch")
            if not u:
                raise MacheteException("Could not automatically infer upstream (parent) branch for `%s`.\n"
                                       "You can either:\n"
                                       "1) specify the desired upstream branch with `--onto` or\n"
                                       "2) pass `--as-root` to attach `%s` as a new root or\n"
                                       "3) edit the definition file manually with `git machete edit`" % (b, b))
            else:
                msg = "Add `%s` onto the inferred upstream (parent) branch `%s`?" % (b, u) + pretty_choices('y', 'N')
                opt_yes_msg = "Adding `%s` onto the inferred upstream (parent) branch `%s`" % (b, u)
                if ask_if(msg, opt_yes_msg) in ('y', 'yes'):
                    onto = u
                else:
                    return

        up_branch[b] = onto
        if onto in down_branches:
            down_branches[onto].append(b)
        else:
            down_branches[onto] = [b]
        print(fmt("Added branch `%s` onto `%s`" % (b, onto)))

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
    # '$GIT_MACHETE_EDITOR', 'editor' (to please Debian-based systems) and 'nano' have been added.
    git_machete_editor_var = "GIT_MACHETE_EDITOR"
    proposed_editor_funs = [
        ("$" + git_machete_editor_var, lambda: os.environ.get(git_machete_editor_var)),
        ("$GIT_EDITOR", lambda: os.environ.get("GIT_EDITOR")),
        ("git config core.editor", lambda: get_config_or_none("core.editor")),
        ("$VISUAL", lambda: os.environ.get("VISUAL")),
        ("$EDITOR", lambda: os.environ.get("EDITOR")),
        ("editor", lambda: "editor"),
        ("nano", lambda: "nano"),
        ("vi", lambda: "vi"),
    ]

    for name, fun in proposed_editor_funs:
        editor = fun()
        if not editor:
            debug("get_default_editor()", "'%s' is undefined" % name)
        else:
            editor_repr = "'%s'%s" % (name, (" (" + editor + ")") if editor != name else "")
            if not find_executable(editor):
                debug("get_default_editor()", "%s is not available" % editor_repr)
                if name == "$" + git_machete_editor_var:
                    # In this specific case, when GIT_MACHETE_EDITOR is defined but doesn't point to a valid executable,
                    # it's more reasonable/less confusing to raise an error and exit without opening anything.
                    raise MacheteException("<b>%s</b> is not available" % editor_repr)
            else:
                debug("get_default_editor()", "%s is available" % editor_repr)
                if name != "$" + git_machete_editor_var and get_config_or_none('advice.macheteEditorSelection') != 'false':
                    sample_alternative = 'nano' if editor.startswith('vi') else 'vi'
                    sys.stderr.write(
                        fmt("Opening <b>%s</b>.\n" % editor_repr,
                            "To override this choice, use <b>%s</b> env var, e.g. `export %s=%s`.\n\n" % (git_machete_editor_var, git_machete_editor_var, sample_alternative),
                            "See `git machete help edit` and `git machete edit --debug` for more details.\n\n"
                            "Use `git config --global advice.macheteEditorSelection false` to suppress this message.\n"))
                return editor

    # This case is extremely unlikely on a modern Unix-like system.
    raise MacheteException("Cannot determine editor. Set `%s` environment variable"
                           " or edit %s directly." % (git_machete_editor_var, definition_file_path))


def edit():
    return run_cmd(get_default_editor(), definition_file_path)


git_version = None


def get_git_version():
    global git_version
    if not git_version:
        # We need to cut out the x.y.z part and not just take the result of 'git version' as is,
        # because the version string in certain distributions of git (esp. on OS X) has an extra suffix,
        # which is irrelevant for our purpose (checking whether certain git CLI features are available/bugs are fixed).
        raw = re.search(r"\d+.\d+.\d+", popen_git("version")).group(0)
        git_version = tuple(map(int, raw.split(".")))
    return git_version


root_dir = None


def get_root_dir():
    global root_dir
    if not root_dir:
        try:
            root_dir = popen_git("rev-parse", "--show-toplevel").strip()
        except MacheteException:
            raise MacheteException("Not a git repository")
    return root_dir


git_dir = None


def get_git_dir():
    global git_dir
    if not git_dir:
        try:
            git_dir = popen_git("rev-parse", "--git-dir").strip()
        except MacheteException:
            raise MacheteException("Not a git repository")
    return git_dir


def get_git_subpath(*fragments):
    return os.path.join(get_git_dir(), *fragments)


def parse_git_timespec_to_unix_timestamp(date):
    try:
        return int(popen_git("rev-parse", "--since=" + date).replace("--max-age=", "").strip())
    except (MacheteException, ValueError):
        raise MacheteException("Cannot parse timespec: `%s`" % date)


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
        raise MacheteException("Cannot perform `git reset --keep %s`. This is most likely caused by local uncommitted changes." % to_revision)


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


short_commit_sha_by_revision_cached = {}


def short_commit_sha_by_revision(revision):
    if revision not in short_commit_sha_by_revision_cached:
        short_commit_sha_by_revision_cached[revision] = find_short_commit_sha_by_revision(revision)
    return short_commit_sha_by_revision_cached[revision]


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


def is_full_sha(revision):
    return re.match("^[0-9a-f]{40}$", revision)


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
    return os.path.isfile(get_git_subpath("rebase-apply", "applying"))


def is_cherry_pick_in_progress():
    return os.path.isfile(get_git_subpath("CHERRY_PICK_HEAD"))


def is_merge_in_progress():
    return os.path.isfile(get_git_subpath("MERGE_HEAD"))


def is_revert_in_progress():
    return os.path.isfile(get_git_subpath("REVERT_HEAD"))


# Note: while rebase is ongoing, the repository is always in a detached HEAD state,
# so we need to extract the name of the currently rebased branch from the rebase-specific internals
# rather than rely on 'git symbolic-ref HEAD' (i.e. the contents of .git/HEAD).
def currently_rebased_branch_or_none():
    # https://stackoverflow.com/questions/3921409

    head_name_file = None

    # .git/rebase-merge directory exists during cherry-pick-powered rebases,
    # e.g. all interactive ones and the ones where '--strategy=' or '--keep-empty' option has been passed
    rebase_merge_head_name_file = get_git_subpath("rebase-merge", "head-name")
    if os.path.isfile(rebase_merge_head_name_file):
        head_name_file = rebase_merge_head_name_file

    # .git/rebase-apply directory exists during the remaining, i.e. am-powered rebases, but also during am sessions.
    rebase_apply_head_name_file = get_git_subpath("rebase-apply", "head-name")
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
        raise MacheteException("Rebase of `%s` in progress. Conclude the rebase first with `git rebase --continue` or `git rebase --abort`." % rb)
    if is_am_in_progress():
        raise MacheteException("`git am` session in progress. Conclude `git am` first with `git am --continue` or `git am --abort`.")
    if is_cherry_pick_in_progress():
        raise MacheteException("Cherry pick in progress. Conclude the cherry pick first with `git cherry-pick --continue` or `git cherry-pick --abort`.")
    if is_merge_in_progress():
        raise MacheteException("Merge in progress. Conclude the merge first with `git merge --continue` or `git merge --abort`.")
    if is_revert_in_progress():
        raise MacheteException("Revert in progress. Conclude the revert first with `git revert --continue` or `git revert --abort`.")


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
        # Note that we don't pass '--all' flag to 'merge-base', so we'll get only one merge-base
        # even if there is more than one (in the rare case of criss-cross histories).
        # This is still okay from the perspective of is-ancestor checks that are our sole use of merge-base:
        # * if any of sha1, sha2 is an ancestor of another,
        #   then there is exactly one merge-base - the ancestor,
        # * if neither of sha1, sha2 is an ancestor of another,
        #   then none of the (possibly more than one) merge-bases is equal to either of sha1/sha2 anyway.
        merge_base_cached[sha1, sha2] = popen_git("merge-base", sha1, sha2).rstrip()
    return merge_base_cached[sha1, sha2]


# Note: the 'git rev-parse --verify' validation is not performed in case for either of earlier/later
# if the corresponding prefix is empty AND the revision is a 40 hex digit hash.
def is_ancestor(earlier_revision, later_revision, earlier_prefix="refs/heads/", later_prefix="refs/heads/"):
    if earlier_prefix == "" and is_full_sha(earlier_revision):
        earlier_sha = earlier_revision
    else:
        earlier_sha = commit_sha_by_revision(earlier_revision, earlier_prefix)
    if later_prefix == "" and is_full_sha(later_revision):
        later_sha = later_revision
    else:
        later_sha = commit_sha_by_revision(later_revision, later_prefix)
    if earlier_sha == later_sha:
        return True
    return merge_base(earlier_sha, later_sha) == earlier_sha


def create_branch(b, out_of_revision):
    run_git("checkout", "-b", b, *([out_of_revision] if out_of_revision else []))
    flush_caches()  # the repository state has changed b/c of a successful branch creation, let's defensively flush all the caches


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
        b, sha, committer_unix_timestamp_and_time_zone = values
        b_stripped = re.sub("^refs/remotes/", "", b)
        remote_branches_cached += [b_stripped]
        commit_sha_by_revision_cached[b] = sha
        committer_unix_timestamp_by_revision_cached[b] = int(committer_unix_timestamp_and_time_zone.split(' ')[0])

    raw_local = non_empty_lines(popen_git("for-each-ref", "--format=%(refname)\t%(objectname)\t%(committerdate:raw)\t%(upstream)", "refs/heads"))

    for line in raw_local:
        values = line.split("\t")
        if len(values) != 4:  # invalid, shouldn't happen
            continue
        b, sha, committer_unix_timestamp_and_time_zone, fetch_counterpart = values
        b_stripped = re.sub("^refs/heads/", "", b)
        fetch_counterpart_stripped = re.sub("^refs/remotes/", "", fetch_counterpart)
        local_branches_cached += [b_stripped]
        commit_sha_by_revision_cached[b] = sha
        committer_unix_timestamp_by_revision_cached[b] = int(committer_unix_timestamp_and_time_zone.split(' ')[0])
        if fetch_counterpart_stripped in remote_branches_cached:
            counterparts_for_fetching_cached[b_stripped] = fetch_counterpart_stripped


def get_sole_remote_branch(b):
    def matches(rb):
        # Note that this matcher is defensively too inclusive:
        # if there is both origin/foo and origin/feature/foo,
        # then both are matched for 'foo';
        # this is to reduce risk wrt. which '/'-separated fragments belong to remote and which to branch name.
        # FIXME: this is still likely to deliver incorrect results in rare corner cases with compound remote names.
        return rb.endswith('/' + b)
    matching_remote_branches = list(filter(matches, remote_branches()))
    return matching_remote_branches[0] if len(matching_remote_branches) == 1 else None


def merged_local_branches():
    return list(map(
        lambda b: re.sub("^refs/heads/", "", b),
        non_empty_lines(popen_git("for-each-ref", "--format=%(refname)", "--merged", "HEAD", "refs/heads"))
    ))


def go(branch):
    run_git("checkout", "--quiet", branch, "--")


def get_hook_path(hook_name):
    hook_dir = get_config_or_none("core.hooksPath") or get_git_subpath("hooks")
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


def merge_fast_forward_only(branch):  # refs/heads/ prefix is assumed for 'branch'
    run_git("merge", "--ff-only", "refs/heads/" + branch)


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
            # only <git-dir>/rebase-merge/author-script (i.e. interactive rebases, for the most part) is affected.
            author_script = get_git_subpath("rebase-merge", "author-script")
            if os.path.isfile(author_script):
                faulty_line_regex = re.compile("[A-Z0-9_]+='[^']*")

                def fix_if_needed(line):
                    return (line.rstrip() + "'\n") if faulty_line_regex.fullmatch(line) else line

                def get_all_lines_fixed():
                    with open(author_script) as f_read:
                        return map(fix_if_needed, f_read.readlines())

                fixed_lines = get_all_lines_fixed()  # must happen before the 'with' clause where we open for writing
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
                         prompt_if_inferred_msg="Branch `%s` not found in the tree of branch dependencies. Merge with the inferred upstream `%s`?" + pretty_choices('y', 'N'),
                         prompt_if_inferred_yes_opt_msg="Branch `%s` not found in the tree of branch dependencies. Merging with the inferred upstream `%s`...")
        merge(with_branch, cb)
    else:
        onto_branch = up(cb,
                         prompt_if_inferred_msg="Branch `%s` not found in the tree of branch dependencies. Rebase onto the inferred upstream `%s`?" + pretty_choices('y', 'N'),
                         prompt_if_inferred_yes_opt_msg="Branch `%s` not found in the tree of branch dependencies. Rebasing onto the inferred upstream `%s`...")
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


def filtered_reflog(b, prefix):
    def is_excluded_reflog_subject(sha_, gs_):
        is_excluded = (
            gs_.startswith("branch: Created from") or
            gs_ == "branch: Reset to " + b or
            gs_ == "branch: Reset to HEAD" or
            gs_.startswith("reset: moving to ") or
            gs_.startswith("fetch . ") or
            gs_ == "rebase finished: %s/%s onto %s" % (prefix, b, sha_)  # the rare case of a no-op rebase
        )
        if is_excluded:
            debug("filtered_reflog(%s, %s) -> is_excluded_reflog_subject(%s, <<<%s>>>)" % (b, prefix, sha_, gs_), "skipping reflog entry")
        return is_excluded

    b_reflog = reflog(prefix + b)
    if not b_reflog:
        return []

    earliest_sha, earliest_gs = b_reflog[-1]  # Note that the reflog is returned from latest to earliest entries.
    shas_to_exclude = set()
    if earliest_gs.startswith("branch: Created from"):
        debug("filtered_reflog(%s, %s)" % (b, prefix),
              "skipping any reflog entry with the hash equal to the hash of the earliest (branch creation) entry: %s" % earliest_sha)
        shas_to_exclude.add(earliest_sha)

    result = [sha for (sha, gs) in reflog(prefix + b) if sha not in shas_to_exclude and not is_excluded_reflog_subject(sha, gs)]
    debug("filtered_reflog(%s, %s)" % (b, prefix),
          "computed filtered reflog (= reflog without branch creation "
          "and branch reset events irrelevant for fork point/upstream inference): %s\n" % (", ".join(result) or "<empty>"))
    return result


def get_latest_checkout_timestamps():
    # Entries are in the format '<branch_name>@{<unix_timestamp> <time-zone>}'
    result = {}
    # %gd - reflog selector (HEAD@{<unix-timestamp> <time-zone>} for `--date=raw`;
    #   `--date=unix` is not available on some older versions of git)
    # %gs - reflog subject
    output = popen_git("reflog", "show", "--format=%gd:%gs", "--date=raw")
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


branch_defs_by_sha_in_reflog = None


def match_log_to_filtered_reflogs(b):
    global branch_defs_by_sha_in_reflog

    if b not in local_branches():
        raise MacheteException("`%s` is not a local branch" % b)

    if branch_defs_by_sha_in_reflog is None:
        def generate_entries():
            for lb in local_branches():
                lb_shas = set()
                for sha_ in filtered_reflog(lb, prefix="refs/heads/"):
                    lb_shas.add(sha_)
                    yield sha_, (lb, lb)
                rb = combined_counterpart_for_fetching_of_branch(lb)
                if rb:
                    for sha_ in filtered_reflog(rb, prefix="refs/remotes/"):
                        if sha_ not in lb_shas:
                            yield sha_, (lb, rb)

        branch_defs_by_sha_in_reflog = {}
        for sha, branch_def in generate_entries():
            if sha in branch_defs_by_sha_in_reflog:
                # The practice shows that it's rather unlikely for a given commit to appear on filtered reflogs of two unrelated branches
                # ("unrelated" as in, not a local branch and its remote counterpart) but we need to handle this case anyway.
                branch_defs_by_sha_in_reflog[sha] += [branch_def]
            else:
                branch_defs_by_sha_in_reflog[sha] = [branch_def]

        def log_result():
            for sha_, branch_defs in branch_defs_by_sha_in_reflog.items():
                yield dim("%s => %s" %
                          (sha_, ", ".join(map(tupled(lambda lb, lb_or_rb: lb if lb == lb_or_rb else "%s (remote counterpart of %s)" % (lb_or_rb, lb)), branch_defs))))

        debug("match_log_to_filtered_reflogs(%s)" % b, "branches containing the given SHA in their filtered reflog: \n%s\n" % "\n".join(log_result()))

    get_second = tupled(lambda lb, lb_or_rb: lb_or_rb)
    for sha in spoonfeed_log_shas(b):
        if sha in branch_defs_by_sha_in_reflog:
            # The entries must be sorted by lb_or_rb to make sure the upstream inference is deterministic
            # (and does not depend on the order in which `generate_entries` iterated through the local branches).
            containing_branch_defs = sorted(filter(tupled(lambda lb, lb_or_rb: lb != b), branch_defs_by_sha_in_reflog[sha]), key=get_second)
            if containing_branch_defs:
                debug("match_log_to_filtered_reflogs(%s)" % b, "commit %s found in filtered reflog of %s" % (sha, " and ".join(map(get_second, branch_defs_by_sha_in_reflog[sha]))))
                yield sha, containing_branch_defs
            else:
                debug("match_log_to_filtered_reflogs(%s)" % b, "commit %s found only in filtered reflog of %s; ignoring" % (sha, " and ".join(map(get_second, branch_defs_by_sha_in_reflog[sha]))))
        else:
            debug("match_log_to_filtered_reflogs(%s)" % b, "commit %s not found in any filtered reflog" % sha)


# Complex routines/commands

def is_merged_to(b, target):
    if commit_sha_by_revision(target) == commit_sha_by_revision(b):
        # If branch is equal to the target, we need to distinguish between the
        # case of branch being "recently" created from the target and the case of
        # branch being fast-forward-merged to the target.
        # The applied heuristics is to check if the filtered reflog of the branch
        # (reflog stripped of trivial events like branch creation, reset etc.)
        # is non-empty.
        return bool(filtered_reflog(b, prefix="refs/heads/"))
    else:
        # If a branch is NOT equal to the target (typically its parent),
        # it's just enough to check if the target is reachable from the branch.
        return is_ancestor(b, target)


def is_merged_to_upstream(b):
    if b not in up_branch:
        return False
    return is_merged_to(b, up_branch[b])


def infer_upstream(b, condition=lambda u: True, reject_reason_message=""):
    for sha, containing_branch_defs in match_log_to_filtered_reflogs(b):
        debug("infer_upstream(%s)" % b, "commit %s found in filtered reflog of %s" % (sha, " and ".join(map(tupled(lambda x, y: y), containing_branch_defs))))

        for candidate, original_matched_branch in containing_branch_defs:
            if candidate != original_matched_branch:
                debug("infer_upstream(%s)" % b, "upstream candidate is %s, which is the local counterpart of %s" % (candidate, original_matched_branch))

            if condition(candidate):
                debug("infer_upstream(%s)" % b, "upstream candidate %s accepted" % candidate)
                return candidate
            else:
                debug("infer_upstream(%s)" % b, "upstream candidate %s rejected (%s)" % (candidate, reject_reason_message))
    return None


DISCOVER_DEFAULT_FRESH_BRANCH_COUNT = 10


def discover_tree():
    global managed_branches, roots, down_branches, up_branch, indent, annotations, opt_checked_out_since, opt_roots
    all_local_branches = local_branches()
    if not all_local_branches:
        raise MacheteException("No local branches found")
    for r in opt_roots:
        if r not in local_branches():
            raise MacheteException("`%s` is not a local branch" % r)
    if opt_roots:
        roots = list(opt_roots)
    elif "master" in local_branches():
        roots = ["master"]
    elif "main" in local_branches():
        # See https://github.com/github/renaming
        roots = ["main"]
    elif "develop" in local_branches():
        roots = ["develop"]
    else:
        roots = []
    down_branches = {}
    up_branch = {}
    indent = "\t"
    annotations = {}

    root_of = dict((b, b) for b in all_local_branches)

    def get_root_of(b):
        if b != root_of[b]:
            root_of[b] = get_root_of(root_of[b])
        return root_of[b]

    non_root_fixed_branches = excluding(all_local_branches, roots)
    last_checkout_timestamps = get_latest_checkout_timestamps()
    non_root_fixed_branches_by_last_checkout_timestamps = sorted((last_checkout_timestamps.get(b) or 0, b) for b in non_root_fixed_branches)
    if opt_checked_out_since:
        threshold = parse_git_timespec_to_unix_timestamp(opt_checked_out_since)
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
            warn("to keep the size of the discovered tree reasonable (ca. %d branches), "
                 "only branches checked out at or after ca. <b>%s</b> are included.\n"
                 "Use `git machete discover --checked-out-since=<date>` (where <date> can be e.g. `'2 weeks ago'` or `2020-06-01`) "
                 "to change this threshold so that less or more branches are included.\n" % (c, threshold_date))
    managed_branches = excluding(all_local_branches, stale_non_root_fixed_branches)
    if opt_checked_out_since and not managed_branches:
        warn("no branches satisfying the criteria. Try moving the value of `--checked-out-since` further to the past.")
        return

    for b in excluding(non_root_fixed_branches, stale_non_root_fixed_branches):
        u = infer_upstream(b,
                           condition=lambda candidate: get_root_of(candidate) != b and candidate not in stale_non_root_fixed_branches,
                           reject_reason_message="choosing this candidate would form a cycle in the resulting graph or the candidate is a stale branch")
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

    # Let's remove merged branches for which no downstream branch have been found.
    merged_branches_to_skip = []
    for b in managed_branches:
        if b in up_branch and not down_branches.get(b):
            u = up_branch[b]
            if is_merged_to(b, u):
                debug("discover_tree()", "inferred upstream of %s is %s, but %s is merged to %s; skipping %s from discovered tree\n" % (b, u, b, u, b))
                merged_branches_to_skip += [b]
    if merged_branches_to_skip:
        warn("skipping %s since %s merged to another branch and would not have any downstream branches.\n"
             % (", ".join("`" + b + "`" for b in merged_branches_to_skip), "it's" if len(merged_branches_to_skip) == 1 else "they're"))
        managed_branches = excluding(managed_branches, merged_branches_to_skip)
        for b in merged_branches_to_skip:
            u = up_branch[b]
            down_branches[u] = excluding(down_branches[u], [b])
            del up_branch[b]
        # We're NOT applying the removal process recursively,
        # so it's theoretically possible that some merged branches became childless
        # after removing the outer layer of childless merged branches.
        # This is rare enough, however, that we can pretty much ignore this corner case.

    print(bold("Discovered tree of branch dependencies:\n"))
    status(warn_on_yellow_edges=False)
    print("")
    do_backup = os.path.isfile(definition_file_path)
    backup_msg = ("\nThe existing definition file will be backed up as %s~" % definition_file_path) if do_backup else ""
    msg = "Save the above tree to %s?%s" % (definition_file_path, backup_msg) + pretty_choices('y', 'e[dit]', 'N')
    opt_yes_msg = "Saving the above tree to %s... %s" % (definition_file_path, backup_msg)
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
                # but the fork point of b is overridden to a commit that is NOT a descendant of u.
                # In this case it's more reasonable to assume that u (and not overridden_fp_sha) is the fork point.
                debug("fork_point_and_containing_branch_defs(%s)" % b,
                      "%s is descendant of its upstream %s, but overridden fork point commit %s is NOT a descendant of %s; falling back to %s as fork point" % (b, u, overridden_fp_sha, u, u))
                return commit_sha_by_revision(u), []
            else:
                debug("fork_point_and_containing_branch_defs(%s)" % b,
                      "fork point of %s is overridden to %s; skipping inference" % (b, overridden_fp_sha))
                return overridden_fp_sha, []

    try:
        fp_sha, containing_branch_defs = next(match_log_to_filtered_reflogs(b))
    except StopIteration:
        if u and is_ancestor(u, b):
            debug("fork_point_and_containing_branch_defs(%s)" % b,
                  "cannot find fork point, but %s is descendant of its upstream %s; falling back to %s as fork point" % (b, u, u))
            return commit_sha_by_revision(u), []
        else:
            raise MacheteException("Cannot find fork point for branch `%s`" % b)
    else:
        debug("fork_point_and_containing_branch_defs(%s)" % b,
              "commit %s is the most recent point in history of %s to occur on "
              "filtered reflog of any other branch or its remote counterpart "
              "(specifically: %s)" % (fp_sha, b, " and ".join(map(tupled(lambda lb, lb_or_rb: lb_or_rb), containing_branch_defs))))

        if u and is_ancestor(u, b) and not is_ancestor(u, fp_sha, later_prefix=""):
            # That happens very rarely in practice (typically current head of any branch, including u, should occur on the reflog of this
            # branch, thus is_ancestor(u, b) should imply is_ancestor(u, FP(b)), but it's still possible in case reflog of
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
            warn("%s config value `%s` does not point to a valid commit" % (to_key, to))
        if not while_descendant_of_sha:
            warn("%s config value `%s` does not point to a valid commit" % (while_descendant_of_key, while_descendant_of))
        return None
    # This check needs to be performed every time the config is retrieved.
    # We can't rely on the values being validated in set_fork_point_override(), since the config could have been modified outside of git-machete.
    if not is_ancestor(to_sha, while_descendant_of_sha, earlier_prefix="", later_prefix=""):
        warn("commit %s pointed by %s config is not an ancestor of commit %s pointed by %s config" %
             (short_commit_sha_by_revision(to), to_key, short_commit_sha_by_revision(while_descendant_of), while_descendant_of_key))
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
        warn(fmt("since branch <b>%s</b> is no longer a descendant of commit %s, " % (b, short_commit_sha_by_revision(while_descendant_of)),
                 "the fork point override to commit %s no longer applies.\n" % short_commit_sha_by_revision(to),
                 "Consider running:\n",
                 "  `git machete fork-point --unset-override %s`\n" % b))
        return None
    debug("get_overridden_fork_point(%s)" % b,
          "since branch %s is descendant of while_descendant_of=%s, fork point of %s is overridden to %s" %
          (b, while_descendant_of, b, to))
    return to


def get_revision_repr(revision):
    short_sha = short_commit_sha_by_revision(revision)
    if is_full_sha(revision) or revision == short_sha:
        return "commit %s" % revision
    else:
        return "%s (commit %s)" % (revision, short_commit_sha_by_revision(revision))


def set_fork_point_override(b, to_revision):
    if b not in local_branches():
        raise MacheteException("`%s` is not a local branch" % b)
    to_sha = commit_sha_by_revision(to_revision, prefix="")
    if not to_sha:
        raise MacheteException("Cannot find revision %s" % to_revision)
    if not is_ancestor(to_sha, b, earlier_prefix=""):
        raise MacheteException("Cannot override fork point: %s is not an ancestor of %s" % (get_revision_repr(to_revision), b))

    to_key = config_key_for_override_fork_point_to(b)
    set_config(to_key, to_sha)

    while_descendant_of_key = config_key_for_override_fork_point_while_descendant_of(b)
    b_sha = commit_sha_by_revision(b, prefix="refs/heads/")
    set_config(while_descendant_of_key, b_sha)

    sys.stdout.write(
        fmt("Fork point for <b>%s</b> is overridden to <b>%s</b>.\n" % (b, get_revision_repr(to_revision)),
            "This applies as long as %s points to (or is descendant of) its current head (commit %s).\n\n" % (b, short_commit_sha_by_revision(b_sha)),
            "This information is stored under git config keys:\n  * `%s`\n  * `%s`\n\n" % (to_key, while_descendant_of_key),
            "To unset this override, use:\n  `git machete fork-point --unset-override %s`\n" % b))


def unset_fork_point_override(b):
    unset_config(config_key_for_override_fork_point_to(b))
    unset_config(config_key_for_override_fork_point_while_descendant_of(b))


def delete_unmanaged():
    branches_to_delete = excluding(local_branches(), managed_branches)
    cb = current_branch_or_none()
    if cb and cb in branches_to_delete:
        branches_to_delete = excluding(branches_to_delete, [cb])
        print(fmt("Skipping current branch `%s`" % cb))
    if branches_to_delete:
        branches_merged_to_head = merged_local_branches()

        branches_to_delete_merged_to_head = [b for b in branches_to_delete if b in branches_merged_to_head]
        for b in branches_to_delete_merged_to_head:
            rb = strict_counterpart_for_fetching_of_branch(b)
            is_merged_to_remote = is_ancestor(b, rb, later_prefix="refs/remotes/") if rb else True
            msg_core = "%s (merged to HEAD%s)" % (bold(b), "" if is_merged_to_remote else (", but not merged to " + rb))
            msg = "Delete branch %s?" % msg_core + pretty_choices('y', 'N', 'q')
            opt_yes_msg = "Deleting branch %s" % msg_core
            ans = ask_if(msg, opt_yes_msg)
            if ans in ('y', 'yes'):
                run_git("branch", "-d" if is_merged_to_remote else "-D", b)
            elif ans in ('q', 'quit'):
                return

        branches_to_delete_unmerged_to_head = [b for b in branches_to_delete if b not in branches_merged_to_head]
        for b in branches_to_delete_unmerged_to_head:
            msg_core = "%s (unmerged to HEAD)" % bold(b)
            msg = "Delete branch %s?" % msg_core + pretty_choices('y', 'N', 'q')
            opt_yes_msg = "Deleting branch %s" % msg_core
            ans = ask_if(msg, opt_yes_msg)
            if ans in ('y', 'yes'):
                run_git("branch", "-D", b)
            elif ans in ('q', 'quit'):
                return
    else:
        print("No branches to delete")


def run_post_slide_out_hook(new_upstream, slid_out_branch, new_downstreams):
    hook_path = get_hook_path("machete-post-slide-out")
    if check_hook_executable(hook_path):
        debug("run_post_slide_out_hook(%s, %s, %s)" % (new_upstream, slid_out_branch, new_downstreams),
              "running machete-post-slide-out hook (%s)" % hook_path)
        exit_code = run_cmd(hook_path, new_upstream, slid_out_branch, *new_downstreams, cwd=get_root_dir())
        if exit_code != 0:
            sys.stderr.write("The machete-post-slide-out hook exited with %d, aborting.\n" % exit_code)
            sys.exit(exit_code)


def slide_out(branches_to_slide_out):
    for b in branches_to_slide_out:
        expect_in_managed_branches(b)
        new_upstream = up_branch.get(b)
        if not new_upstream:
            raise MacheteException("No upstream branch defined for `%s`, cannot slide out" % b)
        dbs = down_branches.get(b)
        if not dbs or len(dbs) == 0:
            raise MacheteException("No downstream branch defined for `%s`, cannot slide out" % b)
        elif len(dbs) > 1:
            flat_dbs = ", ".join("`%s`" % x for x in dbs)
            raise MacheteException("Multiple downstream branches defined for `%s`: %s; cannot slide out" % (b, flat_dbs))

    for bu, bd in zip(branches_to_slide_out[:-1], branches_to_slide_out[1:]):
        if up_branch[bd] != bu:
            raise MacheteException("`%s` is not upstream of `%s`, cannot slide out" % (bu, bd))

    new_upstream = up_branch[branches_to_slide_out[0]]
    new_downstream = down_branches[branches_to_slide_out[-1]][0]
    for b in branches_to_slide_out:
        up_branch[b] = None
        down_branches[b] = None

    go(new_downstream)
    up_branch[new_downstream] = new_upstream
    down_branches[new_upstream] = [(new_downstream if x == branches_to_slide_out[0] else x) for x in down_branches[new_upstream]]
    save_definition_file()
    run_post_slide_out_hook(new_upstream, branches_to_slide_out[-1], [new_downstream])
    if opt_merge:
        print("Merging %s into %s..." % (bold(new_upstream), bold(new_downstream)))
        merge(new_upstream, new_downstream)
    else:
        print("Rebasing %s onto %s..." % (bold(new_downstream), bold(new_upstream)))
        rebase("refs/heads/" + new_upstream, opt_down_fork_point or fork_point(new_downstream, use_overrides=True), new_downstream)


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


def advance(b):
    if not down_branches.get(b):
        raise MacheteException("`%s` does not have any downstream (child) branches to advance towards" % b)

    def connected_with_green_edge(bd):
        return \
            not is_merged_to_upstream(bd) and \
            is_ancestor(b, bd) and \
            (get_overridden_fork_point(bd) or commit_sha_by_revision(b) == fork_point(bd, use_overrides=False))

    candidate_downstreams = list(filter(connected_with_green_edge, down_branches[b]))
    if not candidate_downstreams:
        raise MacheteException("No downstream (child) branch of `%s` is connected to `%s` with a green edge" % (b, b))
    if len(candidate_downstreams) > 1:
        if opt_yes:
            raise MacheteException("More than one downstream (child) branch of `%s` is connected to `%s` with a green edge "
                                   "and `-y/--yes` option is specified" % (b, b))
        else:
            d = pick(candidate_downstreams, "downstream branch towards which `%s` is to be fast-forwarded" % b)
            merge_fast_forward_only(d)
    else:
        d = candidate_downstreams[0]
        ans = ask_if(
            "Fast-forward %s to match %s?" % (bold(b), bold(d)) + pretty_choices('y', 'N'),
            "Fast-forwarding %s to match %s..." % (bold(b), bold(d))
        )
        if ans in ('y', 'yes'):
            merge_fast_forward_only(d)
        else:
            return

    ans = ask_if(
        "\nBranch %s is now merged into %s. Slide %s out of the tree of branch dependencies?" % (bold(d), bold(b), bold(d)) + pretty_choices('y', 'N'),
        "\nBranch %s is now merged into %s. Sliding %s out of the tree of branch dependencies..." % (bold(d), bold(b), bold(d))
    )
    if ans in ('y', 'yes'):
        dds = down_branches.get(d) or []
        for dd in dds:
            up_branch[dd] = b
        down_branches[b] = flat_map(
            lambda bd: dds if bd == d else [bd],
            down_branches[b])
        save_definition_file()
        run_post_slide_out_hook(b, d, dds)


class StopTraversal(Exception):
    def __init__(self):
        pass


def flush_caches():
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
    other_remote_choice = "o[ther-remote]" if can_pick_other_remote else ""
    rb = new_remote + "/" + b
    if not commit_sha_by_revision(rb, prefix="refs/remotes/"):
        msg = "Push untracked branch %s to %s?" % (bold(b), bold(new_remote)) + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice)
        opt_yes_msg = "Pushing untracked branch %s to %s..." % (bold(b), bold(new_remote))
        ans = ask_if(msg, opt_yes_msg)
        if ans in ('y', 'yes', 'yq'):
            push(new_remote, b)
            if ans == 'yq':
                raise StopTraversal
            flush_caches()
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
            "Set the remote of %s to %s without pushing or pulling?" % (bold(b), bold(new_remote)) + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
            "Setting the remote of %s to %s..." % (bold(b), bold(new_remote))
        ),
        BEHIND_REMOTE: (
            "Pull %s (fast-forward only) from %s?" % (bold(b), bold(new_remote)) + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
            "Pulling %s (fast-forward only) from %s..." % (bold(b), bold(new_remote))
        ),
        AHEAD_OF_REMOTE: (
            "Push branch %s to %s?" % (bold(b), bold(new_remote)) + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
            "Pushing branch %s to %s..." % (bold(b), bold(new_remote))
        ),
        DIVERGED_FROM_AND_OLDER_THAN_REMOTE: (
            "Reset branch %s to the commit pointed by %s?" % (bold(b), bold(rb)) + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
            "Resetting branch %s to the commit pointed by %s..." % (bold(b), bold(rb))
        ),
        DIVERGED_FROM_AND_NEWER_THAN_REMOTE: (
            "Push branch %s with force-with-lease to %s?" % (bold(b), bold(new_remote)) + pretty_choices('y', 'N', 'q', 'yq', other_remote_choice),
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
        if ans == 'yq':
            raise StopTraversal
        flush_caches()
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
            flush_caches()
            print("")

    initial_branch = nearest_remaining_branch = current_branch()

    if opt_start_from == "root":
        dest = root_branch(current_branch(), if_unmanaged=PICK_FIRST_ROOT)
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

        needs_slide_out = is_merged_to_upstream(b)
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
                "Branch %s is merged into %s. Slide %s out of the tree of branch dependencies?" % (bold(b), bold(u), bold(b)) + pretty_choices('y', 'N', 'q', 'yq'),
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
                    lambda ud: (down_branches.get(b) or []) if ud == b else [ud],
                    down_branches[u])
                if b in annotations:
                    del annotations[b]
                save_definition_file()
                run_post_slide_out_hook(u, b, down_branches.get(b) or [])
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
                ans = ask_if(
                    "Merge %s into %s?" % (bold(u), bold(b)) + pretty_choices('y', 'N', 'q', 'yq'),
                    "Merging %s into %s..." % (bold(u), bold(b))
                )
            else:
                ans = ask_if(
                    "Rebase %s onto %s?" % (bold(b), bold(u)) + pretty_choices('y', 'N', 'q', 'yq'),
                    "Rebasing %s onto %s..." % (bold(b), bold(u))
                )
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
                        sys.stdout.write(fmt("\nRebase of `%s` in progress; stopping the traversal\n" % rb))
                        return
                if ans == 'yq':
                    return

                flush_caches()
                s, remote = get_strict_remote_sync_status(b)
                needs_remote_sync = s in statuses_to_sync
            elif ans in ('q', 'quit'):
                return

        if needs_remote_sync:
            if s == BEHIND_REMOTE:
                rb = strict_counterpart_for_fetching_of_branch(b)
                ans = ask_if(
                    "Branch %s is behind its remote counterpart %s.\n"
                    "Pull %s (fast-forward only) from %s?" % (bold(b), bold(rb), bold(b), bold(remote)) + pretty_choices('y', 'N', 'q', 'yq'),
                    "Branch %s is behind its remote counterpart %s.\n"
                    "Pulling %s (fast-forward only) from %s..." % (bold(b), bold(rb), bold(b), bold(remote))
                )
                if ans in ('y', 'yes', 'yq'):
                    pull_ff_only(remote, rb)
                    if ans == 'yq':
                        return
                    flush_caches()
                    print("")
                elif ans in ('q', 'quit'):
                    return

            elif s == AHEAD_OF_REMOTE:
                print_new_line(False)
                ans = ask_if(
                    "Push %s to %s?" % (bold(b), bold(remote)) + pretty_choices('y', 'N', 'q', 'yq'),
                    "Pushing %s to %s..." % (bold(b), bold(remote))
                )
                if ans in ('y', 'yes', 'yq'):
                    push(remote, b)
                    if ans == 'yq':
                        return
                    flush_caches()
                elif ans in ('q', 'quit'):
                    return

            elif s == DIVERGED_FROM_AND_OLDER_THAN_REMOTE:
                print_new_line(False)
                rb = strict_counterpart_for_fetching_of_branch(b)
                ans = ask_if(
                    "Branch %s diverged from (and has older commits than) its remote counterpart %s.\n"
                    "Reset branch %s to the commit pointed by %s?" % (bold(b), bold(rb), bold(b), bold(rb)) + pretty_choices('y', 'N', 'q', 'yq'),
                    "Branch %s diverged from (and has older commits than) its remote counterpart %s.\n"
                    "Resetting branch %s to the commit pointed by %s..." % (bold(b), bold(rb), bold(b), bold(rb))
                )
                if ans in ('y', 'yes', 'yq'):
                    reset_keep(rb)
                    if ans == 'yq':
                        return
                    flush_caches()
                elif ans in ('q', 'quit'):
                    return

            elif s == DIVERGED_FROM_AND_NEWER_THAN_REMOTE:
                print_new_line(False)
                rb = strict_counterpart_for_fetching_of_branch(b)
                ans = ask_if(
                    "Branch %s diverged from (and has newer commits than) its remote counterpart %s.\n"
                    "Push %s with force-with-lease to %s?" % (bold(b), bold(rb), bold(b), bold(remote)) + pretty_choices('y', 'N', 'q', 'yq'),
                    "Branch %s diverged from (and has newer commits than) its remote counterpart %s.\n"
                    "Pushing %s with force-with-lease to %s..." % (bold(b), bold(rb), bold(b), bold(remote))
                )
                if ans in ('y', 'yes', 'yq'):
                    push(remote, b, force_with_lease=True)
                    if ans == 'yq':
                        return
                    flush_caches()
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
                    print(fmt("Branch `%s` is untracked and there's no `%s` repository." % (bold(b), bold("origin"))))
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
        if is_merged_to_upstream(b):
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
                        fp_branches_formatted = " and ".join(sorted(map(tupled(lambda lb, lb_or_rb: lb_or_rb), fp_branches_cached[b])))
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
            current = "%s%s" % (bold(colored(prefix, RED)), bold(underline(b, star_if_ascii_only=True)))
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
            first_line = "yellow edge indicates that fork point for `%s` is probably incorrectly inferred" % yellow_edge_branches[0]
        else:
            affected_branches = ", ".join(map(lambda x: "`%s`" % x, yellow_edge_branches))
            first_line = "yellow edges indicate that fork points for %s are probably incorrectly inferred" % affected_branches

        if not opt_list_commits:
            second_line = "Run `git machete status --list-commits` or `git machete status --list-commits-with-hashes` to see more details"
        elif len(yellow_edge_branches) == 1:
            second_line = "Consider using `git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent %s`" % yellow_edge_branches[0]
        else:
            second_line = "Consider using `git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent <branch>` for each affected branch"

        sys.stderr.write("\n")
        warn("%s.\n%s." % (first_line, second_line))


# Main


def usage(c=None):
    short_docs = {
        "add": "Add a branch to the tree of branch dependencies",
        "advance": "Fast-forward the current branch to match one of its downstreams and subsequently slide out this downstream",
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
        "is-managed": "Check if the current branch is managed by git-machete (mostly for scripts)",
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
            <b>Usage: git machete anno [-b|--branch=<branch>] [<annotation text>]</b>

            If invoked without any argument, prints out the custom annotation for the given branch (or current branch, if none specified with `-b/--branch`).

            If invoked with a single empty string argument, like:
            <dim>$ git machete anno ''</dim>
            then clears the annotation for the current branch (or a branch specified with `-b/--branch`).

            In any other case, sets the annotation for the given/current branch to the given argument.
            If multiple arguments are passed to the command, they are concatenated with a single space.

            Note: the same effect can be always achieved by manually editing the definition file.

            <b>Options:</b>
              <b>-b, --branch=<branch></b>      Branch to set the annotation for.
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
                                               If not present, the date is selected automatically so that around """ + str(DISCOVER_DEFAULT_FRESH_BRANCH_COUNT) + """ branches are included.

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
            Also, `reapply`, `slide-out` and `update` allow to specify the fork point explictly by a command-line option.

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
                  Note that this is guaranteed to be exactly one branch in case of `slide-out` (but no guarantees exist in case of `advance` or `traverse`).

                Note: the hook, if present, is executed:
                * zero or once during a `advance` execution (depending on whether the slide-out has been confirmed or not),
                * exactly once during a `slide-out` execution (even if multiple branches are slid out),
                * zero or more times during `traverse` (every time a slide-out operation is confirmed).

                If the hook returns a non-zero exit code, then the execution of the command is aborted,
                i.e. `slide-out` won't attempt rebase of the new downstream branch and `traverse` won't continue the traversal.
                In case of `advance` there is no difference (other than exit code of the entire `advance` command being non-zero),
                since slide-out is the last operation that happens within `advance`.
                Note that non-zero exit code of the hook doesn't cancel the effects of slide-out itself, only the subsequent operations.
                The hook is executed only once the slide-out is complete and can in fact rely on .git/machete file being updated to the new branch layout.

            * <b>machete-pre-rebase <new-base> <fork-point-hash> <branch-being-rebased></b>
                The hook that is executed before rebase is run during `reapply`, `slide-out`, `traverse` and `update`.

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
        "infer": """
            <b>Usage: git machete infer [-l|--list-commits]</b>

            A deprecated alias for `discover`, without the support of newer options.
            Retained for compatibility, to be removed in the next major release.

            Options:
              <b>-l, --list-commits</b>            When printing the discovered tree, additionally lists the messages of commits introduced on each branch (as for `git machete status`).
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
            where <category> is one of: `addable`, `managed`, `slidable`, `slidable-after <branch>`, `unmanaged`, `with-overridden-fork-point`

            Lists all branches that fall into one of the specified categories:
            * `addable`: all branches (local or remote) than can be added to the definition file,
            * `managed`: all branches that appear in the definition file,
            * `slidable`: all managed branches that have exactly one upstream and one downstream (i.e. the ones that can be slid out with `slide-out` command),
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
        "prune-branches": """
            <b>Usage: git machete prune-branches</b>

            A deprecated alias for `delete-unmanaged`, without the support of `--yes` option.
            Retained for compatibility, to be removed in the next major release.
        """,
        "reapply": """
            <b>Usage: git machete reapply [-f|--fork-point=<fork-point-commit>]</b>

            Interactively rebase the current branch on the top of its computed fork point.
            This is useful e.g. for squashing the commits on the current branch to make history more condensed before push to the remote.
            The chunk of the history to be rebased starts at the automatically computed fork point of the current branch by default, but can also be set explicitly by `--fork-point`.
            See `git machete help fork-point` for more details on meaning of the "fork point".

            Note: the current reapplied branch does not need to occur in the definition file.

            <b>Options:</b>
              <b>-f, --fork-point=<fork-point-commit></b>    Specifies the alternative fork point commit after which the rebased part of history is meant to start.
        """,
        "show": """
            <b>Usage: git machete show <direction></b>
            where <direction> is one of: `c[urrent]`, `d[own]`, `f[irst]`, `l[ast]`, `n[ext]`, `p[rev]`, `r[oot]`, `u[p]`

            Outputs name of the branch (or possibly multiple branches, in case of `down`) that is:

            * `current`: the current branch; exits with a non-zero status if none (detached HEAD)
            * `down`:    the direct children/downstream branch of the current branch.
            * `first`:   the first downstream of the root branch of the current branch (like `root` followed by `next`), or the root branch itself if the root has no downstream branches.
            * `last`:    the last branch in the definition file that has the same root as the current branch; can be the root branch itself if the root has no downstream branches.
            * `next`:    the direct successor of the current branch in the definition file.
            * `prev`:    the direct predecessor of the current branch in the definition file.
            * `root`:    the root of the tree where the current branch is located. Note: this will typically be something like `develop` or `master`, since all branches are usually meant to be ultimately merged to one of those.
            * `up`:      the direct parent/upstream branch of the current branch.
        """,
        "slide-out": """
            <b>Usage: git machete slide-out [-d|--down-fork-point=<down-fork-point-commit>] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase] <branch> [<branch> [<branch> ...]]</b>

            Removes the given branch (or multiple branches) from the branch tree definition.
            Then synchronizes the downstream (child) branch of the last specified branch on the top of the upstream (parent) branch of the first specified branch.
            Sync is performed either by rebase (default) or by merge (if `--merge` option passed).

            The most common use is to slide out a single branch whose upstream was a `develop`/`master` branch and that has been recently merged.

            Since this tool is designed to perform only one single rebase/merge at the end, provided branches must form a chain, i.e. all of the following conditions must be met:
            * for i=1..N-1, (i+1)-th branch must be a downstream (child) branch of the i-th branch,
            * all provided branches (including N-th branch) must have exactly one downstream branch,
            * all provided branches must have an upstream branch (so, in other words, roots of branch dependency tree cannot be slid out).

            For example, let's assume the following dependency tree:
            <dim>
              develop
                  adjust-reads-prec
                      block-cancel-order
                          change-table
                              drop-location-type
            </dim>
            And now let's assume that `adjust-reads-prec` and later `block-cancel-order` were merged to develop.
            After running `git machete slide-out adjust-reads-prec block-cancel-order` the tree will be reduced to:
            <dim>
              develop
                  change-table
                      drop-location-type
            </dim>
            and `change-table` will be rebased onto develop (fork point for this rebase is configurable, see `-d` option below).

            Note: This command doesn't delete any branches from git, just removes them from the tree of branch dependencies.

            <b>Options:</b>
              <b>-d, --down-fork-point=<down-fork-point-commit></b>    If updating by rebase, specifies the alternative fork point commit after which the rebased part of history of the downstream branch is meant to start.
                                                                Not allowed if updating by merge. See also doc for `--fork-point` option in `git machete help reapply` and `git machete help update`.

              <b>-M, --merge</b>                                       Update the downstream branch by merge rather than by rebase.

              <b>-n</b>                                                If updating by rebase, equivalent to `--no-interactive-rebase`. If updating by merge, equivalent to `--no-edit-merge`.

              <b>--no-edit-merge</b>                                   If updating by merge, skip opening the editor for merge commit message while doing `git merge` (i.e. pass `--no-edit` flag to underlying `git merge`).
                                                                Not allowed if updating by rebase.

              <b>--no-interactive-rebase</b>                           If updating by rebase, run `git rebase` in non-interactive mode (without `-i/--interactive` flag).
                                                                Not allowed if updating by merge.
        """,
        "status": """
            <b>Usage: git machete s[tatus] [--color=WHEN] [-l|--list-commits] [-L|--list-commits-with-hashes]</b>

            Displays a tree-shaped status of the branches listed in the definition file.

            Apart from simply ASCII-formatting the definition file, this also:

            * colors the edges between upstream (parent) and downstream (children) branches:

              - <b><red>red edge</red></b> means that the downstream branch tip is <b>not a direct descendant</b> of the upstream branch tip,

              - <b><yellow>yellow edge</yellow></b> means that the downstream branch tip is a <b>direct descendant</b> of the upstream branch tip,
                but the fork point (see help on `fork-point`) of the downstream branch is <b>not equal</b> to the upstream branch tip,

              - <b><green>green edge</green></b> means that the downstream branch tip is a <b>direct descendant</b> of the upstream branch tip
                and the fork point of the downstream branch is <b>equal</b> to the upstream branch tip.

              - <b><dim>grey/dimmed edge</dim></b> means that the downstream branch has been <b>merged</b> to the upstream branch,

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
        """,
        "traverse": """
            <b>Usage: git machete traverse [-F|--fetch] [-l|--list-commits] [-M|--merge] [-n|--no-edit-merge|--no-interactive-rebase] [--return-to=WHERE] [--start-from=WHERE] [-w|--whole] [-W] [-y|--yes]</b>

            Traverses the branch dependency in pre-order (i.e. simply in the order as they occur in the definition file) and for each branch:
            * if the branch is merged to its parent/upstream:
              - asks the user whether to slide out the branch from the dependency tree (typically branches are longer needed after they're merged);
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

              <b>--no-edit-merge</b>              If updating by merge, skip opening the editor for merge commit message while doing `git merge` (i.e. pass `--no-edit` flag to underlying `git merge`).
                                           Not allowed if updating by rebase.

              <b>--no-interactive-rebase</b>      If updating by rebase, run `git rebase` in non-interactive mode (without `-i/--interactive` flag).
                                           Not allowed if updating by merge.

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
    aliases = {
        "diff": "d",
        "edit": "e",
        "go": "g",
        "log": "l",
        "status": "s"
    }
    inv_aliases = {v: k for k, v in aliases.items()}

    groups = [
        # 'infer' and 'prune-branches' are deprecated and therefore skipped
        # 'is-managed' is mostly for scripting use and therefore skipped
        ("General topics", ["file", "format", "help", "hooks", "version"]),
        ("Build, display and modify the tree of branch dependencies", ["add", "anno", "discover", "edit", "status"]),
        ("List, check out and delete branches", ["delete-unmanaged", "go", "list", "show"]),
        ("Determine changes specific to the given branch", ["diff", "fork-point", "log"]),
        ("Update git history in accordance with the tree of branch dependencies", ["reapply", "slide-out", "traverse", "update"])
    ]
    if c and c in inv_aliases:
        c = inv_aliases[c]
    if c and c in long_docs:
        print(fmt(textwrap.dedent(long_docs[c])))
    else:
        print()
        short_usage()
        if c and c not in long_docs:
            print("\nUnknown command: '%s'" % c)
        print(fmt("\n<u>TL;DR tip</u>\n\n"
              "    Get familiar with the help for <b>format</b>, <b>edit</b>, <b>status</b> and <b>update</b>, in this order.\n"))
        for hdr, cmds in groups:
            print(underline(hdr))
            print("")
            for cm in cmds:
                alias = (", " + aliases[cm]) if cm in aliases else ""
                print("    %s%-18s%s%s" % (BOLD, cm + alias, ENDC, short_docs[cm]))  # bold(...) can't be used here due to the %-18s format specifier
            sys.stdout.write("\n")
        print(fmt(textwrap.dedent("""
            <u>General options</u>\n
                <b>--debug</b>           Log detailed diagnostic info, including outputs of the executed git commands.
                <b>-h, --help</b>        Print help and exit.
                <b>-v, --verbose</b>     Log the executed git commands.
                <b>--version</b>         Print version and exit.
        """[1:])))


def short_usage():
    print(fmt("<b>Usage: git machete [--debug] [-h] [-v|--verbose] [--version] <command> [command-specific options] [command-specific argument]</b>"))


def version():
    print('git-machete version ' + __version__)


def main():
    launch(sys.argv[1:])


def launch(orig_args):
    def parse_options(in_args, short_opts="", long_opts=[], gnu=True):
        global ascii_only
        global opt_as_root, opt_branch, opt_checked_out_since, opt_color, opt_debug, opt_down_fork_point, opt_fetch, opt_fork_point, opt_inferred, opt_list_commits, opt_list_commits_with_hashes, opt_merge, opt_n, opt_no_edit_merge
        global opt_no_interactive_rebase, opt_onto, opt_override_to, opt_override_to_inferred, opt_override_to_parent, opt_return_to, opt_roots, opt_start_from, opt_stat, opt_unset_override, opt_verbose, opt_yes

        fun = getopt.gnu_getopt if gnu else getopt.getopt
        opts, rest = fun(in_args, short_opts + "hv", long_opts + ['debug', 'help', 'verbose', 'version'])

        for opt, arg in opts:
            if opt in ("-b", "--branch"):
                opt_branch = arg
            elif opt in ("-C", "--checked-out-since"):
                opt_checked_out_since = arg
            elif opt == "--color":
                opt_color = arg
            elif opt in ("-d", "--down-fork-point"):
                opt_down_fork_point = arg
            elif opt == "--debug":
                opt_debug = True
            elif opt in ("-F", "--fetch"):
                opt_fetch = True
            elif opt in ("-f", "--fork-point"):
                opt_fork_point = arg
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
            elif opt in ("-R", "--as-root"):
                opt_as_root = True
            elif opt in ("-r", "--roots"):
                opt_roots = arg.split(",")
            elif opt == "--return-to":
                opt_return_to = arg
            elif opt in ("-s", "--stat"):
                opt_stat = True
            elif opt == "--start-from":
                opt_start_from = arg
            elif opt == "--unset-override":
                opt_unset_override = True
            elif opt in ("-v", "--verbose"):
                opt_verbose = True
            elif opt == "--version":
                version()
                sys.exit()
            elif opt == "-W":
                opt_fetch = True
                opt_start_from = "first-root"
                opt_n = True
                opt_return_to = "nearest-remaining"
            elif opt in ("-w", "--whole"):
                opt_start_from = "first-root"
                opt_n = True
                opt_return_to = "nearest-remaining"
            elif opt in ("-y", "--yes"):
                opt_yes = opt_no_interactive_rebase = True

        if opt_color not in ("always", "auto", "never"):
            raise MacheteException("Invalid argument for `--color`. Valid arguments: `always|auto|never`.")
        else:
            ascii_only = opt_color == "never" or (opt_color == "auto" and not sys.stdout.isatty())

        if opt_as_root and opt_onto:
            raise MacheteException("Option `-R/--as-root` cannot be specified together with `-o/--onto`.")

        if opt_no_edit_merge and not opt_merge:
            raise MacheteException("Option `--no-edit-merge` only makes sense when using merge and must be specified together with `-M/--merge`.")
        if opt_no_interactive_rebase and opt_merge:
            raise MacheteException("Option `--no-interactive-rebase` only makes sense when using rebase and cannot be specified together with `-M/--merge`.")
        if opt_down_fork_point and opt_merge:
            raise MacheteException("Option `-d/--down-fork-point` only makes sense when using rebase and cannot be specified together with `-M/--merge`.")
        if opt_fork_point and opt_merge:
            raise MacheteException("Option `-f/--fork-point` only makes sense when using rebase and cannot be specified together with `-M/--merge`.")

        if opt_n and opt_merge:
            opt_no_edit_merge = True
        if opt_n and not opt_merge:
            opt_no_interactive_rebase = True

        return rest

    def expect_no_param(in_args, extra_explanation=''):
        if len(in_args) > 0:
            raise MacheteException("No argument expected for `%s`%s" % (cmd, extra_explanation))

    def check_optional_param(in_args):
        if not in_args:
            return None
        elif len(in_args) > 1:
            raise MacheteException("`%s` accepts at most one argument" % cmd)
        elif not in_args[0]:
            raise MacheteException("Argument to `%s` cannot be empty" % cmd)
        elif in_args[0][0] == "-":
            raise MacheteException("Option `%s` not recognized" % in_args[0])
        else:
            return in_args[0]

    def check_required_param(in_args, allowed_values):
        if not in_args or len(in_args) > 1:
            raise MacheteException("`%s` expects exactly one argument: one of %s" % (cmd, allowed_values))
        elif not in_args[0]:
            raise MacheteException("Argument to `%s` cannot be empty; expected one of %s" % (cmd, allowed_values))
        elif in_args[0][0] == "-":
            raise MacheteException("Option `%s` not recognized" % in_args[0])
        else:
            return in_args[0]

    global definition_file_path, up_branch
    global opt_as_root, opt_branch, opt_checked_out_since, opt_color, opt_debug, opt_down_fork_point, opt_fetch, opt_fork_point, opt_inferred, opt_list_commits, opt_list_commits_with_hashes, opt_merge, opt_n, opt_no_edit_merge
    global opt_no_interactive_rebase, opt_onto, opt_override_to, opt_override_to_inferred, opt_override_to_parent, opt_return_to, opt_roots, opt_start_from, opt_stat, opt_unset_override, opt_verbose, opt_yes
    try:
        cmd = None
        opt_as_root = False
        opt_branch = None
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
            definition_file_path = get_git_subpath("machete")
            if cmd not in ("discover", "infer"):
                if not os.path.exists(definition_file_path):
                    # We're opening in "append" and not "write" mode to avoid a race condition:
                    # if other process writes to the file between we check the result of `os.path.exists` and call `open`,
                    # then open(..., "w") would result in us clearing up the file contents, while open(..., "a") has no effect.
                    with open(definition_file_path, "a"):
                        pass
                elif os.path.isdir(definition_file_path):
                    # Extremely unlikely case, basically checking if anybody tampered with the repository.
                    raise MacheteException("%s is a directory rather than a regular file, aborting" % definition_file_path)

        def allowed_directions(allow_current):
            current = "c[urrent]|" if allow_current else ""
            return current + "d[own]|f[irst]|l[ast]|n[ext]|p[rev]|r[oot]|u[p]"

        def parse_direction(b, allow_current, down_pick_mode):
            if param in ("c", "current") and allow_current:
                return current_branch()  # throws in case of detached HEAD, as in the spec
            elif param in ("d", "down"):
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
                return root_branch(b, if_unmanaged=PICK_FIRST_ROOT)
            elif param in ("u", "up"):
                return up(b, prompt_if_inferred_msg=None, prompt_if_inferred_yes_opt_msg=None)
            else:
                raise MacheteException("Usage: git machete %s %s" % (cmd, allowed_directions(allow_current)))

        if cmd == "add":
            param = check_optional_param(parse_options(args, "o:Ry", ["onto=", "as-root", "yes"]))
            read_definition_file()
            add(param or current_branch())
        elif cmd == "advance":
            args1 = parse_options(args, "y", ["yes"])
            expect_no_param(args1)
            read_definition_file()
            expect_no_operation_in_progress()
            cb = current_branch()
            expect_in_managed_branches(cb)
            advance(cb)
        elif cmd == "anno":
            params = parse_options(args, "b:", ["branch="])
            read_definition_file(verify_branches=False)
            b = opt_branch or current_branch()
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
            print(os.path.abspath(definition_file_path))
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
            param = check_required_param(parse_options(args), allowed_directions(allow_current=False))
            read_definition_file()
            expect_no_operation_in_progress()
            cb = current_branch()
            dest = parse_direction(cb, allow_current=False, down_pick_mode=True)
            if dest != cb:
                go(dest)
        elif cmd == "help":
            param = check_optional_param(parse_options(args))
            # No need to read definition file.
            usage(param)
        elif cmd == "infer":  # TODO: deprecated in favor of `discover`
            expect_no_param(parse_options(args, "l", ["list-commits"]))
            # No need to read definition file.
            discover_tree()
        elif cmd == "is-managed":
            param = check_optional_param(parse_options(args))
            read_definition_file()
            b = param or current_branch_or_none()
            if b is None or b not in managed_branches:
                sys.exit(1)
        elif cmd == "list":
            list_allowed_values = "addable|managed|slidable|slidable-after <branch>|unmanaged|with-overridden-fork-point"
            list_args = parse_options(args)
            if not list_args:
                raise MacheteException("`git machete list` expects argument(s): %s" % list_allowed_values)
            elif not list_args[0]:
                raise MacheteException("Argument to `git machete list` cannot be empty; expected %s" % list_allowed_values)
            elif list_args[0][0] == "-":
                raise MacheteException("Option `%s` not recognized" % list_args[0])
            elif list_args[0] not in ("addable", "managed", "slidable", "slidable-after", "unmanaged", "with-overridden-fork-point"):
                raise MacheteException("Usage: git machete list %s" % list_allowed_values)
            elif len(list_args) > 2:
                raise MacheteException("Too many arguments to `git machete list %s` " % list_args[0])
            elif list_args[0] in ("addable", "managed", "slidable", "unmanaged", "with-overridden-fork-point") and len(list_args) > 1:
                raise MacheteException("`git machete list %s` does not expect extra arguments" % list_args[0])
            elif list_args[0] == "slidable-after" and len(list_args) != 2:
                raise MacheteException("`git machete list %s` requires an extra <branch> argument" % list_args[0])

            param = list_args[0]
            read_definition_file()
            res = []
            if param == "addable":
                def strip_first_fragment(rb):
                    return re.sub("^[^/]+/", "", rb)

                remote_counterparts_of_local_branches = map_truthy_only(combined_counterpart_for_fetching_of_branch, local_branches())
                qualifying_remote_branches = excluding(remote_branches(), remote_counterparts_of_local_branches)
                res = excluding(local_branches(), managed_branches) + list(map(strip_first_fragment, qualifying_remote_branches))
            elif param == "managed":
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
        elif cmd == "prune-branches":  # TODO: deprecated in favor of `delete-unmanaged`
            expect_no_param(parse_options(args, "y", ["yes"]))
            read_definition_file()
            delete_unmanaged()
        elif cmd == "reapply":
            args1 = parse_options(args, "f:", ["fork-point="])
            expect_no_param(args1, ". Use `-f` or `--fork-point` to specify the fork point commit")
            read_definition_file()
            expect_no_operation_in_progress()
            cb = current_branch()
            rebase_onto_ancestor_commit(cb, opt_fork_point or fork_point(cb, use_overrides=True))
        elif cmd == "show":
            param = check_required_param(parse_options(args), allowed_directions(allow_current=True))
            read_definition_file(verify_branches=False)
            print(parse_direction(current_branch(), allow_current=True, down_pick_mode=False))
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
                raise MacheteException("Invalid argument for `--start-from`. Valid arguments: `here|root|first-root`.")
            if opt_return_to not in ("here", "nearest-remaining", "stay"):
                raise MacheteException("Invalid argument for `--return-to`. Valid arguments: here|nearest-remaining|stay.")
            read_definition_file()
            expect_no_operation_in_progress()
            traverse()
        elif cmd == "update":
            args1 = parse_options(args, "f:Mn", ["fork-point=", "merge", "no-edit-merge", "no-interactive-rebase"])
            expect_no_param(args1, ". Use `-f` or `--fork-point` to specify the fork point commit")
            read_definition_file()
            expect_no_operation_in_progress()
            update()
        elif cmd == "version":
            version()
            sys.exit()
        else:
            short_usage()
            raise MacheteException("\nUnknown command: `%s`. Use `git machete help` to list possible commands" % cmd)

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
            warn("current directory %s no longer exists, "
                 "the nearest existing parent directory is %s" % (initial_current_directory, os.path.abspath(nearest_existing_parent_directory)))


if __name__ == "__main__":
    main()
