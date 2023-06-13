import os.path
import re
import textwrap

from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, launch_command,
                      mock_input_returning, overridden_environment,
                      rewrite_definition_file)


class TestDiscover(BaseTest):

    def test_discover(self) -> None:
        assert_failure(['discover'], "No local branches found")

        (
            self.repo_sandbox
                .new_branch('master')
                .commit()
                .push()
                .new_branch('feature1')
                .commit()
                .new_branch('feature2')
                .commit()
                .check_out("master")
                .new_branch('feature3')
                .commit()
                .push()
                .new_branch('feature4')
                .commit()
        )

        body: str = \
            """
            master
            feature1
            feature2 annotation
            feature3 annotation rebase=no push=no
            """
        rewrite_definition_file(body)
        launch_command('discover', '-y')
        assert os.path.exists(".git/machete~")

        expected_status_output = (
            """
            master
            |
            o-feature1 (untracked)
            | |
            | o-feature2 (untracked)
            |
            o-feature3  rebase=no push=no
              |
              o-feature4 * (untracked)
            """
        )
        assert_success(['status'], expected_status_output)

        expected_discover_output = (
            """
            Discovered tree of branch dependencies:

              feature1 (untracked)
              |
              o-feature2 (untracked)

              master
              |
              o-feature3  rebase=no push=no
                |
                o-feature4 * (untracked)

            Saving the above tree to .git/machete...
            The existing definition file will be backed up as .git/machete~
            """
        )
        assert_success(['discover', '--roots=feature1,master', '-y'], expected_discover_output)

        assert_failure(['discover', '--roots=feature1,lolxd'], "lolxd is not a local branch")

    def test_discover_main_branch_and_edit(self, mocker: MockerFixture) -> None:

        (
            self.repo_sandbox
            .remove_remote()
            .new_branch('feature1')
            .commit()
            .new_branch('main')
            .commit()
            .new_branch('feature2')
            .commit()
        )

        expected_status_output = (
            """
            Discovered tree of branch dependencies:

              main
              |
              o-feature2 *

              feature1

            Save the above tree to .git/machete? (y, e[dit], N) 
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('e'))
        with overridden_environment(GIT_MACHETE_EDITOR='cat'):
            assert_success(['discover'], expected_status_output)

        assert_success(
            ['status'],
            """
            main
            |
            o-feature2 *

            feature1
            """
        )

    def test_discover_checked_out_since_in_future(self) -> None:
        (
            self.repo_sandbox
            .new_branch("root")
            .commit()
        )

        assert_success(
            ["discover", "--checked-out-since=tomorrow"],
            "Warn: no branches satisfying the criteria. "
            "Try moving the value of --checked-out-since further to the past.\n"
        )

    def test_discover_with_stale_branches(self) -> None:
        self.repo_sandbox.remove_remote().new_branch("develop").commit()
        for i in range(20):
            self.repo_sandbox.new_branch(f"branch-{i:02d}").commit()
        actual_output = launch_command("discover", "-y")
        assert re.sub("\\d{4}-\\d{2}-\\d{2}", "YYYY-MM-DD", actual_output, count=1) == textwrap.dedent(  # noqa: FS003
            "            Warn: to keep the size of the discovered tree reasonable (ca. 10 branches), "
            "only branches checked out at or after ca. YYYY-MM-DD are included.\n"
            "            Use git machete discover --checked-out-since=<date> (where <date> can be e.g. '2 weeks ago' or 2020-06-01) "
            "to change this threshold so that less or more branches are included.\n"
            """
            Discovered tree of branch dependencies:

              develop
              |
              ?-branch-10
                |
                o-branch-11
                  |
                  o-branch-12
                    |
                    o-branch-13
                      |
                      o-branch-14
                        |
                        o-branch-15
                          |
                          o-branch-16
                            |
                            o-branch-17
                              |
                              o-branch-18
                                |
                                o-branch-19 *

            Saving the above tree to .git/machete...
            """
        )

    def test_discover_with_merged_branches(self, mocker: MockerFixture) -> None:
        (
            self.repo_sandbox
            .remove_remote()
            .new_branch("master")
            .commit()
            .new_branch("feature1")
            .commit()
            .check_out("master")
            .new_branch("feature2")
            .commit()
            .check_out("master")
            .execute("git merge --ff-only feature1")
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('n'))
        launch_command("discover")
        assert self.repo_sandbox.read_file(".git/machete") == ""

        rewrite_definition_file("master\n  feature1")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('e'))
        with overridden_environment(GIT_MACHETE_EDITOR='cat'):
            assert_success(
                ["discover"],
                """
                Warn: skipping feature1 since it's merged to another branch and would not have any downstream branches.

                Discovered tree of branch dependencies:

                  master *
                  |
                  x-feature2

                Save the above tree to .git/machete?
                The existing definition file will be backed up as .git/machete~ (y, e[dit], N) 
                """
            )

        assert self.repo_sandbox.read_file(".git/machete~") == "master\n  feature1"
