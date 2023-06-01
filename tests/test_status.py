import os
import re
import sys
import textwrap
from tempfile import mkdtemp

import pytest
from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success,
                      fixed_author_and_committer_date, launch_command,
                      mock_input_returning, mock_input_returning_y,
                      mock_run_cmd_and_discard_output, overridden_environment,
                      rewrite_definition_file)


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

    def test_single_invalid_branch_interactive_slide_out(self, mocker: MockerFixture) -> None:
        mocker.patch("git_machete.client.MacheteClient.is_stdout_a_tty", lambda: True)

        (
            self.repo_sandbox
            .remove_remote()
            .new_branch('master')
            .commit()
        )
        body: str = \
            """
            master
            \t\tfoo
            """
        rewrite_definition_file(body)
        expected_output = """
            Skipping foo which is not a local branch (perhaps it has been deleted?).
            Slide it out from the definition file? (y, e[dit], N) 
              master *
        """

        mocker.patch("builtins.input", mock_input_returning(""))
        assert_success(["status"], expected_output)

        mocker.patch("builtins.input", mock_input_returning("e"))
        self.repo_sandbox.set_git_config_key("advice.macheteEditorSelection", "false")
        with overridden_environment(GIT_EDITOR="sed -i.bak '/foo/ d'"):
            assert_success(["status"], expected_output)

    def test_multiple_invalid_branches_interactive_slide_out(self, mocker: MockerFixture) -> None:
        mocker.patch("git_machete.client.MacheteClient.is_stdout_a_tty", lambda: True)

        (
            self.repo_sandbox
            .remove_remote()
            .new_branch('master')
            .commit()
            .new_branch('develop')
            .commit()
            .new_branch('feature')
            .commit()
        )
        body: str = \
            """
            master
            \t\tfoo
            \t\t\t\tbar  PR #1
            \t\tqux
            \t\t\t\tdevelop
            baz
            \t\tfeature
            """
        rewrite_definition_file(body)
        expected_output = """
            Skipping foo, bar, qux, baz which are not local branches (perhaps they have been deleted?).
            Slide them out from the definition file? (y, e[dit], N) 
              master
              |
              o-develop

              feature *
        """
        mocker.patch("builtins.input", mock_input_returning_y)
        assert_success(["status"], expected_output)

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows doesn't distinguish between executable and non-executable files")
    def test_status_advice_ignored_non_executable_hook(self) -> None:
        (
            self.repo_sandbox
            .remove_remote()
            .new_branch('master')
            .commit()
            .new_branch('develop')
            .commit()
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

    def test_status_branch_hook_output(self) -> None:
        (
            self.repo_sandbox
            .remove_remote()
            .new_branch('master')
            .commit()
            .new_branch('develop')
            .commit()
        )

        body: str = \
            """
            master

              develop
            """
        rewrite_definition_file(body)

        self.repo_sandbox.write_to_file(".git/hooks/machete-status-branch", "#!/bin/sh\ngit ls-tree $1 | wc -l | sed 's/ *//'")
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

    def test_extra_space_before_branch_name(self, mocker: MockerFixture) -> None:
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

    def test_squashed_branch_recognized_as_merged(self, mocker: MockerFixture) -> None:
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

    def test_inferring_counterpart_for_fetching_of_branch(self, mocker: MockerFixture) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)

        origin_1_remote_path = mkdtemp()
        self.repo_sandbox.new_repo(origin_1_remote_path, bare=True)

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

    def test_status_when_child_branch_is_pushed_immediately_after_creation(self, mocker: MockerFixture) -> None:
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

    def test_status_fork_point_without_reflogs(self, mocker: MockerFixture) -> None:
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

    def test_status_yellow_edges(self) -> None:
        with fixed_author_and_committer_date():
            (
                self.repo_sandbox
                .remove_remote()
                .new_branch("master")
                .commit()
                .new_branch("develop")
                .commit()
                .new_branch("feature-1")
                .commit()
                .check_out("develop")
                .new_branch("feature-2")
                .commit()
            )
        body: str = \
            """
            master
                feature-1
                feature-2
            """
        rewrite_definition_file(body)

        expected_status_output = (
            """
              master
              |
              ?-feature-1
              |
              ?-feature-2 *

            Warn: yellow edges indicate that fork points for feature-1, feature-2 are probably incorrectly inferred,
            or that some extra branch should be added between each of these branches and its parent.

            Run git machete status --list-commits or git machete status --list-commits-with-hashes to see more details.
            """
        )
        assert_success(['status'], expected_status_output)

        expected_status_output = (
            """
              master
              |
              | Some commit message. -> fork point ??? commit dcd2db5 seems to be a part of the unique history of develop
              | Some commit message.
              ?-feature-1
              |
              | Some commit message. -> fork point ??? commit dcd2db5 seems to be a part of the unique history of develop
              | Some commit message.
              ?-feature-2 *

            Warn: yellow edges indicate that fork points for feature-1, feature-2 are probably incorrectly inferred,
            or that some extra branch should be added between each of these branches and its parent.

            Consider using git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent <branch> for each affected branch,
            or reattaching the affected branches under different parent branches.
            """  # noqa: E501
        )
        assert_success(['status', '-l'], expected_status_output)

    def test_status_non_ascii_junctions(self) -> None:
        (
            self.repo_sandbox
            .remove_remote()
            .new_branch("develop")
            .commit()
            .new_branch("feature-1")
            .commit()
            .check_out("develop")
            .new_branch("feature-2")
            .commit()
        )

        body: str = \
            """
            develop
                feature-1
                feature-2
            """
        rewrite_definition_file(body)

        expected_status_output = (
            """\
              develop
              │
              ├─feature-1
              │
              └─feature-2
            """
        )
        raw_output = launch_command('status', '--color=always')
        assert textwrap.dedent(re.sub('\x1b\\[[^m]+m', '', raw_output)) == textwrap.dedent(expected_status_output)

    def test_status_during_rebase(self) -> None:
        (
            self.repo_sandbox
            .remove_remote()
            .new_branch("master")
            .commit()
            .new_branch("develop")
            .commit()
        )

        body: str = \
            """
            master
                develop
            """
        rewrite_definition_file(body)

        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '1s/^pick /edit /'"):
            launch_command("update")

        expected_status_output = (
            """
            master
            |
            | Some commit message.
            o-REBASING develop *
            """
        )
        assert_success(['status', '-l'], expected_status_output)

    def test_status_during_side_effecting_operations(self) -> None:
        (
            self.repo_sandbox
            .remove_remote()
            .new_branch("master")
            .commit()
            .new_branch("develop")
            .add_file_and_commit("1.txt", "some-content")
            .check_out("master")
            .new_branch("feature")
            .add_file_and_commit("1.txt", "some-other-content")
            .check_out("develop")
        )

        body: str = \
            """
            master
                develop
            """
        rewrite_definition_file(body)

        # AM

        patch_path = self.repo_sandbox.popen("git format-patch feature")
        self.repo_sandbox.execute_ignoring_exit_code(f"git am {patch_path}")

        expected_status_output = (
            """
            master
            |
            | Some commit message.
            o-GIT AM IN PROGRESS develop *
            """
        )
        assert_success(['status', '-l'], expected_status_output)

        self.repo_sandbox.execute("git am --abort")

        # CHERRY-PICK

        self.repo_sandbox.execute_ignoring_exit_code("git cherry-pick feature")

        expected_status_output = (
            """
            master
            |
            | Some commit message.
            o-CHERRY-PICKING develop *
            """
        )
        assert_success(['status', '-l'], expected_status_output)

        self.repo_sandbox.execute("git cherry-pick --abort")

        # MERGE

        self.repo_sandbox.execute_ignoring_exit_code("git merge feature")

        expected_status_output = (
            """
            master
            |
            | Some commit message.
            o-MERGING develop *
            """
        )
        assert_success(['status', '-l'], expected_status_output)

        self.repo_sandbox.execute("git merge --abort")

        # REVERT

        self.repo_sandbox.execute("git revert --no-commit HEAD")

        expected_status_output = (
            """
            master
            |
            | Some commit message.
            o-REVERTING develop *
            """
        )
        assert_success(['status', '-l'], expected_status_output)

        self.repo_sandbox.execute("git revert --abort")
