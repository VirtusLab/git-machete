import io
import os
import random
import re
import string
import textwrap
import time
import unittest
from contextlib import redirect_stdout
from typing import Iterable

from git_machete import cmd
from git_machete.git_operations import GitContext
from git_machete.options import CommandLineOptions

cli_opts: CommandLineOptions = CommandLineOptions()
git: GitContext = GitContext(cli_opts)


class SandboxSetup:
    def __init__(self) -> None:
        self.file_dir = os.path.dirname(os.path.abspath(__file__))
        self.remote_path = os.popen("mktemp -d").read().strip()
        self.sandbox_path = os.popen("mktemp -d").read().strip()

    def execute(self, command: str) -> "SandboxSetup":
        result = os.system(command)
        assert result == 0, f"{command} returned {result}"
        return self

    def new_repo(self, *args: str) -> "SandboxSetup":
        os.chdir(args[0])
        if len(args) > 1:
            opt = args[1]
            self.execute(f"git init {opt}")
        else:
            self.execute("git init")
        return self

    def new_branch(self, branch_name: str) -> "SandboxSetup":
        self.execute(f"git checkout -q -b {branch_name}")
        return self

    def check_out(self, branch: str) -> "SandboxSetup":
        self.execute(f"git checkout -q {branch}")
        return self

    def commit(self, message: str) -> "SandboxSetup":
        f = "%s.txt" % "".join(random.choice(string.ascii_letters) for _ in range(20))
        self.execute(f"touch {f}")
        self.execute(f"git add {f}")
        self.execute(f'git commit -q -m "{message}"')
        return self

    def commit_amend(self, message: str) -> "SandboxSetup":
        self.execute(f'git commit -q --amend -m "{message}"')
        return self

    def push(self) -> "SandboxSetup":
        branch = os.popen("git symbolic-ref --short HEAD").read()
        self.execute(f"git push -q -u origin {branch}")
        return self

    def sleep(self, seconds: int) -> "SandboxSetup":
        time.sleep(seconds)
        return self

    def reset_to(self, revision: str) -> "SandboxSetup":
        self.execute(f'git reset --keep "{revision}"')
        return self

    def delete_branch(self, branch: str) -> "SandboxSetup":
        self.execute(f'git branch -d "{branch}"')
        return self


class MacheteTester(unittest.TestCase):
    @staticmethod
    def adapt(s: str) -> str:
        return textwrap.indent(textwrap.dedent(re.sub(r"\|\n", "| \n", s[1:])), "  ")

    @staticmethod
    def launch_command(*args: str) -> str:
        with io.StringIO() as out:
            with redirect_stdout(out):
                cmd.launch(list(args))
                git.flush_caches()
            return out.getvalue()

    def assert_command(self, cmd: Iterable[str], expected_result: str) -> None:
        self.assertEqual(self.launch_command(*cmd), self.adapt(expected_result))

    def setUp(self) -> None:
        # Status diffs can be quite large, default to ~256 lines of diff context
        # https://docs.python.org/3/library/unittest.html#unittest.TestCase.maxDiff
        self.maxDiff = 80 * 256

        self.setup = SandboxSetup()

        (
            self.setup
            # Create the remote and sandbox repos, chdir into sandbox repo
            .new_repo(self.setup.remote_path, "--bare")
            .new_repo(self.setup.sandbox_path)
            .execute(f"git remote add origin {self.setup.remote_path}")
            .execute('git config user.email "tester@test.com"')
            .execute('git config user.name "Tester Test"')
        )

    def setup_discover_standard_tree(self) -> None:
        (
            self.setup.new_branch("root")
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

    def test_show(self) -> None:
        self.setup_discover_standard_tree()

        self.assertEqual(
            self.launch_command(
                "show", "up",
            ).strip(),
            "hotfix/add-trigger"
        )

        self.assertEqual(
            self.launch_command(
                "show", "up", "call-ws",
            ).strip(),
            "develop"
        )

        self.assertEqual(
            self.launch_command(
                "show", "current"
            ).strip(),
            "ignore-trailing"
        )

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

    def test_traverse_no_push_override(self) -> None:
        self.setup_discover_standard_tree()

        self.launch_command("traverse", "-Wy", "--no-push", "--push")
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

    def test_slide_out(self) -> None:
        (
            self.setup.new_branch("develop")
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

    def test_squash_merge(self) -> None:
        repo = (
            self.setup.new_branch("root")
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
        repo = (
            repo.check_out("develop")
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
        repo = (
            repo.check_out("develop")
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

    def test_help(self) -> None:
        self.launch_command("help")
        for (description, commands) in cmd.command_groups:
            for command in commands:
                self.launch_command("help", command)
