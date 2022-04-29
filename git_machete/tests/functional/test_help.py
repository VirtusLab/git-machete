import io
import re
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from typing import Dict, Iterable
from unittest import mock

import pytest  # type: ignore
from git_machete import cli
from git_machete.docs import long_docs
from git_machete.tests.functional.commons import (GitRepositorySandbox, git,
                                                  mock_run_cmd)


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
    def test_help(self) -> None:
        expected_exit_code = None

        with pytest.raises(SystemExit) as e:
            self.launch_command("help")
        assert expected_exit_code == e.value.code, \
            "Verify that `git machete help` causes SystemExit with " \
            f"{expected_exit_code} exit code."

        for command in long_docs:
            with pytest.raises(SystemExit) as e:
                self.launch_command("help", command)
            assert expected_exit_code == e.value.code, \
                f"Verify that `git machete help {command}` causes SystemExit" \
                f" with {expected_exit_code} exit code."

            with pytest.raises(SystemExit) as e:
                self.launch_command(command, "--help")
            assert expected_exit_code == e.value.code, \
                f"Verify that `git machete {command} --help` causes " \
                f"SystemExit with {expected_exit_code} exit code."
