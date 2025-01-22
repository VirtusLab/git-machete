import pytest

from .base_test import BaseTest
from .mockers import launch_command, rewrite_branch_layout_file
from .mockers_git_repo_sandbox import GitRepositorySandbox


class TestIsManaged(BaseTest):

    def test_is_managed(self) -> None:
        """
        Verify behaviour of a 'git machete is-managed' command.
        """
        (
            GitRepositorySandbox()
            .new_branch("master")
            .commit("master commit.")
            .new_branch("develop")
            .commit("develop commit.")
            .new_branch("feature")
            .commit("feature commit.")
            .check_out("develop")
            .commit("New commit on develop")
        )
        body: str = \
            """
            master
            develop
                feature
            """
        rewrite_branch_layout_file(body)

        # Test `git machete is-managed` without providing the branch name
        launch_command('is-managed')

        launch_command('is-managed', 'develop')

        launch_command('is-managed', 'refs/heads/develop')

        with pytest.raises(SystemExit):
            launch_command('is-managed', 'random_branch_name')
