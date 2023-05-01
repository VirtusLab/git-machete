import os.path
from typing import Any

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, launch_command,
                      mock_input_returning, mock_run_cmd_and_discard_output,
                      overridden_environment, rewrite_definition_file)


class TestDiscover(BaseTest):

    def test_discover(self) -> None:
        (
            self.repo_sandbox
                .new_branch('master')
                .commit()
                .push()
                .new_branch('feature1')
                .commit()
                .new_branch('feature2')
                .commit()
                .check_out("master")
                .new_branch('feature3')
                .commit()
                .push()
                .new_branch('feature4')
                .commit()
        )

        body: str = \
            """
            master
            feature1
            feature2 annotation
            feature3 annotation rebase=no push=no
            """
        rewrite_definition_file(body)
        launch_command('discover', '-y')
        assert os.path.exists(".git/machete~")

        expected_status_output = (
            """
            master
            |
            o-feature1 (untracked)
            | |
            | o-feature2 (untracked)
            |
            o-feature3  rebase=no push=no
              |
              o-feature4 * (untracked)
            """
        )
        assert_success(['status'], expected_status_output)

        expected_discover_output = (
            """
            Discovered tree of branch dependencies:

              feature1 (untracked)
              |
              o-feature2 (untracked)

              master
              |
              o-feature3  rebase=no push=no
                |
                o-feature4 * (untracked)

            Saving the above tree to .git/machete...
            The existing definition file will be backed up as .git/machete~
            """
        )
        assert_success(['discover', '--roots=feature1,master', '-y'], expected_discover_output)

        assert_failure(['discover', '--roots=feature1,lolxd'], "lolxd is not a local branch")

    def test_discover_main_branch_and_edit(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

        (
            self.repo_sandbox
            .remove_remote()
            .new_branch('feature1')
            .commit()
            .new_branch('main')
            .commit()
            .new_branch('feature2')
            .commit()
        )

        expected_status_output = (
            """
            Discovered tree of branch dependencies:

              main
              |
              o-feature2 *

              feature1

            Save the above tree to .git/machete?
            The existing definition file will be backed up as .git/machete~ (y, e[dit], N) 
            """
        )

        mocker.patch('builtins.input', mock_input_returning('e'))
        with overridden_environment(GIT_MACHETE_EDITOR='cat'):
            assert_success(['discover'], expected_status_output)

        assert_success(
            ['status'],
            """
            main
            |
            o-feature2 *

            feature1
            """
        )
