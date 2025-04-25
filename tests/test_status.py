import re
import sys
import textwrap

import pytest
from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, execute,
                      execute_ignoring_exit_code,
                      fixed_author_and_committer_date_in_past, launch_command,
                      mock_input_returning, mock_input_returning_y,
                      overridden_environment, popen, remove_directory,
                      rewrite_branch_layout_file, set_file_executable,
                      write_to_file)
from .mockers_git_repository import (add_file_and_commit, add_remote,
                                     check_out, commit, commit_n_times,
                                     create_repo, create_repo_with_remote,
                                     delete_branch, delete_remote_branch,
                                     new_branch, new_orphan_branch, push,
                                     set_git_config_key, unset_git_config_key)


class TestStatus(BaseTest):

    def test_branch_reappears_in_branch_layout(self) -> None:

        body: str = \
            """
            master
            \tdevelop
            \t\n
            develop
            """
        rewrite_branch_layout_file(body)

        expected_error_message: str = '.git/machete, line 6: branch develop re-appears in the branch layout. ' \
                                      'Edit the branch layout file manually with git machete edit'
        assert_failure(['status'], expected_error_message)

    def test_indent_not_multiply_of_base_indent(self) -> None:
        body: str = \
            """
            master
            \tdevelop
            \t foo
            """
        rewrite_branch_layout_file(body)

        expected_error_message: str = '.git/machete, line 4: invalid indent <TAB><SPACE>, expected a multiply of <TAB>. ' \
                                      'Edit the branch layout file manually with git machete edit'
        assert_failure(['status'], expected_error_message)

    def test_indent_too_deep(self) -> None:
        body: str = \
            """
            master
            \tdevelop
            \t\t\tfoo
            """
        rewrite_branch_layout_file(body)

        expected_error_message: str = '.git/machete, line 4: too much indent (level 3, expected at most 2) for the branch foo. ' \
                                      'Edit the branch layout file manually with git machete edit'
        assert_failure(['status'], expected_error_message)

    def test_single_invalid_branch_interactive_slide_out(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, "git_machete.utils.is_stdout_a_tty", lambda: True)

        create_repo()
        new_branch('master')
        commit()

        body: str = \
            """
            master
            \t\tfoo
            """
        rewrite_branch_layout_file(body)
        expected_output = """
            Skipping foo which is not a local branch (perhaps it has been deleted?).
            Slide it out from the branch layout file? (y, e[dit], N)
              master *
        """

        self.patch_symbol(mocker, "builtins.input", mock_input_returning(""))
        assert_success(["status"], expected_output)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("e"))
        set_git_config_key("advice.macheteEditorSelection", "false")
        with overridden_environment(GIT_EDITOR="sed -i.bak '/foo/ d'"):
            assert_success(["status"], expected_output)

    def test_multiple_invalid_branches_interactive_slide_out(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, "git_machete.utils.is_stdout_a_tty", lambda: True)

        create_repo()
        new_branch('master')
        commit()
        new_branch('develop')
        commit()
        new_branch('feature')
        commit()

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
        rewrite_branch_layout_file(body)
        expected_output = """
            Skipping foo, bar, qux, baz which are not local branches (perhaps they have been deleted?).
            Slide them out from the branch layout file? (y, e[dit], N)
              master
              |
              o-develop

              feature *
        """
        self.patch_symbol(mocker, "builtins.input", mock_input_returning_y)
        assert_success(["status"], expected_output)

    def test_single_invalid_branch_non_interactive_slide_out(self) -> None:
        create_repo()
        new_branch('master')
        commit()

        body: str = \
            """
            master
            \t\tfoo
            """
        rewrite_branch_layout_file(body)
        expected_output = """
            Warning: sliding invalid branch foo out of the branch layout file
              master *
        """
        assert_success(["status"], expected_output)

    def test_multiple_invalid_branches_non_interactive_slide_out(self) -> None:
        create_repo()
        new_branch('master')
        commit()
        new_branch('develop')
        commit()
        new_branch('feature')
        commit()

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
        rewrite_branch_layout_file(body)
        expected_output = """
            Warning: sliding invalid branches foo, bar, qux, baz out of the branch layout file
              master
              |
              o-develop

              feature *
        """
        assert_success(["status"], expected_output)

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows doesn't distinguish between executable and non-executable files")
    def test_status_advice_ignored_non_executable_hook(self) -> None:
        create_repo()
        new_branch('master')
        commit()
        new_branch('develop')
        commit()

        body: str = \
            """
            master
              develop
            """
        rewrite_branch_layout_file(body)

        write_to_file(".git/hooks/machete-status-branch", "#!/bin/sh\ngit ls-tree $1 | wc -l | sed 's/ *//'")
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

        set_git_config_key("advice.ignoredHook", "false")
        assert_success(
            ["status"],
            """
            master
            |
            o-develop *
            """
        )

    def test_status_branch_hook_output(self) -> None:
        create_repo()
        new_branch('master')
        commit()
        new_branch('develop')
        commit()

        body: str = \
            """
            master

              develop
            """
        rewrite_branch_layout_file(body)

        write_to_file(".git/hooks/machete-status-branch", "#!/bin/sh\ngit ls-tree $1 | wc -l | sed 's/ *//'")
        set_file_executable(".git/hooks/machete-status-branch")
        assert_success(
            ["status"],
            """
            master  1
            |
            o-develop *  2
            """
        )

        write_to_file(".git/hooks/machete-status-branch", "#!/bin/sh\necho '    '")
        assert_success(
            ["status"],
            """
            master
            |
            o-develop *
            """
        )

        write_to_file(".git/hooks/machete-status-branch", "#!/bin/sh\nexit 1")
        assert_success(
            ["status"],
            """
            master
            |
            o-develop *
            """
        )

    def test_extra_space_before_branch_name(self) -> None:
        create_repo_with_remote()
        new_branch('master')
        commit()
        push()
        new_branch('bar')
        commit()
        push()
        new_branch('foo')
        commit()
        push()
        set_git_config_key('machete.status.extraSpaceBeforeBranchName', 'true')

        body: str = \
            """
            master
                bar
                    foo
            """
        rewrite_branch_layout_file(body)

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

        set_git_config_key('machete.status.extraSpaceBeforeBranchName', 'false')

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

    def test_status_squashed_branch_recognized_as_merged_with_traverse(self) -> None:

        create_repo_with_remote()
        new_branch("root")
        commit("root")
        push()
        new_branch("develop")
        commit("develop")
        push()
        new_branch("feature")
        commit("feature_1")
        commit("feature_2")
        push()
        new_branch("child")
        commit("child_1")
        commit("child_2")
        push()

        body: str = \
            """
            root
                develop
                    feature
                        child
            """
        rewrite_branch_layout_file(body)

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
        check_out("develop")
        execute("git merge --squash feature")
        execute("git commit -m squash_feature")
        check_out("child")

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

        # under --squash-merge-detection=none, feature is detected as "x" (out of sync) with develop
        expected_output_detection_none = """
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
            """
        assert_success(
            ["status", "-l", "--no-detect-squash-merges"],
            "          Warn: --no-detect-squash-merges is deprecated, "
            "use --squash-merge-detection=none instead\n" + expected_output_detection_none
        )
        assert_success(
            ["status", "-l", "--squash-merge-detection=none"],
            expected_output_detection_none
        )
        set_git_config_key('machete.squashMergeDetection', 'none')
        assert_success(
            ["status", "-l"],
            expected_output_detection_none
        )
        set_git_config_key('machete.squashMergeDetection', 'lolxd')
        assert_failure(
            ["status", "-l"],
            "Invalid value for machete.squashMergeDetection git config key: lolxd. Valid values are none, simple, exact"
        )
        unset_git_config_key('machete.squashMergeDetection')

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
        check_out("develop")
        new_branch("upstream_squash")
        execute("git merge --squash child")
        execute("git commit -m squash_child")
        execute("git push origin upstream_squash:develop")
        check_out("child")
        delete_branch("upstream_squash")

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

    def test_status_for_squash_merge_and_commits_in_between(self) -> None:
        create_repo()
        new_branch("master")
        commit("master first commit")
        new_branch("feature")
        commit("feature commit")
        check_out("master")
        commit("extra commit")
        execute("git merge --squash feature")
        execute("git commit -m squashed")

        body: str = \
            """
            master
                feature
            """
        rewrite_branch_layout_file(body)

        # Here the simple method will not detect the squash merge, as there are commits in master before we merged feature so
        # there's no tree hash in master that matches the tree hash of feature
        expected_status_output_simple = (
            """
            master *
            |
            x-feature
            """
        )
        assert_success(['status'], expected_status_output_simple)
        assert_success(['status', '--squash-merge-detection=simple'], expected_status_output_simple)
        expected_status_output_exact = (
            """
            master *
            |
            m-feature
            """
        )
        assert_success(['status', '--squash-merge-detection=exact'], expected_status_output_exact)
        set_git_config_key('machete.squashMergeDetection', 'exact')
        assert_success(['status'], expected_status_output_exact)

    def test_status_invalid_squash_merge_detection(self) -> None:
        assert_failure(["status", "--squash-merge-detection=invalid"],
                       "Invalid value for --squash-merge-detection flag: invalid. Valid values are none, simple, exact")
        assert_failure(["status", "--squash-merge-detection=none", "--squash-merge-detection=invalid"],
                       "Invalid value for --squash-merge-detection flag: invalid. Valid values are none, simple, exact")

    def test_status_inferring_counterpart_for_fetching_of_branch(self) -> None:
        create_repo_with_remote()
        origin_1_remote_path = create_repo("remote-1", bare=True, switch_dir_to_new_repo=False)
        add_remote('origin_1', origin_1_remote_path)
        new_branch('master')
        commit()
        push()
        new_branch('bar')
        commit()
        push()
        new_branch('foo')
        commit()
        push(set_upstream=False)
        push(remote='origin_1', set_upstream=False)
        new_branch('snickers')
        commit()
        push(remote='origin_1', set_upstream=False)
        new_branch('mars')
        commit_n_times(15)
        push()
        push(remote='origin_1')

        body: str = \
            """
            master
                bar
                    foo
                        snickers
                            mars
            """
        rewrite_branch_layout_file(body)
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

    def test_status_when_child_branch_is_pushed_immediately_after_creation(self) -> None:
        create_repo_with_remote()
        new_branch("master")
        commit("master")
        push()
        new_branch("foo")
        commit("foo")
        new_branch("bar")
        push()
        commit("bar")

        body: str = \
            """
            master
                foo
                    bar
            """
        rewrite_branch_layout_file(body)
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

    def test_status_fork_point_without_reflogs(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit("Develop commit.")
        check_out("master")
        commit()

        body: str = \
            """
            master
                develop
            """
        rewrite_branch_layout_file(body)

        remove_directory(".git/logs/")

        expected_status_output = (
            """
            master *
            |
            | Develop commit.
            x-develop
            """
        )
        assert_success(['status', '-l'], expected_status_output)

    def test_status_yellow_edges(self) -> None:
        with fixed_author_and_committer_date_in_past():
            create_repo()
            new_branch("master")
            commit("master commit")
            new_branch("develop")
            commit("develop commit")
            new_branch("feature-1")
            commit("feature-1 commit")
            check_out("develop")
            new_branch("feature-2")
            commit("feature-2 commit")

        body: str = \
            """
            master
                feature-1
                feature-2
            """
        rewrite_branch_layout_file(body)

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
              | develop commit -> fork point ??? commit 9c47c46 seems to be a part of the unique history of develop
              | feature-1 commit
              ?-feature-1
              |
              | develop commit -> fork point ??? commit 9c47c46 seems to be a part of the unique history of develop
              | feature-2 commit
              ?-feature-2 *

            Warn: yellow edges indicate that fork points for feature-1, feature-2 are probably incorrectly inferred,
            or that some extra branch should be added between each of these branches and its parent.

            Consider using git machete fork-point --override-to=<revision>|--override-to-inferred|--override-to-parent <branch> for each affected branch,
            or reattaching the affected branches under different parent branches.
            """  # noqa: E501
        )
        assert_success(['status', '-l'], expected_status_output)

    def test_status_non_ascii_junctions(self) -> None:
        create_repo()
        new_branch("develop")
        commit()
        new_branch("feature-1")
        commit()
        check_out("develop")
        new_branch("feature-2")
        commit()

        body: str = \
            """
            develop
                feature-1
                feature-2
            """
        rewrite_branch_layout_file(body)

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
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit("Develop commit.")

        body: str = \
            """
            master
                develop
            """
        rewrite_branch_layout_file(body)

        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '1s/^pick /edit /'"):
            launch_command("update")

        expected_status_output = (
            """
            master
            |
            | Develop commit.
            o-REBASING develop *
            """
        )
        assert_success(['status', '-l'], expected_status_output)

    def test_status_during_side_effecting_operations(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        add_file_and_commit("1.txt", "some-content")
        check_out("master")
        new_branch("feature")
        add_file_and_commit("1.txt", "some-other-content")
        check_out("develop")

        body: str = \
            """
            master
                develop
            """
        rewrite_branch_layout_file(body)

        # AM

        patch_path = popen("git format-patch feature")
        execute_ignoring_exit_code(f"git am {patch_path}")

        expected_status_output = (
            """
            master
            |
            | Some commit message.
            o-GIT AM IN PROGRESS develop *
            """
        )
        assert_success(['status', '-l'], expected_status_output)

        execute("git am --abort")

        # CHERRY-PICK

        execute_ignoring_exit_code("git cherry-pick feature")

        expected_status_output = (
            """
            master
            |
            | Some commit message.
            o-CHERRY-PICKING develop *
            """
        )
        assert_success(['status', '-l'], expected_status_output)

        execute("git cherry-pick --abort")

        # MERGE

        execute_ignoring_exit_code("git merge feature")

        expected_status_output = (
            """
            master
            |
            | Some commit message.
            o-MERGING develop *
            """
        )
        assert_success(['status', '-l'], expected_status_output)

        execute("git merge --abort")

        # REVERT

        execute("git revert --no-commit HEAD")

        expected_status_output = (
            """
            master
            |
            | Some commit message.
            o-REVERTING develop *
            """
        )
        assert_success(['status', '-l'], expected_status_output)

        execute("git revert --abort")

    def test_status_no_fork_point_for_child_branch(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        # This will cause that develop will not have a fork point.
        new_orphan_branch("develop")
        commit()

        body: str = \
            """
            master
                develop
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ["status", "-l"],
            """
            master
            |
            x-develop *
            """
        )

    def test_status_removed_from_remote(self) -> None:
        create_repo_with_remote()
        new_branch('main')
        commit()
        push()
        delete_remote_branch('origin/main')

        rewrite_branch_layout_file("main")
        assert_success(
            ["status"],
            "main * (untracked)\n"
        )
