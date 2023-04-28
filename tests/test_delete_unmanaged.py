from .base_test import BaseTest
from .mockers import assert_command, rewrite_definition_file


class TestDeleteUnmanaged(BaseTest):

    def test_delete_unmanaged(self) -> None:
        """
        Verify behaviour of a 'git machete delete-unmanaged' command.
        """

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

        assert_command(
            ["delete-unmanaged", "--yes"],
            """
            Checking for unmanaged branches...
            Skipping current branch feature
            Deleting branch develop (merged to HEAD)
            """
        )

        self.repo_sandbox.check_out("master")
        assert_command(
            ["delete-unmanaged", "-y"],
            """
            Checking for unmanaged branches...
            Deleting branch feature (unmerged to HEAD)
            """
        )

        assert_command(
            ["delete-unmanaged", "-y"],
            """
            Checking for unmanaged branches...
            No branches to delete
            """
        )
