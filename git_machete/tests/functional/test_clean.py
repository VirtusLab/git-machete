import io
import re
import subprocess
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Dict, Iterable
from unittest import mock

import pytest  # type: ignore
from git_machete import cli
from git_machete.tests.functional.commons import (GitRepositorySandbox, git,
                                                  mock_run_cmd)


def mock_ask_if(*args: str, **kwargs: Any) -> str:
    return 'y'


def mock_should_perform_interactive_slide_out(cmd: str) -> bool:
    return True


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

    @mock.patch(
        'git_machete.client.MacheteClient.should_perform_interactive_slide_out',
        mock_should_perform_interactive_slide_out,
    )
    @mock.patch('git_machete.client.MacheteClient.ask_if', mock_ask_if)
    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)
    def test_clean(self) -> None:
        (
            self.repo_sandbox.new_branch('master')
                .commit()
                .push()
                .new_branch('bar')
                .commit()
                .new_branch('bar2')
                .commit()
                .check_out("master")
                .new_branch('foo')
                .commit()
                .push()
                .new_branch('foo2')
                .commit()
                .check_out("master")
                .new_branch('moo')
                .commit()
                .new_branch('moo2')
                .commit()
        )
        self.launch_command('discover')
        (
            self.repo_sandbox
                .check_out("master")
                .new_branch('mars')
                .commit()
                .check_out("master")
        )
        self.launch_command('clean')

        expected_status_output = (
            """
            master *
            |
            o-bar (untracked)
            |
            o-foo
            |
            o-moo (untracked)
            """
        )
        self.assert_command(['status'], expected_status_output)

        with pytest.raises(subprocess.CalledProcessError):
            self.repo_sandbox.check_out("mars")
