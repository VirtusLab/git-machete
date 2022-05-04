import io
import re
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from typing import Dict, Iterable
from unittest import mock

import pytest  # type: ignore
from git_machete import cli
from git_machete.tests.functional.commons import (GitRepositorySandbox,
                                                  get_current_commit_hash, git,
                                                  mock_run_cmd, popen)


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
    def test_squash_merge(self) -> None:
        (
            self.repo_sandbox.new_branch("root")
            .commit("root")
            .push()
            .new_branch("develop")
            .commit("develop")
            .push()
            .new_branch("feature")
            .commit("feature_1")
            .commit("feature_2")
            .push()
            .new_branch("child")
            .commit("child_1")
            .commit("child_2")
            .push()
        )

        self.launch_command("discover", "-y", "--roots=root")

        self.assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            o-develop
              |
              | feature_1
              | feature_2
              o-feature
                |
                | child_1
                | child_2
                o-child *
            """,
        )

        # squash-merge feature onto develop
        (
            self.repo_sandbox.check_out("develop")
            .execute("git merge --squash feature")
            .execute("git commit -m squash_feature")
            .check_out("child")
        )

        # in default mode, feature is detected as "m" (merged) into develop
        self.assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            | squash_feature
            o-develop (ahead of origin)
              |
              m-feature
                |
                | child_1
                | child_2
                o-child *
            """,
        )

        # but under --no-detect-squash-merges, feature is detected as "x" (behind) develop
        self.assert_command(
            ["status", "-l", "--no-detect-squash-merges"],
            """
            root
            |
            | develop
            | squash_feature
            o-develop (ahead of origin)
              |
              | feature_1
              | feature_2
              x-feature
                |
                | child_1
                | child_2
                o-child *
            """,
        )

        # traverse then slides out the branch
        self.launch_command("traverse", "-w", "-y")
        self.assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            | squash_feature
            o-develop
              |
              | child_1
              | child_2
              o-child *
            """,
        )

        # simulate an upstream squash-merge of the feature branch
        (
            self.repo_sandbox.check_out("develop")
            .new_branch("upstream_squash")
            .execute("git merge --squash child")
            .execute("git commit -m squash_child")
            .execute("git push origin upstream_squash:develop")
            .check_out("child")
            .execute("git branch -D upstream_squash")
        )

        # status before fetch will show develop as out of date
        self.assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            | squash_feature
            o-develop (behind origin)
              |
              | child_1
              | child_2
              o-child *
            """,
        )

        # fetch-traverse will fetch upstream squash, detect, and slide out the child branch
        self.launch_command("traverse", "-W", "-y")

        self.assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            | squash_feature
            | squash_child
            o-develop *
            """,
        )

    def test_squash_with_valid_fork_point(self) -> None:
        (
            self.repo_sandbox.new_branch('branch-0')
                .commit("First commit.")
                .commit("Second commit.")
        )
        fork_point = get_current_commit_hash()

        (
            self.repo_sandbox.commit("Third commit.")
                .commit("Fourth commit.")
        )

        self.launch_command('squash', '-f', fork_point)

        expected_branch_log = (
            "Third commit.\n"
            "Second commit.\n"
            "First commit."
        )

        current_branch_log = popen('git log -3 --format=%s')
        assert current_branch_log == \
            expected_branch_log, \
            ("Verify that `git machete squash -f <fork-point>` squashes commit"
                " from one succeeding the fork-point until tip of the branch.")

    def test_squash_with_invalid_fork_point(self) -> None:
        (
            self.repo_sandbox.new_branch('branch-0')
                .commit()
                .new_branch('branch-1a')
                .commit()
        )
        fork_point_to_branch_1a = get_current_commit_hash()

        (
            self.repo_sandbox.check_out('branch-0')
                .new_branch('branch-1b')
                .commit()
        )

        with pytest.raises(SystemExit):
            # First exception MacheteException is raised, followed by SystemExit.
            self.launch_command('squash', '-f', fork_point_to_branch_1a)
