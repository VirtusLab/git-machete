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
from typing import List

from tests.base_test import BaseTest
from tests.cli_runner import launch_command, rewrite_branch_layout_file
from tests.git_repository import commit, create_repo, new_branch


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

        duplicates = {cmd: count for cmd, count in Counter(commands).items() if count > 1}
        assert not duplicates, (
            "The following underlying commands were executed more than once during `git machete status -v`; "
            "each should be served from a `Git` cache after its first invocation:\n" +
            "\n".join(f"  {count}x: {cmd}" for cmd, count in duplicates.items()))
