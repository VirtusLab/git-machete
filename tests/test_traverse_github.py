import textwrap

from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, mock_input_returning,
                      rewrite_branch_layout_file)
from .mockers_code_hosting import mock_from_url
from .mockers_github import MockGitHubAPIState, mock_pr_json, mock_urlopen


class TestTraverseGitHub(BaseTest):

    @staticmethod
    def github_api_state_for_test_traverse_sync_github_prs_multiple_same_head() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='build-chain', base='develop', number=1),
            mock_pr_json(head='build-chain', base='allow-ownership-link', number=2),
        )

    def test_traverse_sync_github_prs_multiple_same_head(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(
            self.github_api_state_for_test_traverse_sync_github_prs_multiple_same_head()))

        (
            self.repo_sandbox
            .new_branch("develop")
            .commit()
            .new_branch("allow-ownership-link")
            .new_branch("build-chain")
        )

        body: str = \
            """
            develop
                allow-ownership-link
                    build-chain
            """
        rewrite_branch_layout_file(body)

        assert_failure(
            ["traverse", "--sync-github-prs"],
            "Multiple PRs have build-chain as its head branch: #1, #2"
        )

    @staticmethod
    def github_api_state_for_test_traverse_sync_github_prs() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='allow-ownership-link', base='develop', number=1),
            mock_pr_json(head='build-chain', base='develop', number=2),
            mock_pr_json(head='call-ws', base='build-chain', number=3),
        )

    def test_traverse_sync_github_prs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = self.github_api_state_for_test_traverse_sync_github_prs()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        (
            self.repo_sandbox
            .new_branch("develop")
            .commit()
            .push()
            .new_branch("allow-ownership-link")
            .commit()
            .push()
            .new_branch("build-chain")
            .commit()
            .push()
            .new_branch("call-ws")
            .commit()
            .push()
        )

        body: str = \
            """
            develop
                allow-ownership-link
                    build-chain
                        call-ws
            """
        rewrite_branch_layout_file(body)
        self.repo_sandbox.check_out("build-chain")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))
        assert_success(
            ["traverse", "--sync-github-prs"],
            """
            Checking for open GitHub PRs... OK
            Branch build-chain has a different PR base (develop) in GitHub than in machete file (allow-ownership-link).
            Retarget PR #2 to allow-ownership-link? (y, N, q, yq)
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n"))
        assert_success(
            ["traverse", "--sync-github-prs"],
            """
            Checking for open GitHub PRs... OK
            Branch build-chain has a different PR base (develop) in GitHub than in machete file (allow-ownership-link).
            Retarget PR #2 to allow-ownership-link? (y, N, q, yq)

              develop
              |
              o-allow-ownership-link
                |
                o-build-chain *
                  |
                  o-call-ws

            No successor of build-chain needs to be slid out or synced with upstream branch or remote; nothing left to update
            """
        )

        assert_success(
            ["traverse", "--sync-github-prs", "-Wy"],
            """
            Fetching origin...

            Checking out the first root branch (develop)
            Checking for open GitHub PRs... OK

            Checking out build-chain

              develop
              |
              o-allow-ownership-link
                |
                o-build-chain *
                  |
                  o-call-ws

            Branch build-chain has a different PR base (develop) in GitHub than in machete file (allow-ownership-link).
            Retargeting PR #2 to allow-ownership-link...
            Base branch of PR #2 has been switched to allow-ownership-link
            Description of PR #2 has been updated
            Description of PR #3 (call-ws -> build-chain) has been updated

              develop
              |
              o-allow-ownership-link
                |
                o-build-chain *  PR #2 (some_other_user)
                  |
                  o-call-ws

            No successor of build-chain needs to be slid out or synced with upstream branch or remote; nothing left to update
            Returned to the initial branch build-chain
            """)

        pr2 = github_api_state.get_pull_by_number(2)
        assert pr2 is not None
        assert pr2['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #1

            ## Chain of upstream PRs as of 2025-01-14

            * PR #1:
              `develop` ← `allow-ownership-link`

              * **PR #2 (THIS ONE)**:
                `allow-ownership-link` ← `build-chain`

            <!-- end git-machete generated -->

            # Summary''')[1:]

        pr3 = github_api_state.get_pull_by_number(3)
        assert pr3 is not None
        assert pr3['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #2

            ## Chain of upstream PRs as of 2025-01-14

            * PR #1:
              `develop` ← `allow-ownership-link`

              * PR #2:
                `allow-ownership-link` ← `build-chain`

                * **PR #3 (THIS ONE)**:
                  `build-chain` ← `call-ws`

            <!-- end git-machete generated -->

            # Summary''')[1:]

        # Let's cover the case where the descriptions don't need to be updated after retargeting.

        pr2['base']['ref'] = 'develop'
        self.repo_sandbox.check_out("build-chain")
        assert_success(
            ["traverse", "-HWy"],
            """
            Fetching origin...

            Checking out the first root branch (develop)
            Checking for open GitHub PRs... OK

            Checking out build-chain

              develop
              |
              o-allow-ownership-link
                |
                o-build-chain *  PR #2 (some_other_user)
                  |
                  o-call-ws

            Branch build-chain has a different PR base (develop) in GitHub than in machete file (allow-ownership-link).
            Retargeting PR #2 to allow-ownership-link...
            Base branch of PR #2 has been switched to allow-ownership-link

              develop
              |
              o-allow-ownership-link
                |
                o-build-chain *  PR #2 (some_other_user)
                  |
                  o-call-ws

            No successor of build-chain needs to be slid out or synced with upstream branch or remote; nothing left to update
            Returned to the initial branch build-chain
            """)
