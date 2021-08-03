from typing import List, Optional, Callable, Tuple, Dict, Match, Set

import os
import re
import sys

from git_machete.contexts import CommandLineContext
from git_machete.exceptions import MacheteException
from git_machete import utils

REFLOG_ENTRY = Tuple[str, str]


class GitContext:

    counterparts_for_fetching_cached: Optional[Dict[str, Optional[str]]] = None  # TODO (#110): default dict with None
    git_version: Tuple[int, ...] = None
    root_dir: str = None
    git_dir: str = None
    config_cached: Optional[Dict[str, str]] = None
    remotes_cached: Optional[List[str]] = None
    fetch_done_for: Set[str] = set()
    short_commit_sha_by_revision_cached: Dict[str, str] = {}
    tree_sha_by_commit_sha_cached: Optional[Dict[str, Optional[str]]] = None  # TODO (#110): default dict with None
    commit_sha_by_revision_cached: Optional[Dict[str, Optional[str]]] = None  # TODO (#110): default dict with None
    committer_unix_timestamp_by_revision_cached: Optional[Dict[str, int]] = None  # TODO (#110): default dict with 0
    local_branches_cached: Optional[List[str]] = None
    remote_branches_cached: Optional[List[str]] = None
    initial_log_shas_cached: Dict[str, List[str]] = {}
    remaining_log_shas_cached: Dict[str, List[str]] = {}
    reflogs_cached: Optional[Dict[str, Optional[List[REFLOG_ENTRY]]]] = None

    def __init__(self) -> None:
        pass


def run_git(cli_ctxt: CommandLineContext, git_cmd: str, *args: str, **kwargs: Dict[str, str]) -> int:
    exit_code = utils.run_cmd(cli_ctxt, "git", git_cmd, *args, **kwargs)
    if not kwargs.get("allow_non_zero") and exit_code != 0:
        raise MacheteException(f"`{utils.cmd_shell_repr('git', git_cmd, *args, **kwargs)}` returned {exit_code}")
    return exit_code


def popen_git(cli_ctxt: CommandLineContext, git_cmd: str, *args: str, **kwargs: Dict[str, str]) -> str:
    exit_code, stdout, stderr = utils.popen_cmd(cli_ctxt, "git", git_cmd, *args, **kwargs)
    if not kwargs.get("allow_non_zero") and exit_code != 0:
        exit_code_msg: str = utils.fmt(f"`{utils.cmd_shell_repr('git', git_cmd, *args, **kwargs)}` returned {exit_code}\n")
        stdout_msg: str = f"\n{utils.bold('stdout')}:\n{utils.dim(stdout)}" if stdout else ""
        stderr_msg: str = f"\n{utils.bold('stderr')}:\n{utils.dim(stderr)}" if stderr else ""
        # Not applying the formatter to avoid transforming whatever characters might be in the output of the command.
        raise MacheteException(exit_code_msg + stdout_msg + stderr_msg, apply_fmt=False)
    return stdout


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
            utils.debug(cli_ctxt, "get_default_editor()", f"'{name}' is undefined")
        else:
            editor_repr = f"'{name}'{(' (' + editor + ')') if editor != name else ''}"
            if not utils.find_executable(cli_ctxt, editor):
                utils.debug(cli_ctxt, "get_default_editor()", f"{editor_repr} is not available")
                if name == "$" + git_machete_editor_var:
                    # In this specific case, when GIT_MACHETE_EDITOR is defined but doesn't point to a valid executable,
                    # it's more reasonable/less confusing to raise an error and exit without opening anything.
                    raise MacheteException(f"<b>{editor_repr}</b> is not available")
            else:
                utils.debug(cli_ctxt, "get_default_editor()", f"{editor_repr} is available")
                if name != "$" + git_machete_editor_var and get_config_or_none(cli_ctxt, 'advice.macheteEditorSelection') != 'false':
                    sample_alternative = 'nano' if editor.startswith('vi') else 'vi'
                    sys.stderr.write(
                        utils.fmt(f"Opening <b>{editor_repr}</b>.\n",
                                  f"To override this choice, use <b>{git_machete_editor_var}</b> env var, e.g. `export {git_machete_editor_var}={sample_alternative}`.\n\n",
                                  "See `git machete help edit` and `git machete edit --debug` for more details.\n\n"
                                  "Use `git config --global advice.macheteEditorSelection false` to suppress this message.\n"))
                return editor

    # This case is extremely unlikely on a modern Unix-like system.
    return None


def get_git_version(cli_ctxt: CommandLineContext) -> Tuple[int, int, int]:
    if not GitContext.git_version:
        # We need to cut out the x.y.z part and not just take the result of 'git version' as is,
        # because the version string in certain distributions of git (esp. on OS X) has an extra suffix,
        # which is irrelevant for our purpose (checking whether certain git CLI features are available/bugs are fixed).
        raw = re.search(r"\d+.\d+.\d+", popen_git(cli_ctxt, "version")).group(0)
        GitContext.git_version = tuple(map(int, raw.split(".")))
    return GitContext.git_version


