from .base_test import BaseTest
from .mockers import (assert_success, fixed_author_and_committer_date_in_past,
                      launch_command, overridden_environment,
                      rewrite_branch_layout_file)


class TestReapply(BaseTest):

    def test_reapply(self) -> None:
        """
        Verify that 'git machete reapply' performs
        'git rebase' to the fork point of the current branch.
        """

        with fixed_author_and_committer_date_in_past():
            (
                self.repo_sandbox
                .remove_remote()
                .new_branch("level-0-branch")
                .commit("Basic commit.")
                .new_branch("level-1-branch")
                .commit("First level-1 commit.")
                .commit("Second level-1 commit.")
                .new_branch("level-2-branch")
                .commit("First level-2 commit.")
                .commit("Second level-2 commit.")
                .commit("Third level-2 commit.")
                .check_out("level-0-branch")
                .commit("New commit on level-0-branch")
            )

        body: str = \
            """
            level-0-branch

                level-1-branch
                    level-2-branch
            """
        rewrite_branch_layout_file(body)

        self.repo_sandbox.check_out("level-1-branch")
        assert_success(
            ["status", "-L"],
            """
            level-0-branch
            |
            | b98ae42  First level-1 commit.
            | 1b657a1  Second level-1 commit.
            x-level-1-branch *
              |
              | 64f8913  First level-2 commit.
              | a6b9ae5  Second level-2 commit.
              | 958f91f  Third level-2 commit.
              o-level-2-branch
            """
        )
        assert launch_command("fork-point", "level-1-branch").strip() == "c0306cdd500fc39869505592200258055407bcc6"

        # Let's substitute the editor opened by git for interactive rebase to-do list
        # so that the test can run in a fully automated manner.
        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '2s/^pick /fixup /'"):
            with fixed_author_and_committer_date_in_past():
                launch_command("reapply")

        assert_success(
            ["status", "-L"],
            """
            level-0-branch
            |
            | 887182d  First level-1 commit.
            x-level-1-branch *
              |
              | 64f8913  First level-2 commit.
              | a6b9ae5  Second level-2 commit.
              | 958f91f  Third level-2 commit.
              x-level-2-branch
            """
        )
        assert launch_command("fork-point", "level-1-branch").strip() == "c0306cdd500fc39869505592200258055407bcc6"

        self.repo_sandbox.check_out("level-2-branch")
        assert launch_command("fork-point", "level-2-branch").strip() == "1b657a15fa4c619fcb4e871176d1471cdbce9093"
        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '2s/^pick /fixup /'"):
            with fixed_author_and_committer_date_in_past():
                launch_command("reapply", "--fork-point=64f8913")

        assert_success(
            ["status", "-L"],
            """
            level-0-branch
            |
            | 887182d  First level-1 commit.
            x-level-1-branch
              |
              | 64f8913  First level-2 commit.
              | a5fcbb0  Second level-2 commit.
              x-level-2-branch *
            """
        )
        assert launch_command("fork-point", "level-2-branch").strip() == "1b657a15fa4c619fcb4e871176d1471cdbce9093"

    def test_reapply_with_rebase_no_qualifier(self) -> None:
        (
            self.repo_sandbox
            .remove_remote()
            .new_branch("level-0-branch")
            .commit("Basic commit.")
            .new_branch("level-1-branch")
            .commit("First level-1 commit.")
            .commit("Second level-1 commit.")
        )

        body: str = \
            """
            level-0-branch
                level-1-branch  rebase=no
            """
        rewrite_branch_layout_file(body)

        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '2s/^pick /fixup /'"):
            assert_success(
                ["reapply"],
                "Warn: branch level-1-branch is marked with rebase=no qualifier\n")
