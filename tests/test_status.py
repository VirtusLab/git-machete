import os
from tempfile import mkdtemp
from typing import Any

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, launch_command,
                      mock_run_cmd_and_discard_output, rewrite_definition_file)


class TestStatus(BaseTest):

    def test_branch_reappears_in_definition(self) -> None:

        body: str = \
            """
            master
            \tdevelop
            \t\n
            develop
            """
        rewrite_definition_file(body)

        expected_error_message: str = '.git/machete, line 6: branch develop re-appears in the tree definition. ' \
                                      'Edit the definition file manually with git machete edit'
        assert_failure(['status'], expected_error_message)

    def test_indent_not_multiply_of_base_indent(self) -> None:
        body: str = \
            """
            master
            \tdevelop
            \t foo
            """
        rewrite_definition_file(body)

        expected_error_message: str = '.git/machete, line 4: invalid indent <TAB><SPACE>, expected a multiply of <TAB>. ' \
                                      'Edit the definition file manually with git machete edit'
        assert_failure(['status'], expected_error_message)

    def test_indent_too_deep(self) -> None:
        body: str = \
            """
            master
            \tdevelop
            \t\t\tfoo
            """
        rewrite_definition_file(body)

        expected_error_message: str = '.git/machete, line 4: too much indent (level 3, expected at most 2) for the branch foo. ' \
                                      'Edit the definition file manually with git machete edit'
        assert_failure(['status'], expected_error_message)

    def test_status_branch_hook_output(self) -> None:
        (
            self.repo_sandbox
            .remove_remote()
            .new_branch('master')
            .commit('master commit')
            .new_branch('develop')
            .commit('develop commit')
        )

        body: str = \
            """
            master
              develop
            """
        rewrite_definition_file(body)

        self.repo_sandbox.write_to_file(".git/hooks/machete-status-branch", "#!/bin/sh\ngit ls-tree $1 | wc -l | sed 's/ *//'")
        assert_success(
            ["status"],
            """
            hint: The '.git/hooks/machete-status-branch' hook was ignored because it's not set as executable.
            hint: You can disable this warning with `git config advice.ignoredHook false`.
              master
              |
              o-develop *
            """
        )

        self.repo_sandbox.set_git_config_key("advice.ignoredHook", "false")
        assert_success(
            ["status"],
            """
            master
            |
            o-develop *
            """
        )

        self.repo_sandbox.set_file_executable(".git/hooks/machete-status-branch")
        assert_success(
            ["status"],
            """
            master  1
            |
            o-develop *  2
            """
        )

        self.repo_sandbox.write_to_file(".git/hooks/machete-status-branch", "#!/bin/sh\necho '    '")
        assert_success(
            ["status"],
            """
            master
            |
            o-develop *
            """
        )

        self.repo_sandbox.write_to_file(".git/hooks/machete-status-branch", "#!/bin/sh\nexit 1")
        assert_success(
            ["status"],
            """
            master
            |
            o-develop *
            """
        )

    def test_extra_space_before_branch_name(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

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
                .set_git_config_key('machete.status.extraSpaceBeforeBranchName', 'true')
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
        assert_success(['status'], expected_status_output)

        self.repo_sandbox.set_git_config_key('machete.status.extraSpaceBeforeBranchName', 'false')

        expected_status_output = (
            """
            master
            |
            o-bar
              |
              o-foo *
            """
        )
        assert_success(['status'], expected_status_output)

    def test_squashed_branch_recognized_as_merged(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

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

        assert_success(
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
        assert_success(
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
        assert_success(
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

        assert_success(
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
        assert_success(
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

        assert_success(
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
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

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
        assert_success(['status'], expected_status_output)

    def test_status_when_child_branch_is_pushed_immediately_after_creation(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

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
        assert_success(['status'], expected_status_output)

    def test_status_fork_point_without_reflogs(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

        (
            self.repo_sandbox
            .remove_remote()
            .new_branch("master")
            .commit()
            .new_branch("develop")
            .commit()
            .check_out("master")
            .commit()
        )
        body: str = \
            """
            master
                develop
            """
        rewrite_definition_file(body)

        self.repo_sandbox.remove_file(".git/logs/")

        expected_status_output = (
            """
            master *
            |
            | Some commit message.
            x-develop
            """
        )
        assert_success(['status', '-l'], expected_status_output)
