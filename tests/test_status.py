from typing import Any

import pytest

from git_machete.exceptions import MacheteException

from .mockers import (assert_command, GitRepositorySandbox, launch_command, mock_exit_script,
                      mock_run_cmd, rewrite_definition_file)


class TestStatus:

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

    def test_branch_reappears_in_definition(self, mocker: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        body: str = \
            """master
            \tdevelop
            \t\n
            develop
            """

        self.repo_sandbox.new_branch("root")
        rewrite_definition_file(body)

        expected_error_message: str = '.git/machete, line 5: branch `develop` re-appears in the tree definition. ' \
                                      'Edit the definition file manually with `git machete edit`'

        with pytest.raises(MacheteException) as e:
            launch_command('status')
        if e:
            assert e.value.parameter == expected_error_message, \
                'Verify that expected error message has appeared if a branch re-appears in tree definition.'

    def test_extra_space_before_branch_name(self, mocker: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox
                .new_branch('master')
                .commit()
                .push()
                .new_branch('bar')
                .commit()
                .push()
                .new_branch('foo')
                .commit()
                .push()
                .add_git_config_key('machete.status.extraSpaceBeforeBranchName', 'true')
        )
        launch_command('discover', '-y')

        expected_status_output = (
"""   master
   |
   o- bar
      |
      o- foo *
"""  # noqa: E122
        )
        assert_command(['status'], expected_status_output.replace('|', '| ', 2), strip_indentation=False)

        self.repo_sandbox.add_git_config_key('machete.status.extraSpaceBeforeBranchName', 'false')

        expected_status_output = (
"""  master
 |
 o-bar
   |
   o-foo *
"""  # noqa: E122
        )
        assert_command(['status'], expected_status_output)
