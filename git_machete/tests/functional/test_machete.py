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
from git_machete.github import get_parsed_github_remote_url
from git_machete.tests.functional.commons import (FAKE_GITHUB_REMOTE_PATTERNS,
                                                  FakeCommandLineOptions,
                                                  GitRepositorySandbox,
                                                  MockContextManager,
                                                  MockGitHubAPIState,
                                                  MockHTTPError,
                                                  get_current_commit_hash, git,
                                                  mock_run_cmd, popen)
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
    def test_show(self) -> None:
        self.setup_discover_standard_tree()

        assert self.launch_command("show", "up").strip() == "hotfix/add-trigger"

        assert self.launch_command("show", "up", "call-ws").strip() == "develop"

        assert self.launch_command("show", "current").strip() == "ignore-trailing"

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
    def test_slide_out(self) -> None:
        (
            self.repo_sandbox.new_branch("develop")
            .commit("develop commit")
            .push()
            .new_branch("slide_root")
            .commit("slide_root_1")
            .push()
            .check_out("slide_root")
            .new_branch("child_a")
            .commit("child_a_1")
            .push()
            .check_out("slide_root")
            .new_branch("child_b")
            .commit("child_b_1")
            .push()
            .check_out("child_b")
            .new_branch("child_c")
            .commit("child_c_1")
            .push()
            .new_branch("child_d")
            .commit("child_d_1")
            .push()
        )

        self.launch_command("discover", "-y", "--roots=develop")

        self.assert_command(
            ["status", "-l"],
            """
            develop
            |
            | slide_root_1
            o-slide_root
              |
              | child_a_1
              o-child_a
              |
              | child_b_1
              o-child_b
                |
                | child_c_1
                o-child_c
                  |
                  | child_d_1
                  o-child_d *
            """,
        )

        # Slide-out a single interior branch with one downstream. (child_c)
        # This rebases the single downstream onto the new upstream. (child_b -> child_d)

        self.launch_command("go", "up")
        self.launch_command("slide-out", "-n")

        self.assert_command(
            ["status", "-l"],
            """
            develop
            |
            | slide_root_1
            o-slide_root
              |
              | child_a_1
              o-child_a
              |
              | child_b_1
              o-child_b
                |
                | child_d_1
                o-child_d * (diverged from origin)
            """,
        )

        # Slide-out an interior branch with multiple downstreams. (slide_root)
        # This rebases all the downstreams onto the new upstream. (develop -> [child_a, child_b])
        self.launch_command("traverse", "-Wy")
        self.launch_command("go", "up")
        self.launch_command("go", "up")

        self.assert_command(
            ["status", "-l"],
            """
                develop
                |
                | slide_root_1
                o-slide_root *
                  |
                  | child_a_1
                  o-child_a
                  |
                  | child_b_1
                  o-child_b
                    |
                    | child_d_1
                    o-child_d
                """,
        )

        self.launch_command("slide-out", "-n")

        self.assert_command(
            ["status", "-l"],
            """
            develop
            |
            | child_a_1
            o-child_a (diverged from origin)
            |
            | child_b_1
            o-child_b * (diverged from origin)
              |
              | child_d_1
              x-child_d
            """,
        )

        self.launch_command("traverse", "-Wy")
        self.assert_command(
            ["status", "-l"],
            """
            develop
            |
            | child_a_1
            o-child_a
            |
            | child_b_1
            o-child_b *
              |
              | child_d_1
              o-child_d
            """,
        )

        # Slide-out a terminal branch. (child_d)
        # This just slices the branch off the tree.
        self.launch_command("go", "down")
        self.launch_command("slide-out", "-n")

        self.assert_command(
            ["status", "-l"],
            """
            develop
            |
            | child_a_1
            o-child_a
            |
            | child_b_1
            o-child_b *
            """,
        )

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_squash_merge(self) -> None:
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

        self.launch_command("discover", "-y", "--roots=root")

        self.assert_command(
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
        self.assert_command(
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
        self.assert_command(
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

        # traverse then slides out the branch
        self.launch_command("traverse", "-w", "-y")
        self.assert_command(
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

        # simulate an upstream squash-merge of the feature branch
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
        self.assert_command(
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
        self.launch_command("traverse", "-W", "-y")

        self.assert_command(
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
    def test_show_up(self) -> None:
        """Verify behaviour of a 'git machete show up' command.

        Verify that 'git machete show up' displays name of a parent/upstream
        branch one above current one in the config file from within current
        root tree.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1-branch")
            .commit()
        )
        self.launch_command("discover", "-y")

        assert 'level-0-branch' == \
            self.launch_command("show", "up").strip(), \
            "Verify that 'git machete show up' displays name of a parent/upstream" \
            "branch one above current one."
        # check short command behaviour
        assert 'level-0-branch' == \
            self.launch_command("show", "u").strip(), \
            "Verify that 'git machete show u' displays name of a parent/upstream" \
            "branch one above current one."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_show_down(self) -> None:
        """Verify behaviour of a 'git machete show down' command.

        Verify that 'git machete show down' displays name of a
        child/downstream branch one below current one.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1-branch")
            .commit()
            .check_out("level-0-branch")
        )
        self.launch_command("discover", "-y")

        assert 'level-1-branch' == \
            self.launch_command("show", "down").strip(), \
            "Verify that 'git machete show down' displays name of " \
            "a child/downstream branch one below current one."
        # check short command behaviour
        assert 'level-1-branch' == \
            self.launch_command("show", "d").strip(), \
            "Verify that 'git machete show d' displays name of " \
            "a child/downstream branch one below current one."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_show_first(self) -> None:
        """Verify behaviour of a 'git machete show first' command.

        Verify that 'git machete show first' displays name of the first downstream
        branch of a root branch of the current branch in the config file if root
        branch has any downstream branches.

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

        assert 'level-1a-branch' == \
            self.launch_command("show", "first").strip(), \
            "Verify that 'git machete show first' displays name of the first downstream" \
            "branch of a root branch of the current branch in the config file if root" \
            "branch has any downstream branches."
        # check short command behaviour
        assert 'level-1a-branch' == \
            self.launch_command("show", "f").strip(), \
            "Verify that 'git machete show f' displays name of the first downstream" \
            "branch of a root branch of the current branch in the config file if root" \
            "branch has any downstream branches."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_show_last(self) -> None:
        """Verify behaviour of a 'git machete show last' command.

        Verify that 'git machete show last' displays name of the last downstream
        branch of a root branch of the current branch in the config file if root
        branch has any downstream branches.

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

        assert 'level-1b-branch' == \
            self.launch_command("show", "last").strip(), \
            "Verify that 'git machete show last' displays name of the last downstream" \
            "branch of a root branch of the current branch in the config file if root" \
            "branch has any downstream branches."
        # check short command behaviour
        assert 'level-1b-branch' == \
            self.launch_command("show", "l").strip(), \
            "Verify that 'git machete show l' displays name of the last downstream" \
            "branch of a root branch of the current branch in the config file if root" \
            "branch has any downstream branches."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_show_next(self) -> None:
        """Verify behaviour of a 'git machete show next' command.

        Verify that 'git machete show next' displays name of
        a branch right after the current one in the config file
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

        assert 'level-1b-branch' == \
            self.launch_command("show", "next").strip(), \
            "Verify that 'git machete show next' displays name of " \
            "a branch right after the current one in the config file" \
            "when successor branch exists within the root tree."
        # check short command behaviour
        assert 'level-1b-branch' == \
            self.launch_command("show", "n").strip(), \
            "Verify that 'git machete show n' displays name of " \
            "a branch right after the current one in the config file" \
            "when successor branch exists within the root tree."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_show_prev(self) -> None:
        """Verify behaviour of a 'git machete show prev' command.

        Verify that 'git machete show prev' displays name of
        a branch right before the current one in the config file
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

        assert 'level-2a-branch' == \
            self.launch_command("show", "prev").strip(), \
            "Verify that 'git machete show prev' displays name of" \
            "a branch right before the current one in the config file" \
            "when predecessor branch exists within the root tree."
        # check short command behaviour
        assert 'level-2a-branch' == \
            self.launch_command("show", "p").strip(), \
            "Verify that 'git machete show p' displays name of" \
            "a branch right before the current one in the config file" \
            "when predecessor branch exists within the root tree."

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    def test_show_root(self) -> None:
        """Verify behaviour of a 'git machete show root' command.

        Verify that 'git machete show root' displays name of the root of
        the current branch.

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

        assert 'level-0-branch' == \
            self.launch_command("show", "root").strip(), \
            "Verify that 'git machete show root' displays name of the root of" \
            "the current branch."
        # check short command behaviour
        assert 'level-0-branch' == \
            self.launch_command("show", "r").strip(), \
            "Verify that 'git machete show r' displays name of the root of" \
            "the current branch."

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

    git_api_state_for_test_retarget_pr = MockGitHubAPIState(
        [{'head': {'ref': 'feature', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'root'}, 'number': '15',
          'html_url': 'www.github.com', 'state': 'open'}])

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('urllib.request.Request', git_api_state_for_test_retarget_pr.new_request())
    @mock.patch('urllib.request.urlopen', MockContextManager)
    def test_retarget_pr(self) -> None:
        branchs_first_commit_msg = "First commit on branch."
        branchs_second_commit_msg = "Second commit on branch."
        (
            self.repo_sandbox.new_branch("root")
                .commit("First commit on root.")
                .new_branch("branch-1")
                .commit(branchs_first_commit_msg)
                .commit(branchs_second_commit_msg)
                .push()
                .new_branch('feature')
                .commit('introduce feature')
                .push()
                .check_out('feature')
                .add_remote('new_origin', 'https://github.com/user/repo.git')
        )

        self.launch_command("discover", "-y")
        self.assert_command(['github', 'retarget-pr'], 'The base branch of PR #15 has been switched to `branch-1`\n', strip_indentation=False)
        self.assert_command(['github', 'retarget-pr'], 'The base branch of PR #15 is already `branch-1`\n', strip_indentation=False)

    git_api_state_for_test_anno_prs = MockGitHubAPIState([
        {'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'hotfix/add-trigger'}, 'number': '3', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'allow-ownership-link', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'}, 'number': '7', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'call-ws', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'}, 'number': '31', 'html_url': 'www.github.com', 'state': 'open'}
    ])

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('git_machete.github.derive_current_user_login', mock_derive_current_user_login)
    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', git_api_state_for_test_anno_prs.new_request())
    def test_anno_prs(self) -> None:
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
                .add_remote('new_origin', 'https://github.com/user/repo.git')
        )
        self.launch_command("discover", "-y")
        self.launch_command('github', 'anno-prs')
        self.assert_command(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing *  PR #3 (github_user) (diverged from & older than origin)

            develop
            |
            x-allow-ownership-link  PR #7 (github_user) (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws  PR #31 (github_user) (ahead of origin)
              |
              x-drop-constraint (untracked)
            """,
        )

    git_api_state_for_test_create_pr = MockGitHubAPIState([{'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'hotfix/add-trigger'}, 'number': '3', 'html_url': 'www.github.com', 'state': 'open'}],
                                                          issues=[{'number': '4'}, {'number': '5'}, {'number': '6'}])

    @mock.patch('git_machete.cli.exit_script', mock_exit_script)
    @mock.patch('git_machete.client.MacheteClient.ask_if', mock_ask_if)
    # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_create_pr` due to `git fetch` executed by `create-pr` subcommand.
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('urllib.error.HTTPError', MockHTTPError)  # need to provide read() method, which does not actually reads error from url
    @mock.patch('urllib.request.Request', git_api_state_for_test_create_pr.new_request())
    @mock.patch('urllib.request.urlopen', MockContextManager)
    def test_github_create_pr(self) -> None:
        (
            self.repo_sandbox.new_branch("root")
                .commit("initial commit")
                .new_branch("develop")
                .commit("first commit")
                .new_branch("allow-ownership-link")
                .commit("Enable ownership links")
                .push()
                .new_branch("build-chain")
                .commit("Build arbitrarily long chains of PRs")
                .check_out("allow-ownership-link")
                .commit("fixes")
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
                .new_branch('chore/fields')
                .commit("remove outdated fields")
                .check_out("call-ws")
                .add_remote('new_origin', 'https://github.com/user/repo.git')
        )

        self.launch_command("discover")
        self.launch_command("github", "create-pr")
        # ahead of origin state, push is advised and accepted
        self.assert_command(
            ['status'],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing (diverged from & older than origin)
                |
                o-chore/fields (untracked)

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws *  PR #4
              |
              x-drop-constraint (untracked)
            """,
        )
        self.repo_sandbox.check_out('chore/fields')
        #  untracked state (can only create pr when branch is pushed)
        self.launch_command("github", "create-pr", "--draft")
        self.assert_command(
            ['status'],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing (diverged from & older than origin)
                |
                o-chore/fields *  PR #5

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws  PR #4
              |
              x-drop-constraint (untracked)
            """,
        )

        (
            self.repo_sandbox.check_out('hotfix/add-trigger')
            .commit('trigger released')
            .commit('minor changes applied')
        )

        # diverged from and newer than origin
        self.launch_command("github", "create-pr")
        self.assert_command(
            ['status'],
            """
            master
            |
            o-hotfix/add-trigger *  PR #6
              |
              x-ignore-trailing (diverged from & older than origin)
                |
                o-chore/fields  PR #5

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws  PR #4
              |
              x-drop-constraint (untracked)
            """,
        )
        expected_error_message = "A pull request already exists for test_repo:hotfix/add-trigger."
        with pytest.raises(MacheteException) as e:
            self.launch_command("github", "create-pr")
        if e:
            assert e.value.args[0] == expected_error_message, 'Verify that expected error message has appeared when given pull request to create is already created.'

        # check against head branch is ancestor or equal to base branch
        (
            self.repo_sandbox.check_out('develop')
            .new_branch('testing/endpoints')
            .push()
        )
        self.launch_command('discover')

        expected_error_message = "All commits in `testing/endpoints` branch are already included in `develop` branch.\nCannot create pull request."
        with pytest.raises(MacheteException) as e:
            self.launch_command("github", "create-pr")
        if e:
            assert e.value.parameter == expected_error_message, 'Verify that expected error message has appeared when head branch is equal or ancestor of base branch.'

        self.repo_sandbox.check_out('develop')
        expected_error_message = "Branch `develop` does not have a parent branch (it is a root), base branch for the PR cannot be established."
        with pytest.raises(MacheteException) as e:
            self.launch_command("github", "create-pr")
        if e:
            assert e.value.parameter == expected_error_message, 'Verify that expected error message has appeared when creating PR from root branch.'

    git_api_state_for_test_create_pr_missing_base_branch_on_remote = MockGitHubAPIState([{'head': {'ref': 'chore/redundant_checks', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'restrict_access'}, 'number': '18', 'html_url': 'www.github.com', 'state': 'open'}])

    # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_create_pr` due to `git fetch` executed by `create-pr` subcommand.
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    @mock.patch('git_machete.github.__get_github_token', mock__get_github_token)
    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('git_machete.client.MacheteClient.ask_if', mock_ask_if)
    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', git_api_state_for_test_create_pr_missing_base_branch_on_remote.new_request())
    def test_github_create_pr_missing_base_branch_on_remote(self) -> None:
        (
            self.repo_sandbox.new_branch("root")
                .commit("initial commit")
                .new_branch("develop")
                .commit("first commit on develop")
                .push()
                .new_branch("feature/api_handling")
                .commit("Introduce GET and POST methods on API")
                .new_branch("feature/api_exception_handling")
                .commit("catch exceptions coming from API")
                .push()
                .delete_branch("root")
        )

        self.launch_command('discover')

        expected_msg = ("Fetching origin...\n"
                        "Warn: Base branch for this PR (`feature/api_handling`) is not found on remote, pushing...\n"
                        "Creating a PR from `feature/api_exception_handling` to `feature/api_handling`... OK, see www.github.com\n")
        self.assert_command(['github', 'create-pr'], expected_msg, strip_indentation=False)
        self.assert_command(
            ['status'],
            """
            develop
            |
            o-feature/api_handling
              |
              o-feature/api_exception_handling *  PR #19
            """,
        )

    git_api_state_for_test_checkout_prs = MockGitHubAPIState([
        {'head': {'ref': 'chore/redundant_checks', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'restrict_access'}, 'number': '18', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'restrict_access', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'allow-ownership-link'}, 'number': '17', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'allow-ownership-link', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'bugfix/feature'}, 'number': '12', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'bugfix/feature', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'enhance/feature'}, 'number': '6', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'enhance/add_user', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'}, 'number': '19', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'testing/add_user', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'bugfix/add_user'}, 'number': '22', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'chore/comments', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'testing/add_user'}, 'number': '24', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'hotfix/add-trigger'}, 'number': '3', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'bugfix/remove-n-option', 'repo': {'full_name': 'testing/checkout_prs', 'html_url': GitRepositorySandbox.second_remote_path}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'}, 'number': '5', 'html_url': 'www.github.com', 'state': 'closed'}
    ])

    @mock.patch('git_machete.cli.exit_script', mock_exit_script)
    # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_checkout_prs` due to `git fetch` executed by `checkout-prs` subcommand.
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('git_machete.github.__get_github_token', mock__get_github_token)
    @mock.patch('urllib.request.Request', git_api_state_for_test_checkout_prs.new_request())
    @mock.patch('urllib.request.urlopen', MockContextManager)
    def test_github_checkout_prs(self) -> None:
        (
            self.repo_sandbox.new_branch("root")
            .commit("initial commit")
            .new_branch("develop")
            .commit("first commit")
            .push()
            .new_branch("enhance/feature")
            .commit("introduce feature")
            .push()
            .new_branch("bugfix/feature")
            .commit("bugs removed")
            .push()
            .new_branch("allow-ownership-link")
            .commit("fixes")
            .push()
            .new_branch('restrict_access')
            .commit('authorized users only')
            .push()
            .new_branch("chore/redundant_checks")
            .commit('remove some checks')
            .push()
            .check_out("root")
            .new_branch("master")
            .commit("Master commit")
            .push()
            .new_branch("hotfix/add-trigger")
            .commit("HOTFIX Add the trigger")
            .push()
            .new_branch("ignore-trailing")
            .commit("Ignore trailing data")
            .push()
            .delete_branch("root")
            .new_branch('chore/fields')
            .commit("remove outdated fields")
            .push()
            .check_out('develop')
            .new_branch('enhance/add_user')
            .commit('allow externals to add users')
            .push()
            .new_branch('bugfix/add_user')
            .commit('first round of fixes')
            .push()
            .new_branch('testing/add_user')
            .commit('add test set for add_user feature')
            .push()
            .new_branch('chore/comments')
            .commit('code maintenance')
            .push()
            .check_out('master')
        )
        for branch in ('chore/redundant_checks', 'restrict_access', 'allow-ownership-link', 'bugfix/feature', 'enhance/add_user', 'testing/add_user', 'chore/comments', 'bugfix/add_user'):
            self.repo_sandbox.execute(f"git branch -D {branch}")

        self.launch_command('discover')

        # not broken chain of pull requests (root found in dependency tree)
        self.launch_command('github', 'checkout-prs', '18')
        self.assert_command(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  PR #3 (github_user)
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
              |
              o-bugfix/feature  PR #6 (github_user)
                |
                o-allow-ownership-link  PR #12 (github_user)
                  |
                  o-restrict_access  PR #17 (github_user)
                    |
                    o-chore/redundant_checks *  PR #18 (github_user)
            """
        )
        # broken chain of pull requests (add new root)
        self.launch_command('github', 'checkout-prs', '24')
        self.assert_command(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  PR #3 (github_user)
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
              |
              o-bugfix/feature  PR #6 (github_user)
                |
                o-allow-ownership-link  PR #12 (github_user)
                  |
                  o-restrict_access  PR #17 (github_user)
                    |
                    o-chore/redundant_checks  PR #18 (github_user)

            bugfix/add_user
            |
            o-testing/add_user  PR #22 (github_user)
              |
              o-chore/comments *  PR #24 (github_user)
            """
        )

        # broken chain of pull requests (branches already added)
        self.launch_command('github', 'checkout-prs', '24')
        self.assert_command(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  PR #3 (github_user)
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
              |
              o-bugfix/feature  PR #6 (github_user)
                |
                o-allow-ownership-link  PR #12 (github_user)
                  |
                  o-restrict_access  PR #17 (github_user)
                    |
                    o-chore/redundant_checks  PR #18 (github_user)

            bugfix/add_user
            |
            o-testing/add_user  PR #22 (github_user)
              |
              o-chore/comments *  PR #24 (github_user)
            """
        )

        # all PRs
        self.launch_command('github', 'checkout-prs', '--all')
        self.assert_command(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing  PR #3 (github_user)
                |
                o-chore/fields

            develop
            |
            o-enhance/feature
            | |
            | o-bugfix/feature  PR #6 (github_user)
            |   |
            |   o-allow-ownership-link  PR #12 (github_user)
            |     |
            |     o-restrict_access  PR #17 (github_user)
            |       |
            |       o-chore/redundant_checks  PR #18 (github_user)
            |
            o-enhance/add_user  PR #19 (github_user)

            bugfix/add_user
            |
            o-testing/add_user  PR #22 (github_user)
              |
              o-chore/comments *  PR #24 (github_user)
            """
        )

        # check against wrong pr number
        repo: str
        org: str
        (org, repo) = get_parsed_github_remote_url(self.repo_sandbox.remote_path)
        expected_error_message = f"PR #100 is not found in repository `{org}/{repo}`"
        with pytest.raises(MacheteException) as e:
            self.launch_command('github', 'checkout-prs', '100')
        if e:
            assert e.value.parameter == expected_error_message, \
                'Verify that expected error message has appeared when given pull request to checkout does not exists.'

        with pytest.raises(MacheteException) as e:
            self.launch_command('github', 'checkout-prs', '19', '100')
        if e:
            assert e.value.parameter == expected_error_message, \
                'Verify that expected error message has appeared when one of the given pull requests to checkout does not exists.'

        # check against user with no open pull requests
        expected_msg = ("Checking for open GitHub PRs...\n"
                        f"Warn: User `tester` has no open pull request in repository `{org}/{repo}`\n")
        self.assert_command(['github', 'checkout-prs', '--by', 'tester'], expected_msg, strip_indentation=False)

        # Check against closed pull request with head branch deleted from remote
        local_path = popen("mktemp -d")
        self.repo_sandbox.new_repo(GitRepositorySandbox.second_remote_path)
        (self.repo_sandbox.new_repo(local_path)
            .execute(f"git remote add origin {GitRepositorySandbox.second_remote_path}")
            .execute('git config user.email "tester@test.com"')
            .execute('git config user.name "Tester Test"')
            .new_branch('main')
            .commit('initial commit')
            .push()
         )
        os.chdir(self.repo_sandbox.local_path)

        expected_error_message = "Could not check out PR #5 because its head branch `bugfix/remove-n-option` is already deleted from `testing`."
        with pytest.raises(MacheteException) as e:
            self.launch_command('github', 'checkout-prs', '5')
        if e:
            assert e.value.parameter == expected_error_message, \
                'Verify that expected error message has appeared when given pull request to checkout have already deleted branch from remote.'

        # Check against pr come from fork
        os.chdir(local_path)
        (self.repo_sandbox
         .new_branch('bugfix/remove-n-option')
         .commit('first commit')
         .push()
         )
        os.chdir(self.repo_sandbox.local_path)

        expected_msg = ("Checking for open GitHub PRs...\n"
                        "Warn: Pull request #5 is already closed.\n"
                        "Pull request `#5` checked out at local branch `bugfix/remove-n-option`\n")

        self.assert_command(['github', 'checkout-prs', '5'], expected_msg, strip_indentation=False)

        # Check against multiple PRs
        expected_msg = 'Checking for open GitHub PRs...\n'

        self.assert_command(['github', 'checkout-prs', '3', '12'], expected_msg, strip_indentation=False)

    git_api_state_for_test_github_checkout_prs_fresh_repo = MockGitHubAPIState([
        {'head': {'ref': 'comments/add_docstrings', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'improve/refactor'}, 'number': '2', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'restrict_access', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'allow-ownership-link'}, 'number': '17', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'improve/refactor', 'repo': mock_repository_info}, 'user': {'login': 'github_user'}, 'base': {'ref': 'chore/sync_to_docs'}, 'number': '1', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'sphinx_export', 'repo': {'full_name': 'testing/checkout_prs', 'html_url': GitRepositorySandbox.second_remote_path}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'comments/add_docstrings'}, 'number': '23', 'html_url': 'www.github.com', 'state': 'closed'}
    ])

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_checkout_prs_freshly_cloned` due to `git fetch` executed by `checkout-prs` subcommand.
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', git_api_state_for_test_github_checkout_prs_fresh_repo.new_request())
    def test_github_checkout_prs_freshly_cloned(self) -> None:
        (
            self.repo_sandbox.new_branch("root")
            .commit("initial commit")
            .new_branch("develop")
            .commit("first commit")
            .push()
            .new_branch("chore/sync_to_docs")
            .commit("synchronize docs")
            .push()
            .new_branch("improve/refactor")
            .commit("refactor code")
            .push()
            .new_branch("comments/add_docstrings")
            .commit("docstring added")
            .push()
            .new_branch("sphinx_export")
            .commit("export docs to html")
            .push()
            .check_out("root")
            .new_branch("master")
            .commit("Master commit")
            .push()
            .delete_branch("root")
            .push()
        )
        for branch in ('develop', 'chore/sync_to_docs', 'improve/refactor', 'comments/add_docstrings'):
            self.repo_sandbox.execute(f"git branch -D {branch}")
        local_path = popen("mktemp -d")
        os.chdir(local_path)
        self.repo_sandbox.execute(f'git clone {self.repo_sandbox.remote_path}')
        os.chdir(os.path.join(local_path, os.listdir()[0]))

        for branch in ('develop', 'chore/sync_to_docs', 'improve/refactor', 'comments/add_docstrings'):
            self.repo_sandbox.execute(f"git branch -D -r origin/{branch}")

        local_path = popen("mktemp -d")
        self.repo_sandbox.new_repo(GitRepositorySandbox.second_remote_path)
        (
            self.repo_sandbox.new_repo(local_path)
            .execute(f"git remote add origin {GitRepositorySandbox.second_remote_path}")
            .execute('git config user.email "tester@test.com"')
            .execute('git config user.name "Tester Test"')
            .new_branch('feature')
            .commit('initial commit')
            .push()
        )
        os.chdir(self.repo_sandbox.local_path)
        self.rewrite_definition_file("master")
        expected_msg = ("Checking for open GitHub PRs...\n"
                        "Pull request `#2` checked out at local branch `comments/add_docstrings`\n")
        self.assert_command(
            ['github', 'checkout-prs', '2'],
            expected_msg,
            strip_indentation=False
        )

        self.assert_command(
            ["status"],
            """
            master

            chore/sync_to_docs
            |
            o-improve/refactor  PR #1 (github_user)
              |
              o-comments/add_docstrings *  PR #2 (github_user)
            """
        )

        # Check against closed pull request
        self.repo_sandbox.execute('git branch -D sphinx_export')
        expected_msg = ("Checking for open GitHub PRs...\n"
                        "Warn: Pull request #23 is already closed.\n"
                        "Pull request `#23` checked out at local branch `sphinx_export`\n")

        self.assert_command(
            ['github', 'checkout-prs', '23'],
            expected_msg,
            strip_indentation=False
        )
        self.assert_command(
            ["status"],
            """
            master

            chore/sync_to_docs
            |
            o-improve/refactor  PR #1 (github_user)
              |
              o-comments/add_docstrings  PR #2 (github_user)
                |
                o-sphinx_export *
            """
        )

    git_api_state_for_test_github_checkout_prs_from_fork_with_deleted_repo = MockGitHubAPIState([
        {'head': {'ref': 'feature/allow_checkout', 'repo': None}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'}, 'number': '2', 'html_url': 'www.github.com', 'state': 'closed'},
        {'head': {'ref': 'bugfix/allow_checkout', 'repo': mock_repository_info}, 'user': {'login': 'github_user'},
         'base': {'ref': 'develop'}, 'number': '3', 'html_url': 'www.github.com', 'state': 'open'}
    ])

    @mock.patch('git_machete.git_operations.GitContext.fetch_ref', mock_fetch_ref)  # need to mock fetch_ref due to underlying `git fetch pull/head` calls
    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_checkout_prs_from_fork_with_deleted_repo` due to `git fetch` executed by `checkout-prs` subcommand.
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', git_api_state_for_test_github_checkout_prs_from_fork_with_deleted_repo.new_request())
    def test_github_checkout_prs_from_fork_with_deleted_repo(self) -> None:
        (
            self.repo_sandbox.new_branch("root")
            .commit('initial master commit')
            .push()
            .new_branch('develop')
            .commit('initial develop commit')
            .push()
        )
        self.launch_command('discover')
        expected_msg = ("Checking for open GitHub PRs...\n"
                        "Warn: Pull request #2 comes from fork and its repository is already deleted. No remote tracking data will be set up for `feature/allow_checkout` branch.\n"
                        "Warn: Pull request #2 is already closed.\n"
                        "Pull request `#2` checked out at local branch `feature/allow_checkout`\n")
        self.assert_command(
            ['github', 'checkout-prs', '2'],
            expected_msg,
            strip_indentation=False
        )

        assert 'feature/allow_checkout' == \
            self.launch_command("show", "current").strip(), \
            "Verify that 'git machete github checkout prs' performs 'git checkout' to " \
            "the head branch of given pull request."

    git_api_state_for_test_github_sync = MockGitHubAPIState([
        {'head': {'ref': 'snickers', 'repo': mock_repository_info}, 'user': {'login': 'other_user'},
         'base': {'ref': 'master'}, 'number': '7', 'html_url': 'www.github.com', 'state': 'open'}
    ])

    @mock.patch('git_machete.client.MacheteClient.should_perform_interactive_slide_out', mock_should_perform_interactive_slide_out)
    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)
    @mock.patch('git_machete.client.MacheteClient.ask_if', mock_ask_if)
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    @mock.patch('git_machete.github.__get_github_token', mock__get_github_token_fake)
    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', git_api_state_for_test_github_sync.new_request())
    def test_github_sync(self) -> None:
        (
            self.repo_sandbox
                .new_branch('master')
                .commit()
                .push()
                .new_branch('bar')
                .commit()
                .new_branch('bar2')
                .commit()
                .check_out("master")
                .new_branch('foo')
                .commit()
                .push()
                .new_branch('foo2')
                .commit()
                .check_out("master")
                .new_branch('moo')
                .commit()
                .new_branch('moo2')
                .commit()
                .check_out("master")
                .new_branch('snickers')
                .push()
        )
        self.launch_command('discover', '-y')
        (
            self.repo_sandbox
                .check_out("master")
                .new_branch('mars')
                .commit()
                .check_out("master")
        )
        self.launch_command('github', 'sync')

        expected_status_output = (
            """
            master *
            |
            o-bar (untracked)
            |
            o-foo
            |
            o-moo (untracked)
            |
            o-snickers  PR #7
            """
        )
        self.assert_command(['status'], expected_status_output)

        with pytest.raises(subprocess.CalledProcessError):
            self.repo_sandbox.check_out("mars")

    def test_squash_with_valid_fork_point(self) -> None:
        (
            self.repo_sandbox.new_branch('branch-0')
                .commit("First commit.")
                .commit("Second commit.")
        )
        fork_point = get_current_commit_hash()

        (
            self.repo_sandbox.commit("Third commit.")
                .commit("Fourth commit.")
        )

        self.launch_command('squash', '-f', fork_point)

        expected_branch_log = (
            "Third commit.\n"
            "Second commit.\n"
            "First commit."
        )

        current_branch_log = popen('git log -3 --format=%s')
        assert current_branch_log == \
            expected_branch_log, \
            ("Verify that `git machete squash -f <fork-point>` squashes commit"
                " from one succeeding the fork-point until tip of the branch.")

    def test_squash_with_invalid_fork_point(self) -> None:
        (
            self.repo_sandbox.new_branch('branch-0')
                .commit()
                .new_branch('branch-1a')
                .commit()
        )
        fork_point_to_branch_1a = get_current_commit_hash()

        (
            self.repo_sandbox.check_out('branch-0')
                .new_branch('branch-1b')
                .commit()
        )

        with pytest.raises(SystemExit):
            # First exception MacheteException is raised, followed by SystemExit.
            self.launch_command('squash', '-f', fork_point_to_branch_1a)

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd_and_forward_stdout)
    def test_slide_out_with_valid_down_fork_point(self) -> None:
        (
            self.repo_sandbox.new_branch('branch-0')
                .commit()
                .new_branch('branch-1')
                .commit()
                .new_branch('branch-2')
                .commit()
                .new_branch('branch-3')
                .commit()
                .commit('Second commit on branch-3.')
        )
        hash_of_second_commit_on_branch_3 = get_current_commit_hash()
        self.repo_sandbox.commit("Third commit on branch-3.")

        self.launch_command('discover', '-y')
        self.launch_command(
            'slide-out', '-n', 'branch-1', 'branch-2', '-d',
            hash_of_second_commit_on_branch_3)

        expected_status_output = (
            """
            branch-0 (untracked)
            |
            | Third commit on branch-3.
            o-branch-3 * (untracked)
            """
        )

        self.assert_command(['status', '-l'], expected_status_output)

    def test_slide_out_with_invalid_down_fork_point(self) -> None:
        (
            self.repo_sandbox.new_branch('branch-0')
                .commit()
                .new_branch('branch-1')
                .commit()
                .new_branch('branch-2')
                .commit()
                .new_branch('branch-3')
                .commit()
                .check_out('branch-2')
                .commit('Commit that is not ancestor of branch-3.')
        )
        hash_of_commit_that_is_not_ancestor_of_branch_2 = get_current_commit_hash()

        self.launch_command('discover', '-y')

        with pytest.raises(SystemExit):
            self.launch_command(
                'slide-out', '-n', 'branch-1', 'branch-2', '-d',
                hash_of_commit_that_is_not_ancestor_of_branch_2)

    def test_slide_out_with_down_fork_point_and_multiple_children_of_last_branch(self) -> None:
        (
            self.repo_sandbox.new_branch('branch-0')
                .commit()
                .new_branch('branch-1')
                .commit()
                .new_branch('branch-2a')
                .commit()
                .check_out('branch-1')
                .new_branch('branch-2b')
                .commit()
        )

        hash_of_only_commit_on_branch_2b = get_current_commit_hash()

        self.launch_command('discover', '-y')

        with pytest.raises(SystemExit):
            self.launch_command(
                'slide-out', '-n', 'branch-1', '-d',
                hash_of_only_commit_on_branch_2b)
