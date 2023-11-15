from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_success, launch_command, mock_input_returning_y,
                      read_branch_layout_file, rewrite_branch_layout_file)


class TestPrune(BaseTest):

    def test_prune(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        (
            self.repo_sandbox.new_branch('main')
                .commit()
                .push()
                .new_branch('unmanaged')
                .commit()
                .push()
                .check_out('main')
                .new_branch('unpushed')
                .commit()
                .check_out('main')
                .new_branch('not_deleted_remotely')
                .commit()
                .push()
                .check_out('main')
                .new_branch('has_downstream')
                .commit()
                .push()
                .new_branch('downstream')
                .commit()
                .check_out('main')
                .new_branch('should_be_pruned')
                .commit()
                .push()
                .delete_remote_branch('origin/should_be_pruned')
                .check_out('main')
        )

        body: str = \
            """
            main
                unpushed
                not_deleted_remotely
                has_downstream
                    downstream
                should_be_pruned
            """
        rewrite_branch_layout_file(body)

        launch_command('prune')

        assert read_branch_layout_file() == "main\n    unpushed\n    not_deleted_remotely\n    has_downstream\n        downstream\n"

        expected_status_output = (
            """
              main *
              |
              o-unpushed (untracked)
              |
              o-not_deleted_remotely
              |
              o-has_downstream
                |
                o-downstream (untracked)
            """
        )
        assert_success(['status'], expected_status_output)

        branches = self.repo_sandbox.get_local_branches()
        assert 'unmanaged' in branches
        assert 'unpushed' in branches
        assert 'not_deleted_remotely' in branches
        assert 'has_downstream' in branches
        assert 'sould_be_pruned' not in branches