def get_root_dir(cli_ctxt: CommandLineContext) -> str:
    if not GitContext.root_dir:
        try:
            GitContext.root_dir = popen_git(cli_ctxt, "rev-parse", "--show-toplevel").strip()
        except MacheteException:
            raise MacheteException("Not a git repository")
    return GitContext.root_dir


def get_git_dir(cli_ctxt: CommandLineContext) -> str:
    if not GitContext.git_dir:
        try:
            GitContext.git_dir = popen_git(cli_ctxt, "rev-parse", "--git-dir").strip()
        except MacheteException:
            raise MacheteException("Not a git repository")
    return GitContext.git_dir


def get_git_subpath(cli_ctxt: CommandLineContext, *fragments: str) -> str:
    return os.path.join(get_git_dir(cli_ctxt), *fragments)


def parse_git_timespec_to_unix_timestamp(cli_ctxt: CommandLineContext, date: str) -> int:
    try:
        return int(popen_git(cli_ctxt, "rev-parse", "--since=" + date).replace("--max-age=", "").strip())
    except (MacheteException, ValueError):
        raise MacheteException(f"Cannot parse timespec: `{date}`")


def ensure_config_loaded(cli_ctxt: CommandLineContext) -> None:
    if GitContext.config_cached is None:
        GitContext.config_cached = {}
        for config_line in utils.non_empty_lines(popen_git(cli_ctxt, "config", "--list")):
            k_v = config_line.split("=", 1)
            if len(k_v) == 2:
                k, v = k_v
                GitContext.config_cached[k.lower()] = v


def get_config_or_none(cli_ctxt: CommandLineContext, key: str) -> Optional[str]:
    ensure_config_loaded(cli_ctxt)
    return GitContext.config_cached.get(key.lower())


def set_config(cli_ctxt: CommandLineContext, key: str, value: str) -> None:
    run_git(cli_ctxt, "config", "--", key, value)
    ensure_config_loaded(cli_ctxt)
    GitContext.config_cached[key.lower()] = value


def unset_config(cli_ctxt: CommandLineContext, key: str) -> None:
    ensure_config_loaded(cli_ctxt)
    if get_config_or_none(cli_ctxt, key):
        run_git(cli_ctxt, "config", "--unset", key)
        del GitContext.config_cached[key.lower()]


def remotes(cli_ctxt: CommandLineContext) -> List[str]:
    if GitContext.remotes_cached is None:
        GitContext.remotes_cached = utils.non_empty_lines(popen_git(cli_ctxt, "remote"))
    return GitContext.remotes_cached


def get_url_of_remote(cli_ctxt: CommandLineContext, remote: str) -> str:
    return popen_git(cli_ctxt, "remote", "get-url", "--", remote).strip()


def fetch_remote(cli_ctxt: CommandLineContext, remote: str) -> None:
    if remote not in GitContext.fetch_done_for:
        run_git(cli_ctxt, "fetch", remote)
        GitContext.fetch_done_for.add(remote)


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


# Implementation of basic git or git-related commands


def find_short_commit_sha_by_revision(cli_ctxt: CommandLineContext, revision: str) -> str:
    return popen_git(cli_ctxt, "rev-parse", "--short", revision + "^{commit}").rstrip()


def short_commit_sha_by_revision(cli_ctxt: CommandLineContext, revision: str) -> str:
    if revision not in GitContext.short_commit_sha_by_revision_cached:
        GitContext.short_commit_sha_by_revision_cached[revision] = find_short_commit_sha_by_revision(cli_ctxt, revision)
    return GitContext.short_commit_sha_by_revision_cached[revision]


def find_commit_sha_by_revision(cli_ctxt: CommandLineContext, revision: str) -> Optional[str]:
    # Without ^{commit}, 'git rev-parse --verify' will not only accept references to other kinds of objects (like trees and blobs),
    # but just echo the argument (and exit successfully) even if the argument doesn't match anything in the object store.
    try:
        return popen_git(cli_ctxt, "rev-parse", "--verify", "--quiet", revision + "^{commit}").rstrip()
    except MacheteException:
        return None


def commit_sha_by_revision(cli_ctxt: CommandLineContext, revision: str, prefix: str = "refs/heads/") -> Optional[str]:
    if GitContext.commit_sha_by_revision_cached is None:
        load_branches(cli_ctxt)
    full_revision: str = prefix + revision
    if full_revision not in GitContext.commit_sha_by_revision_cached:
        GitContext.commit_sha_by_revision_cached[full_revision] = find_commit_sha_by_revision(cli_ctxt, full_revision)
    return GitContext.commit_sha_by_revision_cached[full_revision]


