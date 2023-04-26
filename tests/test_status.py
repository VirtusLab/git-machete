import os
from tempfile import mkdtemp
from typing import Any

import pytest

from git_machete.exceptions import MacheteException

from .base_test import BaseTest
from .mockers import (assert_command, launch_command, mock_exit_script,
                      mock_run_cmd, rewrite_definition_file)


class TestStatus(BaseTest):

    def test_branch_reappears_in_definition(self, mocker: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        body: str = \
            """master
            \tdevelop
            \t\n
            develop
            """

        self.repo_sandbox.new_branch("root")
        rewrite_definition_file(body)

        expected_error_message: str = '.git/machete, line 5: branch develop re-appears in the tree definition. ' \
                                      'Edit the definition file manually with git machete edit'

        with pytest.raises(MacheteException) as e:
            launch_command('status')
        if e:
            assert e.value.parameter == expected_error_message, \
                'Verify that expected error message has appeared if a branch re-appears in tree definition.'

    def test_extra_space_before_branch_name(self, mocker: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox
                .new_branch('master')
                .commit()
                .push()
                .new_branch('bar')
                .commit()
                .push()
                .new_branch('foo')
                .commit()
                .push()
                .add_git_config_key('machete.status.extraSpaceBeforeBranchName', 'true')
        )
        body: str = \
            """
            master
                bar
                    foo
            """
        rewrite_definition_file(body)

        expected_status_output = (
            """
            master
            |
            o- bar
               |
               o- foo *
            """
        )
        assert_command(['status'], expected_status_output)

        self.repo_sandbox.add_git_config_key('machete.status.extraSpaceBeforeBranchName', 'false')

        expected_status_output = (
            """
            master
            |
            o-bar
              |
              o-foo *
            """
        )
        assert_command(['status'], expected_status_output)

    def test_squashed_branch_recognized_as_merged(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("root")
            .commit("root")
            .push()
            .new_branch("develop")
            .commit("develop")
            .push()
            .new_branch("feature")
            .commit("feature_1")
            .commit("feature_2")
            .push()
            .new_branch("child")
            .commit("child_1")
            .commit("child_2")
            .push()
        )

        body: str = \
            """
            root
                develop
                    feature
                        child
            """
        rewrite_definition_file(body)

        assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            o-develop
              |
              | feature_1
              | feature_2
              o-feature
                |
                | child_1
                | child_2
                o-child *
            """,
        )

        # squash-merge feature onto develop
        (
            self.repo_sandbox.check_out("develop")
            .execute("git merge --squash feature")
            .execute("git commit -m squash_feature")
            .check_out("child")
        )

        # in default mode, feature is detected as "m" (merged) into develop
        assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            | squash_feature
            o-develop (ahead of origin)
              |
              m-feature
                |
                | child_1
                | child_2
                o-child *
            """,
        )

        # but under --no-detect-squash-merges, feature is detected as "x" (behind) develop
        assert_command(
            ["status", "-l", "--no-detect-squash-merges"],
            """
            root
            |
            | develop
            | squash_feature
            o-develop (ahead of origin)
              |
              | feature_1
              | feature_2
              x-feature
                |
                | child_1
                | child_2
                o-child *
            """,
        )

        # traverse then slide out the feature branch
        launch_command("traverse", "-w", "-y")

        assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            | squash_feature
            o-develop
              |
              | child_1
              | child_2
              o-child *
            """,
        )

        # simulate an upstream squash-merge of the child branch
        (
            self.repo_sandbox.check_out("develop")
            .new_branch("upstream_squash")
            .execute("git merge --squash child")
            .execute("git commit -m squash_child")
            .execute("git push origin upstream_squash:develop")
            .check_out("child")
            .execute("git branch -D upstream_squash")
        )

        # status before fetch will show develop as out of date
        assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            | squash_feature
            o-develop (behind origin)
              |
              | child_1
              | child_2
              o-child *
            """,
        )

        # fetch-traverse will fetch upstream squash, detect, and slide out the child branch
        launch_command("traverse", "-W", "-y")

        assert_command(
            ["status", "-l"],
            """
            root
            |
            | develop
            | squash_feature
            | squash_child
            o-develop *
            """,
        )

    def test_inferring_counterpart_for_fetching_of_branch(self, mocker: Any) -> None:
        mocker.patch('git_machete.cli.exit_script', mock_exit_script)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        origin_1_remote_path = mkdtemp()
        self.repo_sandbox.new_repo(origin_1_remote_path)

        os.chdir(self.repo_sandbox.local_path)

        (
            self.repo_sandbox
                .add_remote('origin_1', origin_1_remote_path)
                .new_branch('master')
                .commit()
                .push()
                .new_branch('bar')
                .commit()
                .push()
                .new_branch('foo')
                .commit()
                .push(set_upstream=False)
                .push(remote='origin_1', set_upstream=False)
                .new_branch('snickers')
                .commit()
                .push(remote='origin_1', set_upstream=False)
                .new_branch('mars')
                .commit()
                .push()
                .push(remote='origin_1')
        )
        body: str = \
            """
            master
                bar
                    foo
                        snickers
                            mars
            """
        rewrite_definition_file(body)
        expected_status_output = (
            """
            master
            |
            o-bar
              |
              o-foo (untracked)
                |
                o-snickers
                  |
                  o-mars *
            """
        )
        assert_command(['status'], expected_status_output)

    def test_status_when_child_branch_is_pushed_immediately_after_creation(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("master")
            .commit("master")
            .push()
            .new_branch("foo")
            .commit("foo")
            .new_branch("bar")
            .push()
            .commit("bar")
        )
        body: str = \
            """
            master
                foo
                    bar
            """
        rewrite_definition_file(body)
        expected_status_output = (
            """
            master
            |
            o-foo (untracked)
              |
              o-bar * (ahead of origin)
            """
        )
        assert_command(['status'], expected_status_output)
