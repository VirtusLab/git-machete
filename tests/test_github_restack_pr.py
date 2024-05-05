import textwrap

from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success,
                           fixed_author_and_committer_date_in_past,
                           rewrite_branch_layout_file)
from tests.mockers_code_hosting import mock_from_url
from tests.mockers_github import (MockGitHubAPIState,
                                  mock_github_token_for_domain_fake,
                                  mock_pr_json, mock_urlopen)


class TestGitHubRestackPR(BaseTest):

    @staticmethod
    def github_api_state_for_test_restack_pr() -> MockGitHubAPIState:
        body = textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #14

            <!-- end git-machete generated -->
            # Summary''')[1:]
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='feature_1', base='develop', number=14, draft=True),
            mock_pr_json(head='feature', base='develop', number=15, body=body),
            mock_pr_json(head='multiple-pr-branch', base='develop', number=16),
            mock_pr_json(head='multiple-pr-branch', base='feature', number=17),
        )

    def test_github_restack_pr_no_prs_or_multiple_prs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_restack_pr()))

        self.repo_sandbox.new_branch("develop").commit()

        assert_failure(
            ['github', 'restack-pr'],
            "No PRs in example-org/example-repo have develop as its head branch"
        )

        self.repo_sandbox.new_branch("multiple-pr-branch").commit()
        assert_failure(
            ['github', 'restack-pr'],
            "Multiple PRs in example-org/example-repo have multiple-pr-branch as its head branch: #16, #17"
        )

    def test_github_restack_pr_branch_in_sync(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = self.github_api_state_for_test_restack_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

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
        )
        body: str = \
            """
            master
                develop
                feature
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'restack-pr'],
            """
            Base branch of PR #15 has been switched to master
            Description of PR #15 has been updated
            """
        )
        pr = github_api_state.get_pull_by_number(15)
        assert pr is not None
        assert pr['draft'] is False
        assert pr['base']['ref'] == 'master'
        assert pr['body'] == '# Summary'

    def test_github_restack_pr_branch_untracked(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = self.github_api_state_for_test_restack_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        (
            self.repo_sandbox.new_branch("master")
            .commit()
            .new_branch('feature_1')
            .commit()
        )
        body: str = \
            """
            master
                feature_1
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'restack-pr'],
            """
            Base branch of PR #14 has been switched to master
            Pushing untracked branch feature_1 to origin...

              master (untracked)
              |
              o-feature_1 *  PR #14 (some_other_user)

            """
        )
        pr = github_api_state.get_pull_by_number(14)
        assert pr is not None
        assert pr['draft'] is True
        assert pr['base']['ref'] == 'master'
        assert pr['body'] == '# Summary'

    def test_github_restack_pr_branch_diverged_and_newer(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = self.github_api_state_for_test_restack_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        with fixed_author_and_committer_date_in_past():
            (
                self.repo_sandbox.new_branch("master")
                .commit()
                .new_branch('feature')
                .commit()
                .push()
            )
        self.repo_sandbox.amend_commit()
        body: str = \
            """
            master
                feature
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'restack-pr'],
            """
            PR #15 has been temporarily marked as draft
            Base branch of PR #15 has been switched to master
            Description of PR #15 has been updated
            Branch feature diverged from (and has newer commits than) its remote counterpart origin/feature.
            Pushing feature with force-with-lease to origin...

              master (untracked)
              |
              o-feature *  PR #15 (some_other_user)

            PR #15 has been marked as ready for review again
            """
        )
        pr = github_api_state.get_pull_by_number(15)
        assert pr is not None
        assert pr['draft'] is False
        assert pr['base']['ref'] == 'master'

    def test_github_restack_pr_branch_ahead(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = self.github_api_state_for_test_restack_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        (
            self.repo_sandbox.new_branch("master")
            .commit()
            .new_branch('feature')
            .commit()
            .push()
            .commit()
            .set_git_config_key('machete.github.domain', 'git.example.org')
        )
        body: str = \
            """
            master
                feature
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'restack-pr'],
            """
            PR #15 has been temporarily marked as draft
            Base branch of PR #15 has been switched to master
            Description of PR #15 has been updated
            Pushing feature to origin...

              master (untracked)
              |
              o-feature *  PR #15 (some_other_user)

            PR #15 has been marked as ready for review again
            """
        )
        pr = github_api_state.get_pull_by_number(15)
        assert pr is not None
        assert pr['draft'] is False
        assert pr['base']['ref'] == 'master'

    def test_github_restack_pr_branch_ahead_push_no(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = self.github_api_state_for_test_restack_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        (
            self.repo_sandbox.new_branch("master")
            .commit()
            .new_branch('feature')
            .commit()
            .push()
            .commit()
        )

        body: str = \
            """
            master
                feature push=no
            """
        rewrite_branch_layout_file(body)
        assert_failure(
            ['github', 'restack-pr'],
            """
            Branch feature is marked as push=no; aborting the restack.
            Did you want to just use git machete github retarget-pr?
            """
        )

        body = \
            """
            master
                feature
            """
        rewrite_branch_layout_file(body)
        assert_success(
            ['github', 'restack-pr'],
            """
            PR #15 has been temporarily marked as draft
            Base branch of PR #15 has been switched to master
            Description of PR #15 has been updated
            Pushing feature to origin...

              master (untracked)
              |
              o-feature *  PR #15 (some_other_user)

            PR #15 has been marked as ready for review again
            """
        )
        pr = github_api_state.get_pull_by_number(15)
        assert pr is not None
        assert pr['draft'] is False
        assert pr['base']['ref'] == 'master'

    def test_github_restack_pr_branch_no_behind(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_restack_pr()))

        (
            self.repo_sandbox.new_branch("master")
            .commit()
            .new_branch('feature')
            .commit()
            .push()
            .reset_to("HEAD~")
        )
        body: str = \
            """
            master
                feature
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'restack-pr'],
            """
            Warn: Branch feature is behind its remote counterpart. Consider using git pull.

            Base branch of PR #15 has been switched to master
            Description of PR #15 has been updated
            """
        )

    def test_github_restack_pr_branch_diverged_and_older(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = self.github_api_state_for_test_restack_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        (
            self.repo_sandbox.new_branch("master")
            .commit()
            .new_branch('feature')
            .commit()
            .push()
        )
        with fixed_author_and_committer_date_in_past():
            self.repo_sandbox.amend_commit()

        body: str = \
            """
            master
                feature
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'restack-pr'],
            """
            Warn: Branch feature is diverged from and older than its remote counterpart. Consider using git reset --keep.

            Base branch of PR #15 has been switched to master
            Description of PR #15 has been updated
            """
        )
        pr = github_api_state.get_pull_by_number(15)
        assert pr is not None
        assert pr['draft'] is False
        assert pr['base']['ref'] == 'master'
