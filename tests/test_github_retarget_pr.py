import textwrap

from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.cli_runner import assert_failure, assert_success, launch_command, rewrite_branch_layout_file
from tests.git_repository import (add_remote, check_out, commit, create_repo, create_repo_with_remote, new_branch, push, remove_remote,
                                  set_git_config_key, unset_git_config_key)
from tests.mockers_code_hosting import mock_from_url
from tests.mockers_github import MockGitHubAPIState, mock_github_token_for_domain_fake, mock_pr_json, mock_urlopen


class TestGitHubRetargetPR(BaseTest):

    @staticmethod
    def github_api_state_for_test_retarget_pr() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='feature', base='master', number=15),
            mock_pr_json(head='feature_1', base='master', number=20, body='# Based on PR #10\n\n# Summary'),
            mock_pr_json(head='feature_2', base='master', number=25, body=None),
            mock_pr_json(head='feature_3', base='master', number=30),
            mock_pr_json(head='feature_4', base='feature', number=35),
            mock_pr_json(head='feature_4', base='feature', number=40),
        )

    def test_github_retarget_pr(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, "git_machete.github.GitHubToken.for_domain", mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_retarget_pr()))

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
        check_out('develop')
        new_branch('feature_4')
        push()
        check_out('feature')
        # Let's force a 307 redirect during the PATCH.
        add_remote('new_origin', 'https://github.com/example-org/old-example-repo.git')

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
            Switching base branch of PR #15 to develop...
            Warn: GitHub API returned 307 HTTP status with error message: Temporary redirect.
            It looks like the organization or repository name got changed recently and is outdated.
            New organization is example-org and new repository is example-repo.
            You can update your remote repository via: git remote set-url <remote_name> <new_repository_url>.
            OK
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

        check_out("feature_4")

        assert_failure(
            ['github', 'retarget-pr'],
            'Multiple PRs in example-org/old-example-repo have feature_4 as its head branch: #35, #40'
        )

    @staticmethod
    def github_api_state_for_test_github_retarget_pr_explicit_branch() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='feature', base='root', number=15)
        )

    def test_github_retarget_pr_explicit_branch(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, "git_machete.github.GitHubToken.for_domain", mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen',
                          mock_urlopen(self.github_api_state_for_test_github_retarget_pr_explicit_branch()))

        branch_first_commit_msg = "First commit on branch."
        branch_second_commit_msg = "Second commit on branch."

        create_repo_with_remote()
        new_branch("root")
        commit("First commit on root.")
        new_branch("branch-1")
        commit(branch_first_commit_msg)
        commit(branch_second_commit_msg)
        push()
        new_branch('feature')
        commit('introduce feature')
        push()
        check_out('root')
        new_branch('branch-without-pr')
        commit('branch-without-pr')
        push()
        add_remote('new_origin', 'https://github.com/user/repo.git')
        check_out('root')

        body: str = \
            """
            root
                branch-1
                    feature
                branch-without-pr
            """
        rewrite_branch_layout_file(body)
        launch_command("anno", "--sync-github-prs")

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
            'Switching base branch of PR #15 to branch-1... OK\n'
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
            "No PRs in user/repo have branch-without-pr as its head branch")

        assert_success(
            ['github', 'retarget-pr', '--branch', 'branch-without-pr', '--ignore-if-missing'],
            "Warn: no PRs in user/repo have branch-without-pr as its head branch\n")

    def test_github_retarget_pr_multiple_non_origin_remotes(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, "git_machete.github.GitHubToken.for_domain", mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.utils.date.get_current_date', lambda: '2023-12-31')
        github_api_state = self.github_api_state_for_test_retarget_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        branch_first_commit_msg = "First commit on branch."
        branch_second_commit_msg = "Second commit on branch."

        create_repo()
        origin_1_remote_path = create_repo("remote-1", bare=True, switch_dir_to_new_repo=False)
        origin_2_remote_path = create_repo("remote-2", bare=True, switch_dir_to_new_repo=False)

        # branch feature present in each remote, no branch tracking data
        new_branch("root")
        add_remote('origin_1', origin_1_remote_path)
        add_remote('origin_2', origin_2_remote_path)
        commit("First commit on root.")
        push(remote='origin_1')
        push(remote='origin_2')
        new_branch("branch-1")
        commit(branch_first_commit_msg)
        commit(branch_second_commit_msg)
        push(remote='origin_1')
        push(remote='origin_2')
        new_branch('feature')
        commit('introduce feature')
        push(remote='origin_1', set_upstream=False)
        push(remote='origin_2', set_upstream=False)

        body: str = \
            """
            root
                branch-1
                    feature
            """
        rewrite_branch_layout_file(body)

        expected_error_message = (
            "Multiple non-origin remotes correspond to GitHub in this repository: origin_1, origin_2 -> aborting.\n"
            "You can select the repository by providing some or all of git config keys:\n"
            "machete.github.domain, machete.github.organization, machete.github.repository, machete.github.remote\n"
        )
        assert_failure(["github", "retarget-pr"], expected_error_message)

        # branch feature_1 present in each remote, tracking data present
        check_out('feature')
        new_branch('feature_1')
        commit('introduce feature 1')
        push(remote='origin_1')
        push(remote='origin_2')

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
            'Switching base branch of PR #20 to feature... OK\n'
            'Checking for open GitHub PRs... OK\n'
            'Updating description of PR #20... OK\n'
        )
        pr20 = github_api_state.get_pull_by_number(20)
        assert pr20 is not None
        assert pr20['base']['ref'] == 'feature'
        assert pr20['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #15

            ## Chain of upstream PRs as of 2023-12-31

            * PR #15:
              `master` ← `feature`

              * **PR #20 (THIS ONE)**:
                `feature` ← `feature_1`

            <!-- end git-machete generated -->

            # Summary''')[1:]

        # branch feature_2 is not present in any of the remotes
        check_out('feature')
        new_branch('feature_2')
        commit('introduce feature 2')

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
        check_out('feature_2')
        push(remote='origin_1', set_upstream=False)

        set_git_config_key("machete.github.prDescriptionIntroStyle", "none")
        assert_success(
            ['github', 'retarget-pr'],
            'Switching base branch of PR #25 to feature... OK\n'
            'Updating description of PR #25... OK\n'
        )
        pr25 = github_api_state.get_pull_by_number(25)
        assert pr25 is not None
        assert pr25['base']['ref'] == 'feature'
        assert pr25['body'] == ''

        # branch feature_3 present in only one remote: origin_1 and has tracking data
        check_out('feature_2')
        new_branch('feature_3')
        commit('introduce feature 3')
        push(remote='origin_1')

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

        unset_git_config_key("machete.github.prDescriptionIntroStyle")
        assert_success(
            ['github', 'retarget-pr'],
            'Switching base branch of PR #30 to feature_2... OK\n'
            'Checking for open GitHub PRs... OK\n'
            'Updating description of PR #30... OK\n'
        )
        pr30 = github_api_state.get_pull_by_number(30)
        assert pr30 is not None
        assert pr30['base']['ref'] == 'feature_2'
        assert pr30['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #25

            ## Chain of upstream PRs as of 2023-12-31

            * PR #15:
              `master` ← `feature`

              * PR #25:
                `feature` ← `feature_2`

                * **PR #30 (THIS ONE)**:
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
            ['github', 'retarget-pr'],
            'Switching base branch of PR #30 to feature... OK\n'
            'Checking for open GitHub PRs... OK\n'
            'Updating description of PR #30... OK\n'
        )
        pr30 = github_api_state.get_pull_by_number(30)
        assert pr30 is not None
        assert pr30['base']['ref'] == 'feature'
        assert pr30['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #15

            ## Chain of upstream PRs as of 2023-12-31

            * PR #15:
              `master` ← `feature`

              * **PR #30 (THIS ONE)**:
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
            ['github', 'retarget-pr'],
            'Switching base branch of PR #30 to root... OK\n'
            'Updating description of PR #30... OK\n'
        )
        pr30 = github_api_state.get_pull_by_number(30)
        assert pr30 is not None
        assert pr30['base']['ref'] == 'root'
        assert pr30['body'] == '# Summary'

        check_out('feature')
        remove_remote('origin_2')

        assert_success(
            ['github', 'retarget-pr', '-U'],
            """
            Switching base branch of PR #15 to branch-1... OK
            Updating descriptions of other PRs...
            Checking for open GitHub PRs... OK
            Updating description of PR #20 (feature_1 -> feature)... OK
            Updating description of PR #25 (feature_2 -> feature)... OK
            Updating description of PR #35 (feature_4 -> feature)... OK
            """
        )
        pr15 = github_api_state.get_pull_by_number(15)
        assert pr15 is not None
        assert pr15['base']['ref'] == 'branch-1'
        assert pr15['body'] == '# Summary'

        set_git_config_key("machete.github.prDescriptionIntroStyle", "full")
        assert_success(
            ['github', 'retarget-pr', '-U'],
            """
            Base branch of PR #15 is already branch-1
            Checking for open GitHub PRs... OK
            Updating description of PR #15... OK
            Updating descriptions of other PRs...
            """
        )
        pr15 = github_api_state.get_pull_by_number(15)
        assert pr15 is not None
        assert pr15['base']['ref'] == 'branch-1'
        assert pr15['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            ## Tree of downstream PRs as of 2023-12-31

            * **PR #15 (THIS ONE)**:
              `branch-1` ← `feature`

                * PR #20:
                  `feature` ← `feature_1`

                * PR #25:
                  `feature` ← `feature_2`

                * PR #35:
                  `feature` ← `feature_4`

            <!-- end git-machete generated -->

            # Summary''')[1:]

    @staticmethod
    def github_api_state_for_test_retarget_pr_root_branch() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='master', base='root', number=15)
        )

    def test_github_retarget_pr_root_branch(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_retarget_pr_root_branch()))

        create_repo_with_remote()
        new_branch("master")
        commit()
        rewrite_branch_layout_file("master")

        assert_failure(
            ['github', 'retarget-pr'],
            "Branch master does not have a parent branch (it is a root) even though there is an open PR #15 to root.\n"
            "Consider modifying the branch layout file (git machete edit) so that master is a child of root."
        )

    def test_github_retarget_pr_infers_base_repo_from_parent_tracking(self, mocker: MockerFixture) -> None:
        # In a fork workflow the PR is hosted by the base (upstream) repository, not the head (fork) repository.
        # Even with no base* config keys, retarget-pr infers the base repository from the parent branch's tracking remote
        # (just like create-pr does), so it queries the repository that actually hosts the PR.
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
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
            ['github', 'retarget-pr'],
            "Switching base branch of PR #1 to develop... OK\n"
        )
        pr1 = github_api_state.get_pull_by_number(1)
        assert pr1 is not None
        assert pr1['base']['ref'] == 'develop'

    def test_github_retarget_pr_surfaces_base_config_error(self, mocker: MockerFixture) -> None:
        # When a base* config key is set but cannot be resolved (here it points at a nonexistent remote), retarget-pr must
        # surface the misconfiguration rather than silently falling back to the head repository.
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)

        create_repo_with_remote()
        new_branch("master")
        commit()
        push()
        new_branch("feature")
        commit()
        push()
        rewrite_branch_layout_file("master\n\tfeature")

        set_git_config_key("machete.github.baseRemote", "nonexistent")
        assert_failure(
            ['github', 'retarget-pr'],
            "machete.github.baseRemote git config key points to nonexistent remote, but such remote does not exist")

    def test_github_retarget_pr_targets_base_repo(self, mocker: MockerFixture) -> None:
        # In a fork workflow the PR is hosted by the base (upstream) repository, not the head (fork) repository.
        # retarget-pr must therefore honor `machete.github.baseRemote` and query the base repository for the PR.
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
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

        # `origin` (-> example-org/example-repo) is the head/fork remote holding the branches,
        # while `upstream` (-> example-org/example-repo-1) is the base remote that hosts the PR.
        create_repo_with_remote()
        upstream_path = create_repo("remote-1", bare=True, switch_dir_to_new_repo=False)
        add_remote("upstream", upstream_path)

        new_branch("master")
        commit()
        push()
        new_branch("develop")
        commit()
        push()
        new_branch("feature")
        commit()
        push()
        rewrite_branch_layout_file("master\n\tdevelop\n\t\tfeature")

        # Without any base config the client targets the head repository (origin), which does not host the PR.
        assert_failure(
            ['github', 'retarget-pr'],
            "No PRs in example-org/example-repo have feature as its head branch"
        )

        # `machete.github.baseRemote` points retarget-pr at the base repository that actually hosts the PR;
        # the PR's stale base (master) is then retargeted to feature's actual parent (develop).
        set_git_config_key("machete.github.baseRemote", "upstream")
        assert_success(
            ['github', 'retarget-pr'],
            "Switching base branch of PR #1 to develop... OK\n"
        )
        pr1 = github_api_state.get_pull_by_number(1)
        assert pr1 is not None
        assert pr1['base']['ref'] == 'develop'
