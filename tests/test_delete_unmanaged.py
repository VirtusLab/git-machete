from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_success, fixed_author_and_committer_date_in_past,
                      launch_command, mock__run_cmd_and_forward_stdout,
                      mock_input_returning, rewrite_branch_layout_file)


class TestDeleteUnmanaged(BaseTest):

    def test_delete_unmanaged(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.utils._run_cmd', mock__run_cmd_and_forward_stdout)

        with fixed_author_and_committer_date_in_past():
            (
                self.repo_sandbox.new_branch("master")
                    .commit()
                    .new_branch("develop")
                    .commit()
                    .push()
                    .amend_commit("Different commit message")
                    .add_file_and_commit()
                    .new_branch("refactor")
                    .commit()
                    .new_branch("feature")
                    .commit()
                    .check_out("develop")
                    .new_branch("bugfix")
                    .commit()
                    .check_out("feature")
            )
        body: str = \
            """
            master
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("q"))
        launch_command("delete-unmanaged", "-v")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n", "n", "n"))
        launch_command("delete-unmanaged")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("y", "y", "y"))
        assert_success(
            ["delete-unmanaged"],
            """
            Checking for unmanaged branches...
            Skipping current branch feature
            Delete branch bugfix (unmerged to HEAD)? (y, N, q)
            Deleted branch bugfix (was 4e4943a).
            Delete branch develop (merged to HEAD, but not merged to origin/develop)? (y, N, q)
            Deleted branch develop (was 02df5cb).
            Delete branch refactor (merged to HEAD)? (y, N, q)
            Deleted branch refactor (was 73f2ac5).
            """
        )

        self.repo_sandbox.check_out("master")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("q"))
        launch_command("delete-unmanaged")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        launch_command("delete-unmanaged")
        assert_success(
            ["delete-unmanaged", "--yes"],
            """
            Checking for unmanaged branches...
            Deleting branch feature...
            Deleted branch feature (was a18c571).
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
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        launch_command("delete-unmanaged")
        assert self.repo_sandbox.get_local_branches() == ["foo", "master"]

    def test_delete_unmanaged_for_squash_merged_branch(self, mocker: MockerFixture) -> None:
        (
            self.repo_sandbox
            .new_branch("master")
            .remove_remote("origin")
            .commit("master first commit")
            .new_branch("feature")
            .commit("feature commit")
            .check_out("master")
            .commit("extra commit")
            .execute("git merge --squash feature")
            .execute("git commit -m squashed")
        )

        rewrite_branch_layout_file("master")

        # Here the simple method will not detect the squash merge, as there are commits in master before we merged feature so
        # there's no tree hash in master that matches the tree hash of feature
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        assert_success(['delete-unmanaged'],
                       "Checking for unmanaged branches...\n"
                       "Delete branch feature (unmerged to HEAD)? (y, N, q)\n")

        self.repo_sandbox.set_git_config_key('machete.squashMergeDetection', 'exact')
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        assert_success(['delete-unmanaged'],
                       "Checking for unmanaged branches...\n"
                       "Delete branch feature (merged to HEAD)? (y, N, q)\n")
