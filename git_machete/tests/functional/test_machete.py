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
import sys
from contextlib import redirect_stdout, redirect_stderr
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Union
from unittest import mock
from urllib.parse import urlparse, ParseResult, parse_qs
from urllib.error import HTTPError

from git_machete import cli
from git_machete.client import MacheteClient
from git_machete.exceptions import MacheteException
from git_machete.github import get_parsed_github_remote_url
from git_machete.git_operations import GitContext
from git_machete.options import CommandLineOptions
from git_machete.utils import dim, fmt

cli_opts: CommandLineOptions = CommandLineOptions()
git: GitContext = GitContext(cli_opts)

FAKE_GITHUB_REMOTE_PATTERNS = ['(.*)/(.*)']


def get_head_commit_hash() -> str:
    """Returns hash of a commit of the current branch head."""
    with os.popen("git rev-parse HEAD") as git_call:
        return git_call.read().strip()


def mock_run_cmd(cmd: str, *args: str, **kwargs: Any) -> int:
    completed_process: subprocess.CompletedProcess[bytes] = subprocess.run([cmd] + list(args), stdout=subprocess.PIPE,
                                                                           stderr=subprocess.PIPE, **kwargs)
    exit_code: int = completed_process.returncode
    if exit_code != 0:
        sys.stderr.write(dim(f"<exit code: {exit_code}>\n\n"))
    return exit_code


def mock_derive_current_user_login() -> str:
    return "very_complex_user_token"


class FakeCommandLineOptions(CommandLineOptions):
    def __init__(self) -> None:
        super().__init__()
        self.opt_no_interactive_rebase: bool = True
        self.opt_yes: bool = True


class MockGithubAPIState:
    def __init__(self, pulls: List[Dict[str, Any]], issues: List[Dict[str, Any]] = None) -> None:
        self.pulls: List[Dict[str, Any]] = pulls
        self.user: Dict[str, str] = {'login': 'other_user', 'type': 'User', 'company': 'VirtusLab'}  # login must be different from the one used in pull requests, otherwise pull request author will not be annotated
        self.issues: List[Dict[str, Any]] = issues or []

    def new_request(self) -> "MockGithubAPIRequest":
        return MockGithubAPIRequest(self)

    def get_issue(self, issue_no: str) -> Optional[Dict[str, Any]]:
        for issue in self.issues:
            if issue['number'] == issue_no:
                return issue
        return None

    def get_pull(self, pull_no: str) -> Optional[Dict[str, Any]]:
        for pull in self.pulls:
            if pull['number'] == pull_no:
                return pull
        return None


