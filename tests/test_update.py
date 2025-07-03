from pytest_mock import MockerFixture

from git_machete.exceptions import UnderlyingGitException

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, execute,
                      execute_ignoring_exit_code,
                      fixed_author_and_committer_date_in_past, launch_command,
                      mock_input_returning, mock_input_returning_y,
                      overridden_environment, popen, read_file,
                      rewrite_branch_layout_file, set_file_executable,
                      write_to_file)
from .mockers_git_repository import (add_file_and_commit, check_out, commit,
                                     create_repo, get_commit_hash,
                                     get_current_commit_hash, get_git_version,
                                     is_ancestor_or_equal, new_branch,
                                     new_orphan_branch)


class TestUpdate(BaseTest):

    def test_update_with_fork_point_not_specified(self) -> None:
        """
        Verify that 'git machete update --no-interactive-rebase' performs
        'git rebase' to the parent branch of the current branch.
        """

        create_repo()
        new_branch("level-0-branch")
        commit("Basic commit.")
        new_branch("level-1-branch")
        commit("Only level-1 commit.")
        new_branch("level-2-branch")
        commit("Only level-2 commit.")
        check_out("level-0-branch")
        commit("New commit on level-0-branch")

        body: str = \
            """
            level-0-branch
                level-1-branch
                    level-2-branch
            """
        rewrite_branch_layout_file(body)

        parents_new_commit_hash = get_current_commit_hash()
        check_out("level-1-branch")
        launch_command("update", "--no-interactive-rebase")
        new_fork_point_hash = launch_command("fork-point").strip()

        assert parents_new_commit_hash == new_fork_point_hash, \
            ("Verify that 'git machete update --no-interactive-rebase' perform "
             "'git rebase' to the parent branch of the current branch."
             )

    def test_update_by_merge(self) -> None:

        create_repo()
        new_branch("level-0-branch")
        commit("Basic commit.")
        new_branch("level-1-branch")
        commit("Only level-1 commit.")
        new_branch("level-2-branch")
        commit("Only level-2 commit.")
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
        old_level_1_commit_hash = get_current_commit_hash()
        launch_command("update", "--merge", "--no-edit-merge")

        assert is_ancestor_or_equal(old_level_1_commit_hash, "level-1-branch")
        assert is_ancestor_or_equal("level-0-branch", "level-1-branch")

    def test_update_drops_empty_commits(self) -> None:
        """
        Verify that 'git machete update' drops effectively-empty commits if the underlying git supports that behavior.
        """

        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch("level-0-branch")
            commit("Basic commit.")
            new_branch("level-1-branch")
            commit("level-1 commit")
            commit("level-1 commit... but to be cherry-picked onto level-0-branch")
            check_out("level-0-branch")
            commit("New commit on level-0-branch")
            execute("git cherry-pick level-1-branch")

        body: str = \
            """
            level-0-branch
                level-1-branch
            """
        rewrite_branch_layout_file(body)

        parents_new_commit_hash = get_current_commit_hash()
        check_out("level-1-branch")
        # Note that `--empty=drop` is the default in NON-interactive mode.
        # We want to check if effectively empty commits are dropped in interactive mode as well.
        # Let's substitute the editor opened by git for interactive rebase to-do list
        # so that the test can run in a fully automated manner.
        with overridden_environment(GIT_SEQUENCE_EDITOR=":"):
            if get_git_version() >= (2, 26, 0):
                launch_command("update")
            else:
                with fixed_author_and_committer_date_in_past():
                    expected_error_message = "git rebase --interactive --onto refs/heads/level-0-branch " \
                                             "5420e4e155024d8c9181df47ecaeb983c667ce9b level-1-branch returned 1"
                    assert_failure(["update"], expected_error_message, expected_type=UnderlyingGitException)
                execute("git rebase --continue")

        new_fork_point_hash = launch_command("fork-point").strip()
        assert parents_new_commit_hash == new_fork_point_hash, \
            "Verify that 'git machete update' drops effectively-empty commits."
        branch_history = popen('git log level-0-branch..level-1-branch')
        assert "level-1 commit" in branch_history
        assert "level-1 commit... but to be cherry-picked onto level-0-branch" not in branch_history

    def test_update_with_fork_point_specified(self) -> None:
        """
        Verify that 'git machete update --no-interactive-rebase -f <commit_hash>'
        performs 'git rebase' to the upstream branch and drops the commits until
        (included) fork point specified by the option '-f'.
        """

        branch_first_commit_msg = "First commit on branch."
        branch_second_commit_msg = "Second commit on branch."
        create_repo()
        new_branch("root")
        commit("First commit on root.")
        new_branch("branch-1")
        commit(branch_first_commit_msg)
        commit(branch_second_commit_msg)

        branch_second_commit_hash = get_current_commit_hash()
        commit("Third commit on branch.")
        check_out("root")
        commit("Second commit on root.")

        roots_second_commit_hash = get_current_commit_hash()
        check_out("branch-1")

        body: str = \
            """
            root
                branch-1
            """
        rewrite_branch_layout_file(body)

        launch_command(
            "update", "--no-interactive-rebase", "-f", branch_second_commit_hash)
        new_fork_point_hash = launch_command("fork-point").strip()
        branch_history = popen('git log -10 --oneline')

        assert roots_second_commit_hash == new_fork_point_hash, \
            ("Verify that 'git machete update --no-interactive-rebase -f "
             "<commit_hash>' performs 'git rebase' to the upstream branch.")
        assert branch_first_commit_msg not in branch_history, \
            ("Verify that 'git machete update --no-interactive-rebase -f "
             "<commit_hash>' drops the commits until (included) fork point "
             "specified by the option '-f' from the current branch.")
        assert branch_second_commit_msg not in branch_history, \
            ("Verify that 'git machete update --no-interactive-rebase -f "
             "<commit_hash>' drops the commits until (included) fork point "
             "specified by the option '-f' from the current branch.")

    def test_update_with_invalid_fork_point(self) -> None:
        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch('branch-0')
            commit("Commit on branch-0.")
            new_branch("branch-1a")
            commit("Commit on branch-1a.")

            branch_1a_hash = get_current_commit_hash()

            check_out('branch-0')
            new_branch("branch-1b")
            commit("Commit on branch-1b.")

        body: str = \
            """
            branch-0
                branch-1a
                branch-1b
            """
        rewrite_branch_layout_file(body)

        expected_error_message = "Fork point f7b9c8347f11ced17e50b62f95f61523f221c5a2 " \
                                 "is not ancestor of or the tip of the branch-1b branch."
        assert_failure(['update', '-f', branch_1a_hash], expected_error_message)

    def test_update_with_rebase_no_qualifier(self) -> None:
        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch('branch-0')
            commit("Commit on branch-0.")
            new_branch("branch-1")
            commit("Commit on branch-1.")

        body: str = \
            """
            branch-0
                branch-1 rebase=no
            """
        rewrite_branch_layout_file(body)

        assert_failure(
            ['update'],
            "Branch branch-1 is annotated with rebase=no qualifier, aborting.\n"
            "Remove the qualifier using git machete anno or edit branch layout file directly."
        )

    def test_update_with_stop_for_edit(self) -> None:

        create_repo()
        new_branch('branch-0')
        commit()
        new_branch("branch-1")
        commit()

        rewrite_branch_layout_file("branch-0\n\tbranch-1")

        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '1s/^pick /edit /'"):
            launch_command("update")
        # See https://github.com/VirtusLab/git-machete/issues/935, which can only be reproduced on Windows
        # when some file is staged before `git rebase --continue` is executed.
        execute("touch bar.txt")
        execute("git add bar.txt")
        with overridden_environment(GIT_EDITOR="cat"):
            execute("git rebase --continue")

    def test_update_unmanaged_branch(self, mocker: MockerFixture) -> None:

        create_repo()
        new_branch('branch-0')
        commit()
        new_branch("branch-1")
        commit()
        check_out("branch-0")
        commit()
        check_out("branch-1")

        rewrite_branch_layout_file("branch-0")

        original_branch_1_hash = get_commit_hash("branch-1")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning(""))
        assert_failure(["update", "--no-interactive-rebase"], "Aborting.")
        assert get_commit_hash("branch-1") == original_branch_1_hash

        self.patch_symbol(mocker, "builtins.input", mock_input_returning_y)
        assert_success(
            ["update", "--no-interactive-rebase"],
            "Branch branch-1 not found in the tree of branch dependencies. "
            "Rebase onto the inferred upstream branch-0? (y, N)\n")
        assert is_ancestor_or_equal("branch-0", "branch-1")

    def test_update_unmanaged_branch_when_parent_cannot_be_inferred(self) -> None:
        create_repo()
        new_branch('branch-0')
        commit()
        new_orphan_branch("branch-1")
        commit()

        assert_failure(
            ["update", "--no-interactive-rebase"],
            "Branch branch-1 not found in the tree of branch dependencies and its upstream could not be inferred"
        )

    def test_update_with_pre_rebase_hook(self) -> None:
        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch('branch-0')
            commit('0')
            new_branch('branch-1')
            commit('1')

        body: str = \
            """
            branch-0
                branch-1
            """
        rewrite_branch_layout_file(body)

        write_to_file(".git/hooks/machete-pre-rebase", '#!/bin/sh\necho "$@" > machete-pre-rebase-output')
        set_file_executable(".git/hooks/machete-pre-rebase")
        launch_command("update", "-n")
        assert read_file("machete-pre-rebase-output").strip() == \
            "refs/heads/branch-0 5e35f5b08c0e663e9c1a9ceaa5b45dc453f60929 branch-1"

        write_to_file(".git/hooks/machete-pre-rebase", "#!/bin/sh\nexit 1")
        assert_failure(["update", "-n"], "The machete-pre-rebase hook refused to rebase. Error code: 1")

    def test_update_no_interactive_rebase_with_merge(self) -> None:
        assert_failure(
            ['update', '--no-interactive-rebase', '--merge'],
            "Option --no-interactive-rebase only makes sense when using rebase and cannot be specified together with -M/--merge."
        )

    def test_update_fork_point_with_merge(self) -> None:
        assert_failure(
            ['update', '-f', '@', '-M'],
            "Option -f/--fork-point only makes sense when using rebase and cannot be specified together with -M/--merge."
        )

    def test_update_during_side_effecting_operations(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        add_file_and_commit("1.txt", "some-content")
        check_out("master")
        new_branch("feature")
        add_file_and_commit("1.txt", "some-other-content")
        check_out("develop")

        body: str = \
            """
            master
                develop
            """
        rewrite_branch_layout_file(body)

        # AM

        patch_path = popen("git format-patch feature")
        execute_ignoring_exit_code(f"git am {patch_path}")

        assert_failure(["update"],
                       "git am session in progress. Conclude git am first "
                       "with git am --continue or git am --abort.",
                       expected_type=UnderlyingGitException)

        execute("git am --abort")

        # CHERRY-PICK

        execute_ignoring_exit_code("git cherry-pick feature")

        assert_failure(["update"],
                       "Cherry pick in progress. Conclude the cherry pick first with "
                       "git cherry-pick --continue or git cherry-pick --abort.",
                       expected_type=UnderlyingGitException)

        execute("git cherry-pick --abort")

        # MERGE

        execute_ignoring_exit_code("git merge feature")

        assert_failure(["update"],
                       "Merge in progress. Conclude the merge first with "
                       "git merge --continue or git merge --abort.",
                       expected_type=UnderlyingGitException)

        execute("git merge --abort")

        # REBASE

        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '1s/^pick /edit /'"):
            launch_command("update")

        assert_failure(["update"],
                       "Rebase of develop in progress. Conclude the rebase first with "
                       "git rebase --continue or git rebase --abort.",
                       expected_type=UnderlyingGitException)

        execute("git rebase --abort")

        # REVERT

        execute("git revert --no-commit HEAD")

        assert_failure(["update"],
                       "Revert in progress. Conclude the revert first with "
                       "git revert --continue or git revert --abort.",
                       expected_type=UnderlyingGitException)

        execute("git revert --abort")

        # BISECT

        commit()
        execute("git bisect start")
        execute("git bisect bad HEAD")
        execute("git bisect good HEAD~2")

        assert_failure(["update"],
                       "Bisecting in progress. Conclude the bisecting first with git bisect reset.",
                       expected_type=UnderlyingGitException)

        execute("git bisect reset")
