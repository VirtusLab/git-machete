import textwrap

from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, mock_input_returning,
                      rewrite_branch_layout_file)
from .mockers_code_hosting import mock_from_url
from .mockers_git_repository import (check_out, commit,
                                     create_repo_with_remote,
                                     delete_remote_branch, new_branch, push)
from .mockers_github import (MockGitHubAPIState,
                             mock_github_token_for_domain_fake, mock_pr_json,
                             mock_urlopen)


class TestTraverseGitHub(BaseTest):

    @staticmethod
    def github_api_state_for_test_traverse_sync_github_prs_multiple_same_head() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='build-chain', base='develop', number=1),
            mock_pr_json(head='build-chain', base='allow-ownership-link', number=2),
        )

    def test_traverse_sync_github_prs_multiple_same_head(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, "git_machete.github.GitHubToken.for_domain", mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(
            self.github_api_state_for_test_traverse_sync_github_prs_multiple_same_head()))

        create_repo_with_remote()
        new_branch("develop")
        commit()
        new_branch("allow-ownership-link")
        new_branch("build-chain")

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

    def test_traverse_sync_retarget_github_prs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, "git_machete.github.GitHubToken.for_domain", mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')
        github_api_state = self.github_api_state_for_test_traverse_sync_github_prs()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        create_repo_with_remote()
        new_branch("develop")
        commit()
        push()
        new_branch("allow-ownership-link")
        commit()
        push()
        new_branch("build-chain")
        commit()
        push()
        new_branch("call-ws")
        commit()
        push()

        body: str = \
            """
            develop
                allow-ownership-link
                    build-chain
                        call-ws
            """
        rewrite_branch_layout_file(body)
        check_out("build-chain")

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

            ## Chain of upstream PRs as of 2023-12-31

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

            ## Chain of upstream PRs as of 2023-12-31

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
        check_out("build-chain")
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

    def test_traverse_sync_create_github_prs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        github_api_state = MockGitHubAPIState.with_prs()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        create_repo_with_remote()
        new_branch("develop")
        commit()
        new_branch("allow-ownership-link")
        commit()
        new_branch("build-chain")
        commit()
        new_branch("call-ws")
        commit()

        body: str = \
            """
            develop
                allow-ownership-link
                    build-chain
                        call-ws
            """
        rewrite_branch_layout_file(body)
        check_out("develop")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("y", "y", "q"))
        assert_success(
            ["traverse", "--sync-github-prs"],
            """
            Checking for open GitHub PRs... OK
            Push untracked branch develop to origin? (y, N, q, yq)

            Checking out allow-ownership-link

              develop
              |
              o-allow-ownership-link * (untracked)
                |
                o-build-chain (untracked)
                  |
                  o-call-ws (untracked)

            Push untracked branch allow-ownership-link to origin? (y, N, q, yq)

            Branch allow-ownership-link does not have a PR in GitHub.
            Create a PR from allow-ownership-link to develop? (y, d[raft], N, q, yq)
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("yq"))
        assert_success(
            ["traverse", "--sync-github-prs"],
            """
            Checking for open GitHub PRs... OK
            Branch allow-ownership-link does not have a PR in GitHub.
            Create a PR from allow-ownership-link to develop? (y, d[raft], N, q, yq)
            Checking if base branch develop exists in origin remote... YES
            Creating a PR from allow-ownership-link to develop... OK, see www.github.com
            Adding github_user as assignee to PR #1... OK
            Updating descriptions of other PRs...
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("y", "", "y", "draft"))
        assert_success(
            ["traverse", "--sync-github-prs"],
            """
            Checking for open GitHub PRs... OK
            Checking out build-chain

              develop
              |
              o-allow-ownership-link  PR #1 (some_other_user)
                |
                o-build-chain * (untracked)
                  |
                  o-call-ws (untracked)

            Push untracked branch build-chain to origin? (y, N, q, yq)

            Branch build-chain does not have a PR in GitHub.
            Create a PR from build-chain to allow-ownership-link? (y, d[raft], N, q, yq)

            Checking out call-ws

              develop
              |
              o-allow-ownership-link  PR #1 (some_other_user)
                |
                o-build-chain
                  |
                  o-call-ws * (untracked)

            Push untracked branch call-ws to origin? (y, N, q, yq)

            Branch call-ws does not have a PR in GitHub.
            Create a PR from call-ws to build-chain? (y, d[raft], N, q, yq)
            Checking if base branch build-chain exists in origin remote... YES
            Creating a draft PR from call-ws to build-chain... OK, see www.github.com
            Adding github_user as assignee to PR #2... OK
            Updating descriptions of other PRs...

              develop
              |
              o-allow-ownership-link  PR #1 (some_other_user)
                |
                o-build-chain
                  |
                  o-call-ws *  PR #2 (some_other_user)

            Reached branch call-ws which has no successor; nothing left to update
            """
        )
