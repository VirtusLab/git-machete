import os
import subprocess
from tempfile import mkdtemp
from typing import Any, Dict, Optional
from unittest import mock

import pytest

from git_machete.exceptions import MacheteException
from git_machete.git_operations import GitContext, LocalBranchShortName
from git_machete.github import get_parsed_github_remote_url
from git_machete.options import CommandLineOptions

from .mockers import (GitRepositorySandbox, MockContextManager,
                      MockGitHubAPIState, MockHTTPError, assert_command,
                      get_current_commit_hash, git, launch_command,
                      mock_ask_if, mock_exit_script, mock_run_cmd,
                      mock_should_perform_interactive_slide_out,
                      rewrite_definition_file)

FAKE_GITHUB_REMOTE_PATTERNS = ['(.*)/(.*)']


class FakeCommandLineOptions(CommandLineOptions):
    def __init__(self, git: GitContext) -> None:
        super().__init__(git)
        self.opt_no_interactive_rebase: bool = True
        self.opt_yes: bool = True


def mock_fetch_ref(cls: Any, remote: str, ref: str) -> None:
    branch: LocalBranchShortName = LocalBranchShortName.of(ref[ref.index(':') + 1:])
    git.create_branch(branch, get_current_commit_hash(), switch_head=True)


def mock_derive_current_user_login() -> str:
    return "very_complex_user_token"


def mock__get_github_token() -> Optional[str]:
    return None


def mock__get_github_token_fake() -> Optional[str]:
    return 'token'


def mock_input(msg: str) -> str:
    print(msg)
    return '1'


