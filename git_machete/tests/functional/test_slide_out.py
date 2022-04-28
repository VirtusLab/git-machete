import io
import re
import subprocess
import sys
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Dict, Iterable
from unittest import mock

import pytest  # type: ignore
from git_machete import cli
from git_machete.tests.functional.commons import (GitRepositorySandbox,
                                                  get_current_commit_hash, git,
                                                  mock_run_cmd)
from git_machete.utils import dim


def mock_run_cmd_and_forward_stdout(cmd: str, *args: str, **kwargs: Any) -> int:
    completed_process: subprocess.CompletedProcess[bytes] = subprocess.run(
        [cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, ** kwargs)
    print(completed_process.stdout.decode('utf-8'))
    exit_code: int = completed_process.returncode
    if exit_code != 0:
        print(dim(f"<exit code: {exit_code}>\n"), file=sys.stderr)
    return exit_code


class TestMachete:
    mock_repository_info: Dict[str, str] = {'full_name': 'testing/checkout_prs',
                                            'html_url': 'https://github.com/tester/repo_sandbox.git'}

    @staticmethod
    def adapt(s: str) -> str:
        return textwrap.indent(textwrap.dedent(re.sub(r"\|\n", "| \n", s[1:])), "  ")

    @staticmethod
    def launch_command(*args: str) -> str:
        with io.StringIO() as out:
            with redirect_stdout(out):
                with redirect_stderr(out):
                    cli.launch(list(args))
                    git.flush_caches()
            return out.getvalue()

    def assert_command(self, cmds: Iterable[str], expected_result: str, strip_indentation: bool = True) -> None:
        assert self.launch_command(*cmds) == (self.adapt(expected_result) if strip_indentation else expected_result)

    def setup_method(self) -> None:

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

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_slide_out(self) -> None:
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

        self.launch_command("discover", "-y", "--roots=develop")

        self.assert_command(
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

        self.launch_command("go", "up")
        self.launch_command("slide-out", "-n")

        self.assert_command(
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
        self.launch_command("traverse", "-Wy")
        self.launch_command("go", "up")
        self.launch_command("go", "up")

        self.assert_command(
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

        self.launch_command("slide-out", "-n")

        self.assert_command(
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

        self.launch_command("traverse", "-Wy")
        self.assert_command(
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
        self.launch_command("go", "down")
        self.launch_command("slide-out", "-n")

        self.assert_command(
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

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd_and_forward_stdout)
    def test_slide_out_with_valid_down_fork_point(self) -> None:
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

        self.launch_command('discover', '-y')
        self.launch_command(
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

        self.assert_command(['status', '-l'], expected_status_output)

    def test_slide_out_with_invalid_down_fork_point(self) -> None:
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

        self.launch_command('discover', '-y')

        with pytest.raises(SystemExit):
            self.launch_command(
                'slide-out', '-n', 'branch-1', 'branch-2', '-d',
                hash_of_commit_that_is_not_ancestor_of_branch_2)

    def test_slide_out_with_down_fork_point_and_multiple_children_of_last_branch(self) -> None:
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

        self.launch_command('discover', '-y')

        with pytest.raises(SystemExit):
            self.launch_command(
                'slide-out', '-n', 'branch-1', '-d',
                hash_of_only_commit_on_branch_2b)
