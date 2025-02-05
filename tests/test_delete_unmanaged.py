from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_success, execute,
                      fixed_author_and_committer_date_in_past, launch_command,
                      mock__run_cmd_and_forward_stdout, mock_input_returning,
                      rewrite_branch_layout_file)
from .mockers_git_repository import (add_file_and_commit, amend_commit,
                                     check_out, commit, create_repo,
                                     create_repo_with_remote,
                                     get_local_branches, new_branch, push,
                                     set_git_config_key)


class TestDeleteUnmanaged(BaseTest):

    def test_delete_unmanaged(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.utils._run_cmd', mock__run_cmd_and_forward_stdout)

        create_repo_with_remote()
        with fixed_author_and_committer_date_in_past():
            new_branch("master")
            commit("0")
            new_branch("develop")
            commit("1")
            push()
            amend_commit("Different commit message")
            add_file_and_commit()
            new_branch("refactor")
            commit("2")
            new_branch("feature")
            commit("3")
            check_out("develop")
            new_branch("bugfix")
            commit("4")
            check_out("feature")

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
            Deleted branch bugfix (was 172d1a6).
            Delete branch develop (merged to HEAD, but not merged to origin/develop)? (y, N, q)
            Deleted branch develop (was d309888).
            Delete branch refactor (merged to HEAD)? (y, N, q)
            Deleted branch refactor (was 4d223ef).
            """
        )

        check_out("master")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("q"))
        launch_command("delete-unmanaged")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        launch_command("delete-unmanaged")
        assert_success(
            ["delete-unmanaged", "--yes"],
            """
            Checking for unmanaged branches...
            Deleting branch feature...
            Deleted branch feature (was b901dfd).
            """
        )

        assert_success(
            ["delete-unmanaged", "-y"],
            """
            Checking for unmanaged branches...
            No branches to delete
            """
        )

        new_branch("foo")
        check_out("master")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        launch_command("delete-unmanaged")
        assert get_local_branches() == ["foo", "master"]

    def test_delete_unmanaged_for_squash_merged_branch(self, mocker: MockerFixture) -> None:
        create_repo()
        new_branch("master")
        commit("master first commit")
        new_branch("feature")
        commit("feature commit")
        check_out("master")
        commit("extra commit")
        execute("git merge --squash feature")
        execute("git commit -m squashed")

        rewrite_branch_layout_file("master")

        # Here the simple method will not detect the squash merge, as there are commits in master before we merged feature so
        # there's no tree hash in master that matches the tree hash of feature
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        assert_success(['delete-unmanaged'],
                       "Checking for unmanaged branches...\n"
                       "Delete branch feature (unmerged to HEAD)? (y, N, q)\n")

        set_git_config_key('machete.squashMergeDetection', 'exact')
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n"))
        assert_success(['delete-unmanaged'],
                       "Checking for unmanaged branches...\n"
                       "Delete branch feature (merged to HEAD)? (y, N, q)\n")
