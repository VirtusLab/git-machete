import os.path
import re
import textwrap
from typing import Set

from pytest_mock import MockerFixture

from git_machete.utils.terminal import FullTerminalAnsiOutputCodes
from tests.base_test import BaseTest
from tests.cli_runner import assert_failure, assert_success, launch_command, rewrite_branch_layout_file
from tests.git_repository import add_worktree, check_out, commit, create_repo, create_repo_with_remote, merge, new_branch, push
from tests.mockers import mock_input_returning, overridden_environment
from tests.shell import read_file


class TestDiscover(BaseTest):

    def test_discover(self) -> None:
        create_repo_with_remote()
        assert_failure(['discover'], "No local branches found")

        new_branch('master')
        commit()
        push()
        new_branch('feature1')
        commit()
        new_branch('feature2')
        commit()
        check_out("master")
        new_branch('feature3')
        commit()
        push()
        new_branch('feature4')
        commit()

        body: str = \
            """
            master
            feature1
            feature2 annotation
            feature3 annotation rebase=no push=no
            """
        rewrite_branch_layout_file(body)
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
            The existing branch layout file will be backed up as .git/machete~
            """
        )
        assert_success(['discover', '--roots=feature1,master', '-y'], expected_discover_output)

        assert_failure(['discover', '--roots=feature1,lolxd'], "lolxd is not a local branch")

    def test_discover_main_branch_and_edit(self, mocker: MockerFixture) -> None:
        create_repo()
        new_branch('feature1')
        commit()
        new_branch('main')
        commit()
        new_branch('feature2')
        commit()

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

    def test_discover_checked_out_since_in_future(self, mocker: MockerFixture) -> None:
        E = FullTerminalAnsiOutputCodes
        self.patch_symbol(mocker, "git_machete.utils.terminal.is_stdout_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.terminal.is_stderr_a_tty", lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.terminal.is_terminal_fully_fledged", lambda: True)

        create_repo()
        new_branch("root")
        commit()

        assert_success(
            ["discover", "--checked-out-since=tomorrow"],
            f"{E.ORANGE}Warn: {E.ENDC}no branches satisfying the criteria. "
            f"Try moving the value of {E.UNDERLINE}--checked-out-since{E.ENDC_UNDERLINE} further to the past.\n"
        )

    def test_discover_with_stale_branches(self) -> None:
        create_repo()
        new_branch("develop")
        commit()
        for i in range(20):
            new_branch(f"branch-{i:02d}")
            commit()
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
        create_repo()
        new_branch("master")
        commit()
        new_branch("feature1")
        commit()
        check_out("master")
        new_branch("feature2")
        commit()
        check_out("master")
        merge("feature1")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('n'))
        launch_command("discover")
        assert read_file(".git/machete") == ""

        rewrite_branch_layout_file("master\n  feature1")

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
                The existing branch layout file will be backed up as .git/machete~ (y, e[dit], N)
                """
            )

        assert read_file(".git/machete~") == "master\n  feature1"

    def test_discover_is_worktree_independent(self) -> None:
        """Regression test for issue #1754: `discover` must produce the same tree regardless of which
        worktree it is run from.

        `discover` prunes branches by recency using HEAD's reflog, but HEAD's reflog is *per-worktree*.
        Before the fix, a branch checked out only in *another* worktree had a local timestamp of 0, so it
        was pruned as "stale" - and since all worktrees share one `.git/machete` file by default, each
        worktree's `discover` overwrote it with a different tree. `--checked-out-since` makes the pruning
        deterministic (timestamp 0 is always older than any real threshold), so no reliance on the
        freshness cap or on sub-second timestamp ordering is needed.
        """
        create_repo()
        new_branch("master")
        commit()
        check_out("master")
        new_branch("feat_main")
        commit()
        check_out("master")
        new_branch("feat_wt")
        commit()
        # feat_main is (recently) checked out in the main worktree...
        check_out("feat_main")

        main_repo = os.getcwd()
        machete_file = os.path.join(main_repo, ".git", "machete")

        def discover_here() -> Set[str]:
            launch_command("discover", "-y", "--checked-out-since=1 day ago")
            return {line.strip() for line in read_file(machete_file).splitlines() if line.strip()}

        # ...and feat_wt lives in a linked worktree, checked out only there.
        worktree = add_worktree("feat_wt")

        from_main = discover_here()
        os.chdir(worktree)
        from_worktree = discover_here()

        # The two worktrees must agree, and each cross-worktree branch must survive pruning.
        assert from_main == from_worktree, (from_main, from_worktree)
        assert "feat_wt" in from_main    # checked out only in the linked worktree
        assert "feat_main" in from_main  # checked out only in the main worktree