class MockGithubAPIResponse:
    def __init__(self, status_code: int, response_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> None:
        self.response_data: Union[List[Dict[str, Any]], Dict[str, Any]] = response_data
        self.status_code: int = status_code

    def read(self) -> bytes:
        return json.dumps(self.response_data).encode()


class MockGithubAPIRequest:
    def __init__(self, github_api_state: MockGithubAPIState) -> None:
        self.github_api_state: MockGithubAPIState = github_api_state

    def __call__(self, url: str, headers: Dict[str, str] = None, data: Union[str, bytes, None] = None, method: str = '') -> "MockGithubAPIResponse":
        self.parsed_url: ParseResult = urlparse(url, allow_fragments=True)
        self.parsed_query: Dict[str, List[str]] = parse_qs(self.parsed_url.query)
        self.json_data: Union[str, bytes] = data
        self.return_data: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
        self.headers: Dict[str, str] = headers
        return self.handle_method(method)

    def handle_method(self, method: str) -> "MockGithubAPIResponse":
        if method == "GET":
            return self.handle_get()
        elif method == "PATCH":
            return self.handle_patch()
        elif method == "POST":
            return self.handle_post()
        else:
            return self.make_response_object(HTTPStatus.METHOD_NOT_ALLOWED, [])

    def handle_get(self) -> "MockGithubAPIResponse":
        if 'pulls' in self.parsed_url.path:
            full_head_name: Optional[List[str]] = self.parsed_query.get('head')
            number: Optional[str] = self.find_number(self.parsed_url.path, 'pulls')
            if number:
                for pr in self.github_api_state.pulls:
                    if pr['number'] == number:
                        return self.make_response_object(HTTPStatus.OK, pr)
                return self.make_response_object(HTTPStatus.NOT_FOUND, [])
            elif full_head_name:
                head: str = full_head_name[0].split(':')[1]
                for pr in self.github_api_state.pulls:
                    if pr['head']['ref'] == head:
                        return self.make_response_object(HTTPStatus.OK, [pr])
                return self.make_response_object(HTTPStatus.NOT_FOUND, [])
            else:
                return self.make_response_object(HTTPStatus.OK, self.github_api_state.pulls)
        elif self.parsed_url.path.endswith('user'):
            return self.make_response_object(HTTPStatus.OK, self.github_api_state.user)
        else:
            return self.make_response_object(HTTPStatus.NOT_FOUND, [])

    def handle_patch(self) -> "MockGithubAPIResponse":
        if 'issues' in self.parsed_url.path:
            return self.update_issue()
        elif 'pulls' in self.parsed_url.path:
            return self.update_pull_request()
        else:
            return self.make_response_object(HTTPStatus.NOT_FOUND, [])

    def handle_post(self) -> "MockGithubAPIResponse":
        assert not self.parsed_query
        if 'issues' in self.parsed_url.path:
            return self.update_issue()
        elif 'pulls' in self.parsed_url.path:
            return self.update_pull_request()
        else:
            return self.make_response_object(HTTPStatus.NOT_FOUND, [])

    def update_pull_request(self) -> "MockGithubAPIResponse":
        pull_no: str = self.find_number(self.parsed_url.path, 'pulls')
        if not pull_no:
            return self.create_pull_request()
        pull: Dict[str, Any] = self.github_api_state.get_pull(pull_no)
        return self.fill_pull_request_data(json.loads(self.json_data), pull)

    def create_pull_request(self) -> "MockGithubAPIResponse":
        pull = {'number': self.get_next_free_number(self.github_api_state.pulls),
                'user': {'login': 'github_user'},
                'html_url': 'www.github.com',
                'state': 'open',
                'head': {'ref': "", 'repo': {'full_name': 'testing:checkout_prs', 'html_url': os.popen("mktemp -d").read().strip()}},
                'base': {'ref': ""}}
        return self.fill_pull_request_data(json.loads(self.json_data), pull)

    def fill_pull_request_data(self, data: Dict[str, Any], pull: Dict[str, Any]) -> "MockGithubAPIResponse":
        index = self.get_index_or_none(pull, self.github_api_state.issues)
        for key in data.keys():
            if key in ('base', 'head'):
                pull[key]['ref'] = json.loads(self.json_data)[key]
                pull[key]['ref'] = json.loads(self.json_data)[key]
            else:
                pull[key] = json.loads(self.json_data)[key]
        if index:
            self.github_api_state.pulls[index] = pull
        else:
            self.github_api_state.pulls.append(pull)
        return self.make_response_object(HTTPStatus.CREATED, pull)

    def update_issue(self) -> "MockGithubAPIResponse":
        issue_no: str = self.find_number(self.parsed_url.path, 'issues')
        if not issue_no:
            return self.create_issue()
        issue: Dict[str, Any] = self.github_api_state.get_issue(issue_no)
        return self.fill_issue_data(json.loads(self.json_data), issue)

    def create_issue(self) -> "MockGithubAPIResponse":
        issue = {'number': self.get_next_free_number(self.github_api_state.issues)}
        return self.fill_issue_data(json.loads(self.json_data), issue)

    def fill_issue_data(self, data: Dict[str, Any], issue: Dict[str, Any]) -> "MockGithubAPIResponse":
        index = self.get_index_or_none(issue, self.github_api_state.issues)
        for key in data.keys():
            issue[key] = data[key]
        if index is not None:
            self.github_api_state.issues[index] = issue
        else:
            self.github_api_state.issues.append(issue)
        return self.make_response_object(HTTPStatus.CREATED, issue)

    @staticmethod
    def get_index_or_none(entity: Dict[str, Any], base: List[Dict[str, Any]]) -> Optional[int]:
        try:
            return base.index(entity)
        except ValueError:
            return None

    @staticmethod
    def make_response_object(status_code: int, response_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> "MockGithubAPIResponse":
        return MockGithubAPIResponse(status_code, response_data)

    @staticmethod
    def find_number(url: str, entity: str) -> Optional[str]:
        m = re.search(f'{entity}/(\\d+)', url)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def get_next_free_number(entities: List[Dict[str, Any]]) -> str:
        numbers = [int(item['number']) for item in entities]
        return str(max(numbers) + 1)


class MockContextManager:
    def __init__(self, obj: MockGithubAPIResponse) -> None:
        self.obj = obj

    def __enter__(self) -> MockGithubAPIResponse:
        if self.obj.status_code == HTTPStatus.NOT_FOUND:
            raise HTTPError(None, 404, 'Not found', None, None)
        return self.obj

    def __exit__(self, *args: Any) -> None:
        pass


class GitRepositorySandbox:
    second_remote_path = os.popen("mktemp -d").read().strip()

    def __init__(self) -> None:
        with os.popen("mktemp -d") as temp_remote_folder:
            self.remote_path = temp_remote_folder.read().strip()
        with os.popen("mktemp -d") as temp_local_folder:
            self.local_path = temp_local_folder.read().strip()

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
        with os.popen("git symbolic-ref -q --short HEAD") as git_call:
            branch = git_call.read()
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
                with redirect_stderr(out):
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

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
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

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
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
    def test_help(self) -> None:
        self.launch_command("help")
        for (description, commands) in cli.command_groups:
            for command in commands:
                self.launch_command("help", command)

                if command not in {"format", "hooks"}:
                    try:
                        self.launch_command(command, "--help")
                    except SystemExit as e:
                        self.assertIs(e.code, 0)
                    except Exception as e:
                        self.fail(f'Unexpected exception raised: {e}')
                    else:
                        self.fail('SystemExit expected but not raised')

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

        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go up' performs 'git checkout' to "
                "the parent/upstream branch of the current branch."
        )
        # check short command behaviour
        self.repo_sandbox.check_out("level-1-branch")
        self.launch_command("g", "u")
        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete g u' performs 'git checkout' to "
                "the parent/upstream branch of the current branch."
        )

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

        self.assertEqual(
            'level-1-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go down' performs 'git checkout' to "
                "the child/downstream branch of the current branch."
        )
        # check short command behaviour
        self.repo_sandbox.check_out("level-0-branch")
        self.launch_command("g", "d")

        self.assertEqual(
            'level-1-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete g d' performs 'git checkout' to "
                "the child/downstream branch of the current branch.")

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

        self.assertEqual(
            'level-1a-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go first' performs 'git checkout' to"
                "the first downstream branch of a root branch if root branch "
                "has any downstream branches."
        )

        # check short command behaviour
        self.repo_sandbox.check_out("level-3b-branch")
        self.launch_command("g", "f")

        self.assertEqual(
            'level-1a-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete g d' performs 'git checkout' to "
                "the child/downstream branch of the current branch.")

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

        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go first' set current branch to root"
                "if root branch has no downstream."
        )

        # check short command behaviour
        self.launch_command("g", "f")

        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete g f' set current branch to root"
                "if root branch has no downstream."
        )

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

        self.assertEqual(
            'level-1b-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go last' performs 'git checkout' to"
                "the last downstream branch of a root branch if root branch "
                "has any downstream branches."
        )

        # check short command behaviour
        self.repo_sandbox.check_out("level-1a-branch")
        self.launch_command("g", "l")

        self.assertEqual(
            'level-1b-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete g l' performs 'git checkout' to"
                "the last downstream branch of a root branch if root branch "
                "has any downstream branches."
        )

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

        self.assertEqual(
            'level-1b-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go next' performs 'git checkout' to"
                "the next downstream branch right after the current one in the"
                "config file if successor branch exists."
        )
        # check short command behaviour
        self.repo_sandbox.check_out("level-2a-branch")
        self.launch_command("g", "n")

        self.assertEqual(
            'level-1b-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete g n' performs 'git checkout' to"
                "the next downstream branch right after the current one in the"
                "config file if successor branch exists."
        )

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
        self.assertEqual(
            'x-additional-root',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go next' can checkout to branch that doesn't"
                "share root with the current branch.")

        # check short command behaviour
        self.repo_sandbox.check_out("level-1-branch")
        self.launch_command("g", "n")
        self.assertEqual(
            'x-additional-root',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete g n' can checkout to branch that doesn't"
                "share root with the current branch.")

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

        self.assertEqual(
            'level-2a-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go prev' performs 'git checkout' to"
                "the branch right before the current one in the config file"
                "when predecessor branch exists within the root tree."
        )
        # check short command behaviour
        self.repo_sandbox.check_out("level-1b-branch")
        self.launch_command("g", "p")

        self.assertEqual(
            'level-2a-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete g p' performs 'git checkout' to"
                "the branch right before the current one in the config file"
                "when predecessor branch exists within the root tree."
        )

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
        self.assertEqual(
            'a-additional-root',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go prev' can checkout to branch that doesn't"
                "share root with the current branch.")

        # check short command behaviour
        self.repo_sandbox.check_out("level-0-branch")
        self.launch_command("g", "p")
        self.assertEqual(
            'a-additional-root',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete g p' can checkout to branch that doesn't"
                "share root with the current branch.")

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

        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete go root' performs 'git checkout' to"
                "the root of the current branch."
        )
        # check short command behaviour
        self.repo_sandbox.check_out("level-2a-branch")
        self.launch_command("g", "r")
        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "current").strip(),
            msg="Verify that 'git machete g r' performs 'git checkout' to"
                "the root of the current branch."
        )

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

        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "up").strip(),
            msg="Verify that 'git machete show up' displays name of a parent/upstream"
                "branch one above current one."
        )
        # check short command behaviour
        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "u").strip(),
            msg="Verify that 'git machete show u' displays name of a parent/upstream"
                "branch one above current one."
        )

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

        self.assertEqual(
            'level-1-branch',
            self.launch_command("show", "down").strip(),
            msg="Verify that 'git machete show down' displays name of "
                "a child/downstream branch one below current one."
        )
        # check short command behaviour
        self.assertEqual(
            'level-1-branch',
            self.launch_command("show", "d").strip(),
            msg="Verify that 'git machete show d' displays name of "
                "a child/downstream branch one below current one."
        )

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

        self.assertEqual(
            'level-1a-branch',
            self.launch_command("show", "first").strip(),
            msg="Verify that 'git machete show first' displays name of the first downstream"
                "branch of a root branch of the current branch in the config file if root"
                "branch has any downstream branches."
        )
        # check short command behaviour
        self.assertEqual(
            'level-1a-branch',
            self.launch_command("show", "f").strip(),
            msg="Verify that 'git machete show f' displays name of the first downstream"
                "branch of a root branch of the current branch in the config file if root"
                "branch has any downstream branches."
        )

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

        self.assertEqual(
            'level-1b-branch',
            self.launch_command("show", "last").strip(),
            msg="Verify that 'git machete show last' displays name of the last downstream"
                "branch of a root branch of the current branch in the config file if root"
                "branch has any downstream branches."
        )
        # check short command behaviour
        self.assertEqual(
            'level-1b-branch',
            self.launch_command("show", "l").strip(),
            msg="Verify that 'git machete show l' displays name of the last downstream"
                "branch of a root branch of the current branch in the config file if root"
                "branch has any downstream branches."
        )

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

        self.assertEqual(
            'level-1b-branch',
            self.launch_command("show", "next").strip(),
            msg="Verify that 'git machete show next' displays name of "
                "a branch right after the current one in the config file"
                "when successor branch exists within the root tree."
        )
        # check short command behaviour
        self.assertEqual(
            'level-1b-branch',
            self.launch_command("show", "n").strip(),
            msg="Verify that 'git machete show n' displays name of "
                "a branch right after the current one in the config file"
                "when successor branch exists within the root tree."
        )

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

        self.assertEqual(
            'level-2a-branch',
            self.launch_command("show", "prev").strip(),
            msg="Verify that 'git machete show prev' displays name of"
                "a branch right before the current one in the config file"
                "when predecessor branch exists within the root tree."
        )
        # check short command behaviour
        self.assertEqual(
            'level-2a-branch',
            self.launch_command("show", "p").strip(),
            msg="Verify that 'git machete show p' displays name of"
                "a branch right before the current one in the config file"
                "when predecessor branch exists within the root tree."
        )

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

        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "root").strip(),
            msg="Verify that 'git machete show root' displays name of the root of"
                "the current branch."
        )
        # check short command behaviour
        self.assertEqual(
            'level-0-branch',
            self.launch_command("show", "r").strip(),
            msg="Verify that 'git machete show r' displays name of the root of"
                "the current branch."
        )

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

        with self.assertRaises(
                SystemExit,
                msg="Verify that 'git machete advance' raises an error when current branch"
                    "has no downstream branches."):
            self.launch_command("advance")

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
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

        with self.assertRaises(
                SystemExit,
                msg="Verify that 'git machete advance' raises an error when current branch"
                    "has more than one synchronized downstream branch."):
            self.launch_command("advance", '-y')

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
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

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
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
        with os.popen('git log -10 --oneline') as git_call:
            branch_history = git_call.read()

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

    git_api_state_for_test_retarget_pr = MockGithubAPIState(
        [{'head': {'ref': 'feature', 'repo': {}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'root'}, 'number': '15',
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

    git_api_state_for_test_anno_prs = MockGithubAPIState([
        {'head': {'ref': 'ignore-trailing', 'repo': {}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'hotfix/add-trigger'}, 'number': '3', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'allow-ownership-link', 'repo': {}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'}, 'number': '7', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'call-ws', 'repo': {}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'}, 'number': '31', 'html_url': 'www.github.com', 'state': 'open'}
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

    git_api_state_for_test_create_pr = MockGithubAPIState([{'head': {'ref': 'ignore-trailing', 'repo': {}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'hotfix/add-trigger'}, 'number': '3', 'html_url': 'www.github.com', 'state': 'open'}],
                                                          issues=[{'number': '4'}, {'number': '5'}, {'number': '6'}])

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', git_api_state_for_test_create_pr.new_request())
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
        # check against attempt to create already existing pull request
        machete_client = MacheteClient(cli_opts, git)
        expected_error_message = "Pull request for branch hotfix/add-trigger is already created under link www.github.com!\nPR details: PR #6 by github_user: hotfix/add-trigger -> master"
        machete_client.read_definition_file()
        with self.assertRaises(MacheteException) as e:
            machete_client.create_github_pr('hotfix/add-trigger', draft=False)
        if e:
            self.assertEqual(e.exception.parameter, expected_error_message,
                             'Verify that expected error message has appeared when given pull request to create is already created.')

        # check against head branch is ancestor or equal to base branch
        (
            self.repo_sandbox.check_out('develop')
            .new_branch('testing/endpoints')
            .push()
        )
        self.launch_command('discover')

        machete_client = MacheteClient(cli_opts, git)
        machete_client.read_definition_file()
        expected_error_message = "All commits in `testing/endpoints` branch  are already included in `develop` branch.\nCannot create pull request."
        with self.assertRaises(MacheteException) as e:
            machete_client.create_github_pr('testing/endpoints', draft=False)
        if e:
            self.assertEqual(e.exception.parameter, expected_error_message,
                             'Verify that expected error message has appeared when head branch is equal or ancestor of base branch.')

        self.repo_sandbox.check_out('develop')
        expected_error_message = "Branch `develop` does not have a parent branch (it is a root), base branch for the PR cannot be established."
        with self.assertRaises(MacheteException) as e:
            machete_client.create_github_pr('develop', draft=False)
        if e:
            self.assertEqual(e.exception.parameter, expected_error_message,
                             'Verify that expected error message has appeared when creating PR from root branch.')

    git_api_state_for_test_checkout_prs = MockGithubAPIState([
        {'head': {'ref': 'chore/redundant_checks', 'repo': {'full_name': 'testing/checkout_prs'}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'restrict_access'}, 'number': '18', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'restrict_access', 'repo': {'full_name': 'testing/checkout_prs'}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'allow-ownership-link'}, 'number': '17', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'allow-ownership-link', 'repo': {'full_name': 'testing/checkout_prs'}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'bugfix/feature'}, 'number': '12', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'bugfix/feature', 'repo': {'full_name': 'testing/checkout_prs'}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'enhance/feature'}, 'number': '6', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'enhance/add_user', 'repo': {'full_name': 'testing/checkout_prs'}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'}, 'number': '19', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'testing/add_user', 'repo': {'full_name': 'testing/checkout_prs'}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'bugfix/add_user'}, 'number': '22', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'chore/comments', 'repo': {'full_name': 'testing/checkout_prs'}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'testing/add_user'}, 'number': '24', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'ignore-trailing', 'repo': {'full_name': 'testing/checkout_prs'}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'hotfix/add-trigger'}, 'number': '3', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'bugfix/remove-n-option', 'repo': {'full_name': 'testing/checkout_prs', 'html_url': GitRepositorySandbox.second_remote_path}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'develop'}, 'number': '5', 'html_url': 'www.github.com', 'state': 'closed'}
    ])

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_checkout_prs` due to `git fetch` executed by `checkout-prs` subcommand.
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', git_api_state_for_test_checkout_prs.new_request())
    def test_checkout_prs(self) -> None:
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
        # check against wrong pr number
        machete_client = MacheteClient(cli_opts, git)
        repo: str
        org: str
        (org, repo) = get_parsed_github_remote_url(self.repo_sandbox.remote_path)
        expected_error_message = f"PR #100 is not found in repository `{org}/{repo}`"
        machete_client.read_definition_file()
        with self.assertRaises(MacheteException) as e:
            machete_client.checkout_github_prs(100)
        if e:
            self.assertEqual(e.exception.parameter, expected_error_message,
                             'Verify that expected error message has appeared when given pull request to checkout does not exists.')

        # Check against closed pull request with head branch deleted from remote
        local_path = os.popen("mktemp -d").read().strip()
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

        machete_client = MacheteClient(cli_opts, git)
        machete_client.read_definition_file()
        expected_error_message = "Could not check out PR #5 because its head branch `bugfix/remove-n-option` is already deleted from `testing`."
        with self.assertRaises(MacheteException) as e:
            machete_client.checkout_github_prs(5)
        if e:
            self.assertEqual(e.exception.parameter, expected_error_message,
                             'Verify that expected error message has appeared when given pull request to checkout have already deleted branch from remote.')

        machete_client.flush_caches()
        # Check against pr come from fork
        os.chdir(local_path)
        (self.repo_sandbox
         .new_branch('bugfix/remove-n-option')
         .commit('first commit')
         .push()
         )
        os.chdir(self.repo_sandbox.local_path)

        expected_msg = ("Fetching origin...\n"
                        "Fetching testing...\n"
                        "Warn: Pull request #5 is already closed.\n"
                        "A local branch `bugfix/remove-n-option` does not exist, but a remote branch `testing/bugfix/remove-n-option` exists.\n"
                        "Checking out `bugfix/remove-n-option` locally...\n"
                        "Added branch `bugfix/remove-n-option` onto `develop`\n"
                        "Annotating bugfix/remove-n-option as `PR #5 (github_user)`\n"
                        "Pull request `#5` checked out at local branch `bugfix/remove-n-option`\n")

        self.assert_command(['github', 'checkout-prs', '5'], expected_msg, strip_indentation=False)

    git_api_state_for_test_checkout_prs_fresh_repo = MockGithubAPIState([
        {'head': {'ref': 'comments/add_docstrings', 'repo': {'full_name': 'testing:checkout_prs'}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'improve/refactor'}, 'number': '2', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'restrict_access', 'repo': {'full_name': 'testing:checkout_prs'}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'allow-ownership-link'}, 'number': '17', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'improve/refactor', 'repo': {'full_name': 'testing:checkout_prs'}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'chore/sync_to_docs'}, 'number': '1', 'html_url': 'www.github.com', 'state': 'open'},
        {'head': {'ref': 'sphinx_export', 'repo': {'full_name': 'testing:checkout_prs'}}, 'user': {'login': 'github_user'}, 'base': {'ref': 'comments/add_docstrings'}, 'number': '23', 'html_url': 'www.github.com', 'state': 'closed'}
    ])

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_checkout_prs_freshly_cloned` due to `git fetch` executed by `checkout-prs` subcommand.
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', git_api_state_for_test_checkout_prs_fresh_repo.new_request())
    def test_checkout_prs_freshly_cloned(self) -> None:
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
            .delete_branch('root')
            .push()
        )
        for branch in ('develop', 'chore/sync_to_docs', 'improve/refactor', 'comments/add_docstrings'):
            self.repo_sandbox.execute(f"git branch -D {branch}")
        with os.popen("mktemp -d") as local_temp_folder:
            local_path = local_temp_folder.read().strip()
        os.chdir(local_path)
        self.repo_sandbox.execute(f'git clone {self.repo_sandbox.remote_path}')
        os.chdir(os.path.join(local_path, os.listdir()[0]))

        for branch in ('develop', 'chore/sync_to_docs', 'improve/refactor', 'comments/add_docstrings'):
            self.repo_sandbox.execute(f"git branch -D -r origin/{branch}")

        self.rewrite_definition_file("master")
        expected_msg = ("Fetching origin...\n"
                        "A local branch `chore/sync_to_docs` does not exist, but a remote branch `origin/chore/sync_to_docs` exists.\n"
                        "Checking out `chore/sync_to_docs` locally...\n"
                        "Added branch `chore/sync_to_docs` as a new root\n"
                        "A local branch `improve/refactor` does not exist, but a remote branch `origin/improve/refactor` exists.\n"
                        "Checking out `improve/refactor` locally...\n"
                        "Added branch `improve/refactor` onto `chore/sync_to_docs`\n"
                        "A local branch `comments/add_docstrings` does not exist, but a remote branch `origin/comments/add_docstrings` exists.\n"
                        "Checking out `comments/add_docstrings` locally...\nAdded branch `comments/add_docstrings` onto `improve/refactor`\n"
                        "Annotating comments/add_docstrings as `PR #2 (github_user)`\nAnnotating improve/refactor as `PR #1 (github_user)`\n"
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
        expected_msg = ("Fetching origin...\n"
                        "Warn: Pull request #23 is already closed.\n"
                        "A local branch `sphinx_export` does not exist, but a remote branch `origin/sphinx_export` exists.\n"
                        "Checking out `sphinx_export` locally...\n"
                        "Added branch `sphinx_export` onto `comments/add_docstrings`\n"
                        "Annotating sphinx_export as `PR #23 (github_user)`\n"
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
                o-sphinx_export *  PR #23 (github_user)
            """
        )
