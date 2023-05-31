from typing import Any

import pytest

from git_machete.exceptions import ExitCode

from .base_test import BaseTest
from .mockers import (assert_success, launch_command,
                      mock_run_cmd_and_discard_output, rewrite_definition_file)


class TestList(BaseTest):

    def test_list(self, mocker: Any) -> None:
        """
        Verify behaviour of a 'git machete list' command.
        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

        (
            self.repo_sandbox.new_branch("master")
                .commit("master commit.")
                .new_branch("develop")
                .commit("develop commit.")
                .new_branch("feature_0")
                .commit("feature_0 commit.")
                .new_branch("feature_0_0")
                .commit("feature_0_0 commit.")
                .new_branch("feature_0_0_0")
                .commit("feature_0_0_0 commit.")
                .check_out("feature_0")
                .new_branch("feature_0_1")
                .commit("feature_0_1 commit.")
                .check_out("develop")
                .new_branch("feature_1")
                .commit("feature_1 commit.")
        )

        body: str = \
            """
            master
            develop
              feature_0
                feature_0_0
                  feature_0_0_0
                feature_0_1
              feature_1
            """
        rewrite_definition_file(body)

        (
            self.repo_sandbox
                .check_out("develop")
                .new_branch("feature_2")
                .commit("feature_2 commit.")
                .new_branch("feature_3")
                .push()
                .check_out("feature_2")
                .delete_branch("feature_3")
        )

        expected_output = """
        master
        develop
        feature_0
        feature_0_0
        feature_0_0_0
        feature_0_1
        feature_1
        """
        assert_success(
            ['list', 'managed'],
            expected_output
        )

        expected_output = """
        feature_2
        feature_3
        """
        assert_success(
            ['list', 'addable'],
            expected_output
        )

        expected_output = """
        master
        feature_0_0_0
        feature_0_1
        feature_1
        """
        assert_success(
            ['list', 'childless'],
            expected_output
        )

        expected_output = """
        feature_0
        feature_0_0
        feature_0_0_0
        feature_0_1
        feature_1
        """
        assert_success(
            ['list', 'slidable'],
            expected_output
        )

        assert_success(
            ['list', 'slidable-after', 'feature_0_0'],
            "feature_0_0_0\n"
        )
        assert_success(
            ['list', 'slidable-after', 'develop'],
            ""
        )
        assert_success(
            ['list', 'slidable-after', 'feature_0'],
            ""
        )

        assert_success(
            ['list', 'unmanaged'],
            "feature_2\n"
        )

        self.repo_sandbox.check_out("feature_1")
        launch_command('fork-point', '--override-to-inferred')
        assert_success(
            ['list', 'with-overridden-fork-point'],
            "feature_1\n"
        )

        launch_command('fork-point', '--unset-override')
        assert_success(
            ['list', 'with-overridden-fork-point'],
            ""
        )

        with pytest.raises(SystemExit) as e:
            launch_command('list', 'no-such-category')
        assert ExitCode.ARGUMENT_ERROR == e.value.code
