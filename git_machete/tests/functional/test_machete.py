import io
import json
import os
import random
import re
import string
import textwrap
import time
import unittest
import subprocess
from contextlib import redirect_stdout
from typing import Any, Dict, Iterable, List, Optional, Union
from unittest import mock
from urllib.parse import urlparse, ParseResult, parse_qs

from git_machete import cli
from git_machete.client import MacheteClient
from git_machete.exceptions import MacheteException
from git_machete.git_operations import GitContext
from git_machete.options import CommandLineOptions
from git_machete.utils import fmt

cli_opts: CommandLineOptions = CommandLineOptions()
git: GitContext = GitContext(cli_opts)


def get_head_commit_hash() -> str:
    """Returns hash of a commit of the current branch head."""
    return os.popen("git rev-parse HEAD").read().strip()


class FakeCommandLineOptions(CommandLineOptions):
    def __init__(self) -> None:
        super().__init__()
        self.opt_no_interactive_rebase: bool = True
        self.opt_yes: bool = True


class MockGitAPIState:
    def __init__(self) -> None:
        self.pulls: List[Dict[str, Any]] = [
            {'head': {'ref': 'bugfix/remove'}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'},
             'number': '15', 'html_url': 'www.github.com'}]
        self.user: Dict[str, str] = {'login': 'github_user', 'type': 'User', 'company': 'VirtusLab'}
        self.issues: List[Dict[str, Any]] = []

    def get_issue(self, issue_no: str) -> Optional[Dict[str, Any]]:
        for index, issue in enumerate(self.issues):
            if issue['number'] == issue_no:
                return self.issues.pop(index)
        return None

    def get_pull(self, pull_no: str) -> Optional[Dict[str, Any]]:
        for index, pull in enumerate(self.pulls):
            if pull['number'] == pull_no:
                return self.pulls.pop(index)
        return None

    def set_initial_values(self) -> None:
        self.pulls = [
            {'head': {'ref': 'bugfix/remove'}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'},
             'number': '15', 'html_url': 'www.github.com'}]
        self.user = {'login': 'github_user', 'type': 'User', 'company': 'VirtusLab'}
        self.issues = []


class MockGitAPIRequest:

    git_api_state: MockGitAPIState = MockGitAPIState()

    def __init__(self, url: str, headers: Dict[str, str] = None, data: Union[str, bytes, None] = None, method: str = ''):
        self.parsed_url: ParseResult = urlparse(url, allow_fragments=True)
        self.parsed_query = parse_qs(self.parsed_url.query)
        self.status_code: Optional[int] = None
        self.json_data: Union[str, bytes] = data
        self.return_data: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
        self.headers: Dict[str, str] = headers
        self.handle_method(method)

    def handle_method(self, method: str) -> None:
        if method == "GET":
            self.handle_get()
        elif method == "PATCH":
            self.handle_patch()
        elif method == "POST":
            self.handle_post()

    def read(self) -> Union[str, bytes]:
        return json.dumps(self.return_data).encode()

    def handle_get(self) -> None:
        if self.parsed_url.path.endswith('pulls'):
            full_head_name: Optional[List[str]] = self.parsed_query.get('head')
            if full_head_name:
                head: str = full_head_name[0]
                head_name: str = head[head.rfind(':') + 1:]
                for pr in MockGitAPIRequest.git_api_state.pulls:
                    if pr['head']['ref'] == head_name:
                        self.return_data = [pr]
                        self.status_code = 200
                        return
                self.return_data = []
                self.status_code = 404
                return
            else:
                self.status_code = 200
                self.return_data = MockGitAPIRequest.git_api_state.pulls
                return
        elif self.parsed_url.path.endswith('user'):
            self.status_code = 200
            self.return_data = MockGitAPIRequest.git_api_state.user
            return

    def handle_patch(self) -> None:
        if 'issues' in self.parsed_url.path:
            self.update_issue()
        elif 'pulls' in self.parsed_url.path:
            self.update_pull()

    def handle_post(self) -> None:
        if self.parsed_url.path.endswith('issues'):
            if not self.parsed_query:
                self.update_issue(new=True)
        elif self.parsed_url.path.endswith('pulls'):
            if not self.parsed_query:
                self.update_pull(new=True)

    def update_pull(self, new: bool = False) -> None:
        pull: Dict[str, Any]
        if new:
            pull = {'number': self.get_next_free_number(MockGitAPIRequest.git_api_state.pulls),
                    'user': {'login': 'github_user'},
                    'html_url': 'www.github.com'}
        else:
            pull_no: str = self.find_number(self.parsed_url.path)
            pull = MockGitAPIRequest.git_api_state.get_pull(pull_no)
        for key in json.loads(self.json_data).keys():
            if key in ('base', 'head'):
                pull[key] = {'ref': ""}
                pull[key]['ref'] = json.loads(self.json_data)[key]
            else:
                pull[key] = json.loads(self.json_data)[key]
        MockGitAPIRequest.git_api_state.pulls.append(pull)
        self.status_code = 201
        self.return_data = pull

    def update_issue(self, new: bool = False) -> None:
        issue: Dict[str, Any]
        if new:
            issue = {'number': self.get_next_free_number(MockGitAPIRequest.git_api_state.issues)}
        else:
            issue_no = self.find_number(self.parsed_url.path)
            issue = MockGitAPIRequest.git_api_state.get_issue(issue_no)
        for key in json.loads(self.json_data).keys():
            issue[key] = json.loads(self.json_data)[key]
        MockGitAPIRequest.git_api_state.issues.append(issue)
        self.status_code = 201
        self.return_data = issue
        return

    @staticmethod
    def find_number(url: str) -> str:
        m = re.search(r'\d+', url)
        return m.group()

    @staticmethod
    def get_next_free_number(entities: List[Dict[str, Any]]) -> str:
        numbers = [int(item['number']) for item in entities]
        return str(max(numbers) + 1)


class MockContextManager:
    def __init__(self, obj: MockGitAPIRequest) -> None:
        self.obj = obj

    def __enter__(self) -> MockGitAPIRequest:
        return self.obj

    def __exit__(self, *args: Any) -> None:
        pass


class GitRepositorySandbox:
    def __init__(self) -> None:
        self.remote_path = os.popen("mktemp -d").read().strip()
        self.local_path = os.popen("mktemp -d").read().strip()

    def execute(self, command: str) -> "GitRepositorySandbox":
        subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
        return self

    def new_repo(self, *args: str) -> "GitRepositorySandbox":
        os.chdir(args[0])
        opts = args[1:]
        self.execute(f"git init {' '.join(opts)}")
        return self

    def new_branch(self, branch_name: str) -> "GitRepositorySandbox":
        self.execute(f"git checkout -b {branch_name}")
        return self

    def new_root_branch(self, branch_name: str) -> "GitRepositorySandbox":
        self.execute(f"git checkout --orphan {branch_name}")
        return self

    def check_out(self, branch: str) -> "GitRepositorySandbox":
        self.execute(f"git checkout {branch}")
        return self

    def commit(self, message: str = "Some commit message.") -> "GitRepositorySandbox":
        f = "%s.txt" % "".join(random.choice(string.ascii_letters) for _ in range(20))
        self.execute(f"touch {f}")
        self.execute(f"git add {f}")
        self.execute(f'git commit -m "{message}"')
        return self

    def commit_amend(self, message: str) -> "GitRepositorySandbox":
        self.execute(f'git commit --amend -m "{message}"')
        return self

    def push(self) -> "GitRepositorySandbox":
        branch = os.popen("git symbolic-ref -q --short HEAD").read()
        self.execute(f"git push -u origin {branch}")
        return self

    def sleep(self, seconds: int) -> "GitRepositorySandbox":
        time.sleep(seconds)
        return self

    def reset_to(self, revision: str) -> "GitRepositorySandbox":
        self.execute(f'git reset --keep "{revision}"')
        return self

    def delete_branch(self, branch: str) -> "GitRepositorySandbox":
        self.execute(f'git branch -d "{branch}"')
        return self

    def add_remote(self, remote: str, url: str) -> "GitRepositorySandbox":
        self.execute(f'git remote add {remote} {url}')
        return self


