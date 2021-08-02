from typing import List, Optional, Callable, Tuple, Dict

import os
import re
import sys

from git_machete.contexts import CommandLineContext
from git_machete.exceptions import MacheteException
from git_machete import utils


class GitContext:
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


git_version = None


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
        for config_line in utils.non_empty_lines(popen_git(cli_ctxt, "config", "--list")):
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
        remotes_cached = utils.non_empty_lines(popen_git(cli_ctxt, "remote"))
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
