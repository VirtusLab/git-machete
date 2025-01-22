import textwrap

from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success, launch_command,
                           rewrite_branch_layout_file)
from tests.mockers_code_hosting import mock_from_url
from tests.mockers_git_repo_sandbox import GitRepositorySandbox
from tests.mockers_gitlab import MockGitLabAPIState, mock_mr_json, mock_urlopen


class TestGitLabRetargetMR(BaseTest):

    @staticmethod
    def gitlab_api_state_for_test_retarget_mr() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='feature', base='master', number=15),
            mock_mr_json(head='feature_1', base='master', number=20),
            mock_mr_json(head='feature_2', base='master', number=25, body=None),
            mock_mr_json(head='feature_3', base='master', number=30),
            mock_mr_json(head='feature_4', base='feature', number=35),
            mock_mr_json(head='feature_4', base='feature', number=40),
        )

    def test_gitlab_retarget_mr(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.gitlab_api_state_for_test_retarget_mr()))

        repo_sandbox = GitRepositorySandbox()
        (
            repo_sandbox.new_branch("master")
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
            # Let's force a 307 redirect during the PUT.
            .add_remote('new_origin', 'https://gitlab.com/example-org/old-example-repo.git')
        )
        body: str = \
            """
            master
                develop
                    feature
                    feature_4
            """
        rewrite_branch_layout_file(body)

        launch_command("anno", "-L")

        expected_status_output = """
        master (untracked)
        |
        o-develop
          |
          o-feature *  MR !15 (some_other_user) WRONG MR TARGET or MACHETE PARENT? MR has master rebase=no push=no
          |
          o-feature_4  MR !40 (some_other_user) WRONG MR TARGET or MACHETE PARENT? MR has feature rebase=no push=no
        """
        assert_success(
            ['status'],
            expected_result=expected_status_output
        )

        assert_failure(
            ['gitlab', 'retarget-mr'],
            """
            Request PUT https://gitlab.com/api/v4/projects/example-org%2Fold-example-repo/merge_requests/15
            ended up in Non GET methods are not allowed for moved projects response from GitLab.
            Please report this error as a comment under https://github.com/VirtusLab/git-machete/issues/1212.
            As a workaround for now, please check git remote -v.
            Most likely you use an old URL of a project that has been moved since.
            Use git remote set-url <remote> <URL> to update the URL."""
        )

        repo_sandbox.set_remote_url('new_origin', 'https://gitlab.com/example-org/example-repo.git')
        assert_success(
            ['gitlab', 'retarget-mr'],
            "Target branch of MR !15 has been switched to develop\n"
        )

        expected_status_output = """
        master (untracked)
        |
        o-develop
          |
          o-feature *  MR !15 (some_other_user) rebase=no push=no
          |
          o-feature_4  MR !40 (some_other_user) WRONG MR TARGET or MACHETE PARENT? MR has feature rebase=no push=no
        """
        assert_success(
            ['status'],
            expected_result=expected_status_output
        )

        assert_success(
            ['gitlab', 'retarget-mr'],
            'Target branch of MR !15 is already develop\n'
        )

        repo_sandbox.check_out("feature_4")

        assert_failure(
            ['gitlab', 'retarget-mr'],
            'Multiple MRs in example-org/example-repo have feature_4 as its source branch: !35, !40'
        )

    @staticmethod
    def gitlab_api_state_for_test_gitlab_retarget_mr_explicit_branch() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='feature', base='root', number=15)
        )

    def test_gitlab_retarget_mr_explicit_branch(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'urllib.request.urlopen',
                          mock_urlopen(self.gitlab_api_state_for_test_gitlab_retarget_mr_explicit_branch()))

        branch_first_commit_msg = "First commit on branch."
        branch_second_commit_msg = "Second commit on branch."
        (
            GitRepositorySandbox()
            .new_branch("root")
            .commit("First commit on root.")
            .new_branch("branch-1")
            .commit(branch_first_commit_msg)
            .commit(branch_second_commit_msg)
            .push()
            .new_branch('feature')
            .commit('introduce feature')
            .push()
            .check_out('root')
            .new_branch('branch-without-mr')
            .commit('branch-without-mr')
            .push()
            .add_remote('new_origin', 'https://gitlab.com/user/repo.git')
            .check_out('root')
        )

        body: str = \
            """
            root
                branch-1
                    feature
                branch-without-mr
            """
        rewrite_branch_layout_file(body)
        launch_command("anno", "--sync-gitlab-mrs")

        expected_status_output = """
        root * (untracked)
        |
        o-branch-1
        | |
        | o-feature  MR !15 (some_other_user) WRONG MR TARGET or MACHETE PARENT? MR has root rebase=no push=no
        |
        o-branch-without-mr
        """
        assert_success(
            ['status'],
            expected_result=expected_status_output
        )

        assert_success(
            ['gitlab', 'retarget-mr', '--branch', 'feature'],
            'Target branch of MR !15 has been switched to branch-1\n'
        )

        expected_status_output = """
        root * (untracked)
        |
        o-branch-1
        | |
        | o-feature  MR !15 (some_other_user) rebase=no push=no
        |
        o-branch-without-mr
        """
        assert_success(
            ['status'],
            expected_result=expected_status_output
        )

        assert_failure(
            ["gitlab", "retarget-mr", "--branch", "branch-without-mr"],
            "No MRs in user/repo have branch-without-mr as its source branch")

        assert_success(
            ['gitlab', 'retarget-mr', '--branch', 'branch-without-mr', '--ignore-if-missing'],
            "Warn: no MRs in user/repo have branch-without-mr as its source branch\n")

    def test_gitlab_retarget_mr_multiple_non_origin_remotes(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        gitlab_api_state = self.gitlab_api_state_for_test_retarget_mr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')

        branch_first_commit_msg = "First commit on branch."
        branch_second_commit_msg = "Second commit on branch."

        repo_sandbox = GitRepositorySandbox()
        origin_1_remote_path = repo_sandbox.create_repo("remote-1", bare=True)
        origin_2_remote_path = repo_sandbox.create_repo("remote-2", bare=True)

        # branch feature present in each remote, no branch tracking data
        (
            repo_sandbox.remove_remote()
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
            "Multiple non-origin remotes correspond to GitLab in this repository: origin_1, origin_2 -> aborting.\n"
            "You can select the project by providing some or all of git config keys:\n"
            "machete.gitlab.domain, machete.gitlab.namespace, machete.gitlab.project, machete.gitlab.remote\n"  # noqa: FS003
        )
        assert_failure(["gitlab", "retarget-mr"], expected_error_message)

        # branch feature_1 present in each remote, tracking data present
        (
            repo_sandbox.check_out('feature')
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
            ['gitlab', 'retarget-mr'],
            'Target branch of MR !20 has been switched to feature\n'
            'Checking for open GitLab MRs... OK\n'
            'Description of MR !20 has been updated\n'
        )
        mr20 = gitlab_api_state.get_mr_by_number(20)
        assert mr20 is not None
        assert mr20['target_branch'] == 'feature'
        assert mr20['description'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on MR !15

            ## Chain of upstream MRs as of 2023-12-31

            * MR !15:
              `master` ← `feature`

              * **MR !20 (THIS ONE)**:
                `feature` ← `feature_1`

            <!-- end git-machete generated -->

            # Summary''')[1:]

        # branch feature_2 is not present in any of the remotes
        (
            repo_sandbox.check_out('feature')
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

        assert_failure(["gitlab", "retarget-mr"], expected_error_message)

        # branch feature_2 present in only one remote: origin_1 and there is no tracking data available -> infer the remote
        (
            repo_sandbox.check_out('feature_2')
            .push(remote='origin_1', set_upstream=False)
        )

        assert_success(
            ['gitlab', 'retarget-mr'],
            'Target branch of MR !25 has been switched to feature\n'
            'Checking for open GitLab MRs... OK\n'
            'Description of MR !25 has been updated\n'
        )
        mr25 = gitlab_api_state.get_mr_by_number(25)
        assert mr25 is not None
        assert mr25['target_branch'] == 'feature'
        assert mr25['description'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on MR !15

            ## Chain of upstream MRs as of 2023-12-31

            * MR !15:
              `master` ← `feature`

              * **MR !25 (THIS ONE)**:
                `feature` ← `feature_2`

            <!-- end git-machete generated -->
        ''')[1:]

        # branch feature_3 present in only one remote: origin_1 and has tracking data
        (
            repo_sandbox.check_out('feature_2')
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
            ['gitlab', 'retarget-mr'],
            'Target branch of MR !30 has been switched to feature_2\n'
            'Checking for open GitLab MRs... OK\n'
            'Description of MR !30 has been updated\n'
        )
        mr30 = gitlab_api_state.get_mr_by_number(30)
        assert mr30 is not None
        assert mr30['target_branch'] == 'feature_2'
        assert mr30['description'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on MR !25

            ## Chain of upstream MRs as of 2023-12-31

            * MR !15:
              `master` ← `feature`

              * MR !25:
                `feature` ← `feature_2`

                * **MR !30 (THIS ONE)**:
                  `feature_2` ← `feature_3`

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
            ['gitlab', 'retarget-mr'],
            'Target branch of MR !30 has been switched to feature\n'
            'Checking for open GitLab MRs... OK\n'
            'Description of MR !30 has been updated\n'
        )
        mr30 = gitlab_api_state.get_mr_by_number(30)
        assert mr30 is not None
        assert mr30['target_branch'] == 'feature'
        assert mr30['description'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on MR !15

            ## Chain of upstream MRs as of 2023-12-31

            * MR !15:
              `master` ← `feature`

              * **MR !30 (THIS ONE)**:
                `feature` ← `feature_3`

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
            ['gitlab', 'retarget-mr'],
            'Target branch of MR !30 has been switched to root\n'
            'Description of MR !30 has been updated\n'
        )
        mr30 = gitlab_api_state.get_mr_by_number(30)
        assert mr30 is not None
        assert mr30['target_branch'] == 'root'
        assert mr30['description'] == '# Summary'

        repo_sandbox.check_out('feature')
        repo_sandbox.remove_remote('origin_2')

        assert_success(
            ['gitlab', 'retarget-mr', '-U'],
            """
            Target branch of MR !15 has been switched to branch-1
            Updating descriptions of other MRs...
            Checking for open GitLab MRs... OK
            Description of MR !20 (feature_1 -> feature) has been updated
            Description of MR !25 (feature_2 -> feature) has been updated
            Description of MR !35 (feature_4 -> feature) has been updated
            """
        )
        mr15 = gitlab_api_state.get_mr_by_number(15)
        assert mr15 is not None
        assert mr15['target_branch'] == 'branch-1'
        assert mr15['description'] == '# Summary'

        repo_sandbox.set_git_config_key("machete.gitlab.mrDescriptionIntroStyle", "full")
        assert_success(
            ['gitlab', 'retarget-mr', '-U'],
            """
            Target branch of MR !15 is already branch-1
            Checking for open GitLab MRs... OK
            Description of MR !15 has been updated
            Updating descriptions of other MRs...
            """
        )
        mr15 = gitlab_api_state.get_mr_by_number(15)
        assert mr15 is not None
        assert mr15['target_branch'] == 'branch-1'
        assert mr15['description'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            ## Tree of downstream MRs as of 2023-12-31

            * **MR !15 (THIS ONE)**:
              `branch-1` ← `feature`

                * MR !20:
                  `feature` ← `feature_1`

                * MR !25:
                  `feature` ← `feature_2`

                * MR !35:
                  `feature` ← `feature_4`

            <!-- end git-machete generated -->

            # Summary''')[1:]

    @staticmethod
    def gitlab_api_state_for_test_retarget_mr_root_branch() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='master', base='root', number=15)
        )

    def test_gitlab_retarget_mr_root_branch(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.gitlab_api_state_for_test_retarget_mr_root_branch()))

        GitRepositorySandbox().new_branch("master").commit()
        rewrite_branch_layout_file("master")

        assert_failure(
            ['gitlab', 'retarget-mr'],
            "Branch master does not have a parent branch (it is a root) even though there is an open MR !15 to root.\n"
            "Consider modifying the branch layout file (git machete edit) so that master is a child of root."
        )
