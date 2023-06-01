from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_success, fixed_author_and_committer_date,
                      launch_command, mock_input_returning,
                      mock_run_cmd_and_forward_output, rewrite_definition_file)


class TestDeleteUnmanaged(BaseTest):

    def test_delete_unmanaged(self, mocker: MockerFixture) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_forward_output)

        with fixed_author_and_committer_date():
            (
                self.repo_sandbox.new_branch("master")
                    .commit("master commit.")
                    .new_branch("develop")
                    .commit("develop commit.")
                    .new_branch("feature")
                    .commit("feature commit.")
            )
        body: str = \
            """
            master
            """
        rewrite_definition_file(body)

        mocker.patch("builtins.input", mock_input_returning("q"))
        launch_command("delete-unmanaged")
        mocker.patch("builtins.input", mock_input_returning("n"))
        launch_command("delete-unmanaged")
        mocker.patch("builtins.input", mock_input_returning("y"))
        assert_success(
            ["delete-unmanaged"],
            """
            Checking for unmanaged branches...
            Skipping current branch feature
            Delete branch develop (merged to HEAD)? (y, N, q) 
            Deleted branch develop (was 03e727b).

            """
        )

        self.repo_sandbox.check_out("master")
        mocker.patch("builtins.input", mock_input_returning("q"))
        launch_command("delete-unmanaged")
        mocker.patch("builtins.input", mock_input_returning("n"))
        launch_command("delete-unmanaged")
        assert_success(
            ["delete-unmanaged", "--yes"],
            """
            Checking for unmanaged branches...
            Deleting branch feature (unmerged to HEAD)...
            Deleted branch feature (was 87e00e9).

            """
        )

        assert_success(
            ["delete-unmanaged", "-y"],
            """
            Checking for unmanaged branches...
            No branches to delete
            """
        )

        self.repo_sandbox.new_branch("foo").check_out("master")
        mocker.patch("builtins.input", mock_input_returning("n"))
        launch_command("delete-unmanaged")
        assert self.repo_sandbox.get_local_branches() == ["foo", "master"]
