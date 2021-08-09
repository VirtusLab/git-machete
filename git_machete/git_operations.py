from typing import Callable, Dict, Generator, List, Match, Optional, Tuple, Set

import os
import re
import sys

from git_machete.options import CommandLineOptions
from git_machete.exceptions import MacheteException
from git_machete.utils import debug
from git_machete import utils
from git_machete.constants import MAX_COUNT_FOR_INITIAL_LOG

REFLOG_ENTRY = Tuple[str, str]


class GitContext:

    def __init__(self, cli_opts: CommandLineOptions) -> None:
        self.cli_opts: CommandLineOptions = cli_opts
        self.git_version: Tuple[int, ...] = None
        self.root_dir: str = None
        self.git_dir: str = None
        self.__fetch_done_for: Set[str] = set()
        self.__config_cached: Optional[Dict[str, str]] = None
        self.__remotes_cached: Optional[List[str]] = None
        self.__counterparts_for_fetching_cached: Optional[Dict[str, Optional[str]]] = None  # TODO (#110): default dict with None
        self.__short_commit_sha_by_revision_cached: Dict[str, str] = {}
        self.__tree_sha_by_commit_sha_cached: Optional[Dict[str, Optional[str]]] = None  # TODO (#110): default dict with None
        self.__commit_sha_by_revision_cached: Optional[Dict[str, Optional[str]]] = None  # TODO (#110): default dict with None
        self.__committer_unix_timestamp_by_revision_cached: Optional[Dict[str, int]] = None  # TODO (#110): default dict with 0
        self.__local_branches_cached: Optional[List[str]] = None
        self.__remote_branches_cached: Optional[List[str]] = None
        self.__initial_log_shas_cached: Dict[str, List[str]] = {}
        self.__remaining_log_shas_cached: Dict[str, List[str]] = {}
        self.__reflogs_cached: Optional[Dict[str, Optional[List[REFLOG_ENTRY]]]] = None
        self.branch_defs_by_sha_in_reflog: Optional[Dict[str, Optional[List[Tuple[str, str]]]]] = None

    @staticmethod
    def run_git(git_cmd: str, *args: str, **kwargs: Dict[str, str]) -> int:
        exit_code = utils.run_cmd("git", git_cmd, *args, **kwargs)
        if not kwargs.get("allow_non_zero") and exit_code != 0:
            raise MacheteException(f"`{utils.cmd_shell_repr('git', git_cmd, *args, **kwargs)}` returned {exit_code}")
        return exit_code

    @staticmethod
    def popen_git(git_cmd: str, *args: str, **kwargs: Dict[str, str]) -> str:
        exit_code, stdout, stderr = utils.popen_cmd("git", git_cmd, *args, **kwargs)
        if not kwargs.get("allow_non_zero") and exit_code != 0:
            exit_code_msg: str = utils.fmt(f"`{utils.cmd_shell_repr('git', git_cmd, *args, **kwargs)}` returned {exit_code}\n")
            stdout_msg: str = f"\n{utils.bold('stdout')}:\n{utils.dim(stdout)}" if stdout else ""
            stderr_msg: str = f"\n{utils.bold('stderr')}:\n{utils.dim(stderr)}" if stderr else ""
            # Not applying the formatter to avoid transforming whatever characters might be in the output of the command.
            raise MacheteException(exit_code_msg + stdout_msg + stderr_msg, apply_fmt=False)
        return stdout

    def get_default_editor(self) -> Optional[str]:
        # Based on the git's own algorithm for identifying the editor.
        # '$GIT_MACHETE_EDITOR', 'editor' (to please Debian-based systems) and 'nano' have been added.
        git_machete_editor_var = "GIT_MACHETE_EDITOR"
        proposed_editor_funs: List[Tuple[str, Callable[[], Optional[str]]]] = [
            ("$" + git_machete_editor_var, lambda: os.environ.get(git_machete_editor_var)),
            ("$GIT_EDITOR", lambda: os.environ.get("GIT_EDITOR")),
            ("git config core.editor", lambda: self.get_config_or_none("core.editor")),
            ("$VISUAL", lambda: os.environ.get("VISUAL")),
            ("$EDITOR", lambda: os.environ.get("EDITOR")),
            ("editor", lambda: "editor"),
            ("nano", lambda: "nano"),
            ("vi", lambda: "vi"),
        ]

        for name, fun in proposed_editor_funs:
            editor = fun()
            if not editor:
                debug("get_default_editor()", f"'{name}' is undefined")
            else:
                editor_repr = f"'{name}'{(' (' + editor + ')') if editor != name else ''}"
                if not utils.find_executable(editor):
                    debug("get_default_editor()", f"{editor_repr} is not available")
                    if name == "$" + git_machete_editor_var:
                        # In this specific case, when GIT_MACHETE_EDITOR is defined but doesn't point to a valid executable,
                        # it's more reasonable/less confusing to raise an error and exit without opening anything.
                        raise MacheteException(f"<b>{editor_repr}</b> is not available")
                else:
                    debug("get_default_editor()", f"{editor_repr} is available")
                    if name != "$" + git_machete_editor_var and self.get_config_or_none('advice.macheteEditorSelection') != 'false':
                        sample_alternative = 'nano' if editor.startswith('vi') else 'vi'
                        sys.stderr.write(
                            utils.fmt(f"Opening <b>{editor_repr}</b>.\n",
                                      f"To override this choice, use <b>{git_machete_editor_var}</b> env var, e.g. `export {git_machete_editor_var}={sample_alternative}`.\n\n",
                                      "See `git machete help edit` and `git machete edit --debug` for more details.\n\n"
                                      "Use `git config --global advice.macheteEditorSelection false` to suppress this message.\n"))
                    return editor

        # This case is extremely unlikely on a modern Unix-like system.
        return None

    def get_git_version(self) -> Tuple[int, ...]:
        if not self.git_version:
            # We need to cut out the x.y.z part and not just take the result of 'git version' as is,
            # because the version string in certain distributions of git (esp. on OS X) has an extra suffix,
            # which is irrelevant for our purpose (checking whether certain git CLI features are available/bugs are fixed).
            raw = re.search(r"\d+.\d+.\d+", self.popen_git("version")).group(0)
            self.git_version = tuple(map(int, raw.split(".")))
        return self.git_version

    def get_root_dir(self) -> str:
        if not self.root_dir:
            try:
                self.root_dir = self.popen_git("rev-parse", "--show-toplevel").strip()
            except MacheteException:
                raise MacheteException("Not a git repository")
        return self.root_dir

    def __get_git_dir(self) -> str:
        if not self.git_dir:
            try:
                self.git_dir = self.popen_git("rev-parse", "--git-dir").strip()
            except MacheteException:
                raise MacheteException("Not a git repository")
        return self.git_dir

    def get_git_subpath(self, *fragments: str) -> str:
        return os.path.join(self.__get_git_dir(), *fragments)

    def parse_git_timespec_to_unix_timestamp(self, date: str) -> int:
        try:
            return int(self.popen_git("rev-parse", "--since=" + date).replace("--max-age=", "").strip())
        except (MacheteException, ValueError):
            raise MacheteException(f"Cannot parse timespec: `{date}`")

    def __ensure_config_loaded(self) -> None:
        if self.__config_cached is None:
            self.__config_cached = {}
            for config_line in utils.non_empty_lines(self.popen_git("config", "--list")):
                k_v = config_line.split("=", 1)
                if len(k_v) == 2:
                    k, v = k_v
                    self.__config_cached[k.lower()] = v

    def get_config_or_none(self, key: str) -> Optional[str]:
        self.__ensure_config_loaded()
        return self.__config_cached.get(key.lower())

    def set_config(self, key: str, value: str) -> None:
        self.run_git("config", "--", key, value)
        self.__ensure_config_loaded()
        self.__config_cached[key.lower()] = value

    def unset_config(self, key: str) -> None:
        self.__ensure_config_loaded()
        if self.get_config_or_none(key):
            self.run_git("config", "--unset", key)
            del self.__config_cached[key.lower()]

    def remotes(self) -> List[str]:
        if self.__remotes_cached is None:
            self.__remotes_cached = utils.non_empty_lines(self.popen_git("remote"))
        return self.__remotes_cached

    def get_url_of_remote(self, remote: str) -> str:
        return self.popen_git("remote", "get-url", "--", remote).strip()

    def fetch_remote(self, remote: str) -> None:
        if remote not in self.__fetch_done_for:
            self.run_git("fetch", remote)
            self.__fetch_done_for.add(remote)

    def set_upstream_to(self, rb: str) -> None:
        self.run_git("branch", "--set-upstream-to", rb)

    def reset_keep(self, to_revision: str) -> None:
        try:
            self.run_git("reset", "--keep", to_revision)
        except MacheteException:
            raise MacheteException(
                f"Cannot perform `git reset --keep {to_revision}`. This is most likely caused by local uncommitted changes.")

    def push(self, remote: str, b: str, force_with_lease: bool = False) -> None:
        if not force_with_lease:
            opt_force = []
        elif self.get_git_version() >= (1, 8, 5):  # earliest version of git to support 'push --force-with-lease'
            opt_force = ["--force-with-lease"]
        else:
            opt_force = ["--force"]
        args = [remote, b]
        self.run_git("push", "--set-upstream", *(opt_force + args))

    def pull_ff_only(self, remote: str, rb: str) -> None:
        self.fetch_remote(remote)
        self.run_git("merge", "--ff-only", rb)
        # There's apparently no way to set remote automatically when doing 'git pull' (as opposed to 'git push'),
        # so a separate 'git branch --set-upstream-to' is needed.
        self.set_upstream_to(rb)

    def __find_short_commit_sha_by_revision(self, revision: str) -> str:
        return self.popen_git("rev-parse", "--short", revision + "^{commit}").rstrip()

    def short_commit_sha_by_revision(self, revision: str) -> str:
        if revision not in self.__short_commit_sha_by_revision_cached:
            self.__short_commit_sha_by_revision_cached[revision] = self.__find_short_commit_sha_by_revision(revision)
        return self.__short_commit_sha_by_revision_cached[revision]

    def __find_commit_sha_by_revision(self, revision: str) -> Optional[str]:
        # Without ^{commit}, 'git rev-parse --verify' will not only accept references to other kinds of objects (like trees and blobs),
        # but just echo the argument (and exit successfully) even if the argument doesn't match anything in the object store.
        try:
            return self.popen_git("rev-parse", "--verify", "--quiet", revision + "^{commit}").rstrip()
        except MacheteException:
            return None

    def commit_sha_by_revision(self, revision: str, prefix: str = "refs/heads/") -> Optional[str]:
        if self.__commit_sha_by_revision_cached is None:
            self.__load_branches()
        full_revision: str = prefix + revision
        if full_revision not in self.__commit_sha_by_revision_cached:
            self.__commit_sha_by_revision_cached[full_revision] = self.__find_commit_sha_by_revision(full_revision)
        return self.__commit_sha_by_revision_cached[full_revision]

    def __find_tree_sha_by_revision(self, revision: str) -> Optional[str]:
        try:
            return self.popen_git("rev-parse", "--verify", "--quiet", revision + "^{tree}").rstrip()
        except MacheteException:
            return None

    def tree_sha_by_commit_sha(self, commit_sha: str) -> Optional[str]:
        if self.__tree_sha_by_commit_sha_cached is None:
            self.__load_branches()
        if commit_sha not in self.__tree_sha_by_commit_sha_cached:
            self.__tree_sha_by_commit_sha_cached[commit_sha] = self.__find_tree_sha_by_revision(commit_sha)
        return self.__tree_sha_by_commit_sha_cached[commit_sha]

    @staticmethod
    def is_full_sha(revision: str) -> Optional[Match[str]]:
        return re.match("^[0-9a-f]{40}$", revision)

    # Resolve a revision identifier to a full sha
    def full_sha(self, revision: str, prefix: str = "refs/heads/") -> Optional[str]:
        if prefix == "" and self.is_full_sha(revision):
            return revision
        else:
            return self.commit_sha_by_revision(revision, prefix)

    def committer_unix_timestamp_by_revision(self, revision: str, prefix: str = "refs/heads/") -> int:
        if self.__committer_unix_timestamp_by_revision_cached is None:
            self.__load_branches()
        return self.__committer_unix_timestamp_by_revision_cached.get(prefix + revision, 0)

    def inferred_remote_for_fetching_of_branch(self, b: str) -> Optional[str]:
        # Since many people don't use '--set-upstream' flag of 'push', we try to infer the remote instead.
        for r in self.remotes():
            if f"{r}/{b}" in self.remote_branches():
                return r
        return None

    def strict_remote_for_fetching_of_branch(self, b: str) -> Optional[str]:
        remote = self.get_config_or_none(f"branch.{b}.remote")
        return remote.rstrip() if remote else None

    def combined_remote_for_fetching_of_branch(self, b: str) -> Optional[str]:
        return self.strict_remote_for_fetching_of_branch(b) or self.inferred_remote_for_fetching_of_branch(b)

    def __inferred_counterpart_for_fetching_of_branch(self, b: str) -> Optional[str]:
        for r in self.remotes():
            if f"{r}/{b}" in self.remote_branches():
                return f"{r}/{b}"
        return None

    def strict_counterpart_for_fetching_of_branch(self, b: str) -> Optional[str]:
        if self.__counterparts_for_fetching_cached is None:
            self.__load_branches()
        return self.__counterparts_for_fetching_cached.get(b)

    def combined_counterpart_for_fetching_of_branch(self, b: str) -> Optional[str]:
        # Since many people don't use '--set-upstream' flag of 'push' or 'branch', we try to infer the remote if the tracking data is missing.
        return self.strict_counterpart_for_fetching_of_branch(b) or self.__inferred_counterpart_for_fetching_of_branch(b)

    def is_am_in_progress(self) -> bool:
        # As of git 2.24.1, this is how 'cmd_rebase()' in builtin/rebase.c checks whether am is in progress.
        return os.path.isfile(self.get_git_subpath("rebase-apply", "applying"))

    def is_cherry_pick_in_progress(self) -> bool:
        return os.path.isfile(self.get_git_subpath("CHERRY_PICK_HEAD"))

    def is_merge_in_progress(self) -> bool:
        return os.path.isfile(self.get_git_subpath("MERGE_HEAD"))

    def is_revert_in_progress(self) -> bool:
        return os.path.isfile(self.get_git_subpath("REVERT_HEAD"))

    def checkout(self, branch: str) -> None:
        self.run_git("checkout", "--quiet", branch, "--")

    def local_branches(self) -> List[str]:
        if self.__local_branches_cached is None:
            self.__load_branches()
        return self.__local_branches_cached

    def remote_branches(self) -> List[str]:
        if self.__remote_branches_cached is None:
            self.__load_branches()
        return self.__remote_branches_cached

    def __load_branches(self) -> None:
        self.__commit_sha_by_revision_cached = {}
        self.__committer_unix_timestamp_by_revision_cached = {}
        self.__counterparts_for_fetching_cached = {}
        self.__local_branches_cached = []
        self.__remote_branches_cached = []
        self.__tree_sha_by_commit_sha_cached = {}

        # Using 'committerdate:raw' instead of 'committerdate:unix' since the latter isn't supported by some older versions of git.
        raw_remote = utils.non_empty_lines(self.popen_git("for-each-ref", "--format=%(refname)\t%(objectname)\t%(tree)\t%(committerdate:raw)", "refs/remotes"))
        for line in raw_remote:
            values = line.split("\t")
            if len(values) != 4:
                continue  # invalid, shouldn't happen
            b, commit_sha, tree_sha, committer_unix_timestamp_and_time_zone = values
            b_stripped = re.sub("^refs/remotes/", "", b)
            self.__remote_branches_cached += [b_stripped]
            self.__commit_sha_by_revision_cached[b] = commit_sha
            self.__tree_sha_by_commit_sha_cached[commit_sha] = tree_sha
            self.__committer_unix_timestamp_by_revision_cached[b] = int(committer_unix_timestamp_and_time_zone.split(' ')[0])

        raw_local = utils.non_empty_lines(self.popen_git("for-each-ref", "--format=%(refname)\t%(objectname)\t%(tree)\t%(committerdate:raw)\t%(upstream)", "refs/heads"))

        for line in raw_local:
            values = line.split("\t")
            if len(values) != 5:
                continue  # invalid, shouldn't happen
            b, commit_sha, tree_sha, committer_unix_timestamp_and_time_zone, fetch_counterpart = values
            b_stripped = re.sub("^refs/heads/", "", b)
            fetch_counterpart_stripped = re.sub("^refs/remotes/", "", fetch_counterpart)
            self.__local_branches_cached += [b_stripped]
            self.__commit_sha_by_revision_cached[b] = commit_sha
            self.__tree_sha_by_commit_sha_cached[commit_sha] = tree_sha
            self.__committer_unix_timestamp_by_revision_cached[b] = int(committer_unix_timestamp_and_time_zone.split(' ')[0])
            if fetch_counterpart_stripped in self.__remote_branches_cached:
                self.__counterparts_for_fetching_cached[b_stripped] = fetch_counterpart_stripped

    def __log_shas(self, revision: str, max_count: Optional[int]) -> List[str]:
        opts = ([f"--max-count={str(max_count)}"] if max_count else []) + ["--format=%H", f"refs/heads/{revision}"]
        return utils.non_empty_lines(self.popen_git("log", *opts))

    # Since getting the full history of a branch can be an expensive operation for large repositories (compared to all other underlying git operations),
    # there's a simple optimization in place: we first fetch only a couple of first commits in the history,
    # and only fetch the rest if needed.
    def spoonfeed_log_shas(self, b: str) -> Generator[str, None, None]:
        if b not in self.__initial_log_shas_cached:
            self.__initial_log_shas_cached[b] = self.__log_shas(b, max_count=MAX_COUNT_FOR_INITIAL_LOG)
        for sha in self.__initial_log_shas_cached[b]:
            yield sha

        if b not in self.__remaining_log_shas_cached:
            self.__remaining_log_shas_cached[b] = self.__log_shas(b, max_count=None)[MAX_COUNT_FOR_INITIAL_LOG:]
        for sha in self.__remaining_log_shas_cached[b]:
            yield sha

    def __load_all_reflogs(self) -> None:
        # %gd - reflog selector (refname@{num})
        # %H - full hash
        # %gs - reflog subject
        all_branches = [f"refs/heads/{b}" for b in self.local_branches()] + \
                       [f"refs/remotes/{self.combined_counterpart_for_fetching_of_branch(b)}" for b in self.local_branches() if self.combined_counterpart_for_fetching_of_branch(b)]
        # The trailing '--' is necessary to avoid ambiguity in case there is a file called just exactly like one of the branches.
        entries = utils.non_empty_lines(self.popen_git("reflog", "show", "--format=%gD\t%H\t%gs", *(all_branches + ["--"])))
        self.__reflogs_cached = {}
        for entry in entries:
            values = entry.split("\t")
            if len(values) != 3:  # invalid, shouldn't happen
                continue
            selector, sha, subject = values
            branch_and_pos = selector.split("@")
            if len(branch_and_pos) != 2:  # invalid, shouldn't happen
                continue
            b, pos = branch_and_pos
            if b not in self.__reflogs_cached:
                self.__reflogs_cached[b] = []
            self.__reflogs_cached[b] += [(sha, subject)]

    def reflog(self, b: str) -> List[REFLOG_ENTRY]:
        # git version 2.14.2 fixed a bug that caused fetching reflog of more than
        # one branch at the same time unreliable in certain cases
        if self.get_git_version() >= (2, 14, 2):
            if self.__reflogs_cached is None:
                self.__load_all_reflogs()
            return self.__reflogs_cached.get(b, [])
        else:
            if self.__reflogs_cached is None:
                self.__reflogs_cached = {}
            if b not in self.__reflogs_cached:
                # %H - full hash
                # %gs - reflog subject
                self.__reflogs_cached[b] = [
                    tuple(entry.split(":", 1)) for entry in utils.non_empty_lines(  # type: ignore
                        # The trailing '--' is necessary to avoid ambiguity in case there is a file called just exactly like the branch 'b'.
                        self.popen_git("reflog", "show", "--format=%H:%gs", b, "--"))
                ]
            return self.__reflogs_cached[b]

    def create_branch(self, b: str, out_of_revision: str) -> None:
        self.run_git("checkout", "-b", b, out_of_revision)
        self.flush_caches()  # the repository state has changed b/c of a successful branch creation, let's defensively flush all the caches

    def flush_caches(self) -> None:
        self.branch_defs_by_sha_in_reflog = None
        self.__commit_sha_by_revision_cached = None
        self.__config_cached = None
        self.__counterparts_for_fetching_cached = None
        self.__initial_log_shas_cached = {}
        self.__local_branches_cached = None
        self.__reflogs_cached = None
        self.__remaining_log_shas_cached = {}
        self.__remote_branches_cached = None
