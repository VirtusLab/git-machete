from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_success, launch_command, mock_input_returning_y,
                      mock_run_cmd_and_discard_output, rewrite_definition_file)


class TestClean(BaseTest):

    def test_clean(self, mocker: MockerFixture) -> None:
        mocker.patch('builtins.input', mock_input_returning_y)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
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
            Warning: sliding invalid branches: bar2, foo2, moo2, mars out of the definition file
              master *
              |
              o-bar (untracked)
              |
              o-foo
              |
              o-moo (untracked)
            """
        )
        assert_success(['status'], expected_status_output)

        branches = self.repo_sandbox.get_local_branches()
        assert 'foo' in branches
        assert 'mars' not in branches
