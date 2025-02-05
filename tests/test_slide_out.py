import pytest
from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success,
                      fixed_author_and_committer_date_in_past, launch_command,
                      mock_input_returning_y, read_branch_layout_file,
                      read_file, rewrite_branch_layout_file,
                      set_file_executable, write_to_file)
from .mockers_git_repository import (amend_commit, check_out, commit,
                                     create_repo, create_repo_with_remote,
                                     delete_remote_branch,
                                     get_current_commit_hash,
                                     get_local_branches, new_branch, push)


class TestSlideOut(BaseTest):

    def test_slide_out(self, mocker: MockerFixture) -> None:
        create_repo_with_remote()
        new_branch("develop")
        commit("develop commit")
        push()
        new_branch("slide_root")
        commit("slide_root_1")
        push()
        check_out("slide_root")
        new_branch("child_a")
        commit("child_a_1")
        push()
        check_out("slide_root")
        new_branch("child_b")
        commit("child_b_1")
        push()
        check_out("child_b")
        new_branch("child_c")
        commit("child_c_1")
        push()
        new_branch("child_d")
        commit("child_d_1")
        push()

        body: str = \
            """
            develop
                slide_root
                    child_a
                    child_b
                        child_c
                            child_d
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | slide_root_1
            o-slide_root
              |
              | child_a_1
              o-child_a
              |
              | child_b_1
              o-child_b
                |
                | child_c_1
                o-child_c
                  |
                  | child_d_1
                  o-child_d *
            """,
        )

        # Slide-out a single interior branch with one downstream. (child_c)
        # This rebases the single downstream onto the new upstream. (child_b -> child_d)

        launch_command("go", "up")
        launch_command("slide-out", "-n")

        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | slide_root_1
            o-slide_root
              |
              | child_a_1
              o-child_a
              |
              | child_b_1
              o-child_b
                |
                | child_d_1
                o-child_d * (diverged from origin)
            """,
        )

        # Slide-out an interior branch with multiple downstreams (slide_root).
        # This rebases all the downstreams onto the new upstream (develop -> [child_a, child_b]).
        launch_command("go", "up")
        launch_command("go", "up")

        assert_success(
            ["status", "-l"],
            """
                develop
                |
                | slide_root_1
                o-slide_root *
                  |
                  | child_a_1
                  o-child_a
                  |
                  | child_b_1
                  o-child_b
                    |
                    | child_d_1
                    o-child_d (diverged from origin)
                """,
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        launch_command("slide-out", "-n", "--delete", "--merge")

        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | slide_root_1
            | child_a_1
            o-child_a
            |
            | slide_root_1
            | child_b_1
            o-child_b *
              |
              | child_d_1
              o-child_d (diverged from origin)
            """
        )

        # Slide-out and delete a terminal branch (child_d).
        # This just slices the branch off the tree.
        launch_command("go", "down")
        assert "child_d" in get_local_branches()
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        assert_success(
            ["slide-out", "-n", "--delete"],
            "Delete branch child_d (unmerged to HEAD)? (y, N, q)\n"
        )
        assert "child_d" not in get_local_branches()

        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | slide_root_1
            | child_a_1
            o-child_a
            |
            | slide_root_1
            | child_b_1
            o-child_b *
            """,
        )

    def test_slide_out_with_post_slide_out_hook(self) -> None:
        create_repo()
        new_branch('branch-0')
        commit()
        new_branch('branch-1')
        commit()
        new_branch('branch-2')
        commit()

        body: str = \
            """
            branch-0
                branch-1
                    branch-2
            """
        rewrite_branch_layout_file(body)

        write_to_file(".git/hooks/machete-post-slide-out", '#!/bin/sh\necho "$@" > machete-post-slide-out-output')
        set_file_executable(".git/hooks/machete-post-slide-out")
        launch_command("slide-out", "-n", "branch-1")
        assert "branch-0 branch-1 branch-2" == read_file("machete-post-slide-out-output").strip()

        write_to_file(".git/hooks/machete-post-slide-out", "#!/bin/sh\nexit 1")
        assert_failure(["slide-out", "-n", "branch-2"], "The machete-post-slide-out hook exited with 1, aborting.")

    def test_slide_out_with_invalid_down_fork_point(self) -> None:
        create_repo()
        with fixed_author_and_committer_date_in_past():
            new_branch('branch-0')
            commit('0')
            new_branch('branch-1')
            commit('1')
            new_branch('branch-2')
            commit('2')
            new_branch('branch-3')
            commit('3')
            check_out('branch-2')
            commit('Commit that is not ancestor of branch-3.')

        hash_of_commit_that_is_not_ancestor_of_branch_2 = get_current_commit_hash()

        body: str = \
            """
            branch-0
                branch-1
                    branch-2
                        branch-3
            """
        rewrite_branch_layout_file(body)

        assert_failure(
            ['slide-out', '-n', 'branch-1', 'branch-2', '-d', hash_of_commit_that_is_not_ancestor_of_branch_2],
            "Fork point baedab8d1f2be48c73f35e7617c9217649049e02 is not ancestor of or the tip of the branch-3 branch."
        )

    def test_slide_out_with_down_fork_point_and_no_child_of_last_branch(self) -> None:
        create_repo()
        new_branch('branch-0')
        commit()
        new_branch('branch-1')
        commit()

        body: str = \
            """
            branch-0
                branch-1
            """
        rewrite_branch_layout_file(body)

        assert_failure(
            ['slide-out', '-d=@~', 'branch-1'],
            "Last branch to slide out must have a child branch if option --down-fork-point is passed"
        )

    def test_slide_out_with_down_fork_point_and_single_child_of_last_branch(self) -> None:
        create_repo_with_remote()
        new_branch('branch-0')
        commit()
        new_branch('branch-1')
        commit()
        new_branch('branch-2')
        commit()
        new_branch('branch-3')
        commit()
        commit('Second commit on branch-3.')

        hash_of_second_commit_on_branch_3 = get_current_commit_hash()
        commit("Third commit on branch-3.")

        body: str = \
            """
            branch-0
                branch-1
                    branch-2
                        branch-3
            """
        rewrite_branch_layout_file(body)
        launch_command(
            'slide-out', '-n', 'branch-1', 'branch-2', '-d',
            hash_of_second_commit_on_branch_3)

        expected_status_output = (
            """
            branch-0 (untracked)
            |
            | Third commit on branch-3.
            o-branch-3 * (untracked)
            """
        )

        assert_success(['status', '-l'], expected_status_output)

    def test_slide_out_with_rebase_no_qualifier(self, mocker: MockerFixture) -> None:
        create_repo()
        new_branch('branch-0')
        commit("Commit on branch-0.")
        new_branch('branch-1')
        commit("Commit on branch-1.")
        new_branch('branch-2')
        commit('Commit on branch-2.')
        check_out('branch-0')
        amend_commit('New commit message')

        body: str = \
            """
            branch-0
                branch-1
                    branch-2  rebase=no
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        assert_success(
            ['slide-out', '-n', 'branch-1', '--delete'],
            "Delete branch branch-1 (unmerged to HEAD)? (y, N, q)\n"
        )

        expected_status_output = (
            """
            branch-0 *
            |
            | Commit on branch-1.
            | Commit on branch-2.
            x-branch-2  rebase=no
            """
        )
        assert_success(['status', '-l'], expected_status_output)

    def test_slide_out_with_slide_out_no_qualifier(self) -> None:
        create_repo()
        new_branch('branch-0')
        commit()
        new_branch('branch-1')
        commit()
        new_branch('branch-2')
        commit()

        body: str = \
            """
            branch-0
                branch-1  slide-out=no
                    branch-2
            """
        rewrite_branch_layout_file(body)

        assert_failure(
            ['slide-out', 'branch-1'],
            "Branch branch-1 is annotated with slide-out=no qualifier, aborting.\n"
            "Remove the qualifier using git machete anno or edit branch layout file directly."
        )

    def test_slide_out_with_down_fork_point_and_multiple_children_of_last_branch(self) -> None:
        create_repo()
        new_branch('branch-0')
        commit()
        new_branch('branch-1')
        commit()
        new_branch('branch-2a')
        commit()
        check_out('branch-1')
        new_branch('branch-2b')
        commit()

        hash_of_only_commit_on_branch_2b = get_current_commit_hash()

        body: str = \
            """
            branch-0
                branch-1
                    branch-2a
                    branch-2b
            """
        rewrite_branch_layout_file(body)

        assert_failure(
            ['slide-out', '-n', 'branch-1', '-d', hash_of_only_commit_on_branch_2b],
            "Last branch to slide out can't have more than one child branch if option --down-fork-point is passed"
        )

    def test_slide_out_with_invalid_sequence_of_branches(self) -> None:
        create_repo()
        new_branch('branch-0')
        commit()
        new_branch('branch-1')
        commit()
        new_branch('branch-2a')
        commit()
        new_branch('branch-3')
        commit()
        check_out('branch-1')
        new_branch('branch-2b')
        commit()

        body: str = \
            """
            branch-0
                branch-1
                    branch-2a
                        branch-3
                    branch-2b
            """
        rewrite_branch_layout_file(body)

        assert_failure(
            ['slide-out', 'branch-0'],
            "No upstream branch defined for branch-0, cannot slide out"
        )
        assert_failure(
            ['slide-out', 'branch-3', 'branch-2a'],
            "No downstream branch defined for branch-3, cannot slide out"
        )
        assert_failure(
            ['slide-out', 'branch-2a', 'branch-1'],
            "branch-1 is not downstream of branch-2a, cannot slide out"
        )
        assert_failure(
            ['slide-out', 'branch-1', 'branch-2a'],
            "Multiple downstream branches defined for branch-1: branch-2a, branch-2b; cannot slide out"
        )

    def test_slide_out_down_fork_point_with_merge(self) -> None:
        assert_failure(
            ['slide-out', '--down-fork-point=@', '-M'],
            "Option -d/--down-fork-point only makes sense when using rebase and cannot be specified together with -M/--merge."
        )

    def test_slide_out_removed_from_remote(self) -> None:
        create_repo_with_remote()

        new_branch('main')
        commit()
        push()
        new_branch('unmanaged')
        commit()
        push()
        check_out('main')
        new_branch('unpushed')
        commit()
        check_out('main')
        new_branch('not_deleted_remotely')
        commit()
        push()
        check_out('main')
        new_branch('has_downstream')
        commit()
        push()
        new_branch('downstream')
        commit()
        check_out('main')
        new_branch('should_be_pruned')
        commit()
        push()
        delete_remote_branch('origin/should_be_pruned')
        check_out('main')

        body: str = \
            """
            main
                unpushed
                not_deleted_remotely
                has_downstream
                    downstream
                should_be_pruned PR #123
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['slide-out', '--removed-from-remote', '--delete'],
            "Sliding out should_be_pruned\nDeleting branch should_be_pruned...\n")

        assert read_branch_layout_file() == "main\n    unpushed\n    not_deleted_remotely\n    has_downstream\n        downstream\n"

        expected_status_output = (
            """
              main *
              |
              o-unpushed (untracked)
              |
              o-not_deleted_remotely
              |
              o-has_downstream
                |
                o-downstream (untracked)
            """
        )
        assert_success(['status'], expected_status_output)

        branches = get_local_branches()
        assert 'unmanaged' in branches
        assert 'unpushed' in branches
        assert 'not_deleted_remotely' in branches
        assert 'has_downstream' in branches
        assert 'should_be_pruned' not in branches

        delete_remote_branch('origin/not_deleted_remotely')
        launch_command('slide-out', '--removed-from-remote', '--verbose')

        assert read_branch_layout_file() == "main\n    unpushed\n    has_downstream\n        downstream\n"
        branches = get_local_branches()
        assert 'not_deleted_remotely' in branches

    @pytest.mark.parametrize('extra_arg', ['foo', '-d=foo', '--down-fork-point=foo', '-M', '--merge', '-n', '--no-interactive-rebase'])
    def test_slide_out_removed_from_remote_with_extra_args(self, extra_arg: str) -> None:
        assert_failure(
            ['slide-out', '--removed-from-remote', extra_arg],
            "Only --delete can be passed with --removed-from-remote",
        )
