from .base_test import BaseTest
from .mockers import (assert_failure, assert_success,
                      fixed_author_and_committer_date_in_past, launch_command,
                      overridden_environment, rewrite_branch_layout_file)
from .mockers_git_repository import check_out, commit, create_repo, new_branch


class TestReapply(BaseTest):

    def test_reapply(self) -> None:
        """
        Verify that 'git machete reapply' performs
        'git rebase' to the fork point of the current branch.
        """

        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch("level-0-branch")
            commit("Basic commit.")
            new_branch("level-1-branch")
            commit("First level-1 commit.")
            commit("Second level-1 commit.")
            new_branch("level-2-branch")
            commit("First level-2 commit.")
            commit("Second level-2 commit.")
            commit("Third level-2 commit.")
            check_out("level-0-branch")
            commit("New commit on level-0-branch")

        body: str = \
            """
            level-0-branch

                level-1-branch
                    level-2-branch
            """
        rewrite_branch_layout_file(body)

        check_out("level-1-branch")
        assert_success(
            ["status", "-L"],
            """
            level-0-branch
            |
            | 9562e34  First level-1 commit.
            | 7af07f4  Second level-1 commit.
            x-level-1-branch *
              |
              | 96ab6f4  First level-2 commit.
              | dcc4641  Second level-2 commit.
              | ae40f61  Third level-2 commit.
              o-level-2-branch
            """
        )
        assert launch_command("fork-point", "level-1-branch").strip() == "5420e4e155024d8c9181df47ecaeb983c667ce9b"

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
            | 4bc2902  First level-1 commit.
            x-level-1-branch *
              |
              | 96ab6f4  First level-2 commit.
              | dcc4641  Second level-2 commit.
              | ae40f61  Third level-2 commit.
              x-level-2-branch
            """
        )
        assert launch_command("fork-point", "level-1-branch").strip() == "5420e4e155024d8c9181df47ecaeb983c667ce9b"

        check_out("level-2-branch")
        assert launch_command("fork-point", "level-2-branch").strip() == "7af07f47250298d435ba34691890e925b6f08dda"
        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '2s/^pick /fixup /'"):
            with fixed_author_and_committer_date_in_past():
                launch_command("reapply", "--fork-point=96ab6f4")

        assert_success(
            ["status", "-L"],
            """
            level-0-branch
            |
            | 4bc2902  First level-1 commit.
            x-level-1-branch
              |
              | 96ab6f4  First level-2 commit.
              | 1c4cc02  Second level-2 commit.
              x-level-2-branch *
            """
        )
        assert launch_command("fork-point", "level-2-branch").strip() == "7af07f47250298d435ba34691890e925b6f08dda"

    def test_reapply_with_rebase_no_qualifier(self) -> None:
        create_repo()
        new_branch("level-0-branch")
        commit("Basic commit.")
        new_branch("level-1-branch")
        commit("First level-1 commit.")
        commit("Second level-1 commit.")

        body: str = \
            """
            level-0-branch
                level-1-branch  rebase=no
            """
        rewrite_branch_layout_file(body)

        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '2s/^pick /fixup /'"):
            assert_failure(
                ["reapply"],
                "Branch level-1-branch is annotated with rebase=no qualifier, aborting.\n"
                "Remove the qualifier using git machete anno or edit branch layout file directly.")
