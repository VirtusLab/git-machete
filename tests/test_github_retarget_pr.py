import textwrap
from tempfile import mkdtemp

from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success, launch_command,
                           rewrite_branch_layout_file)
from tests.mockers_github import (MockGitHubAPIState, mock_from_url,
                                  mock_pr_json, mock_urlopen)


class TestGitHubRetargetPR(BaseTest):

    @staticmethod
    def github_api_state_for_test_retarget_pr() -> MockGitHubAPIState:
        return MockGitHubAPIState(
            mock_pr_json(head='feature', base='master', number=15),
            mock_pr_json(head='feature_1', base='master', number=20, body='# Based on PR #10\n\n# Summary'),
            mock_pr_json(head='feature_2', base='master', number=25, body=None),
            mock_pr_json(head='feature_3', base='master', number=30),
            mock_pr_json(head='feature_4', base='feature', number=35),
            # Let's include another PR for `feature_2`, but with a different base branch
            mock_pr_json(head='feature_4', base='feature', number=40),
        )

    def test_github_retarget_pr(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_retarget_pr()))

        (
            self.repo_sandbox.new_branch("master")
            .commit()
            .new_branch("develop")
            .commit()
            .commit()
            .push()
            .new_branch('feature')
            .commit()
            .push()
            .check_out('develop')
            .new_branch('feature_4')
            .push()
            .check_out('feature')
            # Let's force a 307 redirect during the PATCH.
            .add_remote('new_origin', 'https://github.com/example-org/old-example-repo.git')
        )
        body: str = \
            """
            master
                develop
                    feature
                    feature_4
            """
        rewrite_branch_layout_file(body)

        launch_command("anno", "-H")

        expected_status_output = """
        master (untracked)
        |
        o-develop
          |
          o-feature *  PR #15 (some_other_user) WRONG PR BASE or MACHETE PARENT? PR has master rebase=no push=no
          |
          o-feature_4  PR #40 (some_other_user) WRONG PR BASE or MACHETE PARENT? PR has feature rebase=no push=no
        """
        assert_success(
            ['status'],
            expected_result=expected_status_output
        )

        assert_success(
            ['github', 'retarget-pr'],
            """
            Warn: GitHub API returned 307 HTTP status with error message: Temporary redirect.
            It looks like the organization or repository name got changed recently and is outdated.
            New organization is example-org and new repository is example-repo.
            You can update your remote repository via: git remote set-url <remote_name> <new_repository_url>.
            Base branch of PR #15 has been switched to develop
            """
        )

        expected_status_output = """
        master (untracked)
        |
        o-develop
          |
          o-feature *  PR #15 (some_other_user) rebase=no push=no
          |
          o-feature_4  PR #40 (some_other_user) WRONG PR BASE or MACHETE PARENT? PR has feature rebase=no push=no
        """
        assert_success(
            ['status'],
            expected_result=expected_status_output
        )

        assert_success(
            ['github', 'retarget-pr'],
            'Base branch of PR #15 is already develop\n'
        )

        self.repo_sandbox.check_out("feature_4")

        assert_failure(
            ['github', 'retarget-pr'],
            'Multiple PRs have feature_4 as its head: #35, #40'
        )

    @staticmethod
    def github_api_state_for_test_github_retarget_pr_explicit_branch() -> MockGitHubAPIState:
        return MockGitHubAPIState(
            mock_pr_json(head='feature', base='root', number=15)
        )

    def test_github_retarget_pr_explicit_branch(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'urllib.request.urlopen',
                          mock_urlopen(self.github_api_state_for_test_github_retarget_pr_explicit_branch()))

        branch_first_commit_msg = "First commit on branch."
        branch_second_commit_msg = "Second commit on branch."
        (
            self.repo_sandbox.new_branch("root")
                .commit("First commit on root.")
                .new_branch("branch-1")
                .commit(branch_first_commit_msg)
                .commit(branch_second_commit_msg)
                .push()
                .new_branch('feature')
                .commit('introduce feature')
                .push()
                .check_out('root')
                .new_branch('branch-without-pr')
                .commit('branch-without-pr')
                .push()
                .add_remote('new_origin', 'https://github.com/user/repo.git')
                .check_out('root')
        )

        body: str = \
            """
            root
                branch-1
                    feature
                branch-without-pr
            """
        rewrite_branch_layout_file(body)
        launch_command("anno", "-H")

        expected_status_output = """
        root * (untracked)
        |
        o-branch-1
        | |
        | o-feature  PR #15 (some_other_user) WRONG PR BASE or MACHETE PARENT? PR has root rebase=no push=no
        |
        o-branch-without-pr
        """
        assert_success(
            ['status'],
            expected_result=expected_status_output
        )

        assert_success(
            ['github', 'retarget-pr', '--branch', 'feature'],
            'Base branch of PR #15 has been switched to branch-1\n'
        )

        expected_status_output = """
        root * (untracked)
        |
        o-branch-1
        | |
        | o-feature  PR #15 (some_other_user) rebase=no push=no
        |
        o-branch-without-pr
        """
        assert_success(
            ['status'],
            expected_result=expected_status_output
        )

        assert_failure(
            ["github", "retarget-pr", "--branch", "branch-without-pr"],
            "No PRs have branch-without-pr as its head")

        assert_success(
            ['github', 'retarget-pr', '--branch', 'branch-without-pr', '--ignore-if-missing'],
            "Warn: no PRs have branch-without-pr as its head\n")

    def test_github_retarget_pr_multiple_non_origin_remotes(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = self.github_api_state_for_test_retarget_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')

        branch_first_commit_msg = "First commit on branch."
        branch_second_commit_msg = "Second commit on branch."

        origin_1_remote_path = mkdtemp()
        origin_2_remote_path = mkdtemp()
        self.repo_sandbox.new_repo(origin_1_remote_path, bare=True, switch_dir_to_new_repo=False)
        self.repo_sandbox.new_repo(origin_2_remote_path, bare=True, switch_dir_to_new_repo=False)

        # branch feature present in each remote, no branch tracking data
        (
            self.repo_sandbox.remove_remote()
                .new_branch("root")
                .add_remote('origin_1', origin_1_remote_path)
                .add_remote('origin_2', origin_2_remote_path)
                .commit("First commit on root.")
                .push(remote='origin_1')
                .push(remote='origin_2')
                .new_branch("branch-1")
                .commit(branch_first_commit_msg)
                .commit(branch_second_commit_msg)
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
        rewrite_branch_layout_file(body)

        expected_error_message = (
            "Multiple non-origin remotes correspond to GitHub in this repository: origin_1, origin_2 -> aborting.\n"
            "You can also select the repository by providing some or all of git config keys: "
            "machete.github.{domain,remote,organization,repository}.\n"  # noqa: FS003
        )
        assert_failure(["github", "retarget-pr"], expected_error_message)

        # branch feature_1 present in each remote, tracking data present
        (
            self.repo_sandbox.check_out('feature')
                .new_branch('feature_1')
                .commit('introduce feature 1')
                .push(remote='origin_1')
                .push(remote='origin_2')
        )

        body = \
            """
            root
                branch-1
                    feature
                        feature_1
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'retarget-pr'],
            'Base branch of PR #20 has been switched to feature\n'
            'Checking for open GitHub PRs (to determine PR chain)... OK\n'
            'Description of PR #20 has been updated\n'
        )
        pr20 = github_api_state.get_pull_by_number(20)
        assert pr20 is not None
        assert pr20['base']['ref'] == 'feature'
        assert pr20['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #15

            ## Full chain of PRs as of 2023-12-31

            * PR #20: `feature_1` ➔ `feature`
            * PR #15: `feature` ➔ `master`

            <!-- end git-machete generated -->
            # Summary''')[1:]

        # branch feature_2 is not present in any of the remotes
        (
            self.repo_sandbox.check_out('feature')
                .new_branch('feature_2')
                .commit('introduce feature 2')
        )

        body = \
            """
            root
                branch-1
                    feature
                        feature_1
                        feature_2
            """
        rewrite_branch_layout_file(body)

        assert_failure(["github", "retarget-pr"], expected_error_message)

        # branch feature_2 present in only one remote: origin_1 and there is no tracking data available -> infer the remote
        (
            self.repo_sandbox.check_out('feature_2')
                .push(remote='origin_1', set_upstream=False)
        )

        assert_success(
            ['github', 'retarget-pr'],
            'Base branch of PR #25 has been switched to feature\n'
            'Checking for open GitHub PRs (to determine PR chain)... OK\n'
            'Description of PR #25 has been updated\n'
        )
        pr25 = github_api_state.get_pull_by_number(25)
        assert pr25 is not None
        assert pr25['base']['ref'] == 'feature'
        assert pr25['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #15

            ## Full chain of PRs as of 2023-12-31

            * PR #25: `feature_2` ➔ `feature`
            * PR #15: `feature` ➔ `master`

            <!-- end git-machete generated -->''')[1:]

        # branch feature_3 present in only one remote: origin_1 and has tracking data
        (
            self.repo_sandbox.check_out('feature_2')
                .new_branch('feature_3')
                .commit('introduce feature 3')
                .push(remote='origin_1')
        )

        body = \
            """
            root
                branch-1
                    feature
                        feature_1
                        feature_2
                            feature_3
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'retarget-pr'],
            'Base branch of PR #30 has been switched to feature_2\n'
            'Checking for open GitHub PRs (to determine PR chain)... OK\n'
            'Description of PR #30 has been updated\n'
        )
        pr30 = github_api_state.get_pull_by_number(30)
        assert pr30 is not None
        assert pr30['base']['ref'] == 'feature_2'
        assert pr30['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #25

            ## Full chain of PRs as of 2023-12-31

            * PR #30: `feature_3` ➔ `feature_2`
            * PR #25: `feature_2` ➔ `feature`
            * PR #15: `feature` ➔ `master`

            <!-- end git-machete generated -->
            # Summary''')[1:]

        body = \
            """
            root
                branch-1
                    feature
                        feature_1
                        feature_2
                        feature_3
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'retarget-pr'],
            'Base branch of PR #30 has been switched to feature\n'
            'Checking for open GitHub PRs (to determine PR chain)... OK\n'
            'Description of PR #30 has been updated\n'
        )
        pr30 = github_api_state.get_pull_by_number(30)
        assert pr30 is not None
        assert pr30['base']['ref'] == 'feature'
        assert pr30['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #15

            ## Full chain of PRs as of 2023-12-31

            * PR #30: `feature_3` ➔ `feature`
            * PR #15: `feature` ➔ `master`

            <!-- end git-machete generated -->
            # Summary''')[1:]

        body = \
            """
            root
                branch-1
                    feature
                        feature_1
                        feature_2
                feature_3
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'retarget-pr'],
            'Base branch of PR #30 has been switched to root\n'
            'Description of PR #30 has been updated\n'
        )
        pr30 = github_api_state.get_pull_by_number(30)
        assert pr30 is not None
        assert pr30['base']['ref'] == 'root'
        assert pr30['body'] == '# Summary'

    @staticmethod
    def github_api_state_for_test_retarget_pr_root_branch() -> MockGitHubAPIState:
        return MockGitHubAPIState(
            mock_pr_json(head='master', base='root', number=15)
        )

    def test_github_retarget_pr_root_branch(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_retarget_pr_root_branch()))

        self.repo_sandbox.new_branch("master").commit()
        rewrite_branch_layout_file("master")

        assert_failure(
            ['github', 'retarget-pr'],
            "Branch master does not have a parent branch (it is a root) even though there is an open PR #15 to root.\n"
            "Consider modifying the branch layout file (git machete edit) so that master is a child of root."
        )