def find_tree_sha_by_revision(cli_ctxt: CommandLineContext, revision: str) -> Optional[str]:
    try:
        return popen_git(cli_ctxt, "rev-parse", "--verify", "--quiet", revision + "^{tree}").rstrip()
    except MacheteException:
        return None


def tree_sha_by_commit_sha(cli_ctxt: CommandLineContext, commit_sha: str) -> Optional[str]:
    if GitContext.tree_sha_by_commit_sha_cached is None:
        load_branches(cli_ctxt)
    if commit_sha not in GitContext.tree_sha_by_commit_sha_cached:
        GitContext.tree_sha_by_commit_sha_cached[commit_sha] = find_tree_sha_by_revision(cli_ctxt, commit_sha)
    return GitContext.tree_sha_by_commit_sha_cached[commit_sha]


def is_full_sha(revision: str) -> Optional[Match[str]]:
    return re.match("^[0-9a-f]{40}$", revision)


# Resolve a revision identifier to a full sha
def full_sha(cli_ctxt: CommandLineContext, revision: str, prefix: str = "refs/heads/") -> Optional[str]:
    if prefix == "" and is_full_sha(revision):
        return revision
    else:
        return commit_sha_by_revision(cli_ctxt, revision, prefix)


def committer_unix_timestamp_by_revision(cli_ctxt: CommandLineContext, revision: str, prefix: str = "refs/heads/") -> int:
    if GitContext.committer_unix_timestamp_by_revision_cached is None:
        load_branches(cli_ctxt)
    return GitContext.committer_unix_timestamp_by_revision_cached.get(prefix + revision, 0)


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


def strict_counterpart_for_fetching_of_branch(cli_ctxt: CommandLineContext, b: str) -> Optional[str]:
    if GitContext.counterparts_for_fetching_cached is None:
        load_branches(cli_ctxt)
    return GitContext.counterparts_for_fetching_cached.get(b)


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


def go(cli_ctxt: CommandLineContext, branch: str) -> None:
    run_git(cli_ctxt, "checkout", "--quiet", branch, "--")


def local_branches(cli_ctxt: CommandLineContext) -> List[str]:
    if GitContext.local_branches_cached is None:
        load_branches(cli_ctxt)
    return GitContext.local_branches_cached


def remote_branches(cli_ctxt: CommandLineContext) -> List[str]:
    if GitContext.remote_branches_cached is None:
        load_branches(cli_ctxt)
    return GitContext.remote_branches_cached


def load_branches(cli_ctxt: CommandLineContext) -> None:
    GitContext.commit_sha_by_revision_cached = {}
    GitContext.committer_unix_timestamp_by_revision_cached = {}
    GitContext.counterparts_for_fetching_cached = {}
    GitContext.local_branches_cached = []
    GitContext.remote_branches_cached = []
    GitContext.tree_sha_by_commit_sha_cached = {}

    # Using 'committerdate:raw' instead of 'committerdate:unix' since the latter isn't supported by some older versions of git.
    raw_remote = utils.non_empty_lines(popen_git(cli_ctxt, "for-each-ref", "--format=%(refname)\t%(objectname)\t%(tree)\t%(committerdate:raw)", "refs/remotes"))
    for line in raw_remote:
        values = line.split("\t")
        if len(values) != 4:
            continue  # invalid, shouldn't happen
        b, commit_sha, tree_sha, committer_unix_timestamp_and_time_zone = values
        b_stripped = re.sub("^refs/remotes/", "", b)
        GitContext.remote_branches_cached += [b_stripped]
        GitContext.commit_sha_by_revision_cached[b] = commit_sha
        GitContext.tree_sha_by_commit_sha_cached[commit_sha] = tree_sha
        GitContext.committer_unix_timestamp_by_revision_cached[b] = int(committer_unix_timestamp_and_time_zone.split(' ')[0])

    raw_local = utils.non_empty_lines(popen_git(cli_ctxt, "for-each-ref", "--format=%(refname)\t%(objectname)\t%(tree)\t%(committerdate:raw)\t%(upstream)", "refs/heads"))

    for line in raw_local:
        values = line.split("\t")
        if len(values) != 5:
            continue  # invalid, shouldn't happen
        b, commit_sha, tree_sha, committer_unix_timestamp_and_time_zone, fetch_counterpart = values
        b_stripped = re.sub("^refs/heads/", "", b)
        fetch_counterpart_stripped = re.sub("^refs/remotes/", "", fetch_counterpart)
        GitContext.local_branches_cached += [b_stripped]
        GitContext.commit_sha_by_revision_cached[b] = commit_sha
        GitContext.tree_sha_by_commit_sha_cached[commit_sha] = tree_sha
        GitContext.committer_unix_timestamp_by_revision_cached[b] = int(committer_unix_timestamp_and_time_zone.split(' ')[0])
        if fetch_counterpart_stripped in GitContext.remote_branches_cached:
            GitContext.counterparts_for_fetching_cached[b_stripped] = fetch_counterpart_stripped
