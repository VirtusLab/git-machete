import textwrap

from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success,
                           fixed_author_and_committer_date_in_past,
                           rewrite_branch_layout_file)
from tests.mockers_code_hosting import mock_from_url
from tests.mockers_gitlab import (MockGitLabAPIState,
                                  mock_gitlab_token_for_domain_fake,
                                  mock_mr_json, mock_urlopen)


class TestGitLabRestackMR(BaseTest):

    @staticmethod
    def gitlab_api_state_for_test_restack_mr() -> MockGitLabAPIState:
        body = textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on MR !14

            <!-- end git-machete generated -->
            # Summary''')[1:]
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='feature_1', base='develop', number=14, draft=True),
            mock_mr_json(head='feature', base='develop', number=15, body=body),
            mock_mr_json(head='multiple-mr-branch', base='develop', number=16),
            mock_mr_json(head='multiple-mr-branch', base='feature', number=17),
        )

    def test_gitlab_restack_mr_no_mrs_or_multiple_mrs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.gitlab_api_state_for_test_restack_mr()))

        self.repo_sandbox.new_branch("develop").commit()

        assert_failure(
            ['gitlab', 'restack-mr'],
            "No MRs have develop as its source branch"
        )

        self.repo_sandbox.new_branch("multiple-mr-branch").commit()
        assert_failure(
            ['gitlab', 'restack-mr'],
            "Multiple MRs have multiple-mr-branch as its source branch: !16, !17"
        )

    def test_gitlab_restack_mr_branch_in_sync(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        gitlab_api_state = self.gitlab_api_state_for_test_restack_mr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

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
            ['gitlab', 'restack-mr'],
            """
            Target branch of MR !15 has been switched to master
            Description of MR !15 has been updated
            """
        )
        mr = gitlab_api_state.get_mr_by_number(15)
        assert mr is not None
        assert mr['draft'] is False
        assert mr['target_branch'] == 'master'
        assert mr['description'] == '# Summary'

    def test_gitlab_restack_mr_branch_untracked(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        gitlab_api_state = self.gitlab_api_state_for_test_restack_mr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

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
            ['gitlab', 'restack-mr'],
            """
            Target branch of MR !14 has been switched to master
            Pushing untracked branch feature_1 to origin...

              master (untracked)
              |
              o-feature_1 *  MR !14 (some_other_user)

            """
        )
        mr = gitlab_api_state.get_mr_by_number(14)
        assert mr is not None
        assert mr['draft'] is True
        assert mr['target_branch'] == 'master'
        assert mr['description'] == '# Summary'

    def test_gitlab_restack_mr_branch_diverged_and_newer(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        gitlab_api_state = self.gitlab_api_state_for_test_restack_mr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

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

        mr = gitlab_api_state.get_mr_by_number(15)
        assert mr is not None
        original_title = mr['title']
        assert_success(
            ['gitlab', 'restack-mr'],
            """
            MR !15 has been temporarily marked as draft
            Target branch of MR !15 has been switched to master
            Description of MR !15 has been updated
            Branch feature diverged from (and has newer commits than) its remote counterpart origin/feature.
            Pushing feature with force-with-lease to origin...

              master (untracked)
              |
              o-feature *  MR !15 (some_other_user)

            MR !15 has been marked as ready for review again
            """
        )
        mr = gitlab_api_state.get_mr_by_number(15)
        assert mr is not None
        assert mr['draft'] is False
        assert mr['title'] == original_title
        assert mr['target_branch'] == 'master'

    def test_gitlab_restack_mr_branch_ahead(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        gitlab_api_state = self.gitlab_api_state_for_test_restack_mr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

        (
            self.repo_sandbox.new_branch("master")
            .commit()
            .new_branch('feature')
            .commit()
            .push()
            .commit()
            .set_git_config_key('machete.gitlab.domain', 'git.example.org')
        )
        body: str = \
            """
            master
                feature
            """
        rewrite_branch_layout_file(body)

        assert_success(
            ['gitlab', 'restack-mr'],
            """
            MR !15 has been temporarily marked as draft
            Target branch of MR !15 has been switched to master
            Description of MR !15 has been updated
            Pushing feature to origin...

              master (untracked)
              |
              o-feature *  MR !15 (some_other_user)

            MR !15 has been marked as ready for review again
            """
        )
        mr = gitlab_api_state.get_mr_by_number(15)
        assert mr is not None
        assert mr['draft'] is False
        assert mr['target_branch'] == 'master'

    def test_gitlab_restack_mr_branch_ahead_push_no(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        gitlab_api_state = self.gitlab_api_state_for_test_restack_mr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

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

        assert_success(
            ['gitlab', 'restack-mr'],
            """
            Warn: Branch feature is marked as push=no; skipping the push.
            Did you want to just use git machete gitlab retarget-mr?

            Target branch of MR !15 has been switched to master
            Description of MR !15 has been updated
            """
        )
        mr = gitlab_api_state.get_mr_by_number(15)
        assert mr is not None
        assert mr['draft'] is False
        assert mr['target_branch'] == 'master'

    def test_gitlab_restack_mr_branch_no_behind(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.gitlab_api_state_for_test_restack_mr()))

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
            ['gitlab', 'restack-mr'],
            """
            Warn: Branch feature is behind its remote counterpart. Consider using git pull.

            Target branch of MR !15 has been switched to master
            Description of MR !15 has been updated
            """
        )

    def test_gitlab_restack_mr_branch_diverged_and_older(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        gitlab_api_state = self.gitlab_api_state_for_test_restack_mr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

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
            ['gitlab', 'restack-mr'],
            """
            Warn: Branch feature is diverged from and older than its remote counterpart. Consider using git reset --keep.

            Target branch of MR !15 has been switched to master
            Description of MR !15 has been updated
            """
        )
        mr = gitlab_api_state.get_mr_by_number(15)
        assert mr is not None
        assert mr['draft'] is False
        assert mr['target_branch'] == 'master'
