from typing import Any

import pytest

from .base_test import BaseTest
from .mockers import (get_commit_hash, get_current_commit_hash, launch_command,
                      mock_run_cmd, rewrite_definition_file)


class TestAdvance(BaseTest):

    def test_advance_for_no_downstream_branches(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete advance' command.

        Verify that 'git machete advance' raises an error when current branch
        has no downstream branches.

        """

        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("root")
                .commit()
        )
        body: str = "root"
        rewrite_definition_file(body)

        with pytest.raises(SystemExit):
            launch_command("advance")

    def test_advance_with_push_for_one_downstream_branch(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete advance' command.

        Verify that when there is only one, rebased downstream branch of a
        current branch 'git machete advance' merges commits from that branch,
        pushes the current branch and slides out child branches of the downstream branch.
        Also, it edits the git machete discovered tree to reflect new dependencies.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("root")
            .commit()
            .new_branch("level-1-branch")
            .commit()
        )
        body: str = \
            """
            root
                level-1-branch
            """
        rewrite_definition_file(body)
        level_1_commit_hash = get_current_commit_hash()

        self.repo_sandbox.check_out("root")
        self.repo_sandbox.push()
        launch_command("advance", "-y")

        root_commit_hash = get_current_commit_hash()
        origin_root_commit_hash = get_commit_hash("origin/root")

        assert level_1_commit_hash == root_commit_hash, \
            ("Verify that when there is only one, rebased downstream branch of a "
             "current branch, then 'git machete advance' merges commits from that branch "
             "and slides out child branches of the downstream branch.")
        assert root_commit_hash == origin_root_commit_hash, \
            ("Verify that when there is only one, rebased downstream branch of a "
             "current branch, and the current branch is tracked, "
             "then 'git machete advance' pushes the current branch.")
        assert "level-1-branch" not in launch_command("status"), \
            ("Verify that branch to which advance was performed is removed "
             "from the git-machete tree and the structure of the git machete "
             "tree is updated.")

    def test_advance_without_push_for_one_downstream_branch(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete advance' command.

        Verify that when there is only one, rebased downstream branch of a
        current branch 'git machete advance' merges commits from that branch
        and slides out child branches of the downstream branch.
        Also, it edits the git machete discovered tree to reflect new dependencies.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("root")
            .commit()
            .new_branch("level-1-branch")
            .commit()
        )

        body: str = \
            """
            root
                level-1-branch
            """
        rewrite_definition_file(body)
        level_1_commit_hash = get_current_commit_hash()

        self.repo_sandbox.check_out("root")
        launch_command("advance", "-y")

        root_commit_hash = get_current_commit_hash()

        assert level_1_commit_hash == root_commit_hash, \
            ("Verify that when there is only one, rebased downstream branch of a "
             "current branch, then 'git machete advance' merges commits from that branch "
             "and slides out child branches of the downstream branch.")
        assert "level-1-branch" not in launch_command("status"), \
            ("Verify that branch to which advance was performed is removed "
             "from the git-machete tree and the structure of the git machete "
             "tree is updated.")

    def test_advance_for_a_few_possible_downstream_branches_and_yes_option(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete advance' command.

        Verify that 'git machete advance -y' raises an error when current branch
        has more than one synchronized downstream branch and option '-y' is passed.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("root")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .check_out("root")
            .new_branch("level-1b-branch")
            .commit()
            .check_out("root")
        )

        body: str = \
            """
            root
                level-1a-branch
                level-1b-branch
            """
        rewrite_definition_file(body)

        with pytest.raises(SystemExit):
            launch_command("advance", '-y')
