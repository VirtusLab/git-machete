"""Regression test guarding against duplicate command invocations in `--verbose` mode.

Caches inside `git_machete.git.Git` are supposed to make every underlying git command
run at most once per top-level CLI invocation. When that contract is accidentally broken
(e.g. by an extra `Git` / `MacheteConfig` instance constructed somewhere in the dispatch path,
or by a getter that bypasses its memoization), the duplicate becomes visible in `-v` output.

We assert on the verbose log rather than on a mocked spy so that the test exercises the same
output path the user sees - the line format `_subproc._run_cmd` / `_popen_cmd` print is exactly
the one a human would read to investigate a wasted git call.
"""

from collections import Counter
from typing import Dict, List

from tests.base_test import BaseTest
from tests.cli_runner import launch_command, rewrite_branch_layout_file
from tests.git_repository import commit, create_repo, new_branch

# Some underlying commands are legitimately invoked more than once during a single `status`
# render; the per-command count below is the upper bound the assertion will tolerate before
# flagging a regression. Anything not listed defaults to 1 (the strict "exactly once" rule
# that the test is built around).
MAX_ALLOWED_INVOCATIONS: Dict[str, int] = {
    # On git versions without `git worktree list --porcelain` (i.e. git < 2.5),
    # `Git.load_branch_by_worktree_root_dir` stands in for the missing porcelain output by
    # calling `git symbolic-ref --quiet HEAD` itself to learn the current branch in the
    # (sole) current worktree; `status` then calls the same command a second time via
    # `get_currently_checked_out_branch_or_none` for the `*`-marker logic. Adding a
    # dedicated `Git`-level cache just for this would need a separate is-cached flag (because
    # `None` is itself a valid result for detached HEAD), which isn't worth the noise for a
    # corner that only matters in the oldest-git CI image. On git >= 2.5 the porcelain path
    # provides the branch info without a separate `symbolic-ref` call, so the count stays
    # at 1 and the cap is unused.
    "git -c log.showSignature=false symbolic-ref --quiet HEAD": 2,
}


def _extract_verbose_commands(output: str) -> List[str]:
    """Pull out the command lines emitted by `verbose_mode` in `git_machete.utils.cmd`.

    `print_command` writes each invocation on its own line as `escape_markup(get_cmd_shell_repr(...))`.
    All `git` calls go through `GIT_EXEC = ("git", "-c", "log.showSignature=false")`, and `machete-status-branch`
    hook invocations are emitted with their `ASCII_ONLY=...` env prefix - both shapes are matched here.
    The status tree itself (printed to stdout) starts with whitespace / tree-drawing characters,
    so the prefix filter is enough to skip it.
    """
    commands: List[str] = []
    for line in output.splitlines():
        if line.startswith("git -c log.showSignature=false ") or line.startswith("ASCII_ONLY="):
            commands.append(line)
    return commands


class TestNoDuplicateCommands(BaseTest):

    def test_status_does_not_run_any_underlying_command_twice(self) -> None:
        # A minimal but non-trivial layout (root + child) so `status` exercises both
        # the parent-of-child fork-point logic and the per-branch reflog lookup.
        create_repo()
        commit("Initial commit on master.")
        new_branch("develop")
        commit("Commit on develop.")

        rewrite_branch_layout_file(
            """
            master
            \tdevelop
            """
        )

        output = launch_command("status", "--verbose")

        commands = _extract_verbose_commands(output)
        # Sanity check: if the filter ever stops matching the actual log format, every other assertion below would trivially pass.
        assert commands, (
            "No verbose command lines were captured - the `-v` output format likely changed; "
            "update `_extract_verbose_commands` to match.\n"
            f"Raw output was:\n{output}")

        over_cap = {
            cmd: count for cmd, count in Counter(commands).items()
            if count > MAX_ALLOWED_INVOCATIONS.get(cmd, 1)
        }
        assert not over_cap, (
            "The following underlying commands were executed more times than allowed during "
            "`git machete status -v`; each should be served from a `Git` cache after its first "
            "invocation (or listed in `MAX_ALLOWED_INVOCATIONS` with a justifying comment):\n" +
            "\n".join(
                f"  {count}x (cap: {MAX_ALLOWED_INVOCATIONS.get(cmd, 1)}x): {cmd}"
                for cmd, count in over_cap.items()))
