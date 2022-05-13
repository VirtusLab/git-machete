from typing import Any

import pytest

from .mockers import (GitRepositorySandbox, assert_command,
                      get_current_commit_hash, launch_command, mock_run_cmd,
                      mock_run_cmd_and_forward_stdout)


class TestSlideOut:

    def setup_method(self, mocker: Any) -> None:

        self.repo_sandbox = GitRepositorySandbox()

        (
            self.repo_sandbox
            # Create the remote and sandbox repos, chdir into sandbox repo
            .new_repo(self.repo_sandbox.remote_path, "--bare")
            .new_repo(self.repo_sandbox.local_path)
            .execute(f"git remote add origin {self.repo_sandbox.remote_path}")
            .execute('git config user.email "tester@test.com"')
            .execute('git config user.name "Tester Test"')
        )

    def test_slide_out(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        (
            self.repo_sandbox.new_branch("develop")
            .commit("develop commit")
            .push()
            .new_branch("slide_root")
            .commit("slide_root_1")
            .push()
            .check_out("slide_root")
            .new_branch("child_a")
            .commit("child_a_1")
            .push()
            .check_out("slide_root")
            .new_branch("child_b")
            .commit("child_b_1")
            .push()
            .check_out("child_b")
            .new_branch("child_c")
            .commit("child_c_1")
            .push()
            .new_branch("child_d")
            .commit("child_d_1")
            .push()
        )

        launch_command("discover", "-y", "--roots=develop")

        assert_command(
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

        assert_command(
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

        # Slide-out an interior branch with multiple downstreams. (slide_root)
        # This rebases all the downstreams onto the new upstream. (develop -> [child_a, child_b])
        launch_command("traverse", "-Wy")
        launch_command("go", "up")
        launch_command("go", "up")

        assert_command(
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
                    o-child_d
                """,
        )

        launch_command("slide-out", "-n")

        assert_command(
            ["status", "-l"],
            """
            develop
            |
            | child_a_1
            o-child_a (diverged from origin)
            |
            | child_b_1
            o-child_b * (diverged from origin)
              |
              | child_d_1
              x-child_d
            """,
        )

        launch_command("traverse", "-Wy")
        assert_command(
            ["status", "-l"],
            """
            develop
            |
            | child_a_1
            o-child_a
            |
            | child_b_1
            o-child_b *
              |
              | child_d_1
              o-child_d
            """,
        )

        # Slide-out a terminal branch. (child_d)
        # This just slices the branch off the tree.
        launch_command("go", "down")
        launch_command("slide-out", "-n")

        assert_command(
            ["status", "-l"],
            """
            develop
            |
            | child_a_1
            o-child_a
            |
            | child_b_1
            o-child_b *
            """,
        )

    def test_slide_out_with_valid_down_fork_point(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_forward_stdout)

        (
            self.repo_sandbox.new_branch('branch-0')
                .commit()
                .new_branch('branch-1')
                .commit()
                .new_branch('branch-2')
                .commit()
                .new_branch('branch-3')
                .commit()
                .commit('Second commit on branch-3.')
        )
        hash_of_second_commit_on_branch_3 = get_current_commit_hash()
        self.repo_sandbox.commit("Third commit on branch-3.")

        launch_command('discover', '-y')
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

        assert_command(['status', '-l'], expected_status_output)

    def test_slide_out_with_invalid_down_fork_point(self, mocker: Any) -> None:
        (
            self.repo_sandbox.new_branch('branch-0')
                .commit()
                .new_branch('branch-1')
                .commit()
                .new_branch('branch-2')
                .commit()
                .new_branch('branch-3')
                .commit()
                .check_out('branch-2')
                .commit('Commit that is not ancestor of branch-3.')
        )
        hash_of_commit_that_is_not_ancestor_of_branch_2 = get_current_commit_hash()

        launch_command('discover', '-y')

        with pytest.raises(SystemExit):
            launch_command(
                'slide-out', '-n', 'branch-1', 'branch-2', '-d',
                hash_of_commit_that_is_not_ancestor_of_branch_2)

    def test_slide_out_with_down_fork_point_and_multiple_children_of_last_branch(self, mocker: Any) -> None:
        (
            self.repo_sandbox.new_branch('branch-0')
                .commit()
                .new_branch('branch-1')
                .commit()
                .new_branch('branch-2a')
                .commit()
                .check_out('branch-1')
                .new_branch('branch-2b')
                .commit()
        )

        hash_of_only_commit_on_branch_2b = get_current_commit_hash()

        launch_command('discover', '-y')

        with pytest.raises(SystemExit):
            launch_command(
                'slide-out', '-n', 'branch-1', '-d',
                hash_of_only_commit_on_branch_2b)
