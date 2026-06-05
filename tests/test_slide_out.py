
import pytest
from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.cli_runner import (assert_failure, assert_success, launch_command,
                              read_branch_layout_file,
                              rewrite_branch_layout_file)
from tests.git_repository import (amend_commit, check_out, commit, create_repo,
                                  create_repo_with_remote, delete_branch,
                                  delete_remote_branch, get_current_branch,
                                  get_current_commit_hash, get_local_branches,
                                  new_branch, push)
from tests.mockers import (fixed_author_and_committer_date_in_past,
                           mock_input_returning_y)
from tests.shell import read_file, set_file_executable, write_to_file


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

        assert_success(["go", "up"], "Checking out child_c... OK\n")
        assert_success(
            ["slide-out", "-n"],
            "Sliding out child_c\n"
            "Reattaching child_d under child_b\n"
            "Checking out child_b... OK\n"
            "Checking out child_d... OK\n"
            "Rebasing child_d onto child_b...\n"
        )

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
        assert_success(["go", "up"], "Checking out child_b... OK\n")
        assert_success(["go", "up"], "Checking out slide_root... OK\n")

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
        assert_success(
            ["slide-out", "-n", "--delete", "--merge"],
            "Sliding out slide_root\n"
            "Reattaching child_a, child_b under develop\n"
            "Checking out develop... OK\n"
            "Checking out child_a... OK\n"
            "Merging develop into child_a...\n"
            "Checking out child_b... OK\n"
            "Merging develop into child_b...\n"
            "Delete branch slide_root (merged to HEAD)? (y, N, q)\n"
        )

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
        assert_success(
            ["go", "down"],
            "Checking out child_d... OK\n"
            "Tip: run git machete go (without a direction) to pick a branch interactively.\n"
        )
        assert "child_d" in get_local_branches()
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        assert_success(
            ["slide-out", "-n", "--delete"],
            "Sliding out child_d\n"
            "Checking out child_b... OK\n"
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

    def test_slide_out_branch_other_than_current(self) -> None:
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

        assert_success(["slide-out", "branch-1"], "Sliding out branch-1\n")
        # Branch should not be changed by slide-out if the current branch has NOT been slid out
        assert get_current_branch() == "branch-2"

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
        assert_success(
            ["slide-out", "-n", "branch-1"],
            "Sliding out branch-1\n"
            "Reattaching branch-2 under branch-0\n"
            "Checking out branch-2... OK\n"
            "Rebasing branch-2 onto branch-0...\n"
        )
        assert "branch-0 branch-1 branch-2" == read_file("machete-post-slide-out-output").strip()

        write_to_file(".git/hooks/machete-post-slide-out", "#!/bin/sh\nexit 1")
        assert_failure(["slide-out", "-n", "branch-2"], "The machete-post-slide-out hook exited with 1, aborting.")

    def test_slide_out_multiple_pivots_fires_post_slide_out_hook_per_pivot(self) -> None:
        # With `--no-rebase` multiple branches with surviving children can be slid out at once;
        # the post-slide-out hook then fires once per such pivot (each with its own new parent and children).
        create_repo()
        new_branch('master')
        commit()
        new_branch('a')
        commit()
        new_branch('x')
        commit()
        check_out('master')
        new_branch('b')
        commit()
        new_branch('y')
        commit()

        body: str = \
            """
            master
                a
                    x
                b
                    y
            """
        rewrite_branch_layout_file(body)

        write_to_file(".git/hooks/machete-post-slide-out", '#!/bin/sh\necho "$@" >> machete-post-slide-out-output')
        set_file_executable(".git/hooks/machete-post-slide-out")

        check_out('master')
        assert_success(
            ["slide-out", "--no-rebase", "a", "b"],
            "Sliding out a\n"
            "Sliding out b\n"
            "Reattaching x under master\n"
            "Reattaching y under master\n"
        )
        assert read_file("machete-post-slide-out-output").splitlines() == ["master a x", "master b y"]

    def test_slide_out_root_branch_with_post_slide_out_hook(self) -> None:
        """Test that post-slide-out hook receives empty string for new_upstream when sliding out root branch."""
        create_repo()
        new_branch('root')
        commit()
        new_branch('child-1')
        commit()
        check_out('root')
        new_branch('child-2')
        commit()

        body: str = \
            """
            root
                child-1
                child-2
            """
        rewrite_branch_layout_file(body)

        # Create hook that explicitly shows each argument (including empty ones)
        hook_script = '#!/bin/sh\nprintf "argc=%d arg1=[%s] arg2=[%s] arg3=[%s] arg4=[%s]\\n" ' \
                      '"$#" "$1" "$2" "$3" "$4" > machete-post-slide-out-output'
        write_to_file(".git/hooks/machete-post-slide-out", hook_script)
        set_file_executable(".git/hooks/machete-post-slide-out")
        assert_success(
            ["slide-out", "-n", "root"],
            "Sliding out root\n"
            "Reattaching child-1, child-2 as new root branches\n"
        )
        # Hook receives: "" (empty new_upstream), "root" (slid out branch), "child-1" "child-2" (new downstreams)
        hook_output = read_file("machete-post-slide-out-output").strip()
        assert hook_output == "argc=4 arg1=[] arg2=[root] arg3=[child-1] arg4=[child-2]", \
            f"Expected 4 args with first being empty, got: '{hook_output}'"

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
            "Branch to slide out must have a child branch if option --down-fork-point is passed"
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
        assert_success(
            ['slide-out', '-n', 'branch-1', 'branch-2', '-d', hash_of_second_commit_on_branch_3],
            "Sliding out branch-1\n"
            "Sliding out branch-2\n"
            "Reattaching branch-3 under branch-0\n"
            "Checking out branch-3... OK\n"
            "Rebasing branch-3 onto branch-0...\n"
        )

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
            "Sliding out branch-1\n"
            "Reattaching branch-2 under branch-0\n"
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
            "Branch to slide out can't have more than one child branch if option --down-fork-point is passed"
        )

    def test_slide_out_with_multiple_pivots_in_rebase_mode(self) -> None:
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

        # In rebase/merge mode at most one slid-out branch may have surviving (not-also-slid-out) children,
        # so there's a single branch to rebase those children onto. Here both `branch-1` (surviving child `branch-2b`)
        # and `branch-2a` (surviving child `branch-3`) would need their children reattached, hence the error.
        def multiple_pivots_failure(pivots: str) -> str:
            return (
                f"Multiple branches to slide out have child branches that would need to be reattached: {pivots}.\n"
                "git-machete can't pick a single branch to rebase/merge their children onto.\n"
                "Pass --no-rebase to slide out without syncing the children, or slide out the branches in separate runs."
            )
        assert_failure(
            ['slide-out', 'branch-2a', 'branch-1'],
            multiple_pivots_failure("branch-2a, branch-1")
        )
        assert_failure(
            ['slide-out', 'branch-1', 'branch-2a'],
            multiple_pivots_failure("branch-1, branch-2a")
        )

    def test_slide_out_non_chain_branches(self) -> None:
        # Sliding out a set of branches that do NOT form a chain used to fail with a cryptic
        # "No downstream branch defined for ..." error; now it just removes them from the layout.
        create_repo()
        new_branch('master')
        commit()
        new_branch('a')
        commit()
        check_out('master')
        new_branch('b')
        commit()
        check_out('master')
        new_branch('c')
        commit()

        body: str = \
            """
            master
                a
                b
                c
            """
        rewrite_branch_layout_file(body)

        check_out('master')
        assert_success(
            ['slide-out', 'a', 'b'],
            "Sliding out a\n"
            "Sliding out b\n"
        )

        assert read_branch_layout_file().splitlines() == ["master", "    c"]

    def test_slide_out_branch_and_its_only_child_together(self) -> None:
        # Sliding out a branch together with its only child (which is therefore a leaf) leaves no surviving
        # children to reattach, so there's nothing to rebase - and no chain requirement to satisfy.
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

        assert_success(
            ['slide-out', '-n', 'branch-3', 'branch-2a'],
            "Sliding out branch-3\n"
            "Sliding out branch-2a\n"
        )

        assert read_branch_layout_file().splitlines() == [
            "branch-0",
            "    branch-1",
            "        branch-2b",
        ]

    def test_slide_out_multiple_pivots_with_no_rebase(self) -> None:
        # `--no-rebase` lifts the single-pivot restriction: each slid-out branch's children are simply
        # reattached to their own nearest surviving ancestor, with no rebase/merge.
        create_repo()
        new_branch('master')
        commit()
        new_branch('a')
        commit()
        new_branch('x')
        commit()
        check_out('master')
        new_branch('b')
        commit()
        new_branch('y')
        commit()

        body: str = \
            """
            master
                a
                    x
                b
                    y
            """
        rewrite_branch_layout_file(body)

        check_out('master')
        assert_success(
            ['slide-out', '--no-rebase', 'a', 'b'],
            "Sliding out a\n"
            "Sliding out b\n"
            "Reattaching x under master\n"
            "Reattaching y under master\n"
        )

        assert read_branch_layout_file().splitlines() == [
            "master",
            "    x",
            "    y",
        ]

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
        delete_remote_branch('origin/has_downstream')
        new_branch('downstream')
        commit()
        check_out('main')
        new_branch('should_be_pruned')
        commit()
        push()
        delete_remote_branch('origin/should_be_pruned')
        check_out('main')
        new_branch('with_qualifier')
        commit()
        push()
        delete_remote_branch('origin/with_qualifier')
        check_out('main')

        body: str = \
            """
            main
                unpushed
                not_deleted_remotely
                has_downstream
                    downstream
                should_be_pruned PR #123
                with_qualifier slide-out=no
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['slide-out', '--removed-from-remote', '--delete'],
            "Sliding out should_be_pruned\n"
            "Skipping with_qualifier as it's marked as slide-out=no\n"
            "Deleting branch should_be_pruned...\n")

        assert read_branch_layout_file().splitlines() == [
            "main",
            "    unpushed",
            "    not_deleted_remotely",
            "    has_downstream",
            "        downstream",
            "    with_qualifier slide-out=no"
        ]

        expected_status_output = (
            """
              main *
              |
              o-unpushed (untracked)
              |
              o-not_deleted_remotely
              |
              o-has_downstream (untracked)
              | |
              | o-downstream (untracked)
              |
              o-with_qualifier  slide-out=no (untracked)
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

        assert read_branch_layout_file().splitlines() == [
            "main",
            "    unpushed",
            "    has_downstream",
            "        downstream",
            "    with_qualifier slide-out=no"
        ]
        branches = get_local_branches()
        assert 'not_deleted_remotely' in branches

    @pytest.mark.parametrize('extra_arg', ['foo', '-d=foo', '--down-fork-point=foo', '-M', '--merge', '-n',
                                           '--no-interactive-rebase', '--no-rebase'])
    def test_slide_out_removed_from_remote_with_extra_args(self, extra_arg: str) -> None:
        create_repo()
        assert_failure(
            ['slide-out', '--removed-from-remote', extra_arg],
            "Only --delete can be passed with --removed-from-remote",
        )

    def test_slide_out_with_no_rebase(self) -> None:
        """Test that --no-rebase flag skips rebasing downstream branches."""
        create_repo()
        new_branch("root")
        commit("root commit")
        new_branch("branch-1")
        commit("branch-1 commit")
        new_branch("branch-2")
        commit("branch-2 commit")

        body: str = \
            """
            root
                branch-1
                    branch-2
            """
        rewrite_branch_layout_file(body)

        # Get commit hash of branch-2 before slide-out
        branch_2_commit_before = get_current_commit_hash()

        # Slide out branch-1 with --no-rebase, branch-2 should not be rebased
        assert_success(
            ["slide-out", "branch-1", "--no-rebase"],
            "Sliding out branch-1\n"
            "Reattaching branch-2 under root\n"
        )

        # Verify that branch-2 is now a child of root in the layout
        expected_layout = ["root", "    branch-2"]
        assert read_branch_layout_file().splitlines() == expected_layout

        # Verify we're still on branch-2
        assert get_current_branch() == "branch-2"

        # Verify that branch-2 was NOT rebased (commit hash unchanged)
        branch_2_commit_after = get_current_commit_hash()
        assert branch_2_commit_before == branch_2_commit_after

    def test_slide_out_no_rebase_conflicts_with_merge(self) -> None:
        """Test that --no-rebase and --merge cannot be used together."""
        assert_failure(
            ['slide-out', '--no-rebase', '-M'],
            "Option -M/--merge cannot be specified together with --no-rebase."
        )

    def test_slide_out_no_rebase_conflicts_with_down_fork_point(self) -> None:
        """Test that --no-rebase and --down-fork-point cannot be used together."""
        assert_failure(
            ['slide-out', '--no-rebase', '--down-fork-point=@'],
            "Option -d/--down-fork-point only makes sense when using rebase and cannot be specified together with --no-rebase."
        )

    def test_slide_out_no_rebase_conflicts_with_no_interactive_rebase(self) -> None:
        """Test that --no-rebase and --no-interactive-rebase cannot be used together."""
        assert_failure(
            ['slide-out', '--no-rebase', '--no-interactive-rebase'],
            "Option --no-interactive-rebase only makes sense when using rebase and cannot be specified together with --no-rebase."
        )

    def test_slide_out_no_rebase_conflicts_with_no_edit_merge(self) -> None:
        """Test that --no-rebase and --no-edit-merge cannot be used together."""
        assert_failure(
            ['slide-out', '--no-rebase', '--no-edit-merge'],
            "Option --no-edit-merge only makes sense when using merge and cannot be specified together with --no-rebase."
        )

    def test_slide_out_root_branch(self) -> None:
        """Test that root branches can be slid out and children become new roots without rebasing."""
        create_repo()
        new_branch("root")
        commit("root commit")
        new_branch("child-1")
        commit("child-1 commit")
        new_branch("child-2")
        commit("child-2 commit")
        check_out("root")
        new_branch("child-3")
        commit("child-3 commit")

        body: str = \
            """
            root
                child-1
                    child-2
                child-3
            """
        rewrite_branch_layout_file(body)

        # Get commit hashes before slide-out to verify no rebase happens
        check_out("child-1")
        child_1_commit_before = get_current_commit_hash()
        check_out("child-2")
        child_2_commit_before = get_current_commit_hash()
        check_out("child-3")
        child_3_commit_before = get_current_commit_hash()

        # Slide out the root branch
        check_out("root")
        assert_success(
            ["slide-out"],
            "Sliding out root\n"
            "Reattaching child-1, child-3 as new root branches\n"
            "Checking out child-1... OK\n"
        )

        # Verify that child-1 and child-3 are now root branches in the layout
        expected_layout = ["child-1", "    child-2", "child-3"]
        assert read_branch_layout_file().splitlines() == expected_layout

        # Verify we're on child-1 (first downstream)
        assert get_current_branch() == "child-1"

        # Verify that NO rebase happened (commit hashes unchanged)
        child_1_commit_after = get_current_commit_hash()
        assert child_1_commit_before == child_1_commit_after

        check_out("child-2")
        child_2_commit_after = get_current_commit_hash()
        assert child_2_commit_before == child_2_commit_after

        check_out("child-3")
        child_3_commit_after = get_current_commit_hash()
        assert child_3_commit_before == child_3_commit_after

    def test_slide_out_root_branch_with_no_rebase(self) -> None:
        """Test that a root branch with a single child can be slid out with --no-rebase flag (though it's redundant)."""
        create_repo()
        new_branch("root")
        commit("root commit")
        new_branch("child-1")
        commit("child-1 commit")
        new_branch("child-2")
        commit("child-2 commit")

        body: str = \
            """
            root
                child-1
                    child-2
            """
        rewrite_branch_layout_file(body)

        # Get commit hashes before slide-out to verify no rebase happens
        check_out("child-1")
        child_1_commit_before = get_current_commit_hash()
        check_out("child-2")
        child_2_commit_before = get_current_commit_hash()

        # Slide out the root branch with --no-rebase
        check_out("root")
        assert_success(
            ["slide-out", "--no-rebase"],
            "Sliding out root\n"
            "Reattaching child-1 as new root branch\n"
            "Checking out child-1... OK\n"
        )

        # Verify that child-1 became a root branch (keeping child-2 underneath) in the layout
        expected_layout = ["child-1", "    child-2"]
        assert read_branch_layout_file().splitlines() == expected_layout

        # Verify we're on child-1 (first downstream)
        assert get_current_branch() == "child-1"

        # Verify that NO rebase happened (commit hashes unchanged)
        child_1_commit_after = get_current_commit_hash()
        assert child_1_commit_before == child_1_commit_after

        check_out("child-2")
        child_2_commit_after = get_current_commit_hash()
        assert child_2_commit_before == child_2_commit_after

    def test_slide_out_root_branch_with_no_downstreams(self) -> None:
        """Test that when sliding out a root branch with no downstreams, we stay on that branch."""
        create_repo()
        new_branch("root-1")
        commit("root-1 commit")
        new_branch("root-2")
        commit("root-2 commit")

        body: str = \
            """
            root-1
            root-2
            """
        rewrite_branch_layout_file(body)

        # Slide out root-2 (which has no downstreams)
        check_out("root-2")
        assert_success(["slide-out"], "Sliding out root-2\n")

        # Verify that only root-1 remains in the layout
        expected_layout = ["root-1"]
        assert read_branch_layout_file().splitlines() == expected_layout

        # Verify we're still on root-2 (the slid-out branch, since it has no downstreams to check out)
        assert get_current_branch() == "root-2"

    def test_slide_out_branch_already_deleted_from_git(self) -> None:
        """Regression test: `slide-out <branch>` for a branch that has already been
        deleted from git must succeed cleanly, without first auto-pruning the branch
        with a `Warning: sliding invalid branch ... out` message and then failing
        with `Branch ... not found in the tree of branch dependencies`.
        """
        create_repo()
        new_branch('branch-0')
        commit()
        new_branch('branch-1')
        commit()
        check_out('branch-0')
        new_branch('branch-2')
        commit()

        body: str = \
            """
            branch-0
                branch-1
                branch-2
            """
        rewrite_branch_layout_file(body)

        delete_branch('branch-1')

        # The explicit slide-out should succeed cleanly (no warning, no error)
        # and remove the (now-orphaned-in-git) branch from the layout.
        assert_success(["slide-out", "branch-1"], "Sliding out branch-1\n")

        expected_layout = ["branch-0", "    branch-2"]
        assert read_branch_layout_file().splitlines() == expected_layout
