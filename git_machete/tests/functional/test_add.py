import io
import re
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from typing import Iterable
from unittest import mock

from git_machete import cli
from git_machete.tests.functional.commons import (GitRepositorySandbox, git,
                                                  mock_run_cmd)


class TestMachete:

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
    def test_add(self) -> None:
        """
        Verify behaviour of a 'git machete add' command.
        """
        (
            self.repo_sandbox.new_branch("master")
                .commit("master commit.")
                .new_branch("develop")
                .commit("develop commit.")
                .new_branch("feature")
                .commit("feature commit.")
                .check_out("develop")
                .commit("New commit on develop")
        )
        self.launch_command("discover", "-y")
        self.repo_sandbox.new_branch("bugfix/feature_fail")

        self.assert_command(
            ['add', '-y', 'bugfix/feature_fail'],
            'Adding `bugfix/feature_fail` onto the inferred upstream (parent) branch `develop`\n'
            'Added branch `bugfix/feature_fail` onto `develop`\n',
            strip_indentation=False
        )

        # test with --onto option
        self.repo_sandbox.new_branch("chore/remove_indentation")

        self.assert_command(
            ['add', '--onto=feature'],
            'Added branch `chore/remove_indentation` onto `feature`\n',
            strip_indentation=False
        )
