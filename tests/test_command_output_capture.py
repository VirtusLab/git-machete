import io
import os
import sys
import textwrap
from typing import Any

from .mockers import (adapt, GitRepositorySandbox, assert_command, launch_command,
                      launch_command1, mock_run_cmd)


class TestCommandOutputCapture:

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

    def test(self, mocker: Any) -> None:
        """
        Verify behaviour of a 'git machete diff' command.
        """
        (
            self.repo_sandbox.new_branch("master")
                .add_file_with_content_and_commit(message='master commit1')
                .push()
                .new_branch("develop")
                .add_file_with_content_and_commit(file_name='develop_file_name.txt', file_content='Develop content', message='develop commit')
                .push()
        )

        launch_command("discover", "-y")

        self.repo_sandbox.new_branch("bugfix/feature_fail")

        no_output_cmds = []
        if launch_command('add', '-y', 'bugfix/feature_fail') == '':
            no_output_cmds.append('add')

        if launch_command('diff', 'develop') == '':
            no_output_cmds.append('diff')

        if launch_command('log') == '':
            no_output_cmds.append('log')

        print('cmds with no output: ', no_output_cmds)
