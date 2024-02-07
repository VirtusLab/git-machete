import os
import textwrap
from tempfile import mkdtemp

from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success,
                           fixed_author_and_committer_date_in_past,
                           launch_command, mock_input_returning,
                           mock_input_returning_y, rewrite_branch_layout_file)
from tests.mockers_github import (MockGitHubAPIState, mock_from_url,
                                  mock_github_token_for_domain_fake,
                                  mock_github_token_for_domain_none,
                                  mock_pr_json, mock_urlopen)


class TestGitHubCreatePR(BaseTest):

    @staticmethod
    def github_api_state_for_test_create_pr() -> MockGitHubAPIState:
        return MockGitHubAPIState(
            mock_pr_json(head='ignore-trailing', base='hotfix/add-trigger', number=3)
        )

    def test_github_create_pr(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')
        github_api_state = self.github_api_state_for_test_create_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

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
                .amend_commit("HOTFIX Add the trigger (amended)")
                .new_branch("ignore-trailing")
                .commit("Ignore trailing data")
                .sleep(1)
                .amend_commit("Ignore trailing data (amended)")
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
                    ignore-trailing  PR #3
                        chore/fields
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
            """
        rewrite_branch_layout_file(body)

        launch_command("github", "create-pr")
        # ahead of origin state, push is advised and accepted
        assert_success(
            ['status'],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing  PR #3 (diverged from & older than origin)
                |
                o-chore/fields (untracked)

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws *  PR #4 (some_other_user)
              |
              x-drop-constraint (untracked)
            """,
        )

        # untracked state (can only create PR when branch is pushed)
        self.repo_sandbox.check_out('chore/fields')

        self.repo_sandbox.write_to_file(".git/info/milestone", "42")
        self.repo_sandbox.write_to_file(".git/info/reviewers", "foo\n\nbar")
        self.repo_sandbox.write_to_file(".github/pull_request_template.md", "# PR title\n## Summary\n## Test plan\n")
        assert_success(
            ["github", "create-pr", "--draft"],
            """
            Push untracked branch chore/fields to origin? (y, Q)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing  PR #3 (diverged from & older than origin)
                  |
                  o-chore/fields *

              develop
              |
              x-allow-ownership-link (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              o-call-ws  PR #4 (some_other_user)
                |
                x-drop-constraint (untracked)

            Fetching origin...
            Creating a draft PR from chore/fields to ignore-trailing... OK, see www.github.com
            Updating description of PR #5 to include the chain of PRs... OK
            Setting milestone of PR #5 to #42... OK
            Adding github_user as assignee to PR #5... OK
            Adding foo, bar as reviewers to PR #5... OK
            """
        )
        pr = github_api_state.get_pull_by_number(5)
        assert pr is not None
        assert pr['title'] == 'remove outdated fields'
        assert pr['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #3

            ## Full chain of PRs as of 2023-12-31

            * PR #5: `chore/fields` ➔ `ignore-trailing`
            * PR #3: `ignore-trailing` ➔ `hotfix/add-trigger`

            <!-- end git-machete generated -->

            # PR title
            ## Summary
            ## Test plan
        ''')[1:]
        assert pr['draft'] is True
        assert pr['milestone'] == '42'
        assert pr['assignees'] == ['github_user']
        assert pr['reviewers'] == ['foo', 'bar']

        assert_success(
            ['status'],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing  PR #3 (diverged from & older than origin)
                |
                o-chore/fields *  PR #5 (some_other_user)

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws  PR #4 (some_other_user)
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
            o-hotfix/add-trigger *  PR #6 (some_other_user)
              |
              x-ignore-trailing  PR #3 (diverged from & older than origin)
                |
                o-chore/fields  PR #5 (some_other_user)

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws  PR #4 (some_other_user)
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
        rewrite_branch_layout_file(body)

        expected_error_message = "All commits in testing/endpoints branch are already included in develop branch.\n" \
                                 "Cannot create pull request."
        assert_failure(["github", "create-pr"], expected_error_message)

        self.repo_sandbox.check_out('develop')
        expected_error_message = "Branch develop does not have a parent branch (it is a root), " \
                                 "base branch for the PR cannot be established."
        assert_failure(["github", "create-pr"], expected_error_message)

        self.repo_sandbox.write_to_file(".git/info/reviewers", "invalid-user")
        self.repo_sandbox.write_to_file(".git/info/description", "# PR title\n")
        self.repo_sandbox.check_out("allow-ownership-link")
        assert_success(
            ["github", "create-pr", "--title=PR title set explicitly"],
            f"""
            Push allow-ownership-link to origin? (y, N, q)

              master
              |
              o-hotfix/add-trigger
                |
                x-ignore-trailing (diverged from & older than origin)
                  |
                  o-chore/fields

              develop
              |
              x-allow-ownership-link *
              | |
              | x-build-chain (untracked)
              |
              o-call-ws
              | |
              | x-drop-constraint (untracked)
              |
              o-testing/endpoints

            Fetching origin...
            Creating a PR from allow-ownership-link to develop... OK, see www.github.com
            Setting milestone of PR #7 to #42... OK
            Adding github_user as assignee to PR #7... OK
            Adding invalid-user as reviewer to PR #7...
            Warn: There are some invalid reviewers in .git{os.path.sep}info{os.path.sep}reviewers file.
            Skipped adding reviewers to pull request.
            """
        )

        pr = github_api_state.get_pull_by_number(7)
        assert pr is not None
        assert pr['title'] == 'PR title set explicitly'

    def test_github_create_pr_for_root_branch(self) -> None:
        self.repo_sandbox.new_branch("master").commit()
        rewrite_branch_layout_file("master")
        assert_failure(
            ["github", "create-pr"],
            "Branch master does not have a parent branch (it is a root), base branch for the PR cannot be established."
        )

    @staticmethod
    def github_api_state_for_test_create_pr_for_chain_in_description() -> MockGitHubAPIState:
        return MockGitHubAPIState(
            mock_pr_json(head='allow-ownership-link', base='develop', number=1),
            mock_pr_json(head='build-chain', base='allow-ownership-link', number=2)
        )

    def test_github_create_pr_for_chain_in_description(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = self.github_api_state_for_test_create_pr_for_chain_in_description()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')

        (
            self.repo_sandbox
            .new_branch("develop")
            .commit("first commit")
            .new_branch("allow-ownership-link")
            .commit("Enable ownership links")
            .push()
            .new_branch("build-chain")
            .commit("Build arbitrarily long chains of PRs")
            .push()
            .new_branch("call-ws")
            .commit("Call web service")
            .push()
            .new_branch("drop-constraint")
            .commit("Drop unneeded SQL constraints")
            .push()
        )
        body: str = \
            """
            develop
                allow-ownership-link  PR #1
                    build-chain  PR #2
                        call-ws
                            drop-constraint
            """
        rewrite_branch_layout_file(body)

        self.repo_sandbox.check_out("call-ws")
        launch_command("github", "create-pr")
        pr = github_api_state.get_pull_by_number(3)
        assert pr is not None
        assert pr['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #2

            ## Full chain of PRs as of 2023-12-31

            * PR #3: `call-ws` ➔ `build-chain`
            * PR #2: `build-chain` ➔ `allow-ownership-link`
            * PR #1: `allow-ownership-link` ➔ `develop`

            <!-- end git-machete generated -->
        ''')[1:]

        self.repo_sandbox.write_to_file(".github/pull_request_template.md", "# PR title\n## Summary\n## Test plan\n")
        self.repo_sandbox.check_out("drop-constraint")
        launch_command("github", "create-pr", "--yes")
        pr = github_api_state.get_pull_by_number(4)
        assert pr is not None
        assert pr['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #3

            ## Full chain of PRs as of 2023-12-31

            * PR #4: `drop-constraint` ➔ `call-ws`
            * PR #3: `call-ws` ➔ `build-chain`
            * PR #2: `build-chain` ➔ `allow-ownership-link`
            * PR #1: `allow-ownership-link` ➔ `develop`

            <!-- end git-machete generated -->

            # PR title
            ## Summary
            ## Test plan
        ''')[1:]

    @staticmethod
    def github_api_state_for_test_create_pr_missing_base_branch_on_remote() -> MockGitHubAPIState:
        return MockGitHubAPIState(
            mock_pr_json(head='chore/redundant_checks', base='restrict_access', number=18)
        )

    def test_github_create_pr_missing_base_branch_on_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        github_api_state = self.github_api_state_for_test_create_pr_missing_base_branch_on_remote()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        (
            self.repo_sandbox.new_branch("root")
                .commit("initial commit")
                .new_branch("develop")
                .commit("first commit on develop")
                .push()
                .new_branch("feature/api_handling")
                .commit("Introduce GET and POST methods on API")
                .new_branch("feature/api_exception_handling")
                .commit("catch exceptions coming from API\n\ncommit body\nanother line")
                .push()
                .delete_branch("root")
        )
        body: str = \
            """
            develop
                feature/api_handling
                    feature/api_exception_handling
            """
        rewrite_branch_layout_file(body)

        expected_msg = ("Fetching origin...\n"
                        "Warn: Base branch for this PR (feature/api_handling) is not found on remote, pushing...\n"
                        "Pushing untracked branch feature/api_handling to origin...\n"
                        "Creating a PR from feature/api_exception_handling to feature/api_handling... OK, see www.github.com\n")

        self.repo_sandbox.set_git_config_key("machete.github.annotateWithUrls", "true")
        assert_success(['github', 'create-pr', '--yes'], expected_msg)
        assert_success(
            ['status'],
            """
            develop
            |
            o-feature/api_handling
              |
              o-feature/api_exception_handling *  PR #19 (some_other_user) www.github.com
            """,
        )
        pr = github_api_state.get_pull_by_number(19)
        assert pr is not None
        assert pr['body'] == 'commit body\nanother line'

    @staticmethod
    def github_api_state_for_test_github_create_pr_with_multiple_non_origin_remotes() -> MockGitHubAPIState:
        return MockGitHubAPIState(
            mock_pr_json(head='branch-1', base='root', number=15)
        )

    def test_github_create_pr_with_multiple_non_origin_remotes(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')
        github_api_state = self.github_api_state_for_test_github_create_pr_with_multiple_non_origin_remotes()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        origin_1_remote_path = mkdtemp()
        origin_2_remote_path = mkdtemp()
        self.repo_sandbox.new_repo(origin_1_remote_path, bare=True, switch_dir_to_new_repo=False)
        self.repo_sandbox.new_repo(origin_2_remote_path, bare=True, switch_dir_to_new_repo=False)

        # branch feature present in each of the remotes, no branch tracking data, remote origin_1 picked manually
        (
            self.repo_sandbox
                .remove_remote('origin')
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
                .commit('introduce feature\n\ncommit body')
                .push(remote='origin_1', set_upstream=False)
                .push(remote='origin_2', set_upstream=False)
        )
        body: str = \
            """
            root
                branch-1
                    feature
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('q'))
        expected_result = """
        Branch feature is untracked and there's no origin repository.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit the operation:
        """
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('3'))
        assert_failure(
            ['github', 'create-pr'],
            "Invalid index: 3"
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('xd'))
        assert_failure(
            ['github', 'create-pr'],
            "Could not establish remote repository, operation interrupted."
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('1', 'n'))
        assert_failure(
            ['github', 'create-pr'],
            "Multiple non-origin remotes correspond to GitHub in this repository: origin_1, origin_2 -> aborting.\n"
            "You can also select the repository by providing some or all of git config keys: "
            "machete.github.{domain,remote,organization,repository}.\n"  # noqa: FS003
        )

        expected_result = """
        Branch feature is untracked and there's no origin repository.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit the operation:
        Branch feature is untracked, but its remote counterpart candidate origin_1/feature already exists and both branches point to the same commit.
        Set the remote of feature to origin_1 without pushing or pulling? (y, N, q, yq)
        """  # noqa: E501

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('1', 'q'))
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('1', 'yq'))
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        self.repo_sandbox.execute("git branch --unset-upstream feature")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('1', 'y'))
        expected_result = """
        Branch feature is untracked and there's no origin repository.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit the operation:
        Branch feature is untracked, but its remote counterpart candidate origin_1/feature already exists and both branches point to the same commit.
        Set the remote of feature to origin_1 without pushing or pulling? (y, N, q, yq)

          root
          |
          o-branch-1
            |
            o-feature *

        Fetching origin_1...
        Creating a PR from feature to branch-1... OK, see www.github.com
        Updating description of PR #16 to include the chain of PRs... OK
        """  # noqa: E501

        self.repo_sandbox.write_to_file(".git/info/description", "overridden description")
        self.repo_sandbox.set_git_config_key("machete.github.forceDescriptionFromCommitMessage", "true")
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )
        pr = github_api_state.get_pull_by_number(16)
        assert pr is not None
        assert pr['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #15

            ## Full chain of PRs as of 2023-12-31

            * PR #16: `feature` ➔ `branch-1`
            * PR #15: `branch-1` ➔ `root`

            <!-- end git-machete generated -->

            commit body''')[1:]

        # branch feature_1 present in each of the remotes, tracking data present
        (
            self.repo_sandbox.check_out('feature')
                .new_branch('feature_1')
                .commit('introduce feature 1')
                .push(remote='origin_1')
                .push(remote='origin_2')
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('n'))
        assert_failure(
            ['github', 'create-pr'],
            "Command github create-pr can NOT be executed on the branch that is not managed by git machete "
            "(is not present in branch layout file). "
            "To successfully execute this command either add current branch to the file via commands add, discover or edit "
            "or agree on adding the branch to the branch layout file during the execution of github create-pr command."
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y'))
        expected_result = """
        Add feature_1 onto the inferred upstream (parent) branch feature? (y, N)
        Added branch feature_1 onto feature
        Fetching origin_2...
        Creating a PR from feature_1 to feature... OK, see www.github.com
        Updating description of PR #17 to include the chain of PRs... OK
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

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y', '1', 'y'))

        expected_result = """
        Add feature_2 onto the inferred upstream (parent) branch feature? (y, N)
        Added branch feature_2 onto feature
        Branch feature_2 is untracked and there's no origin repository.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit the operation:
        Push untracked branch feature_2 to origin_1? (y, Q)

          root
          |
          o-branch-1
            |
            o-feature  PR #16 (some_other_user)
              |
              o-feature_1  PR #17 (some_other_user)
              |
              o-feature_2 *

        Fetching origin_1...
        Creating a PR from feature_2 to feature... OK, see www.github.com
        Updating description of PR #18 to include the chain of PRs... OK
        """
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

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y'))
        expected_result = """
        Add feature_3 onto the inferred upstream (parent) branch feature_2? (y, N)
        Added branch feature_3 onto feature_2
        Fetching origin_1...
        Creating a PR from feature_3 to feature_2... OK, see www.github.com
        Updating description of PR #19 to include the chain of PRs... OK
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

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y', 'y'))
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

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y', 'y'))
        expected_result = """
        Add feature_5 onto the inferred upstream (parent) branch feature_3? (y, N)
        Added branch feature_5 onto feature_3
        Fetching origin...
        Warn: Base branch for this PR (feature_3) is not found on remote, pushing...
        Push untracked branch feature_3 to origin? (y, Q)
        Creating a PR from feature_5 to feature_3... OK, see www.github.com
        """
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

    def test_github_create_pr_for_no_push_qualifier(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitHubAPIState()))

        (
            self.repo_sandbox
            .new_branch("master").commit().push()
            .new_branch("develop").commit()
        )

        rewrite_branch_layout_file("master\n\tdevelop push=no")

        assert_success(
            ['github', 'create-pr'],
            """
            Fetching origin...
            Creating a PR from develop to master... OK, see www.github.com
            """
        )

    def test_github_create_pr_for_no_remotes(self) -> None:
        (
            self.repo_sandbox
            .remove_remote()
            .new_branch("master").commit()
            .new_branch("develop").commit()
        )

        rewrite_branch_layout_file("master\n\tdevelop")

        assert_failure(
            ['github', 'create-pr'],
            "Could not create pull request - there are no remote repositories!"
        )

    def test_github_create_pr_for_branch_behind_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitHubAPIState()))

        (
            self.repo_sandbox
            .new_branch("master").commit().push()
            .new_branch("develop").commit().commit().push().reset_to("HEAD~")
        )

        rewrite_branch_layout_file("master\n\tdevelop")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('q'))
        assert_failure(
            ['github', 'create-pr'],
            "Pull request creation interrupted."
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y'))
        assert_success(
            ['github', 'create-pr'],
            """
            Warn: Branch develop is behind its remote counterpart. Consider using git pull.
            Proceed with pull request creation? (y, Q)
            Fetching origin...
            Creating a PR from develop to master... OK, see www.github.com
            """
        )

    def test_github_create_pr_for_untracked_branch(self, mocker: MockerFixture) -> None:
        (
            self.repo_sandbox
            .new_branch("master").commit().push()
            .new_branch("develop").commit()
        )

        rewrite_branch_layout_file("master\n\tdevelop")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('q'))
        assert_success(
            ['github', 'create-pr'],
            "Push untracked branch develop to origin? (y, Q)\n"
        )

    def test_github_create_pr_for_branch_diverged_from_and_newer_than_remote(self, mocker: MockerFixture) -> None:
        (
            self.repo_sandbox
            .new_branch("master").commit().push()
            .new_branch("develop").commit().push()
            .amend_commit("Different commit message")
        )

        rewrite_branch_layout_file("master\n\tdevelop")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('yq'))
        assert_success(
            ['github', 'create-pr'],
            """
            Branch develop diverged from (and has newer commits than) its remote counterpart origin/develop.
            Push develop with force-with-lease to origin? (y, N, q)
            """
        )

    def test_github_create_pr_for_branch_diverged_from_and_older_than_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitHubAPIState()))

        (
            self.repo_sandbox
            .new_branch("master").commit().push()
            .new_branch("develop").commit().push()
        )
        with fixed_author_and_committer_date_in_past():
            self.repo_sandbox.amend_commit()

        rewrite_branch_layout_file("master\n\tdevelop")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y'))
        assert_success(
            ['github', 'create-pr'],
            """
            Warn: Branch develop is diverged from and older than its remote counterpart. Consider using git reset --keep.
            Proceed with pull request creation? (y, Q)
            Fetching origin...
            Creating a PR from develop to master... OK, see www.github.com
            """
        )
