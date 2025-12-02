

from git_machete.exceptions import ExitCode

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, launch_command,
                      launch_command_capturing_output_and_exception,
                      rewrite_branch_layout_file)
from .mockers_git_repository import (check_out, commit,
                                     create_repo_with_remote, delete_branch,
                                     new_branch, push)


class TestList(BaseTest):

    def test_list(self) -> None:
        """
        Verify behaviour of a 'git machete list' command.
        """

        create_repo_with_remote()
        new_branch("master")
        commit("master commit.")
        new_branch("develop")
        commit("develop commit.")
        new_branch("feature_0")
        commit("feature_0 commit.")
        new_branch("feature_0_0")
        commit("feature_0_0 commit.")
        new_branch("feature_0_0_0")
        commit("feature_0_0_0 commit.")
        check_out("feature_0")
        new_branch("feature_0_1")
        commit("feature_0_1 commit.")
        check_out("develop")
        new_branch("feature_1")
        commit("feature_1 commit.")

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
        rewrite_branch_layout_file(body)

        check_out("develop")
        new_branch("feature_2")
        commit("feature_2 commit.")
        new_branch("feature_3")
        push()
        check_out("feature_2")
        delete_branch("feature_3")

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
        master
        develop
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

        check_out("feature_1")
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

        output, e = launch_command_capturing_output_and_exception('list', 'no-such-category')
        assert type(e) is SystemExit
        assert e.code == ExitCode.ARGUMENT_ERROR

    def test_list_invalid_flag_combinations(self) -> None:
        assert_failure(["list", "slidable-after"], "git machete list slidable-after requires an extra <branch> argument")
        assert_failure(["list", "slidable", "some-branch"], "git machete list slidable does not expect extra arguments")
