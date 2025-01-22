from pytest_mock import MockerFixture

from tests.base_test import BaseTest, GitRepositorySandbox
from tests.mockers import (assert_failure, assert_success, launch_command,
                           rewrite_branch_layout_file)
from tests.mockers_gitlab import (MockGitLabAPIState,
                                  mock_gitlab_token_for_domain_fake,
                                  mock_mr_json, mock_urlopen)


class TestGitLabAnnoMRs(BaseTest):

    @staticmethod
    def gitlab_api_state_for_test_anno_mrs() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(number=3, user='some_other_user', head='ignore-trailing', base='hotfix/add-trigger'),
            mock_mr_json(number=7, user='some_other_user', head='allow-ownership-link', base='develop'),
            mock_mr_json(number=31, user='gitlab_user', head='call-ws', base='develop'),
            mock_mr_json(number=37, user='gitlab_user', head='develop', base='master')
        )

    def test_gitlab_anno_mrs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.gitlab_api_state_for_test_anno_mrs()))

        repo_sandbox = GitRepositorySandbox()
        (
            repo_sandbox
            .new_branch("root")
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
            .amend_commit("HOTFIX Add the trigger (amended)")
            .new_branch("ignore-trailing")
            .commit("Ignore trailing data")
            .sleep(1)
            .amend_commit("Ignore trailing data (amended)")
            .push()
            .reset_to("ignore-trailing@{1}")  # noqa: FS003
            .delete_branch("root")
            .add_remote('new_origin', 'https://gitlab.com/user/repo.git')
        )
        body: str = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
            """
        rewrite_branch_layout_file(body)

        # test that `anno-mrs` add `rebase=no push=no` qualifiers to branches associated with the MRs whose owner
        # is different than the current user, overwrite annotation text but doesn't overwrite existing qualifiers
        launch_command('anno', '-b=allow-ownership-link', 'rebase=no')
        launch_command('anno', '-b=build-chain', 'rebase=no push=no')
        launch_command('gitlab', 'anno-mrs', '--debug')
        assert_success(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing *  MR !3 (some_other_user) rebase=no push=no (diverged from & older than origin)

            develop  MR !37 WRONG MR TARGET or MACHETE PARENT? MR has master
            |
            x-allow-ownership-link  MR !7 (some_other_user) rebase=no (ahead of origin)
            | |
            | x-build-chain  rebase=no push=no (untracked)
            |
            o-call-ws  MR !31 (ahead of origin)
              |
              x-drop-constraint (untracked)
            """
        )

        # Test anno-mrs using custom remote URL provided by git config keys
        (
            repo_sandbox
            .remove_remote('new_origin')
            .set_git_config_key('machete.gitlab.remote', 'origin')
            .set_git_config_key('machete.gitlab.namespace', 'custom_user')
            .set_git_config_key('machete.gitlab.project', 'custom_repo')
        )

        launch_command('gitlab', 'anno-mrs')
        assert_success(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing *  MR !3 (some_other_user) rebase=no push=no (diverged from & older than origin)

            develop  MR !37 WRONG MR TARGET or MACHETE PARENT? MR has master
            |
            x-allow-ownership-link  MR !7 (some_other_user) rebase=no (ahead of origin)
            | |
            | x-build-chain  rebase=no push=no (untracked)
            |
            o-call-ws  MR !31 (ahead of origin)
              |
              x-drop-constraint (untracked)
            """,
        )

    @staticmethod
    def gitlab_api_state_for_test_local_branch_name_different_than_tracking_branch_name() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='feature_repo', base='root', number=15),
            mock_mr_json(head='feature_1', base='feature_repo', number=20)
        )

    def test_gitlab_anno_mrs_local_branch_name_different_than_tracking_branch_name(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'urllib.request.urlopen',
                          mock_urlopen(self.gitlab_api_state_for_test_local_branch_name_different_than_tracking_branch_name()))

        (
            GitRepositorySandbox()
            .new_branch("root")
            .commit("First commit on root.")
            .push()
            .new_branch('feature_repo')
            .commit('introduce feature')
            .push()
            .new_branch('feature')
            .commit('introduce feature')
            .push(tracking_branch='feature_repo')
            .new_branch('feature_1')
            .commit('introduce feature')
            .push()
            .delete_branch('feature_repo')
            .add_remote('new_origin', 'https://gitlab.com/user/repo.git')
        )

        body: str = \
            """
            root
                feature
                    feature_1
            """
        rewrite_branch_layout_file(body)
        launch_command("gitlab", "anno-mrs", "--with-urls")

        expected_status_output = """
        root
        |
        o-feature
          |
          o-feature_1 *  MR !20 (some_other_user) www.gitlab.com rebase=no push=no
        """
        assert_success(
            ['status'],
            expected_result=expected_status_output
        )

    def test_gitlab_anno_mrs_no_remotes(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        assert_failure(
            ["gitlab", "anno-mrs"],
            """
            Remotes are defined for this repository, but none of them seems to correspond to GitLab (see git remote -v for details).
            It is possible that you are using a custom GitLab URL.
            If that is the case, you can provide project information explicitly via some or all of git config keys:
            machete.gitlab.domain, machete.gitlab.namespace, machete.gitlab.project, machete.gitlab.remote
            """
        )

        repo_sandbox.remove_remote()
        assert_failure(["gitlab", "anno-mrs"], "No remotes defined for this repository (see git remote)")

    def test_gitlab_anno_mrs_multiple_non_origin_gitlab_remotes(self) -> None:
        (
            GitRepositorySandbox()
            .remove_remote("origin")
            .add_remote("origin-1", "https://gitlab.com/tester/repo_sandbox-1.git")
            .add_remote("origin-2", "https://gitlab.com/tester/repo_sandbox-2.git")
        )
        assert_failure(
            ["gitlab", "anno-mrs"],
            """
            Multiple non-origin remotes correspond to GitLab in this repository: origin-1, origin-2 -> aborting.
            You can select the project by providing some or all of git config keys:
            machete.gitlab.domain, machete.gitlab.namespace, machete.gitlab.project, machete.gitlab.remote
            """  # noqa: E501
        )
