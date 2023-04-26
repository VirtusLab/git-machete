from typing import Any

from .base_test import BaseTest
from .mockers import assert_command, mock_run_cmd, rewrite_definition_file


class TestAdd(BaseTest):

    def test_add(self, mocker: Any) -> None:
        """
        Verify the behaviour of a 'git machete add' command.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("master")
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
        rewrite_definition_file(body)

        self.repo_sandbox.new_branch("bugfix/feature_fail")

        # Test `git machete add` without providing the branch name
        assert_command(
            ['add', '-y'],
            'Adding bugfix/feature_fail onto the inferred upstream (parent) branch develop\n'
            'Added branch bugfix/feature_fail onto develop\n'
        )

        self.repo_sandbox.check_out('develop')
        self.repo_sandbox.new_branch("bugfix/some_feature")
        assert_command(
            ['add', '-y', 'bugfix/some_feature'],
            'Adding bugfix/some_feature onto the inferred upstream (parent) branch develop\n'
            'Added branch bugfix/some_feature onto develop\n'
        )

        self.repo_sandbox.check_out('develop')
        self.repo_sandbox.new_branch("bugfix/another_feature")
        assert_command(
            ['add', '-y', 'refs/heads/bugfix/another_feature'],
            'Adding bugfix/another_feature onto the inferred upstream (parent) branch develop\n'
            'Added branch bugfix/another_feature onto develop\n'
        )

        # test with --onto option
        self.repo_sandbox.new_branch("chore/remove_indentation")

        assert_command(
            ['add', '--onto=feature'],
            'Added branch chore/remove_indentation onto feature\n'
        )

    def test_add_check_out_remote_branch(self, mocker: Any) -> None:
        """
        Verify the behaviour of a 'git machete add' command in the special case when a remote branch is checked out locally.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("master")
            .commit("master commit.")
            .new_branch("feature/foo")
            .push()
            .check_out("master")
            .delete_branch("feature/foo")
        )

        assert_command(
            ['add', '-y', 'foo'],
            'A local branch foo does not exist. Creating out of the current HEAD\n'
            'Added branch foo as a new root\n'
        )

        assert_command(
            ['add', '-y', '--as-root', 'feature/foo'],
            'A local branch feature/foo does not exist, but a remote branch origin/feature/foo exists.\n'
            'Checking out feature/foo locally...\n'
            'Added branch feature/foo as a new root\n'
        )
