import subprocess
from typing import Any

import pytest

from .mockers import (GitRepositorySandbox, assert_command, launch_command,
                      mock_ask_if, mock_run_cmd,
                      mock_should_perform_interactive_slide_out,
                      rewrite_definition_file)


class TestClean:

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

    def test_clean(self, mocker: Any) -> None:
        mocker.patch(
            'git_machete.client.MacheteClient.should_perform_interactive_slide_out',
            mock_should_perform_interactive_slide_out,
        )
        mocker.patch('git_machete.client.MacheteClient.ask_if', mock_ask_if)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)
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
                .check_out("master")
                .new_branch('mars')
                .commit()
                .check_out("master")
        )

        body: str = \
            """
            master
                bar
                    bar2
                foo
                    foo2
                moo
                    moo2
                mars
            """
        rewrite_definition_file(body)

        launch_command('clean')

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
        assert_command(['status'], expected_status_output)

        with pytest.raises(subprocess.CalledProcessError):
            self.repo_sandbox.check_out("mars")
