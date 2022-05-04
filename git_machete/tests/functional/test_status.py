import sys
from typing import Any, Optional

import pytest  # type: ignore
from git_machete.exceptions import MacheteException
from git_machete.tests.functional.commons import (GitRepositorySandbox,
                                                  launch_command, mock_run_cmd,
                                                  rewrite_definition_file)


def mock_exit_script(status_code: Optional[int] = None, error: Optional[BaseException] = None) -> None:
    if error:
        raise error
    else:
        sys.exit(status_code)


class TestMachete:

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
            assert e.value.parameter == expected_error_message, 'Verify that expected error message has appeared a branch re-appears in tree definition.'
