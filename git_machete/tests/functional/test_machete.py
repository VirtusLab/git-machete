import os
import sys
from typing import Optional
from unittest import mock

import pytest  # type: ignore
from git_machete.exceptions import MacheteException
from git_machete.tests.functional.commons import (GitRepositorySandbox,
                                                  assert_command, git,
                                                  launch_command, mock_run_cmd)


def mock_exit_script(status_code: Optional[int] = None, error: Optional[BaseException] = None) -> None:
    if error:
        raise error
    else:
        sys.exit(status_code)


class TestMachete:

    @staticmethod
    def rewrite_definition_file(new_body: str) -> None:
        definition_file_path = git.get_main_git_subpath("machete")
        with open(os.path.join(os.getcwd(), definition_file_path), 'w') as def_file:
            def_file.writelines(new_body)

    def setup_method(self) -> None:

        self.repo_sandbox = GitRepositorySandbox()

        (
            self.repo_sandbox
            # Create the remote and sandbox repos, chdir into sandbox repo
            .new_repo(self.repo_sandbox.remote_path, "--bare")
            .new_repo(self.repo_sandbox.local_path)
            .execute(f"git remote add origin {self.repo_sandbox.remote_path}")
            .execute('git config user.email "tester@test.com"')
            .execute('git config user.name "Tester Test"')
        )

    def setup_discover_standard_tree(self) -> None:
        (
            self.repo_sandbox.new_branch("root")
            .commit("root")
            .new_branch("develop")
            .commit("develop commit")
            .new_branch("allow-ownership-link")
            .commit("Allow ownership links")
            .push()
            .new_branch("build-chain")
            .commit("Build arbitrarily long chains")
            .check_out("allow-ownership-link")
            .commit("1st round of fixes")
            .check_out("develop")
            .commit("Other develop commit")
            .push()
            .new_branch("call-ws")
            .commit("Call web service")
            .commit("1st round of fixes")
            .push()
            .new_branch("drop-constraint")
            .commit("Drop unneeded SQL constraints")
            .check_out("call-ws")
            .commit("2nd round of fixes")
            .check_out("root")
            .new_branch("master")
            .commit("Master commit")
            .push()
            .new_branch("hotfix/add-trigger")
            .commit("HOTFIX Add the trigger")
            .push()
            .commit_amend("HOTFIX Add the trigger (amended)")
            .new_branch("ignore-trailing")
            .commit("Ignore trailing data")
            .sleep(1)
            .commit_amend("Ignore trailing data (amended)")
            .push()
            .reset_to("ignore-trailing@{1}")
            .delete_branch("root")
        )

        launch_command("discover", "-y", "--roots=develop,master")
        assert_command(
            ["status"],
            """
            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws (ahead of origin)
              |
              x-drop-constraint (untracked)

            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing * (diverged from & older than origin)
            """,
        )

    @mock.patch('git_machete.cli.exit_script', mock_exit_script)
    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_branch_reappears_in_definition(self) -> None:
        body: str = \
            """master
            \tdevelop
            \t\n
            develop
            """

        self.repo_sandbox.new_branch("root")
        self.rewrite_definition_file(body)

        expected_error_message: str = '.git/machete, line 5: branch `develop` re-appears in the tree definition. ' \
                                      'Edit the definition file manually with `git machete edit`'

        with pytest.raises(MacheteException) as e:
            launch_command('status')
        if e:
            assert e.value.parameter == expected_error_message, 'Verify that expected error message has appeared a branch re-appears in tree definition.'

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_traverse_no_push(self) -> None:
        self.setup_discover_standard_tree()

        launch_command("traverse", "-Wy", "--no-push")
        assert_command(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link (diverged from origin)
            | |
            | | Build arbitrarily long chains
            | o-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws (ahead of origin)
              |
              | Drop unneeded SQL constraints
              o-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger (diverged from origin)
              |
              | Ignore trailing data (amended)
              o-ignore-trailing *
            """,
        )

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_traverse_no_push_override(self) -> None:
        self.setup_discover_standard_tree()
        self.repo_sandbox.check_out("hotfix/add-trigger")
        launch_command("t", "-Wy", "--no-push", "--push", "--start-from=here")
        assert_command(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            x-allow-ownership-link (ahead of origin)
            | |
            | | Build arbitrarily long chains
            | x-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws (ahead of origin)
              |
              | Drop unneeded SQL constraints
              x-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger *
              |
              | Ignore trailing data (amended)
              o-ignore-trailing
            """,
        )
        self.repo_sandbox.check_out("ignore-trailing")
        launch_command("t", "-Wy", "--no-push", "--push")
        assert_command(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link
            | |
            | | Build arbitrarily long chains
            | o-build-chain
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws
              |
              | Drop unneeded SQL constraints
              o-drop-constraint

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger
              |
              | Ignore trailing data (amended)
              o-ignore-trailing *
            """,
        )

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_traverse_no_push_untracked(self) -> None:
        self.setup_discover_standard_tree()

        launch_command("traverse", "-Wy", "--no-push-untracked")
        assert_command(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link
            | |
            | | Build arbitrarily long chains
            | o-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws
              |
              | Drop unneeded SQL constraints
              o-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger
              |
              | Ignore trailing data (amended)
              o-ignore-trailing *
            """,
        )

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_discover_traverse_squash(self) -> None:
        self.setup_discover_standard_tree()

        launch_command("traverse", "-Wy")
        assert_command(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link
            | |
            | | Build arbitrarily long chains
            | o-build-chain
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws
              |
              | Drop unneeded SQL constraints
              o-drop-constraint

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger
              |
              | Ignore trailing data (amended)
              o-ignore-trailing *
            """,
        )

        # Go from ignore-trailing to call-ws which has >1 commit to be squashed
        for _ in range(4):
            launch_command("go", "prev")
        launch_command("squash")
        assert_command(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link
            | |
            | | Build arbitrarily long chains
            | o-build-chain
            |
            | Call web service
            o-call-ws * (diverged from origin)
              |
              | Drop unneeded SQL constraints
              x-drop-constraint

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger
              |
              | Ignore trailing data (amended)
              o-ignore-trailing
            """,
        )

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_go_up(self) -> None:
        """Verify behaviour of a 'git machete go up' command.

        Verify that 'git machete go up' performs 'git checkout' to the
        parent/upstream branch of the current branch.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1-branch")
            .commit()
        )
        launch_command("discover", "-y")

        launch_command("go", "up")

        assert 'level-0-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete go up' performs 'git checkout' to " \
            "the parent/upstream branch of the current branch."
        # check short command behaviour
        self.repo_sandbox.check_out("level-1-branch")
        launch_command("g", "u")
        assert 'level-0-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete g u' performs 'git checkout' to " \
            "the parent/upstream branch of the current branch."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_go_down(self) -> None:
        """Verify behaviour of a 'git machete go down' command.

        Verify that 'git machete go down' performs 'git checkout' to the
        child/downstream branch of the current branch.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1-branch")
            .commit()
            .check_out("level-0-branch")
        )
        launch_command("discover", "-y")

        launch_command("go", "down")

        assert 'level-1-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete go down' performs 'git checkout' to " \
            "the child/downstream branch of the current branch."
        # check short command behaviour
        self.repo_sandbox.check_out("level-0-branch")
        launch_command("g", "d")

        assert 'level-1-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete g d' performs 'git checkout' to " \
            "the child/downstream branch of the current branch."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_go_first_root_with_downstream(self) -> None:
        """Verify behaviour of a 'git machete go first' command.

        Verify that 'git machete go first' performs 'git checkout' to
        the first downstream branch of a root branch in the config file
        if root branch has any downstream branches.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
            .new_branch("level-2b-branch")
            .commit()
            .new_branch("level-3b-branch")
            .commit()
            # a added so root will be placed in the config file after the level-0-branch
            .new_root_branch("a-additional-root")
            .commit()
            .new_branch("branch-from-a-additional-root")
            .commit()
            .check_out("level-3b-branch")
        )
        launch_command("discover", "-y")

        launch_command("go", "first")

        assert 'level-1a-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete go first' performs 'git checkout' to" \
            "the first downstream branch of a root branch if root branch " \
            "has any downstream branches."

        # check short command behaviour
        self.repo_sandbox.check_out("level-3b-branch")
        launch_command("g", "f")

        assert 'level-1a-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete g d' performs 'git checkout' to " \
            "the child/downstream branch of the current branch."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_go_first_root_without_downstream(self) -> None:
        """Verify behaviour of a 'git machete go first' command.

        Verify that 'git machete go first' set current branch to root
        if root branch has no downstream.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
        )
        launch_command("discover", "-y")

        launch_command("go", "first")

        assert 'level-0-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete go first' set current branch to root" \
            "if root branch has no downstream."

        # check short command behaviour
        launch_command("g", "f")

        assert 'level-0-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete g f' set current branch to root" \
            "if root branch has no downstream."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_go_last(self) -> None:
        """Verify behaviour of a 'git machete go last' command.

        Verify that 'git machete go last' performs 'git checkout' to
        the last downstream branch of a root branch if root branch
        has any downstream branches.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
            # x added so root will be placed in the config file after the level-0-branch
            .new_root_branch("x-additional-root")
            .commit()
            .new_branch("branch-from-x-additional-root")
            .commit()
            .check_out("level-1a-branch")
        )
        launch_command("discover", "-y")

        launch_command("go", "last")

        assert 'level-1b-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete go last' performs 'git checkout' to" \
            "the last downstream branch of a root branch if root branch " \
            "has any downstream branches."

        # check short command behaviour
        self.repo_sandbox.check_out("level-1a-branch")
        launch_command("g", "l")

        assert 'level-1b-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete g l' performs 'git checkout' to" \
            "the last downstream branch of a root branch if root branch " \
            "has any downstream branches."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_go_next_successor_exists(self) -> None:
        """Verify behaviour of a 'git machete go next' command.

        Verify that 'git machete go next' performs 'git checkout' to
        the branch right after the current one in the config file
        when successor branch exists within the root tree.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
            .check_out("level-2a-branch")
        )
        launch_command("discover", "-y")

        launch_command("go", "next")

        assert 'level-1b-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete go next' performs 'git checkout' to" \
            "the next downstream branch right after the current one in the" \
            "config file if successor branch exists."
        # check short command behaviour
        self.repo_sandbox.check_out("level-2a-branch")
        launch_command("g", "n")

        assert 'level-1b-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete g n' performs 'git checkout' to" \
            "the next downstream branch right after the current one in the" \
            "config file if successor branch exists."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_go_next_successor_on_another_root_tree(self) -> None:
        """Verify behaviour of a 'git machete go next' command.

        Verify that 'git machete go next' can checkout to branch that doesn't
        share root with the current branch.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1-branch")
            .commit()
            # x added so root will be placed in the config file after the level-0-branch
            .new_root_branch("x-additional-root")
            .commit()
            .check_out("level-1-branch")
        )
        launch_command("discover", "-y")

        launch_command("go", "next")
        assert 'x-additional-root' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete go next' can checkout to branch that doesn't" \
            "share root with the current branch."

        # check short command behaviour
        self.repo_sandbox.check_out("level-1-branch")
        launch_command("g", "n")
        assert 'x-additional-root' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete g n' can checkout to branch that doesn't" \
            "share root with the current branch."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_go_prev_successor_exists(self) -> None:
        """Verify behaviour of a 'git machete go prev' command.

        Verify that 'git machete go prev' performs 'git checkout' to
        the branch right before the current one in the config file
        when predecessor branch exists within the root tree.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
        )
        launch_command("discover", "-y")

        launch_command("go", "prev")

        assert 'level-2a-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete go prev' performs 'git checkout' to" \
            "the branch right before the current one in the config file" \
            "when predecessor branch exists within the root tree."
        # check short command behaviour
        self.repo_sandbox.check_out("level-1b-branch")
        launch_command("g", "p")

        assert 'level-2a-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete g p' performs 'git checkout' to" \
            "the branch right before the current one in the config file" \
            "when predecessor branch exists within the root tree."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_go_prev_successor_on_another_root_tree(self) -> None:
        """Verify behaviour of a 'git machete go prev' command.

        Verify that 'git machete go prev' raises an error when predecessor
        branch doesn't exist.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            # a added so root will be placed in the config file before the level-0-branch
            .new_root_branch("a-additional-root")
            .commit()
            .check_out("level-0-branch")
        )
        launch_command("discover", "-y")

        launch_command("go", "prev")
        assert 'a-additional-root' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete go prev' can checkout to branch that doesn't" \
            "share root with the current branch."

        # check short command behaviour
        self.repo_sandbox.check_out("level-0-branch")
        launch_command("g", "p")
        assert 'a-additional-root' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete g p' can checkout to branch that doesn't" \
            "share root with the current branch."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_go_root(self) -> None:
        """Verify behaviour of a 'git machete go root' command.

        Verify that 'git machete go root' performs 'git checkout' to
        the root of the current branch.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
            .new_root_branch("additional-root")
            .commit()
            .new_branch("branch-from-additional-root")
            .commit()
            .check_out("level-2a-branch")
        )
        launch_command("discover", "-y")

        launch_command("go", "root")

        assert 'level-0-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete go root' performs 'git checkout' to" \
            "the root of the current branch."
        # check short command behaviour
        self.repo_sandbox.check_out("level-2a-branch")
        launch_command("g", "r")
        assert 'level-0-branch' == \
            launch_command("show", "current").strip(), \
            "Verify that 'git machete g r' performs 'git checkout' to" \
            "the root of the current branch."
