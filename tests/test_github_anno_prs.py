from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.cli_runner import assert_failure, assert_success, launch_command, rewrite_branch_layout_file
from tests.git_repository import (add_remote, amend_commit, check_out, commit, create_repo, create_repo_with_remote, delete_branch,
                                  new_branch, push, remove_remote, reset_to, set_git_config_key, wait_to_bump_commit_timestamp)
from tests.mockers_code_hosting import mock_from_url
from tests.mockers_github import MockGitHubAPIState, mock_github_token_for_domain_fake, mock_pr_json, mock_urlopen


class TestGitHubAnnoPRs(BaseTest):

    @staticmethod
    def github_api_state_for_test_anno_prs() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(number=3, user='some_other_user', head='ignore-trailing', base='hotfix/add-trigger'),
            mock_pr_json(number=7, user='some_other_user', head='allow-ownership-link', base='develop'),
            mock_pr_json(number=31, user='github_user', head='call-ws', base='develop'),
            mock_pr_json(number=37, user='github_user', head='develop', base='master')
        )

    def test_github_anno_prs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(self.github_api_state_for_test_anno_prs()))

        create_repo_with_remote()
        new_branch("root")
        commit("root")
        new_branch("develop")
        commit("develop commit")
        new_branch("allow-ownership-link")
        commit("Allow ownership links")
        push()
        new_branch("build-chain")
        commit("Build arbitrarily long chains")
        check_out("allow-ownership-link")
        commit("1st round of fixes")
        check_out("develop")
        commit("Other develop commit")
        push()
        new_branch("call-ws")
        commit("Call web service")
        commit("1st round of fixes")
        push()
        new_branch("drop-constraint")
        commit("Drop unneeded SQL constraints")
        check_out("call-ws")
        commit("2nd round of fixes")
        check_out("root")
        new_branch("master")
        commit("Master commit")
        push()
        new_branch("hotfix/add-trigger")
        commit("HOTFIX Add the trigger")
        push()
        amend_commit("HOTFIX Add the trigger (amended)")
        new_branch("ignore-trailing")
        commit("Ignore trailing data")
        wait_to_bump_commit_timestamp()
        amend_commit("Ignore trailing data (amended)")
        push()
        reset_to("ignore-trailing@{1}")  # noqa: FS003
        delete_branch("root")
        add_remote('new_origin', 'https://github.com/user/repo.git')

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

        # test that `anno-prs` add `rebase=no push=no` qualifiers to branches associated with the PRs whose owner
        # is different than the current user, overwrite annotation text but doesn't overwrite existing qualifiers
        launch_command('anno', '-b=allow-ownership-link', 'rebase=no')
        launch_command('anno', '-b=build-chain', 'rebase=no push=no')
        launch_command('github', 'anno-prs', '--debug')
        assert_success(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing *  PR #3 (some_other_user) rebase=no push=no (diverged from & older than origin)

            develop  PR #37 WRONG PR BASE or MACHETE PARENT? PR has master
            |
            x-allow-ownership-link  PR #7 (some_other_user) rebase=no (ahead of origin)
            | |
            | x-build-chain  rebase=no push=no (untracked)
            |
            o-call-ws  PR #31 (ahead of origin)
              |
              x-drop-constraint (untracked)
            """
        )

        # Test anno-prs using custom remote URL provided by git config keys
        remove_remote('new_origin')
        set_git_config_key('machete.github.remote', 'origin')
        set_git_config_key('machete.github.organization', 'custom_user')
        set_git_config_key('machete.github.repository', 'custom_repo')

        launch_command('github', 'anno-prs')
        assert_success(
            ["status"],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing *  PR #3 (some_other_user) rebase=no push=no (diverged from & older than origin)

            develop  PR #37 WRONG PR BASE or MACHETE PARENT? PR has master
            |
            x-allow-ownership-link  PR #7 (some_other_user) rebase=no (ahead of origin)
            | |
            | x-build-chain  rebase=no push=no (untracked)
            |
            o-call-ws  PR #31 (ahead of origin)
              |
              x-drop-constraint (untracked)
            """,
        )

    @staticmethod
    def github_api_state_for_test_local_branch_name_different_than_tracking_branch_name() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='feature_repo', base='root', number=15),
            mock_pr_json(head='feature_1', base='feature_repo', number=20)
        )

    def test_github_anno_prs_local_branch_name_different_than_tracking_branch_name(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, "git_machete.github.GitHubToken.for_domain", mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen',
                          mock_urlopen(self.github_api_state_for_test_local_branch_name_different_than_tracking_branch_name()))

        create_repo_with_remote()
        new_branch("root")
        commit("First commit on root.")
        push()
        new_branch('feature_repo')
        commit('introduce feature 1')
        push()
        new_branch('feature')
        commit('introduce feature 2')
        push(tracking_branch='feature_repo')
        new_branch('feature_1')
        commit('introduce feature 3')
        push()
        delete_branch('feature_repo')
        add_remote('new_origin', 'https://github.com/user/repo.git')

        body: str = \
            """
            root
                feature
                    feature_1
            """
        rewrite_branch_layout_file(body)
        launch_command("github", "anno-prs", "--with-urls")

        expected_status_output = """
        root
        |
        o-feature
          |
          o-feature_1 *  PR #20 (some_other_user) www.github.com rebase=no push=no
        """
        assert_success(
            ['status'],
            expected_result=expected_status_output
        )

    def test_github_anno_prs_no_remotes(self) -> None:
        create_repo_with_remote()
        assert_failure(
            ["github", "anno-prs"],
            """
            Remotes are defined for this repository, but none of them seems to correspond to GitHub (see git remote -v for details).
            It is possible that you are using a custom GitHub URL.
            If that is the case, you can provide repository information explicitly via some or all of git config keys:
            machete.github.domain, machete.github.organization, machete.github.repository, machete.github.remote
            """
        )

        remove_remote()
        assert_failure(["github", "anno-prs"], "No remotes defined for this repository (see git remote)")

    def test_github_anno_prs_targets_base_repo(self, mocker: MockerFixture) -> None:
        # In a fork workflow the PRs are hosted by the base (upstream) repository, not the head (fork) repository.
        # Reading commands must therefore honor `machete.github.baseRemote` and query the base repository for PRs.
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
            mock_pr_json(number=1, head='feature', base='develop', repo_id=1, base_repo_id=2, user='github_user'),
            mock_pr_json(number=2, head='develop', base='master', repo_id=1, base_repo_id=2, user='github_user'))
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        # `origin` (-> example-org/example-repo) is the head/fork remote holding the branches,
        # while `upstream` (-> example-org/example-repo-1) is the base remote that hosts the PRs.
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

        # Without any base config the client targets the head repository (origin), which does not host these PRs.
        launch_command("github", "anno-prs")
        assert_success(
            ["status"],
            """
            master
            |
            o-develop
              |
              o-feature *
            """
        )

        # `machete.github.baseRemote` points reading commands at the base repository that actually hosts the PRs.
        set_git_config_key("machete.github.baseRemote", "upstream")
        launch_command("github", "anno-prs")
        assert_success(
            ["status"],
            """
            master
            |
            o-develop  PR #2
              |
              o-feature *  PR #1
            """
        )

    def test_github_anno_prs_multiple_non_origin_github_remotes(self) -> None:
        create_repo()
        add_remote("origin-1", "https://github.com/tester/repo_sandbox-1.git")
        add_remote("origin-2", "https://github.com/tester/repo_sandbox-2.git")
        assert_failure(
            ["github", "anno-prs"],
            """
            Multiple non-origin remotes correspond to GitHub in this repository: origin-1, origin-2 -> aborting.
            You can select the repository by providing some or all of git config keys:
            machete.github.domain, machete.github.organization, machete.github.repository, machete.github.remote
            """
        )
