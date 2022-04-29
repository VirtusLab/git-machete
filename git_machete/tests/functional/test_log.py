import io
import re
import subprocess
import sys
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Dict
from unittest import mock

from git_machete import cli
from git_machete.tests.functional.commons import (GitRepositorySandbox,
                                                  get_current_commit_hash, git)
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

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd_and_forward_stdout)
    def test_log(self) -> None:
        self.repo_sandbox.new_branch('root')
        self.repo_sandbox.commit()
        roots_only_commit_hash = get_current_commit_hash()

        self.repo_sandbox.new_branch('child')
        self.repo_sandbox.commit()
        childs_first_commit_hash = get_current_commit_hash()
        self.repo_sandbox.commit()
        childs_second_commit_hash = get_current_commit_hash()

        log_content = self.launch_command('log')

        assert childs_first_commit_hash in log_content, \
            "Verify that oldest commit from current branch is visible when " \
            "executing `git machete log`."
        assert childs_second_commit_hash in log_content, \
            "Verify that youngest commit from current branch is visible when " \
            "executing `git machete log`."
        assert roots_only_commit_hash not in log_content, \
            "Verify that commits from parent branch are not visible when " \
            "executing `git machete log`."