class MacheteTester(unittest.TestCase):
    @staticmethod
    def adapt(s: str) -> str:
        return textwrap.indent(textwrap.dedent(re.sub(r"\|\n", "| \n", s[1:])), "  ")

    @staticmethod
    def launch_command(*args: str) -> str:
        with io.StringIO() as out:
            with redirect_stdout(out):
                cli.launch(list(args))
                git.flush_caches()
            return out.getvalue()

    @staticmethod
    def rewrite_definition_file(new_body: str) -> None:
        definition_file_path = git.get_git_subpath("machete")
        with open(os.path.join(os.getcwd(), definition_file_path), 'w') as def_file:
            def_file.writelines(new_body)

    def assert_command(self, cmds: Iterable[str], expected_result: str, strip_indentation: bool = True) -> None:
        self.assertEqual(self.launch_command(*cmds), self.adapt(expected_result) if strip_indentation else expected_result)

    def setUp(self) -> None:
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

    def test_branch_reappers_in_definition(self) -> None:
        body: str = \
            """master
            \tdevelop
            \t\n
            develop
            """
        expected_error_msg: str = fmt('.git/machete, line 5: branch `develop` re-appears in the tree definition. Edit the definition file manually with `git machete edit`')

        self.repo_sandbox.new_branch("root")
        self.rewrite_definition_file(body)

        machete_client = MacheteClient(cli_opts, git)  # Only to workaround sys.exit while calling launch(['status'])
        try:
            machete_client.read_definition_file()
        except MacheteException as e:
            if e.parameter != expected_error_msg:
                self.fail(f'Actual Exception message: {e} \nis not equal to expected message: {expected_error_msg}')

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

    def test_help(self) -> None:
        self.launch_command("help")
        for (description, commands) in cli.command_groups:
            for command in commands:
                self.launch_command("help", command)

                if command not in ("format", "hooks"):
                    try:
                        self.launch_command(command, "--help")
                    except SystemExit as e:
                        self.assertIs(e.code, None)
                    except Exception as e:
                        self.fail(f'Unexpected exception raised: {e}')
                    else:
                        self.fail('SystemExit expected but not raised')

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

        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go up' performs 'git checkout' to "
                "the parent/upstream branch of the current branch."
        )

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

        self.assertEqual(
            'level-1-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go down' performs 'git checkout' to "
                "the child/downstream branch of the current branch."
        )

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

        self.assertEqual(
            'level-1a-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go first' performs 'git checkout' to"
                "the first downstream branch of a root branch if root branch "
                "has any downstream branches."
        )

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

        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go first' set current branch to root"
                "if root branch has no downstream."
        )

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

        self.assertEqual(
            'level-1b-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go last' performs 'git checkout' to"
                "the last downstream branch of a root branch if root branch "
                "has any downstream branches."
        )

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

        self.assertEqual(
            'level-1b-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go next' performs 'git checkout' to"
                "the next downstream branch right after the current one in the"
                "config file if successor branch exists."
        )

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
        self.assertEqual(
            'x-additional-root',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go next' can checkout to branch that doesn't"
                "share root with the current branch.")

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

        self.assertEqual(
            'level-2a-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go prev' performs 'git checkout' to"
                "the branch right before the current one in the config file"
                "when predecessor branch exists within the root tree."
        )

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
        self.assertEqual(
            'a-additional-root',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go prev' can checkout to branch that doesn't"
                "share root with the current branch.")

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

        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go root' performs 'git checkout' to"
                "the root of the current branch."
        )

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

        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "up").strip(),
            msg="Verify that 'git machete show up' displays name of a parent/upstream"
                "branch one above current one."
        )

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

        self.assertEqual(
            'level-1-branch',
            self.launch_command("show", "down").strip(),
            msg="Verify that 'git machete show down' displays name of "
                "a child/downstream branch one below current one."
        )

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

        self.assertEqual(
            'level-1a-branch',
            self.launch_command("show", "first").strip(),
            msg="Verify that 'git machete show first' displays name of the first downstream"
                "branch of a root branch of the current branch in the config file if root"
                "branch has any downstream branches."
        )

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

        self.assertEqual(
            'level-1b-branch',
            self.launch_command("show", "last").strip(),
            msg="Verify that 'git machete show last' displays name of the last downstream"
                "branch of a root branch of the current branch in the config file if root"
                "branch has any downstream branches."
        )

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

        self.assertEqual(
            'level-1b-branch',
            self.launch_command("show", "next").strip(),
            msg="Verify that 'git machete show next' displays name of "
                "a branch right after the current one in the config file"
                "when successor branch exists within the root tree."
        )

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

        self.assertEqual(
            'level-2a-branch',
            self.launch_command("show", "prev").strip(),
            msg="Verify that 'git machete show prev' displays name of"
                "a branch right before the current one in the config file"
                "when predecessor branch exists within the root tree."
        )

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

        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "root").strip(),
            msg="Verify that 'git machete show root' displays name of the root of"
                "the current branch."
        )

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

        with self.assertRaises(
                SystemExit,
                msg="Verify that 'git machete advance' raises an error when current branch"
                    "has no downstream branches."):
            self.launch_command("advance")

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
        level_1_commit_hash = get_head_commit_hash()

        self.repo_sandbox.check_out("root")
        self.launch_command("advance", "-y")

        root_top_commit_hash = get_head_commit_hash()

        self.assertEqual(
            level_1_commit_hash,
            root_top_commit_hash,
            msg="Verify that when there is only one, rebased downstream branch of a"
                "current branch 'git machete advance' merges commits from that branch"
                "and slides out child branches of the downstream branch."
        )
        self.assertNotIn(
            "level-1-branch",
            self.launch_command("status"),
            msg="Verify that branch to which advance was performed is removed "
                "from the git-machete tree and the structure of the git machete "
                "tree is updated.")

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

        with self.assertRaises(
                SystemExit,
                msg="Verify that 'git machete advance' raises an error when current branch"
                    "has more than one synchronized downstream branch."):
            self.launch_command("advance", '-y')

    def test_update_with_fork_point_not_specified(self) -> None:
        """Verify behaviour of a 'git machete update --no-interactive rebase' command.

        Verify that 'git machete update --no-interactive rebase' performs
        'git rebase' to the parent branch of the current branch.

        """
        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit("Basic commit.")
            .new_branch("level-1-branch")
            .commit("Only level-1 commit.")
            .new_branch("level-2-branch")
            .commit("Only level-2 commit.")
            .check_out("level-0-branch")
            .commit("New commit on level-0-branch")
        )
        self.launch_command("discover", "-y")

        parents_new_commit_hash = get_head_commit_hash()
        self.repo_sandbox.check_out("level-1-branch")
        self.launch_command("update", "--no-interactive-rebase")
        new_forkpoint_hash = self.launch_command("fork-point").strip()

        self.assertEqual(
            parents_new_commit_hash,
            new_forkpoint_hash,
            msg="Verify that 'git machete update --no-interactive rebase' perform"
                "'git rebase' to the parent branch of the current branch."
        )

    def test_update_with_fork_point_specified(self) -> None:
        """Verify behaviour of a 'git machete update --no-interactive rebase -f <commit_hash>' cmd.

        Verify that 'git machete update --no-interactive rebase -f <commit_hash>'
        performs 'git rebase' to the upstream branch and drops the commits until
        (included) fork point specified by the option '-f'.

        """
        branchs_first_commit_msg = "First commit on branch."
        branchs_second_commit_msg = "Second commit on branch."
        (
            self.repo_sandbox.new_branch("root")
            .commit("First commit on root.")
            .new_branch("branch-1")
            .commit(branchs_first_commit_msg)
            .commit(branchs_second_commit_msg)
        )
        branch_second_commit_hash = get_head_commit_hash()
        (
            self.repo_sandbox.commit("Third commit on branch.")
            .check_out("root")
            .commit("Second commit on root.")
        )
        roots_second_commit_hash = get_head_commit_hash()
        self.repo_sandbox.check_out("branch-1")
        self.launch_command("discover", "-y")

        self.launch_command(
            "update", "--no-interactive-rebase", "-f", branch_second_commit_hash)
        new_forkpoint_hash = self.launch_command("fork-point").strip()
        branch_history = os.popen('git log -10 --oneline').read()

        self.assertEqual(
            roots_second_commit_hash,
            new_forkpoint_hash,
            msg="Verify that 'git machete update --no-interactive rebase -f "
                "<commit_hash>' performs 'git rebase' to the upstream branch."
        )

        self.assertNotIn(
            branchs_first_commit_msg,
            branch_history,
            msg="Verify that 'git machete update --no-interactive rebase -f "
                "<commit_hash>' drops the commits until (included) fork point "
                "specified by the option '-f' from the current branch."
        )

        self.assertNotIn(
            branchs_second_commit_msg,
            branch_history,
            msg="Verify that 'git machete update --no-interactive rebase -f "
                "<commit_hash>' drops the commits until (included) fork point "
                "specified by the option '-f' from the current branch."
        )

    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', MockGitAPIRequest)
    def test_retarget_pr(self) -> None:
        MockGitAPIRequest.git_api_state.set_initial_values()
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
        MockGitAPIRequest.git_api_state.pulls = [{'head': {'ref': 'feature'}, 'user': {'login': 'github_user'}, 'base': {'ref': 'root'}, 'number': '15', 'html_url': 'www.github.com'}]
        self.launch_command("discover", "-y")
        self.assert_command(['github', 'retarget-pr'], 'The base branch of PR #15 has been switched to `branch-1`\n', strip_indentation=False)
        self.assert_command(['github', 'retarget-pr'], 'The base branch of PR #15 is already `branch-1`\n', strip_indentation=False)

    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', MockGitAPIRequest)
    def test_anno_prs(self) -> None:
        MockGitAPIRequest.git_api_state.set_initial_values()
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
        MockGitAPIRequest.git_api_state.pulls = [
            {'head': {'ref': 'ignore-trailing'}, 'user': {'login': 'github_user'}, 'base': {'ref': 'hotfix/add-trigger'}, 'number': '3', 'html_url': 'www.github.com'},
            {'head': {'ref': 'allow-ownership-link'}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'}, 'number': '7', 'html_url': 'www.github.com'},
            {'head': {'ref': 'call-ws'}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'}, 'number': '31', 'html_url': 'www.github.com'}
        ]
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

    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', MockGitAPIRequest)
    def test_github_create_pr(self) -> None:
        MockGitAPIRequest.git_api_state.set_initial_values()
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
                .add_remote('new_origin', 'https://github.com/user/repo.git')
                .check_out("call-ws")
        )
        MockGitAPIRequest.git_api_state.pulls = [{'head': {'ref': 'ignore-trailing'}, 'user': {'login': 'github_user'}, 'base': {'ref': 'hotfix/add-trigger'}, 'number': '3', 'html_url': 'www.github.com'}]
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
        # check against attempt to create already existing pull request
        machete_client = MacheteClient(cli_opts, git)
        expected_error_message = "Pull request for branch hotfix/add-trigger is already created under link www.github.com!\nPR details: PR #6 by github_user: hotfix/add-trigger -> master"
        machete_client.read_definition_file()
        with self.assertRaises(MacheteException) as e:
            machete_client.create_github_pr('hotfix/add-trigger', draft=False)
        if e:
            self.assertEqual(e.exception.parameter, expected_error_message,
                             'Verify that expected error message has appeared when given pull request to create is already created.')
