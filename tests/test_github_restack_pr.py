import textwrap

from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.cli_runner import assert_failure, assert_success, rewrite_branch_layout_file
from tests.git_repository import (add_remote, amend_commit, commit, create_repo, create_repo_with_remote, new_branch, push, reset_to,
                                  set_git_config_key)
from tests.mockers import fixed_author_and_committer_date_in_past
from tests.mockers_code_hosting import mock_from_url
from tests.mockers_github import MockGitHubAPIState, mock_github_token_for_domain_fake, mock_pr_json, mock_urlopen


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

        create_repo_with_remote()
        new_branch("develop")
        commit()

        assert_failure(
            ['github', 'restack-pr'],
            "No PRs in example-org/example-repo have develop as its head branch"
        )

        new_branch("multiple-pr-branch")
        commit()

        assert_failure(
            ['github', 'restack-pr'],
            "Multiple PRs in example-org/example-repo have multiple-pr-branch as its head branch: #16, #17"
        )

    def test_github_restack_pr_branch_in_sync(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = self.github_api_state_for_test_restack_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        create_repo_with_remote()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        commit()
        push()
        new_branch('feature')
        commit()
        push()

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
            Switching base branch of PR #15 to master... OK
            Updating description of PR #15... OK
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

        create_repo_with_remote()
        new_branch("master")
        commit()
        new_branch('feature_1')
        commit()

        body: str = \
            """
            master
                feature_1
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'restack-pr'],
            """
            Temporarily marking PR #14 as draft... OK (already a draft)
            Switching base branch of PR #14 to master... OK
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

        create_repo_with_remote()
        with fixed_author_and_committer_date_in_past():
            new_branch("master")
            commit()
            new_branch('feature')
            commit()
            push()

        amend_commit()
        body: str = \
            """
            master
                feature
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'restack-pr'],
            """
            Temporarily marking PR #15 as draft... OK
            Switching base branch of PR #15 to master... OK
            Updating description of PR #15... OK
            Branch feature diverged from (and has newer commits than) its remote counterpart origin/feature.
            Pushing feature with force-with-lease to origin...

              master (untracked)
              |
              o-feature *  PR #15 (some_other_user)

            Marking PR #15 as ready for review again... OK
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

        create_repo_with_remote()
        new_branch("master")
        commit()
        new_branch('feature')
        commit()
        push()
        commit()
        set_git_config_key('machete.github.domain', 'git.example.org')

        body: str = \
            """
            master
                feature
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'restack-pr'],
            """
            Temporarily marking PR #15 as draft... OK
            Switching base branch of PR #15 to master... OK
            Updating description of PR #15... OK
            Pushing feature to origin...

              master (untracked)
              |
              o-feature *  PR #15 (some_other_user)

            Marking PR #15 as ready for review again... OK
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

        create_repo_with_remote()
        new_branch("master")
        commit()
        new_branch('feature')
        commit()
        push()
        commit()

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
            Temporarily marking PR #15 as draft... OK
            Switching base branch of PR #15 to master... OK
            Updating description of PR #15... OK
            Pushing feature to origin...

              master (untracked)
              |
              o-feature *  PR #15 (some_other_user)

            Marking PR #15 as ready for review again... OK
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

        create_repo_with_remote()
        new_branch("master")
        commit()
        new_branch('feature')
        commit()
        push()
        reset_to("HEAD~")

        body: str = \
            """
            master
                feature
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'restack-pr'],
            """
            Warn: branch feature is behind its remote counterpart. Consider using git pull.

            Switching base branch of PR #15 to master... OK
            Updating description of PR #15... OK
            """
        )

    def test_github_restack_pr_branch_diverged_and_older(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = self.github_api_state_for_test_restack_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        create_repo_with_remote()
        new_branch("master")
        commit()
        new_branch('feature')
        commit()
        push()

        with fixed_author_and_committer_date_in_past():
            amend_commit()

        body: str = \
            """
            master
                feature
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['github', 'restack-pr'],
            """
            Warn: branch feature is diverged from and older than its remote counterpart. Consider using git reset --keep.

            Switching base branch of PR #15 to master... OK
            Updating description of PR #15... OK
            """
        )
        pr = github_api_state.get_pull_by_number(15)
        assert pr is not None
        assert pr['draft'] is False
        assert pr['base']['ref'] == 'master'

    def test_github_restack_pr_infers_base_repo_from_parent_tracking(self, mocker: MockerFixture) -> None:
        # In a fork workflow the PR is hosted by the base (upstream) repository, not the head (fork) repository.
        # Even with no base* config keys, restack-pr infers the base repository from the parent branch's tracking remote
        # (just like create-pr does), so it queries the repository that actually hosts the PR.
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        repositories = {
            1: {'owner': {'login': 'example-org'}, 'name': 'example-repo',
                'clone_url': 'https://github.com/example-org/example-repo.git'},
            2: {'owner': {'login': 'example-org'}, 'name': 'example-repo-1',
                'clone_url': 'https://github.com/example-org/example-repo-1.git'},
        }
        github_api_state = MockGitHubAPIState(
            repositories,
            mock_pr_json(number=1, head='feature', base='master', repo_id=1, base_repo_id=2, user='github_user'))
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        # `origin` (-> example-org/example-repo) is the head/fork remote holding the branches, while
        # `upstream` (-> example-org/example-repo-1) is the base remote that hosts the PR. The parent branch (develop)
        # tracks `upstream`, so the base repository is inferred from it - no machete.github.base* key is set.
        create_repo_with_remote()
        upstream_path = create_repo("remote-1", bare=True, switch_dir_to_new_repo=False)
        add_remote("upstream", upstream_path)

        new_branch("master")
        commit()
        push()
        new_branch("develop")
        commit()
        push(remote="upstream")
        new_branch("feature")
        commit()
        push()
        rewrite_branch_layout_file("master\n\tdevelop\n\t\tfeature")

        assert_success(
            ['github', 'restack-pr'],
            "Switching base branch of PR #1 to develop... OK\n"
        )
        pr = github_api_state.get_pull_by_number(1)
        assert pr is not None
        assert pr['base']['ref'] == 'develop'