class TestGithub:
    mock_repository_info: Dict[str, str] = {'full_name': 'testing/checkout_prs',
                                            'html_url': 'https://github.com/tester/repo_sandbox.git'}

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

    git_api_state_for_test_retarget_pr = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'feature', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'root'}, 'number': '15',
                'html_url': 'www.github.com', 'state': 'open'
            },
            {
                'head': {'ref': 'feature_1', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'root'}, 'number': '20',
                'html_url': 'www.github.com', 'state': 'open'
            },
            {
                'head': {'ref': 'feature_2', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'root'}, 'number': '25',
                'html_url': 'www.github.com', 'state': 'open'
            },
            {
                'head': {'ref': 'feature_3', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'root'}, 'number': '35',
                'html_url': 'www.github.com', 'state': 'open'
            }
        ]
    )

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('urllib.request.Request', git_api_state_for_test_retarget_pr.new_request())
    @mock.patch('urllib.request.urlopen', MockContextManager)
    def test_github_retarget_pr(self) -> None:
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

        launch_command("discover", "-y")
        launch_command("anno", "-H")

        expected_status_output = """
        root (untracked)
        |
        o-branch-1
          |
          o-feature *  PR #15 (github_user) WRONG PR BASE or MACHETE PARENT? PR has 'root'
        """
        assert_command(
            ['status'],
            expected_result=expected_status_output
        )

        assert_command(
            ['github', 'retarget-pr'],
            'The base branch of PR #15 has been switched to branch-1\n',
            strip_indentation=False
        )

        expected_status_output = """
        root (untracked)
        |
        o-branch-1
          |
          o-feature *  PR #15
        """
        assert_command(
            ['status'],
            expected_result=expected_status_output
        )

        assert_command(
            ['github', 'retarget-pr'],
            'The base branch of PR #15 is already branch-1\n',
            strip_indentation=False
        )

    @mock.patch('git_machete.cli.exit_script', mock_exit_script)
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('urllib.request.Request', git_api_state_for_test_retarget_pr.new_request())
    @mock.patch('urllib.request.urlopen', MockContextManager)
    def test_github_retarget_pr_multiple_non_origin_remotes(self) -> None:
        branchs_first_commit_msg = "First commit on branch."
        branchs_second_commit_msg = "Second commit on branch."

        origin_1_remote_path = mkdtemp()
        origin_2_remote_path = mkdtemp()
        self.repo_sandbox.new_repo(origin_1_remote_path, switch_dir_to_new_repo=False)
        self.repo_sandbox.new_repo(origin_2_remote_path, switch_dir_to_new_repo=False)

        # branch feature present in each remote, no branch tracking data
        (
            self.repo_sandbox.remove_remote(remote='origin')
                .new_branch("root")
                .add_remote('origin_1', origin_1_remote_path)
                .add_remote('origin_2', origin_2_remote_path)
                .commit("First commit on root.")
                .push(remote='origin_1')
                .push(remote='origin_2')
                .new_branch("branch-1")
                .commit(branchs_first_commit_msg)
                .commit(branchs_second_commit_msg)
                .push(remote='origin_1')
                .push(remote='origin_2')
                .new_branch('feature')
                .commit('introduce feature')
                .push(remote='origin_1', set_upstream=False)
                .push(remote='origin_2', set_upstream=False)
        )

        launch_command("discover", "-y")
        expected_error_message = (
            "Multiple non-origin remotes correspond to GitHub in this repository: origin_1, origin_2 -> aborting. \n"
            "You can also select the repository by providing 3 git config keys: `machete.github.{remote,organization,repository}`\n"
        )
        with pytest.raises(MacheteException) as e:
            launch_command("github", "retarget-pr")
        if e:
            assert e.value.args[0] == expected_error_message, \
                'Verify that expected error message has appeared when given pull request to create is already created.'

        # branch feature_1 present in each remote, tracking data present
        (
            self.repo_sandbox.check_out('feature')
                .new_branch('feature_1')
                .commit('introduce feature 1')
                .push(remote='origin_1')
                .push(remote='origin_2')
        )

        launch_command("discover", "-y")
        assert_command(
            ['github', 'retarget-pr'],
            'The base branch of PR #20 has been switched to feature\n',
            strip_indentation=False
        )

        # branch feature_2 is not present in any of the remotes
        (
            self.repo_sandbox.check_out('feature')
                .new_branch('feature_2')
                .commit('introduce feature 2')
        )

        launch_command("discover", "-y")
        with pytest.raises(MacheteException) as e:
            launch_command("github", "retarget-pr")
        if e:
            assert e.value.args[0] == expected_error_message, \
                'Verify that expected error message has appeared when given pull request to create is already created.'

        # branch feature_2 present in only one remote: origin_1 and there is no tracking data available -> infer the remote
        (
            self.repo_sandbox.check_out('feature_2')
                .push(remote='origin_1', set_upstream=False)
        )

        assert_command(
            ['github', 'retarget-pr'],
            'The base branch of PR #25 has been switched to feature\n',
            strip_indentation=False
        )

        # branch feature_3 present in only one remote: origin_1 and has tracking data
        (
            self.repo_sandbox.check_out('feature_2')
                .new_branch('feature_3')
                .commit('introduce feature 3')
                .push(remote='origin_1')
        )

        launch_command("discover", "-y")
        assert_command(
            ['github', 'retarget-pr'],
            'The base branch of PR #35 has been switched to feature_2\n',
            strip_indentation=False
        )

    git_api_state_for_test_anno_prs = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'hotfix/add-trigger'},
                'number': '3',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'allow-ownership-link', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '7',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'call-ws', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '31',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ]
    )

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('git_machete.github.derive_current_user_login', mock_derive_current_user_login)
    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', git_api_state_for_test_anno_prs.new_request())
    def test_github_anno_prs(self) -> None:
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
        launch_command("discover", "-y")
        launch_command('github', 'anno-prs')
        assert_command(
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
            """
        )

        # Test anno-prs using custom remote URL provided by git config keys
        (
            self.repo_sandbox
                .remove_remote('new_origin')
                .add_git_config_key('machete.github.remote', 'custom_origin')
                .add_git_config_key('machete.github.organization', 'custom_user')
                .add_git_config_key('machete.github.repository', 'custom_repo')
        )

        launch_command("discover", "-y")
        launch_command('github', 'anno-prs')
        assert_command(
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

    git_api_state_for_test_create_pr = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'hotfix/add-trigger'},
                'number': '3',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ],
        issues=[
            {'number': '4'},
            {'number': '5'},
            {'number': '6'}
        ]
    )

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

        launch_command("discover")
        launch_command("github", "create-pr")
        # ahead of origin state, push is advised and accepted
        assert_command(
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
        launch_command("github", "create-pr", "--draft")
        assert_command(
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
        launch_command("github", "create-pr")
        assert_command(
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
            launch_command("github", "create-pr")
        if e:
            assert e.value.args[0] == expected_error_message, \
                'Verify that expected error message has appeared when given pull request to create is already created.'

        # check against head branch is ancestor or equal to base branch
        (
            self.repo_sandbox.check_out('develop')
                .new_branch('testing/endpoints')
                .push()
        )
        launch_command('discover')

        expected_error_message = "All commits in testing/endpoints branch are already included in develop branch.\n" \
                                 "Cannot create pull request."
        with pytest.raises(MacheteException) as e:
            launch_command("github", "create-pr")
        if e:
            assert e.value.parameter == expected_error_message, \
                'Verify that expected error message has appeared when head branch is equal or ancestor of base branch.'

        self.repo_sandbox.check_out('develop')
        expected_error_message = "Branch develop does not have a parent branch (it is a root), " \
                                 "base branch for the PR cannot be established."
        with pytest.raises(MacheteException) as e:
            launch_command("github", "create-pr")
        if e:
            assert e.value.parameter == expected_error_message, \
                'Verify that expected error message has appeared when creating PR from root branch.'

    git_api_state_for_test_create_pr_missing_base_branch_on_remote = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'chore/redundant_checks', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'restrict_access'},
                'number': '18',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ]
    )

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

        launch_command('discover')

        expected_msg = ("Fetching origin...\n"
                        "Warn: Base branch for this PR (feature/api_handling) is not found on remote, pushing...\n"
                        "Creating a PR from feature/api_exception_handling to feature/api_handling... OK, see www.github.com\n")
        assert_command(['github', 'create-pr'], expected_msg, strip_indentation=False)
        assert_command(
            ['status'],
            """
            develop
            |
            o-feature/api_handling
              |
              o-feature/api_exception_handling *  PR #19
            """,
        )

    git_api_state_for_test_github_create_pr_with_multiple_non_origin_remotes = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'branch-1', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'root'}, 'number': '15',
                'html_url': 'www.github.com', 'state': 'open'
            }
        ],
        issues=[
            {'number': '16'},
            {'number': '17'},
            {'number': '18'},
            {'number': '19'},
            {'number': '20'},
        ]
    )

    @mock.patch('git_machete.cli.exit_script', mock_exit_script)
    @mock.patch('git_machete.client.MacheteClient.ask_if', mock_ask_if)
    # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_create_pr` due to `git fetch` executed by `create-pr` subcommand.
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    @mock.patch('git_machete.github.__get_github_token', mock__get_github_token)
    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('urllib.error.HTTPError', MockHTTPError)  # need to provide read() method, which does not actually reads error from url
    @mock.patch('urllib.request.Request', git_api_state_for_test_github_create_pr_with_multiple_non_origin_remotes.new_request())
    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('builtins.input', mock_input)
    def test_github_create_pr_with_multiple_non_origin_remotes(self) -> None:
        origin_1_remote_path = mkdtemp()
        origin_2_remote_path = mkdtemp()
        self.repo_sandbox.new_repo(origin_1_remote_path, "--bare", switch_dir_to_new_repo=False)
        self.repo_sandbox.new_repo(origin_2_remote_path, "--bare", switch_dir_to_new_repo=False)

        # branch feature present in each of the remotes, no branch tracking data, remote origin_1 picked manually via mock_input()
        (
            self.repo_sandbox.remove_remote(remote='origin')
                .new_branch("root")
                .add_remote('origin_1', origin_1_remote_path)
                .add_remote('origin_2', origin_2_remote_path)
                .commit("First commit on root.")
                .push(remote='origin_1')
                .push(remote='origin_2')
                .new_branch("branch-1")
                .commit('First commit on branch-1.')
                .push(remote='origin_1')
                .push(remote='origin_2')
                .new_branch('feature')
                .commit('introduce feature')
                .push(remote='origin_1', set_upstream=False)
                .push(remote='origin_2', set_upstream=False)
        )

        launch_command("discover", "-y")
        expected_result = """
        Branch feature is untracked and there's no origin repository.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit creating pull request: 
        Branch feature is untracked, but its remote counterpart candidate origin_1/feature already exists and both branches point to the same commit.

          root
          |
          o-branch-1
            |
            o-feature *

        Fetching origin_1...
        Creating a PR from feature to branch-1... OK, see www.github.com
        """  # noqa: W291, E501
        assert_command(
            ['github', 'create-pr'],
            expected_result,
            indent=''
        )
        # branch feature_1 present in each of the remotes, tracking data present
        (
            self.repo_sandbox.check_out('feature')
                .new_branch('feature_1')
                .commit('introduce feature 1')
                .push(remote='origin_1')
                .push(remote='origin_2')
        )

        expected_result = """
        Added branch feature_1 onto feature
        Fetching origin_2...
        Creating a PR from feature_1 to feature... OK, see www.github.com
        """
        assert_command(
            ['github', 'create-pr'],
            expected_result,
            indent=''
        )

        # branch feature_2 not present in any of the remotes, remote origin_1 picked manually via mock_input()
        (
            self.repo_sandbox.check_out('feature')
                .new_branch('feature_2')
                .commit('introduce feature 2')
        )

        expected_result = """
        Added branch feature_2 onto feature
        Branch feature_2 is untracked and there's no origin repository.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit creating pull request: 

          root
          |
          o-branch-1
            |
            o-feature  PR #16
              |
              o-feature_1  PR #17
              |
              o-feature_2 *

        Fetching origin_1...
        Creating a PR from feature_2 to feature... OK, see www.github.com
        """  # noqa: W291
        assert_command(
            ['github', 'create-pr'],
            expected_result,
            indent=''
        )

        # branch feature_2 present in only one remote: origin_1, no tracking data
        (
            self.repo_sandbox.check_out('feature_2')
                .new_branch('feature_3')
                .commit('introduce feature 3')
                .push(remote='origin_1', set_upstream=False)
        )

        expected_result = """
        Added branch feature_3 onto feature_2
        Branch feature_3 is untracked, but its remote counterpart candidate origin_1/feature_3 already exists and both branches point to the same commit.

          root
          |
          o-branch-1
            |
            o-feature  PR #16
              |
              o-feature_1  PR #17
              |
              o-feature_2  PR #18
                |
                o-feature_3 *

        Fetching origin_1...
        Creating a PR from feature_3 to feature_2... OK, see www.github.com
        """  # noqa: E501
        assert_command(
            ['github', 'create-pr'],
            expected_result,
            indent=''
        )

        # branch feature_3 present in only one remote: origin_2, tracking data present
        (
            self.repo_sandbox.check_out('feature_3')
                .new_branch('feature_4')
                .commit('introduce feature 4')
                .push(remote='origin_2')
        )

        expected_result = """
        Added branch feature_4 onto feature_3
        Fetching origin_2...
        Warn: Base branch for this PR (feature_3) is not found on remote, pushing...
        Creating a PR from feature_4 to feature_3... OK, see www.github.com
        """
        assert_command(
            ['github', 'create-pr'],
            expected_result,
            indent=''
        )

        # branch feature_3 present in only one remote: origin_2 with tracking data, origin remote present - takes priority
        (
            self.repo_sandbox.add_remote('origin', self.repo_sandbox.remote_path)
                .check_out('feature_3')
                .new_branch('feature_5')
                .commit('introduce feature 5')
                .push(remote='origin_2')
        )

        expected_result = """
        Added branch feature_5 onto feature_3
        Fetching origin...
        Creating a PR from feature_5 to feature_3... OK, see www.github.com
        """
        assert_command(
            ['github', 'create-pr'],
            expected_result,
            indent=''
        )

    git_api_state_for_test_checkout_prs = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'chore/redundant_checks', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'restrict_access'},
                'number': '18',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'restrict_access', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'allow-ownership-link'},
                'number': '17',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'allow-ownership-link', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'bugfix/feature'},
                'number': '12',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'bugfix/feature', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'enhance/feature'},
                'number': '6',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'enhance/add_user', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '19',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'testing/add_user', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'bugfix/add_user'},
                'number': '22',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {'head': {'ref': 'chore/comments', 'repo': mock_repository_info},
             'user': {'login': 'github_user'},
             'base': {'ref': 'testing/add_user'},
             'number': '24',
             'html_url': 'www.github.com',
             'state': 'open'
             },
            {
                'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'hotfix/add-trigger'},
                'number': '3',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'bugfix/remove-n-option',
                         'repo': {'full_name': 'testing/checkout_prs', 'html_url': GitRepositorySandbox.second_remote_path}},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '5',
                'html_url': 'www.github.com',
                'state': 'closed'
            }
        ]
    )

    @mock.patch('git_machete.cli.exit_script', mock_exit_script)
    # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_checkout_prs`
    # due to `git fetch` executed by `checkout-prs` subcommand.
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('git_machete.github.__get_github_token', mock__get_github_token)
    @mock.patch('urllib.request.Request', git_api_state_for_test_checkout_prs.new_request())
    @mock.patch('urllib.request.urlopen', MockContextManager)
    def test_github_checkout_prs(self, tmp_path: Any) -> None:
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
        for branch in ('chore/redundant_checks', 'restrict_access', 'allow-ownership-link', 'bugfix/feature', 'enhance/add_user',
                       'testing/add_user', 'chore/comments', 'bugfix/add_user'):
            self.repo_sandbox.execute(f"git branch -D {branch}")

        launch_command('discover')

        # not broken chain of pull requests (root found in dependency tree)
        launch_command('github', 'checkout-prs', '18')
        assert_command(
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
        launch_command('github', 'checkout-prs', '24')
        assert_command(
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
        launch_command('github', 'checkout-prs', '24')
        assert_command(
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
        launch_command('github', 'checkout-prs', '--all')
        assert_command(
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
        _, org, repo = get_parsed_github_remote_url(self.repo_sandbox.remote_path, remote='origin')
        expected_error_message = f"PR #100 is not found in repository {org}/{repo}"
        with pytest.raises(MacheteException) as e:
            launch_command('github', 'checkout-prs', '100')
        if e:
            assert e.value.parameter == expected_error_message, \
                'Verify that expected error message has appeared when given pull request to checkout does not exists.'

        with pytest.raises(MacheteException) as e:
            launch_command('github', 'checkout-prs', '19', '100')
        if e:
            assert e.value.parameter == expected_error_message, \
                'Verify that expected error message has appeared when one of the given pull requests to checkout does not exists.'

        # check against user with no open pull requests
        expected_msg = ("Checking for open GitHub PRs...\n"
                        f"Warn: User tester has no open pull request in repository {org}/{repo}\n")
        assert_command(['github', 'checkout-prs', '--by', 'tester'], expected_msg, strip_indentation=False)

        # Check against closed pull request with head branch deleted from remote
        local_path = tmp_path
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

        expected_error_message = "Could not check out PR #5 because its head branch bugfix/remove-n-option " \
                                 "is already deleted from testing."
        with pytest.raises(MacheteException) as e:
            launch_command('github', 'checkout-prs', '5')
        if e:
            assert e.value.parameter == expected_error_message, \
                'Verify that expected error message has appeared when given pull request to checkout ' \
                'have already deleted branch from remote.'

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
                        "Pull request #5 checked out at local branch bugfix/remove-n-option\n")

        assert_command(['github', 'checkout-prs', '5'], expected_msg, strip_indentation=False)

        # Check against multiple PRs
        expected_msg = 'Checking for open GitHub PRs...\n'

        assert_command(['github', 'checkout-prs', '3', '12'], expected_msg, strip_indentation=False)

    git_api_state_for_test_github_checkout_prs_fresh_repo = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'comments/add_docstrings', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'improve/refactor'},
                'number': '2',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'restrict_access', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'allow-ownership-link'},
                'number': '17',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'improve/refactor', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'chore/sync_to_docs'},
                'number': '1',
                'html_url': 'www.github.com',
                'state': 'open'
            },
            {
                'head': {'ref': 'sphinx_export',
                         'repo': {'full_name': 'testing/checkout_prs', 'html_url': GitRepositorySandbox.second_remote_path}},
                'user': {'login': 'github_user'},
                'base': {'ref': 'comments/add_docstrings'},
                'number': '23',
                'html_url': 'www.github.com',
                'state': 'closed'
            }
        ]
    )

    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_checkout_prs_freshly_cloned`
    # due to `git fetch` executed by `checkout-prs` subcommand.
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    @mock.patch('urllib.request.urlopen', MockContextManager)
    @mock.patch('urllib.request.Request', git_api_state_for_test_github_checkout_prs_fresh_repo.new_request())
    def test_github_checkout_prs_freshly_cloned(self, tmp_path: Any) -> None:
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
        local_path = tmp_path
        os.chdir(local_path)
        self.repo_sandbox.execute(f'git clone {self.repo_sandbox.remote_path}')
        os.chdir(os.path.join(local_path, os.listdir()[0]))

        for branch in ('develop', 'chore/sync_to_docs', 'improve/refactor', 'comments/add_docstrings'):
            self.repo_sandbox.execute(f"git branch -D -r origin/{branch}")

        local_path = tmp_path
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
        rewrite_definition_file("master")
        expected_msg = ("Checking for open GitHub PRs...\n"
                        "Pull request #2 checked out at local branch comments/add_docstrings\n")
        assert_command(
            ['github', 'checkout-prs', '2'],
            expected_msg,
            strip_indentation=False
        )

        assert_command(
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
                        "Pull request #23 checked out at local branch sphinx_export\n")

        assert_command(
            ['github', 'checkout-prs', '23'],
            expected_msg,
            strip_indentation=False
        )
        assert_command(
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

    git_api_state_for_test_github_checkout_prs_from_fork_with_deleted_repo = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'feature/allow_checkout', 'repo': None},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '2',
                'html_url': 'www.github.com',
                'state': 'closed'
            },
            {
                'head': {'ref': 'bugfix/allow_checkout', 'repo': mock_repository_info},
                'user': {'login': 'github_user'},
                'base': {'ref': 'develop'},
                'number': '3',
                'html_url': 'www.github.com',
                'state': 'open'}
        ]
    )

    @mock.patch('git_machete.git_operations.GitContext.fetch_ref', mock_fetch_ref)
    # need to mock fetch_ref due to underlying `git fetch pull/head` calls
    @mock.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
    @mock.patch('git_machete.options.CommandLineOptions', FakeCommandLineOptions)
    @mock.patch('git_machete.github.GITHUB_REMOTE_PATTERNS', FAKE_GITHUB_REMOTE_PATTERNS)
    # We need to mock GITHUB_REMOTE_PATTERNS in the tests for `test_github_checkout_prs_from_fork_with_deleted_repo`
    # due to `git fetch` executed by `checkout-prs` subcommand.
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
        launch_command('discover')
        expected_msg = ("Checking for open GitHub PRs...\n"
                        "Warn: Pull request #2 comes from fork and its repository is already deleted. "
                        "No remote tracking data will be set up for feature/allow_checkout branch.\n"
                        "Warn: Pull request #2 is already closed.\n"
                        "Pull request #2 checked out at local branch feature/allow_checkout\n")
        assert_command(
            ['github', 'checkout-prs', '2'],
            expected_msg,
            strip_indentation=False
        )

        assert 'feature/allow_checkout' == launch_command("show", "current").strip(), \
            ("Verify that 'git machete github checkout prs' performs 'git checkout' to "
             "the head branch of given pull request."
             )

    git_api_state_for_test_github_sync = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'snickers', 'repo': mock_repository_info},
                'user': {'login': 'other_user'},
                'base': {'ref': 'master'},
                'number': '7',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ]
    )

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
        launch_command('discover', '-y')
        (
            self.repo_sandbox
                .check_out("master")
                .new_branch('mars')
                .commit()
                .check_out("master")
        )
        launch_command('github', 'sync')

        expected_status_output = (
            """
            master
            |
            o-bar (untracked)
            |
            o-foo
            |
            o-moo (untracked)
            |
            o-snickers *  PR #7
            """
        )
        assert_command(['status'], expected_status_output)

        with pytest.raises(subprocess.CalledProcessError):
            self.repo_sandbox.check_out("mars")
