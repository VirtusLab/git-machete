from tempfile import mkdtemp

from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success, launch_command,
                           mock_input_returning, mock_input_returning_y,
                           mock_run_cmd_and_discard_output,
                           rewrite_definition_file)
from tests.mockers_github import (MockGitHubAPIState, MockHTTPError,
                                  mock_from_url,
                                  mock_github_token_for_domain_none,
                                  mock_repository_info, mock_urlopen)


class TestGitHubCreatePR(BaseTest):

    git_api_state_for_test_create_pr = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'ignore-trailing', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
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

    def test_github_create_pr(self, mocker: MockerFixture) -> None:
        mocker.patch('builtins.input', mock_input_returning_y)
        mocker.patch('git_machete.github.RemoteAndOrganizationAndRepository.from_url', mock_from_url)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('urllib.error.HTTPError', MockHTTPError)  # need to provide read() method, which does not actually reads error from url
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_create_pr.new_request())
        mocker.patch('urllib.request.urlopen', mock_urlopen)

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
                .reset_to("ignore-trailing@{1}")  # noqa: FS003
                .delete_branch("root")
                .new_branch('chore/fields')
                .commit("remove outdated fields")
                .check_out("call-ws")
                .add_remote('new_origin', 'https://github.com/user/repo.git')
        )
        body: str = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing
                        chore/fields
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
            """
        rewrite_definition_file(body)

        launch_command("github", "create-pr")
        # ahead of origin state, push is advised and accepted
        assert_success(
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
        assert_success(
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
        assert_success(
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
        assert_failure(["github", "create-pr"], expected_error_message)

        # check against head branch is ancestor or equal to base branch
        (
            self.repo_sandbox.check_out('develop')
                .new_branch('testing/endpoints')
                .push()
        )
        body = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing
                        chore/fields
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
                testing/endpoints
            """
        rewrite_definition_file(body)

        expected_error_message = "All commits in testing/endpoints branch are already included in develop branch.\n" \
                                 "Cannot create pull request."
        assert_failure(["github", "create-pr"], expected_error_message)

        self.repo_sandbox.check_out('develop')
        expected_error_message = "Branch develop does not have a parent branch (it is a root), " \
                                 "base branch for the PR cannot be established."
        assert_failure(["github", "create-pr"], expected_error_message)

    git_api_state_for_test_create_pr_missing_base_branch_on_remote = MockGitHubAPIState(
        [
            {
                'head': {'ref': 'chore/redundant_checks', 'repo': mock_repository_info},
                'user': {'login': 'some_other_user'},
                'base': {'ref': 'restrict_access'},
                'number': '18',
                'html_url': 'www.github.com',
                'state': 'open'
            }
        ]
    )

    def test_github_create_pr_missing_base_branch_on_remote(self, mocker: MockerFixture) -> None:
        mocker.patch('builtins.input', mock_input_returning_y)
        mocker.patch('git_machete.github.RemoteAndOrganizationAndRepository.from_url', mock_from_url)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('urllib.request.urlopen', mock_urlopen)
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_create_pr_missing_base_branch_on_remote.new_request())

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
        body: str = \
            """
            develop
                feature/api_handling
                    feature/api_exception_handling
            """
        rewrite_definition_file(body)

        expected_msg = ("Fetching origin...\n"
                        "Warn: Base branch for this PR (feature/api_handling) is not found on remote, pushing...\n"
                        "Push untracked branch feature/api_handling to origin? (y, Q) \n"
                        "Creating a PR from feature/api_exception_handling to feature/api_handling... OK, see www.github.com\n")
        assert_success(['github', 'create-pr'], expected_msg)
        assert_success(
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
                'user': {'login': 'some_other_user'},
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

    def test_github_create_pr_with_multiple_non_origin_remotes(self, mocker: MockerFixture) -> None:
        mocker.patch('builtins.input', mock_input_returning('1', 'y', 'y'))
        mocker.patch('git_machete.github.RemoteAndOrganizationAndRepository.from_url', mock_from_url)
        mocker.patch('git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd_and_discard_output)
        mocker.patch('urllib.error.HTTPError', MockHTTPError)  # need to provide read() method, which does not actually read error from url
        mocker.patch('urllib.request.Request', self.git_api_state_for_test_github_create_pr_with_multiple_non_origin_remotes.new_request())
        mocker.patch('urllib.request.urlopen', mock_urlopen)

        origin_1_remote_path = mkdtemp()
        origin_2_remote_path = mkdtemp()
        self.repo_sandbox.new_repo(origin_1_remote_path, bare=True, switch_dir_to_new_repo=False)
        self.repo_sandbox.new_repo(origin_2_remote_path, bare=True, switch_dir_to_new_repo=False)

        # branch feature present in each of the remotes, no branch tracking data, remote origin_1 picked manually via mock_input()
        (
            self.repo_sandbox.remove_remote()
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
        body: str = \
            """
            root
                branch-1
                    feature
            """
        rewrite_definition_file(body)

        expected_result = """
        Branch feature is untracked and there's no origin repository.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit creating pull request: 
        Branch feature is untracked, but its remote counterpart candidate origin_1/feature already exists and both branches point to the same commit.
        Set the remote of feature to origin_1 without pushing or pulling? (y, N, q, yq, o[ther-remote]) 

          root
          |
          o-branch-1
            |
            o-feature *

        Fetching origin_1...
        Creating a PR from feature to branch-1... OK, see www.github.com
        """  # noqa: W291, E501
        assert_success(
            ['github', 'create-pr'],
            expected_result
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
        Add feature_1 onto the inferred upstream (parent) branch feature? (y, N) 
        Added branch feature_1 onto feature
        Fetching origin_2...
        Creating a PR from feature_1 to feature... OK, see www.github.com
        """
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        # branch feature_2 not present in any of the remotes, remote origin_1 picked manually via mock_input()
        (
            self.repo_sandbox.check_out('feature')
                .new_branch('feature_2')
                .commit('introduce feature 2')
        )

        mocker.patch('builtins.input', mock_input_returning('y', '1', 'y'))

        expected_result = """
        Add feature_2 onto the inferred upstream (parent) branch feature? (y, N) 
        Added branch feature_2 onto feature
        Branch feature_2 is untracked and there's no origin repository.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit creating pull request: 
        Push untracked branch feature_2 to origin_1? (y, Q, o[ther-remote]) 

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
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        # branch feature_2 present in only one remote: origin_1, no tracking data
        (
            self.repo_sandbox.check_out('feature_2')
                .new_branch('feature_3')
                .commit('introduce feature 3')
                .push(remote='origin_1', set_upstream=False)
        )

        mocker.patch('builtins.input', mock_input_returning('y'))
        expected_result = """
        Add feature_3 onto the inferred upstream (parent) branch feature_2? (y, N) 
        Added branch feature_3 onto feature_2
        Fetching origin_1...
        Creating a PR from feature_3 to feature_2... OK, see www.github.com
        """  # noqa: E501
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        # branch feature_3 present in only one remote: origin_2, tracking data present
        (
            self.repo_sandbox.check_out('feature_3')
                .new_branch('feature_4')
                .commit('introduce feature 4')
                .push(remote='origin_2')
        )

        mocker.patch('builtins.input', mock_input_returning('y', 'y'))
        expected_result = """
        Add feature_4 onto the inferred upstream (parent) branch feature_3? (y, N) 
        Added branch feature_4 onto feature_3
        Fetching origin_2...
        Warn: Base branch for this PR (feature_3) is not found on remote, pushing...
        Push untracked branch feature_3 to origin_2? (y, Q) 
        Creating a PR from feature_4 to feature_3... OK, see www.github.com
        """
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        # branch feature_3 present in only one remote: origin_2 with tracking data, origin remote present - takes priority
        (
            self.repo_sandbox.add_remote('origin', self.repo_sandbox.remote_path)
                .check_out('feature_3')
                .new_branch('feature_5')
                .commit('introduce feature 5')
                .push(remote='origin_2')
        )

        mocker.patch('builtins.input', mock_input_returning('y', 'y'))
        expected_result = """
        Add feature_5 onto the inferred upstream (parent) branch feature_3? (y, N) 
        Added branch feature_5 onto feature_3
        Fetching origin...
        Push untracked branch feature_3 to origin? (y, Q) 
        Creating a PR from feature_5 to feature_3... OK, see www.github.com
        """
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )
