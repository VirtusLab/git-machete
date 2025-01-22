from pytest_mock import MockerFixture

from . import mockers_github, mockers_gitlab
from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, launch_command,
                      rewrite_branch_layout_file)
from .mockers_git_repo_sandbox import GitRepositorySandbox
from .mockers_github import (MockGitHubAPIState,
                             mock_github_token_for_domain_fake)
from .mockers_gitlab import (MockGitLabAPIState,
                             mock_gitlab_token_for_domain_fake)


class TestAnno(BaseTest):

    def test_anno(self) -> None:
        """
        Verify behaviour of a 'git machete anno' command.
        """

        (
            GitRepositorySandbox()
            .new_branch("master")
            .commit("master commit.")
            .new_branch("develop")
            .commit("develop commit.")
            .new_branch("feature")
            .commit("feature commit.")
            .check_out("develop")
            .commit("New commit on develop")
        )
        body: str = \
            """
            master
            develop
                feature
            """
        rewrite_branch_layout_file(body)

        # Test `git machete anno` without providing the branch name
        launch_command('anno', 'Custom annotation for `develop` branch')
        assert_success(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature (untracked)
            """,
        )

        launch_command('anno', '-b=feature', 'Custom annotation for `feature` branch')
        assert_success(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature  Custom annotation for `feature` branch (untracked)
            """,
        )

        launch_command('anno', '-b=refs/heads/feature', 'Custom annotation for `feature` branch')
        assert_success(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature  Custom annotation for `feature` branch (untracked)
            """,
        )

        # check if annotation qualifiers are parsed correctly and that they can be overwritten by `git machete anno`
        launch_command('anno', '-b=refs/heads/feature', 'push=no Custom annotation for `feature` branch rebase=no')
        assert_success(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature  Custom annotation for `feature` branch rebase=no push=no (untracked)
            """,
        )
        launch_command('anno', '-b=refs/heads/feature', 'Custom annotation for `feature` branch')
        assert_success(
            ["status"],
            """
            master (untracked)

            develop *  Custom annotation for `develop` branch (untracked)
            |
            x-feature  Custom annotation for `feature` branch (untracked)
            """,
        )

        assert_success(
            ['anno'],
            'Custom annotation for `develop` branch\n'
        )

        assert_success(
            ['anno', '-b', 'feature'],
            'Custom annotation for `feature` branch\n'
        )

        assert_success(
            ['anno', '-b', 'feature', ''],
            ""
        )

        assert_success(
            ['anno', '-b', 'feature'],
            ""
        )

    @staticmethod
    def github_api_state_for_test_anno_prs() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mockers_github.mock_pr_json(number=1, user='github_user', base='master', head='develop'),
            mockers_github.mock_pr_json(number=2, user='github_user', base='develop', head='feature')
        )

    def test_anno_sync_github_prs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mockers_github.mock_urlopen(self.github_api_state_for_test_anno_prs()))
        (
            GitRepositorySandbox()
            .new_branch("master")
            .commit()
            .new_branch("develop")
            .new_branch("feature")
            .add_remote('new_origin', 'https://github.com/user/repo.git')
        )
        body: str = \
            """
            master
                develop
                    feature
            """
        rewrite_branch_layout_file(body)

        assert_success(['anno', '--sync-github-prs'], """
            Checking for open GitHub PRs... OK
            Annotating develop as PR #1
            Annotating feature as PR #2
        """)
        assert_success(
            ["status"],
            """
            master (untracked)
            |
            o-develop  PR #1 (untracked)
              |
              o-feature *  PR #2 (untracked)
            """,
        )

    def test_anno_sync_both_github_and_gitlab(self) -> None:
        assert_failure(
            ['anno', '--sync-github-prs', '--sync-gitlab-mrs'],
            "Option -H/--sync-github-prs cannot be specified together with -L/--sync-gitlab-mrs."
        )

    @staticmethod
    def gitlab_api_state_for_test_anno_mrs() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mockers_gitlab.mock_mr_json(number=1, user='gitlab_user', base='master', head='develop'),
            mockers_gitlab.mock_mr_json(number=2, user='gitlab_user', base='develop', head='feature')
        )

    def test_anno_sync_gitlab_mrs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mockers_gitlab.mock_urlopen(self.gitlab_api_state_for_test_anno_mrs()))
        (
            GitRepositorySandbox()
            .new_branch("master")
            .commit()
            .new_branch("develop")
            .new_branch("feature")
            .add_remote('new_origin', 'https://gitlab.com/user/repo.git')
        )
        body: str = \
            """
            master
                develop
                    feature
            """
        rewrite_branch_layout_file(body)

        assert_success(['anno', '--sync-gitlab-mrs'], """
            Checking for open GitLab MRs... OK
            Annotating develop as MR !1
            Annotating feature as MR !2
        """)

        assert_success(
            ["status"],
            """
            master (untracked)
            |
            o-develop  MR !1 (untracked)
              |
              o-feature *  MR !2 (untracked)
            """,
        )
