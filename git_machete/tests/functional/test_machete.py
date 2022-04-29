import io
import os
import re
import subprocess
import sys
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Dict, Iterable, Optional
from unittest import mock

import pytest  # type: ignore
from git_machete import cli
from git_machete.exceptions import MacheteException
from git_machete.git_operations import LocalBranchShortName
from git_machete.tests.functional.commons import (GitRepositorySandbox,
                                                  get_current_commit_hash, git,
                                                  mock_run_cmd)
from git_machete.utils import dim


def mock_exit_script(status_code: Optional[int] = None, error: Optional[BaseException] = None) -> None:
    if error:
        raise error
    else:
        sys.exit(status_code)


def mock_fetch_ref(cls: Any, remote: str, ref: str) -> None:
    branch: LocalBranchShortName = LocalBranchShortName.of(ref[ref.index(':') + 1:])
    git.create_branch(branch, get_current_commit_hash(), switch_head=True)


def mock_run_cmd_and_forward_stdout(cmd: str, *args: str, **kwargs: Any) -> int:
    completed_process: subprocess.CompletedProcess[bytes] = subprocess.run(
        [cmd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, ** kwargs)
    print(completed_process.stdout.decode('utf-8'))
    exit_code: int = completed_process.returncode
    if exit_code != 0:
        print(dim(f"<exit code: {exit_code}>\n"), file=sys.stderr)
    return exit_code


def mock_derive_current_user_login() -> str:
    return "very_complex_user_token"


def mock_ask_if(*args: str, **kwargs: Any) -> str:
    return 'y'


def mock__get_github_token() -> Optional[str]:
    return None


def mock_push(remote: str, branch: LocalBranchShortName, force_with_lease: bool = False) -> None:
    pass


def mock__get_github_token_fake() -> Optional[str]:
    return 'token'


def mock_should_perform_interactive_slide_out(cmd: str) -> bool:
    return True


class TestMachete:
    mock_repository_info: Dict[str, str] = {'full_name': 'testing/checkout_prs',
                                            'html_url': 'https://github.com/tester/repo_sandbox.git'}

    @staticmethod
    def adapt(s: str) -> str:
        return textwrap.indent(textwrap.dedent(re.sub(r"\|\n", "| \n", s[1:])), "  ")

    @staticmethod
    def launch_command(*args: str) -> str:
        with io.StringIO() as out:
            with redirect_stdout(out):
                with redirect_stderr(out):
                    cli.launch(list(args))
                    git.flush_caches()
            return out.getvalue()

    @staticmethod
    def rewrite_definition_file(new_body: str) -> None:
        definition_file_path = git.get_main_git_subpath("machete")
        with open(os.path.join(os.getcwd(), definition_file_path), 'w') as def_file:
            def_file.writelines(new_body)

    def assert_command(self, cmds: Iterable[str], expected_result: str, strip_indentation: bool = True) -> None:
        assert self.launch_command(*cmds) == (self.adapt(expected_result) if strip_indentation else expected_result)

    def setup_method(self) -> None:
        # Status diffs can be quite large, default to ~256 lines of diff context
        # https://docs.python.org/3/library/unittest.html#unittest.TestCase.maxDiff
        self.maxDiff = 80 * 256

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

        self.launch_command("discover", "-y", "--roots=develop,master")
        self.assert_command(
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
            self.launch_command('status')
        if e:
            assert e.value.parameter == expected_error_message, 'Verify that expected error message has appeared a branch re-appears in tree definition.'

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_traverse_no_push(self) -> None:
        self.setup_discover_standard_tree()

        self.launch_command("traverse", "-Wy", "--no-push")
        self.assert_command(
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
        self.launch_command("t", "-Wy", "--no-push", "--push", "--start-from=here")
        self.assert_command(
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
        self.launch_command("t", "-Wy", "--no-push", "--push")
        self.assert_command(
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

        self.launch_command("traverse", "-Wy", "--no-push-untracked")
        self.assert_command(
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

        self.launch_command("traverse", "-Wy")
        self.assert_command(
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
            self.launch_command("go", "prev")
        self.launch_command("squash")
        self.assert_command(
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
        self.launch_command("discover", "-y")

        self.launch_command("go", "up")

        assert 'level-0-branch' == \
            self.launch_command("show", "current").strip(), \
            "Verify that 'git machete go up' performs 'git checkout' to " \
            "the parent/upstream branch of the current branch."
        # check short command behaviour
        self.repo_sandbox.check_out("level-1-branch")
        self.launch_command("g", "u")
        assert 'level-0-branch' == \
            self.launch_command("show", "current").strip(), \
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
        self.launch_command("discover", "-y")

        self.launch_command("go", "down")

        assert 'level-1-branch' == \
            self.launch_command("show", "current").strip(), \
            "Verify that 'git machete go down' performs 'git checkout' to " \
            "the child/downstream branch of the current branch."
        # check short command behaviour
        self.repo_sandbox.check_out("level-0-branch")
        self.launch_command("g", "d")

        assert 'level-1-branch' == \
            self.launch_command("show", "current").strip(), \
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
        self.launch_command("discover", "-y")

        self.launch_command("go", "first")

        assert 'level-1a-branch' == \
            self.launch_command("show", "current").strip(), \
            "Verify that 'git machete go first' performs 'git checkout' to" \
            "the first downstream branch of a root branch if root branch " \
            "has any downstream branches."

        # check short command behaviour
        self.repo_sandbox.check_out("level-3b-branch")
        self.launch_command("g", "f")

        assert 'level-1a-branch' == \
            self.launch_command("show", "current").strip(), \
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
        self.launch_command("discover", "-y")

        self.launch_command("go", "first")

        assert 'level-0-branch' == \
            self.launch_command("show", "current").strip(), \
            "Verify that 'git machete go first' set current branch to root" \
            "if root branch has no downstream."

        # check short command behaviour
        self.launch_command("g", "f")

        assert 'level-0-branch' == \
            self.launch_command("show", "current").strip(), \
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
        self.launch_command("discover", "-y")

        self.launch_command("go", "last")

        assert 'level-1b-branch' == \
            self.launch_command("show", "current").strip(), \
            "Verify that 'git machete go last' performs 'git checkout' to" \
            "the last downstream branch of a root branch if root branch " \
            "has any downstream branches."

        # check short command behaviour
        self.repo_sandbox.check_out("level-1a-branch")
        self.launch_command("g", "l")

        assert 'level-1b-branch' == \
            self.launch_command("show", "current").strip(), \
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
        self.launch_command("discover", "-y")

        self.launch_command("go", "next")

        assert 'level-1b-branch' == \
            self.launch_command("show", "current").strip(), \
            "Verify that 'git machete go next' performs 'git checkout' to" \
            "the next downstream branch right after the current one in the" \
            "config file if successor branch exists."
        # check short command behaviour
        self.repo_sandbox.check_out("level-2a-branch")
        self.launch_command("g", "n")

        assert 'level-1b-branch' == \
            self.launch_command("show", "current").strip(), \
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
        self.launch_command("discover", "-y")

        self.launch_command("go", "next")
        assert 'x-additional-root' == \
            self.launch_command("show", "current").strip(), \
            "Verify that 'git machete go next' can checkout to branch that doesn't" \
            "share root with the current branch."

        # check short command behaviour
        self.repo_sandbox.check_out("level-1-branch")
        self.launch_command("g", "n")
        assert 'x-additional-root' == \
            self.launch_command("show", "current").strip(), \
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
        self.launch_command("discover", "-y")

        self.launch_command("go", "prev")

        assert 'level-2a-branch' == \
            self.launch_command("show", "current").strip(), \
            "Verify that 'git machete go prev' performs 'git checkout' to" \
            "the branch right before the current one in the config file" \
            "when predecessor branch exists within the root tree."
        # check short command behaviour
        self.repo_sandbox.check_out("level-1b-branch")
        self.launch_command("g", "p")

        assert 'level-2a-branch' == \
            self.launch_command("show", "current").strip(), \
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
        self.launch_command("discover", "-y")

        self.launch_command("go", "prev")
        assert 'a-additional-root' == \
            self.launch_command("show", "current").strip(), \
            "Verify that 'git machete go prev' can checkout to branch that doesn't" \
            "share root with the current branch."

        # check short command behaviour
        self.repo_sandbox.check_out("level-0-branch")
        self.launch_command("g", "p")
        assert 'a-additional-root' == \
            self.launch_command("show", "current").strip(), \
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
        self.launch_command("discover", "-y")

        self.launch_command("go", "root")

        assert 'level-0-branch' == \
            self.launch_command("show", "current").strip(), \
            "Verify that 'git machete go root' performs 'git checkout' to" \
            "the root of the current branch."
        # check short command behaviour
        self.repo_sandbox.check_out("level-2a-branch")
        self.launch_command("g", "r")
        assert 'level-0-branch' == \
            self.launch_command("show", "current").strip(), \
            "Verify that 'git machete g r' performs 'git checkout' to" \
            "the root of the current branch."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_advance_with_no_downstream_branches(self) -> None:
        """Verify behaviour of a 'git machete advance' command.

        Verify that 'git machete advance' raises an error when current branch
        has no downstream branches.

        """
        (
            self.repo_sandbox.new_branch("root")
            .commit()
        )
        self.launch_command("discover", "-y")

        with pytest.raises(SystemExit):
            self.launch_command("advance")

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('git_machete.git_operations.GitContext.push', mock_push)
    def test_advance_with_one_downstream_branch(self) -> None:
        """Verify behaviour of a 'git machete advance' command.

        Verify that when there is only one, rebased downstream branch of a
        current branch 'git machete advance' merges commits from that branch
        and slides out child branches of the downstream branch. It edits the git
        machete discovered tree to reflect new dependencies.

        """
        (
            self.repo_sandbox.new_branch("root")
            .commit()
            .new_branch("level-1-branch")
            .commit()
            .new_branch("level-2-branch")
            .commit()
            .check_out("level-1-branch")
        )
        self.launch_command("discover", "-y")
        level_1_commit_hash = get_current_commit_hash()

        self.repo_sandbox.check_out("root")
        self.launch_command("advance", "-y")

        root_top_commit_hash = get_current_commit_hash()

        assert level_1_commit_hash == \
            root_top_commit_hash, \
            "Verify that when there is only one, rebased downstream branch of a" \
            "current branch 'git machete advance' merges commits from that branch" \
            "and slides out child branches of the downstream branch."
        assert "level-1-branch" not in \
            self.launch_command("status"), \
            "Verify that branch to which advance was performed is removed " \
            "from the git-machete tree and the structure of the git machete " \
            "tree is updated."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_advance_with_few_possible_downstream_branches_and_yes_option(self) -> None:
        """Verify behaviour of a 'git machete advance' command.

        Verify that 'git machete advance -y' raises an error when current branch
        has more than one synchronized downstream branch and option '-y' is passed.

        """
        (
            self.repo_sandbox.new_branch("root")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .check_out("root")
            .new_branch("level-1b-branch")
            .commit()
            .check_out("root")
        )
        self.launch_command("discover", "-y")

        with pytest.raises(SystemExit):
            self.launch_command("advance", '-y')
