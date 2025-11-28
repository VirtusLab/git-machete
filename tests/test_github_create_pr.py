import os
import textwrap

from pytest_mock import MockerFixture

from tests.base_test import BaseTest
from tests.mockers import (assert_failure, assert_success, execute,
                           fixed_author_and_committer_date_in_past,
                           launch_command, mock_input_returning,
                           mock_input_returning_y, rewrite_branch_layout_file,
                           sleep, write_to_file)
from tests.mockers_code_hosting import mock_from_url
from tests.mockers_git_repository import (add_remote, amend_commit, check_out,
                                          commit, create_repo,
                                          create_repo_with_remote,
                                          delete_branch, delete_remote_branch,
                                          new_branch, push, remove_remote,
                                          reset_to, set_git_config_key)
from tests.mockers_github import (MockGitHubAPIState,
                                  mock_github_token_for_domain_fake,
                                  mock_github_token_for_domain_none,
                                  mock_pr_json, mock_urlopen)


class TestGitHubCreatePR(BaseTest):

    @staticmethod
    def github_api_state_for_test_create_pr() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='ignore-trailing', base='hotfix/add-trigger', number=3)
        )

    def test_github_create_pr(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')
        github_api_state = self.github_api_state_for_test_create_pr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        create_repo_with_remote()
        new_branch("root")
        commit("initial commit")
        new_branch("develop")
        commit("first commit")
        new_branch("allow-ownership-link")
        commit("Enable ownership links")
        push()
        new_branch("build-chain")
        commit("Build arbitrarily long chains of PRs")
        check_out("allow-ownership-link")
        commit("fixes")
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
        sleep(1)
        amend_commit("Ignore trailing data (amended)")
        push()
        reset_to("ignore-trailing@{1}")  # noqa: FS003
        delete_branch("root")
        new_branch('chore/fields')
        commit("remove outdated fields")
        check_out("call-ws")
        add_remote('new_origin', 'https://github.com/user/repo.git')

        body: str = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing  PR #3
                        chore/fields
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
            """
        rewrite_branch_layout_file(body)

        launch_command("github", "create-pr")
        # ahead of origin state, push is advised and accepted
        assert_success(
            ['status'],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing  PR #3 (diverged from & older than origin)
                |
                o-chore/fields (untracked)

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws *  PR #4 (some_other_user)
              |
              x-drop-constraint (untracked)
            """,
        )

        # untracked state (can only create PR when branch is pushed)
        check_out('chore/fields')

        write_to_file(".git/info/milestone", "42")
        write_to_file(".git/info/reviewers", "foo\n\nbar")
        template = "# PR title\n## Summary\n## Test plan\n\n<!-- start git-machete generated -->\n<!-- end git-machete generated -->\n"
        write_to_file(".github/pull_request_template.md", template)
        assert_success(
            ["github", "create-pr", "--draft"],
            """
            Push untracked branch chore/fields to origin? (y, Q)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing  PR #3 (diverged from & older than origin)
                  |
                  o-chore/fields *

              develop
              |
              x-allow-ownership-link (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              o-call-ws  PR #4 (some_other_user)
                |
                x-drop-constraint (untracked)

            Checking if head branch chore/fields exists in origin remote... YES
            Checking if base branch ignore-trailing exists in origin remote... YES
            Creating a draft PR from chore/fields to ignore-trailing... OK, see www.github.com
            Checking for open GitHub PRs... OK
            Updating description of PR #5 to include the chain of PRs... OK
            Setting milestone of PR #5 to 42... OK
            Adding github_user as assignee to PR #5... OK
            Adding foo, bar as reviewers to PR #5... OK
            """
        )
        pr = github_api_state.get_pull_by_number(5)
        assert pr is not None
        assert pr['title'] == 'remove outdated fields'
        assert pr['body'] == textwrap.dedent('''
            # PR title
            ## Summary
            ## Test plan

            <!-- start git-machete generated -->

            # Based on PR #3

            ## Chain of upstream PRs as of 2023-12-31

            * PR #3:
              `hotfix/add-trigger` ← `ignore-trailing`

              * **PR #5 (THIS ONE)**:
                `ignore-trailing` ← `chore/fields`

            <!-- end git-machete generated -->
        ''')[1:]
        assert pr['draft'] is True
        assert pr['milestone'] == '42'
        assert pr['assignees'] == ['github_user']
        assert pr['reviewers'] == ['foo', 'bar']

        assert_success(
            ['status'],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing  PR #3 (diverged from & older than origin)
                |
                o-chore/fields *  PR #5 (some_other_user)

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws  PR #4 (some_other_user)
              |
              x-drop-constraint (untracked)
            """,
        )

        check_out('hotfix/add-trigger')
        commit('trigger released')
        commit('minor changes applied')

        # diverged from and newer than origin
        assert_success(
            ["github", "create-pr", "-U"],
            """
            Branch hotfix/add-trigger diverged from (and has newer commits than) its remote counterpart origin/hotfix/add-trigger.
            Push hotfix/add-trigger with force-with-lease to origin? (y, N, q)

              master
              |
              o-hotfix/add-trigger *
                |
                x-ignore-trailing  PR #3 (diverged from & older than origin)
                  |
                  o-chore/fields  PR #5 (some_other_user)

              develop
              |
              x-allow-ownership-link (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              o-call-ws  PR #4 (some_other_user)
                |
                x-drop-constraint (untracked)

            Checking if head branch hotfix/add-trigger exists in origin remote... YES
            Checking if base branch master exists in origin remote... YES
            Creating a PR from hotfix/add-trigger to master... OK, see www.github.com
            Updating description of PR #6 to include the chain of PRs... OK
            Setting milestone of PR #6 to 42... OK
            Adding github_user as assignee to PR #6... OK
            Adding foo, bar as reviewers to PR #6... OK
            Updating descriptions of other PRs...
            Checking for open GitHub PRs... OK
            Description of PR #3 (ignore-trailing -> hotfix/add-trigger) has been updated
            Description of PR #5 (chore/fields -> ignore-trailing) has been updated
            """
        )
        pr5 = github_api_state.get_pull_by_number(5)
        assert pr5 is not None
        assert pr5["body"] == textwrap.dedent("""
            # PR title
            ## Summary
            ## Test plan

            <!-- start git-machete generated -->

            # Based on PR #3

            ## Chain of upstream PRs as of 2023-12-31

            * PR #6:
              `master` ← `hotfix/add-trigger`

              * PR #3:
                `hotfix/add-trigger` ← `ignore-trailing`

                * **PR #5 (THIS ONE)**:
                  `ignore-trailing` ← `chore/fields`

            <!-- end git-machete generated -->
        """)[1:]

        expected_error_message = "A pull request already exists for test_repo:hotfix/add-trigger."
        assert_failure(["github", "create-pr"], expected_error_message)

        # check against head branch is ancestor or equal to base branch
        check_out('develop')
        new_branch('testing/endpoints')
        push()

        body = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing
                        chore/fields
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
                testing/endpoints
            """
        rewrite_branch_layout_file(body)

        expected_error_message = "All commits in testing/endpoints branch are already included in develop branch.\n" \
                                 "Cannot create pull request."
        assert_failure(["github", "create-pr"], expected_error_message)

        check_out('develop')
        expected_error_message = "Branch develop does not have a parent branch (it is a root), " \
                                 "base branch for the PR cannot be established."
        assert_failure(["github", "create-pr"], expected_error_message)

        write_to_file(".git/info/reviewers", "invalid-user")
        write_to_file(".git/info/description", "# PR title\n")
        check_out("allow-ownership-link")
        assert_success(
            ["github", "create-pr", "--title=PR title set explicitly"],
            f"""
            Push allow-ownership-link to origin? (y, N, q)

              master
              |
              o-hotfix/add-trigger
                |
                x-ignore-trailing (diverged from & older than origin)
                  |
                  o-chore/fields

              develop
              |
              x-allow-ownership-link *
              | |
              | x-build-chain (untracked)
              |
              o-call-ws
              | |
              | x-drop-constraint (untracked)
              |
              o-testing/endpoints

            Checking if head branch allow-ownership-link exists in origin remote... YES
            Checking if base branch develop exists in origin remote... YES
            Creating a PR from allow-ownership-link to develop... OK, see www.github.com
            Setting milestone of PR #7 to 42... OK
            Adding github_user as assignee to PR #7... OK
            Adding invalid-user as reviewer to PR #7...
            Warn: there are some invalid reviewers (non-collaborators) in .git{os.path.sep}info{os.path.sep}reviewers file.
            Skipped adding reviewers to the pull request.
            OK
            """
        )

        pr = github_api_state.get_pull_by_number(7)
        assert pr is not None
        assert pr['title'] == 'PR title set explicitly'

    def test_github_create_pr_for_root_branch(self) -> None:
        create_repo()
        new_branch("master")
        commit()

        rewrite_branch_layout_file("master")
        assert_failure(
            ["github", "create-pr"],
            "Branch master does not have a parent branch (it is a root), base branch for the PR cannot be established."
        )

    @staticmethod
    def github_api_state_for_test_create_pr_for_chain_in_description() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='allow-ownership-link', base='develop', number=1),
            mock_pr_json(head='build-chain', base='allow-ownership-link', number=2)
        )

    def test_github_create_pr_for_chain_in_description(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        github_api_state = self.github_api_state_for_test_create_pr_for_chain_in_description()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')

        create_repo_with_remote()
        new_branch("develop")
        commit("first commit")
        new_branch("allow-ownership-link")
        commit("Enable ownership links")
        push()
        new_branch("build-chain")
        commit("Build arbitrarily long chains of PRs")
        push()
        new_branch("call-ws")
        commit("Call web service")
        push()
        new_branch("drop-constraint")
        commit("Drop unneeded SQL constraints")
        push()

        body: str = \
            """
            develop
                allow-ownership-link  PR #1
                    build-chain  PR #2
                        call-ws
                            drop-constraint
            """
        rewrite_branch_layout_file(body)

        check_out("call-ws")
        launch_command("github", "create-pr")
        pr = github_api_state.get_pull_by_number(3)
        assert pr is not None
        assert pr['body'] == textwrap.dedent('''
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
        ''')[1:]

        write_to_file("PULL_REQUEST_TEMPLATE.md", "# PR title\n## Summary\n## Test plan\n")
        check_out("drop-constraint")
        launch_command("github", "create-pr", "--yes")
        pr = github_api_state.get_pull_by_number(4)
        assert pr is not None
        assert pr['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #3

            ## Chain of upstream PRs as of 2023-12-31

            * PR #1:
              `develop` ← `allow-ownership-link`

              * PR #2:
                `allow-ownership-link` ← `build-chain`

                * PR #3:
                  `build-chain` ← `call-ws`

                  * **PR #4 (THIS ONE)**:
                    `call-ws` ← `drop-constraint`

            <!-- end git-machete generated -->

            # PR title
            ## Summary
            ## Test plan
        ''')[1:]

    @staticmethod
    def github_api_state_for_test_create_pr_missing_base_branch_on_remote() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='chore/redundant_checks', base='restrict_access', number=18)
        )

    def test_github_create_pr_missing_base_branch_on_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        github_api_state = self.github_api_state_for_test_create_pr_missing_base_branch_on_remote()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        create_repo_with_remote()
        new_branch("root")
        commit("initial commit")
        new_branch("develop")
        commit("first commit on develop")
        push()
        new_branch("feature/api_handling")
        commit("Introduce GET and POST methods on API")
        new_branch("feature/api_exception_handling")
        commit("catch exceptions coming from API\n\ncommit body\nanother line")
        push()
        delete_branch("root")

        body: str = \
            """
            develop
                feature/api_handling
                    feature/api_exception_handling
            """
        rewrite_branch_layout_file(body)

        expected_msg = ("Checking if head branch feature/api_exception_handling exists in origin remote... YES\n"
                        "Checking if base branch feature/api_handling exists in origin remote... NO\n"
                        "Pushing untracked branch feature/api_handling to origin...\n"
                        "Creating a PR from feature/api_exception_handling to feature/api_handling... OK, see www.github.com\n")

        set_git_config_key("machete.github.annotateWithUrls", "true")
        assert_success(['github', 'create-pr', '--yes'], expected_msg)
        assert_success(
            ['status'],
            """
            develop
            |
            o-feature/api_handling
              |
              o-feature/api_exception_handling *  PR #19 (some_other_user) www.github.com
            """,
        )
        pr = github_api_state.get_pull_by_number(19)
        assert pr is not None
        assert pr['body'] == 'commit body\nanother line'

    @staticmethod
    def github_api_state_for_test_github_create_pr_with_multiple_non_origin_remotes() -> MockGitHubAPIState:
        return MockGitHubAPIState.with_prs(
            mock_pr_json(head='branch-1', base='root', number=15)
        )

    def test_github_create_pr_with_multiple_non_origin_remotes(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')
        github_api_state = self.github_api_state_for_test_github_create_pr_with_multiple_non_origin_remotes()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        (_, remote_path) = create_repo_with_remote()
        origin_1_remote_path = create_repo("remote-1", bare=True, switch_dir_to_new_repo=False)
        origin_2_remote_path = create_repo("remote-2", bare=True, switch_dir_to_new_repo=False)

        # branch feature present in each of the remotes, no branch tracking data, remote origin_1 picked manually
        remove_remote("origin")
        new_branch("root")
        add_remote('origin_1', origin_1_remote_path)
        add_remote('origin_2', origin_2_remote_path)
        commit("First commit on root.")
        push(remote='origin_1')
        push(remote='origin_2')
        new_branch("branch-1")
        commit('First commit on branch-1.')
        push(remote='origin_1')
        push(remote='origin_2')
        new_branch('feature')
        commit('introduce feature\n\ncommit body')
        push(remote='origin_1', set_upstream=False)
        push(remote='origin_2', set_upstream=False)

        body: str = \
            """
            root
                branch-1
                    feature
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('q'))
        expected_result = """
        Branch feature is untracked and there's no origin remote.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit the operation:
        """
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('3'))
        assert_failure(
            ['github', 'create-pr'],
            "Invalid index: 3"
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('xd'))
        assert_failure(
            ['github', 'create-pr'],
            "Could not establish remote repository, operation interrupted."
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('1', 'n'))
        assert_failure(
            ['github', 'create-pr'],
            "Multiple non-origin remotes correspond to GitHub in this repository: origin_1, origin_2 -> aborting.\n"
            "You can select the repository by providing some or all of git config keys:\n"
            "machete.github.domain, machete.github.organization, machete.github.repository, machete.github.remote\n"
        )

        expected_result = """
        Branch feature is untracked and there's no origin remote.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit the operation:
        Branch feature is untracked, but its remote counterpart candidate origin_1/feature already exists and both branches point to the same commit.
        Set the remote of feature to origin_1 without pushing or pulling? (y, N, q, yq)
        """  # noqa: E501

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('1', 'q'))
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('1', 'yq'))
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        execute("git branch --unset-upstream feature")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('1', 'y'))
        expected_result = """
        Branch feature is untracked and there's no origin remote.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit the operation:
        Branch feature is untracked, but its remote counterpart candidate origin_1/feature already exists and both branches point to the same commit.
        Set the remote of feature to origin_1 without pushing or pulling? (y, N, q, yq)

          root
          |
          o-branch-1
            |
            o-feature *

        Warn: base branch branch-1 lives in example-org/example-repo-2 repository,
        while head branch feature lives in example-org/example-repo-1 repository.
        git-machete will now attempt to create a PR in example-org/example-repo-2.

        Note that due to the limitations of GitHub's PR model, it is not possible to cleanly create stacked PRs from forks.
        For example, in a hypothetical chain some-other-branch -> feature -> branch-1, a PR from some-other-branch to feature
        could not be created in example-org/example-repo-2, since its head branch feature lives in example-org/example-repo-1.
        Generally, PRs need to be created in whatever repository the base branch lives.

        Checking if head branch feature exists in origin_1 remote... YES
        Checking if base branch branch-1 exists in origin_2 remote... YES
        Creating a PR from feature to branch-1... OK, see www.github.com
        Checking for open GitHub PRs... OK
        Updating description of PR #16 to include the chain of PRs... OK
        """  # noqa: E501

        write_to_file(".git/info/description", "overridden description")
        set_git_config_key("machete.github.forceDescriptionFromCommitMessage", "true")
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )
        pr = github_api_state.get_pull_by_number(16)
        assert pr is not None
        assert pr['body'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on PR #15

            ## Chain of upstream PRs as of 2023-12-31

            * PR #15:
              `root` ← `branch-1`

              * **PR #16 (THIS ONE)**:
                `branch-1` ← `feature`

            <!-- end git-machete generated -->

            commit body''')[1:]

        # branch feature_1 present in each of the remotes, tracking data present
        check_out('feature')
        new_branch('feature_1')
        commit('introduce feature 1')
        push(remote='origin_1')
        push(remote='origin_2')

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('n'))
        assert_failure(
            ['github', 'create-pr'],
            "Subcommand create-pr can NOT be executed on the branch that is not managed by git machete"
            " (is not present in branch layout file).\n"
            "To successfully execute this command either add current branch to the file "
            "via commands add, discover or edit or agree on adding the branch to the branch layout file "
            "during the execution of create-pr subcommand."
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y'))
        expected_result = """
        Add feature_1 onto the inferred upstream (parent) branch feature? (y, N)
        Added branch feature_1 onto feature
        Warn: base branch feature lives in example-org/example-repo-1 repository,
        while head branch feature_1 lives in example-org/example-repo-2 repository.
        git-machete will now attempt to create a PR in example-org/example-repo-1.

        Note that due to the limitations of GitHub's PR model, it is not possible to cleanly create stacked PRs from forks.
        For example, in a hypothetical chain some-other-branch -> feature_1 -> feature, a PR from some-other-branch to feature_1
        could not be created in example-org/example-repo-1, since its head branch feature_1 lives in example-org/example-repo-2.
        Generally, PRs need to be created in whatever repository the base branch lives.

        Checking if head branch feature_1 exists in origin_2 remote... YES
        Checking if base branch feature exists in origin_1 remote... YES
        Creating a PR from feature_1 to feature... OK, see www.github.com
        Checking for open GitHub PRs... OK
        Updating description of PR #17 to include the chain of PRs... OK
        """
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        # branch feature_2 not present in any of the remotes, remote origin_1 picked manually via mock_input()
        check_out('feature')
        new_branch('feature_2')
        commit('introduce feature 2')

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y', '1', 'y'))

        expected_result = """
        Add feature_2 onto the inferred upstream (parent) branch feature? (y, N)
        Added branch feature_2 onto feature
        Branch feature_2 is untracked and there's no origin remote.
        [1] origin_1
        [2] origin_2
        Select number 1..2 to specify the destination remote repository, or 'q' to quit the operation:
        Push untracked branch feature_2 to origin_1? (y, Q)

          root
          |
          o-branch-1
            |
            o-feature  PR #16 (some_other_user)
              |
              o-feature_1  PR #17 (some_other_user)
              |
              o-feature_2 *

        Checking if head branch feature_2 exists in origin_1 remote... YES
        Checking if base branch feature exists in origin_1 remote... YES
        Creating a PR from feature_2 to feature... OK, see www.github.com
        Checking for open GitHub PRs... OK
        Updating description of PR #18 to include the chain of PRs... OK
        """
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        # branch feature_2 present in only one remote: origin_1, no tracking data
        check_out('feature_2')
        new_branch('feature_3')
        commit('introduce feature 3')
        push(remote='origin_1', set_upstream=False)

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y'))
        expected_result = """
        Add feature_3 onto the inferred upstream (parent) branch feature_2? (y, N)
        Added branch feature_3 onto feature_2
        Checking if head branch feature_3 exists in origin_1 remote... YES
        Checking if base branch feature_2 exists in origin_1 remote... YES
        Creating a PR from feature_3 to feature_2... OK, see www.github.com
        Checking for open GitHub PRs... OK
        Updating description of PR #19 to include the chain of PRs... OK
        """  # noqa: E501
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        # branch feature_3 present in only one remote: origin_2, tracking data present
        check_out('feature_3')
        new_branch('feature_4')
        commit('introduce feature 4')
        push(remote='origin_2')

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y', 'y'))
        expected_result = """
        Add feature_4 onto the inferred upstream (parent) branch feature_3? (y, N)
        Added branch feature_4 onto feature_3
        Warn: base branch feature_3 lives in example-org/example-repo-1 repository,
        while head branch feature_4 lives in example-org/example-repo-2 repository.
        git-machete will now attempt to create a PR in example-org/example-repo-1.

        Note that due to the limitations of GitHub's PR model, it is not possible to cleanly create stacked PRs from forks.
        For example, in a hypothetical chain some-other-branch -> feature_4 -> feature_3, a PR from some-other-branch to feature_4
        could not be created in example-org/example-repo-1, since its head branch feature_4 lives in example-org/example-repo-2.
        Generally, PRs need to be created in whatever repository the base branch lives.

        Checking if head branch feature_4 exists in origin_2 remote... YES
        Checking if base branch feature_3 exists in origin_1 remote... YES
        Creating a PR from feature_4 to feature_3... OK, see www.github.com
        Checking for open GitHub PRs... OK
        Updating description of PR #20 to include the chain of PRs... OK
        """
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

        # branch feature_3 present in only one remote: origin_2 with tracking data, origin remote present - takes priority
        add_remote('origin', remote_path)
        check_out('feature_3')
        new_branch('feature_5')
        commit('introduce feature 5')
        push(remote='origin_2')

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y', 'y'))
        expected_result = """
        Add feature_5 onto the inferred upstream (parent) branch feature_3? (y, N)
        Added branch feature_5 onto feature_3
        Warn: base branch feature_3 lives in example-org/example-repo-1 repository,
        while head branch feature_5 lives in example-org/example-repo-2 repository.
        git-machete will now attempt to create a PR in example-org/example-repo-1.

        Note that due to the limitations of GitHub's PR model, it is not possible to cleanly create stacked PRs from forks.
        For example, in a hypothetical chain some-other-branch -> feature_5 -> feature_3, a PR from some-other-branch to feature_5
        could not be created in example-org/example-repo-1, since its head branch feature_5 lives in example-org/example-repo-2.
        Generally, PRs need to be created in whatever repository the base branch lives.

        Checking if head branch feature_5 exists in origin_2 remote... YES
        Checking if base branch feature_3 exists in origin_1 remote... YES
        Creating a PR from feature_5 to feature_3... OK, see www.github.com
        Checking for open GitHub PRs... OK
        Updating description of PR #21 to include the chain of PRs... OK
        """
        assert_success(
            ['github', 'create-pr'],
            expected_result
        )

    def test_github_create_pr_for_no_push_qualifier(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitHubAPIState.with_prs()))

        create_repo_with_remote()
        new_branch("master")
        commit()
        push()

        new_branch("develop")
        commit()
        push()  # Push the branch so it exists in the remote

        # Add another commit to make the branch AHEAD_OF_REMOTE,
        # which tests the case where push=no prevents automatic push during create-pr
        commit()

        rewrite_branch_layout_file("master\n\tdevelop push=no")

        assert_success(
            ['github', 'create-pr'],
            """
            Checking if head branch develop exists in origin remote... YES
            Checking if base branch master exists in origin remote... YES
            Creating a PR from develop to master... OK, see www.github.com
            """
        )

    def test_github_create_pr_for_no_remotes(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()

        rewrite_branch_layout_file("master\n\tdevelop")

        assert_failure(
            ['github', 'create-pr'],
            "Could not create pull request - there are no remote repositories!"
        )

    def test_github_create_pr_for_branch_behind_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitHubAPIState.with_prs()))

        create_repo_with_remote()
        new_branch("master")
        commit()
        push()
        new_branch("develop")
        commit()
        commit()
        push()
        reset_to("HEAD~")

        rewrite_branch_layout_file("master\n\tdevelop")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('q'))
        assert_failure(
            ['github', 'create-pr'],
            "Interrupted creating pull request."
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y'))
        assert_success(
            ['github', 'create-pr'],
            """
            Warn: branch develop is behind its remote counterpart. Consider using git pull.
            Proceed with creating pull request? (y, Q)
            Checking if head branch develop exists in origin remote... YES
            Checking if base branch master exists in origin remote... YES
            Creating a PR from develop to master... OK, see www.github.com
            """
        )

    def test_github_create_pr_for_untracked_branch(self, mocker: MockerFixture) -> None:
        create_repo_with_remote()
        new_branch("master")
        commit()
        push()
        new_branch("develop")
        commit()

        rewrite_branch_layout_file("master\n\tdevelop")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('q'))
        assert_success(
            ['github', 'create-pr'],
            "Push untracked branch develop to origin? (y, Q)\n"
        )

    def test_github_create_pr_for_branch_diverged_from_and_newer_than_remote(self, mocker: MockerFixture) -> None:
        create_repo_with_remote()

        new_branch("master")
        commit()
        push()

        new_branch("develop")
        commit()
        push()

        amend_commit("Different commit message")

        rewrite_branch_layout_file("master\n\tdevelop")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('yq'))
        assert_success(
            ['github', 'create-pr'],
            """
            Branch develop diverged from (and has newer commits than) its remote counterpart origin/develop.
            Push develop with force-with-lease to origin? (y, N, q)
            """
        )

    def test_github_create_pr_for_branch_diverged_from_and_older_than_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitHubAPIState.with_prs()))

        create_repo_with_remote()

        new_branch("master")
        commit()
        push()

        new_branch("develop")
        commit()
        push()

        with fixed_author_and_committer_date_in_past():
            amend_commit()

        rewrite_branch_layout_file("master\n\tdevelop")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y'))
        assert_success(
            ['github', 'create-pr'],
            """
            Warn: branch develop is diverged from and older than its remote counterpart. Consider using git reset --keep.
            Proceed with creating pull request? (y, Q)
            Checking if head branch develop exists in origin remote... YES
            Checking if base branch master exists in origin remote... YES
            Creating a PR from develop to master... OK, see www.github.com
            """
        )

    def test_github_create_pr_when_base_branch_disappeared_from_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)

        (local_path, remote_path) = create_repo_with_remote()

        new_branch("develop")
        commit()
        push()

        new_branch("feature")
        commit()
        push()

        os.chdir(remote_path)
        delete_branch("develop")
        os.chdir(local_path)

        rewrite_branch_layout_file("develop\n\tfeature")

        expected_error_message = (
            "Base branch develop has been removed from origin remote since the last fetch/push.\n"
            "Do you really want to create a PR to this branch?"
        )
        assert_failure(['github', 'create-pr'], expected_error_message)

    def test_github_create_pr_when_base_branch_appeared_on_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitHubAPIState.with_prs()))

        create_repo_with_remote()

        new_branch("develop")
        commit()
        push()

        delete_remote_branch("origin/develop")

        new_branch("feature")
        commit()
        push()

        rewrite_branch_layout_file("develop\n\tfeature")
        assert_success(
            ['github', 'create-pr'],
            """
            Checking if head branch feature exists in origin remote... YES
            Checking if base branch develop exists in origin remote... YES
            Creating a PR from feature to develop... OK, see www.github.com
            """
        )

    def test_github_create_pr_with_title_from_file(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        github_api_state = MockGitHubAPIState.with_prs()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        create_repo_with_remote()

        new_branch("develop")
        commit("Some commit")
        push()

        new_branch("feature")
        commit("Add feature")
        push()

        rewrite_branch_layout_file("develop\n\tfeature")

        pr_title = "Feature Implementation"
        write_to_file(".git/info/title", pr_title)

        launch_command("github", "create-pr")

        pr = github_api_state.get_pull_by_number(1)
        assert pr is not None
        assert pr['title'] == pr_title

        assert_success(
            ['status'],
            """
            develop
            |
            o-feature *  PR #1 (some_other_user)
            """,
        )

    def test_github_create_pr_with_base_flag(self, mocker: MockerFixture) -> None:
        """Test that --base flag overrides the upstream branch from .git/machete"""
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.github.GitHubToken.for_domain', mock_github_token_for_domain_none)
        github_api_state = MockGitHubAPIState.with_prs()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(github_api_state))

        create_repo_with_remote()

        new_branch("main")
        commit("Main commit")
        push()

        new_branch("develop")
        commit("Develop commit")
        push()

        new_branch("feature")
        commit("Add feature")
        push()

        # Set up branch layout where feature is downstream of develop
        rewrite_branch_layout_file("main\ndevelop\n\tfeature")

        # Use --base to override the upstream branch (develop) and create PR against main instead
        launch_command("github", "create-pr", "--base", "main")

        # Verify that PR was created with main as base, not develop
        pr = github_api_state.get_pull_by_number(1)
        assert pr is not None
        assert pr['base']['ref'] == 'main'  # Should be main due to --base flag
        assert pr['head']['ref'] == 'feature'

        assert_success(
            ['status'],
            """
            main

            develop
            |
            o-feature *  PR #1 (some_other_user)
            """,
        )

    def test_github_create_pr_with_missing_head_branch_on_remote(self, mocker: MockerFixture) -> None:
        """Test that creating a PR fails gracefully when head branch doesn't exist in remote"""
        # No need to mock GitHub API or input since we catch the error before making API calls
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)

        (local_path, remote_path) = create_repo_with_remote()
        new_branch("develop")
        commit("develop commit")
        push()

        new_branch("feature")
        commit("feature commit")
        push()

        # Delete the branch from the actual remote repository to simulate the scenario
        os.chdir(remote_path)
        delete_branch("feature")
        os.chdir(local_path)

        rewrite_branch_layout_file("develop\n\tfeature")

        # This should now fail with a clear error message before attempting to call the GitHub API
        expected_error_message = (
            "Head branch feature has been removed from origin remote since the last fetch/push.\n"
            "Do you really want to create a PR for this branch?"
        )
        assert_failure(['github', 'create-pr'], expected_error_message)
