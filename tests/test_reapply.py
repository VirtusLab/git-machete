import os
from typing import Any

from .base_test import BaseTest
from .mockers import (assert_command, get_current_commit_hash, launch_command,
                      mock_run_cmd, rewrite_definition_file)


class TestReapply(BaseTest):

    def test_reapply(self, mocker: Any) -> None:
        """
        Verify that 'git machete reapply' performs
        'git rebase' to the fork point of the current branch.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        self.repo_sandbox.new_branch("level-0-branch").commit("Basic commit.")
        parents_old_commit_hash = get_current_commit_hash()
        (
            self.repo_sandbox
            .new_branch("level-1-branch")
            .commit("First level-1 commit.")
            .commit("Second level-1 commit.")
            .new_branch("level-2-branch")
            .commit("Only level-2 commit.")
            .check_out("level-0-branch")
            .commit("New commit on level-0-branch")
        )
        body: str = \
            """
            level-0-branch

                level-1-branch
                    level-2-branch
            """
        rewrite_definition_file(body)

        self.repo_sandbox.check_out("level-1-branch")
        assert_command(
            ["status", "-l"],
            """
            level-0-branch (untracked)
            |
            | First level-1 commit.
            | Second level-1 commit.
            x-level-1-branch * (untracked)
              |
              | Only level-2 commit.
              o-level-2-branch (untracked)
            """
        )
        assert launch_command("fork-point").strip() == parents_old_commit_hash

        try:
            # Let's substitute the editor opened by git for interactive rebase to-do list
            # so that the test can run in a fully automated manner.
            os.environ["GIT_SEQUENCE_EDITOR"] = "sed -i.bak '2s/^pick /fixup /'"

            launch_command("reapply")
        finally:
            del os.environ["GIT_SEQUENCE_EDITOR"]

        assert_command(
            ["status", "-l"],
            """
            level-0-branch (untracked)
            |
            | First level-1 commit.
            x-level-1-branch * (untracked)
              |
              | Only level-2 commit.
              x-level-2-branch (untracked)
            """
        )
        assert launch_command("fork-point").strip() == parents_old_commit_hash
