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
from tests.mockers_gitlab import (MockGitLabAPIState,
                                  mock_gitlab_token_for_domain_fake,
                                  mock_gitlab_token_for_domain_none,
                                  mock_mr_json, mock_urlopen)


class TestGitLabCreateMR(BaseTest):

    @staticmethod
    def gitlab_api_state_for_test_create_mr() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='ignore-trailing', base='hotfix/add-trigger', number=3)
        )

    def test_gitlab_create_mr(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')
        gitlab_api_state = self.gitlab_api_state_for_test_create_mr()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

        create_repo_with_remote()
        new_branch("root")
        commit("initial commit")
        new_branch("develop")
        commit("first commit")
        new_branch("allow-ownership-link")
        commit("Enable ownership links")
        push()
        new_branch("build-chain")
        commit("Build arbitrarily long chains of MRs")
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
        add_remote('new_origin', 'https://gitlab.com/user/repo.git')

        body: str = \
            """
            master
                hotfix/add-trigger
                    ignore-trailing  MR !3
                        chore/fields
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
            """
        rewrite_branch_layout_file(body)

        launch_command("gitlab", "create-mr")
        # ahead of origin state, push is advised and accepted
        assert_success(
            ['status'],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing  MR !3 (diverged from & older than origin)
                |
                o-chore/fields (untracked)

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws *  MR !4 (some_other_user)
              |
              x-drop-constraint (untracked)
            """,
        )

        # untracked state (can only create MR when branch is pushed)
        check_out('chore/fields')

        write_to_file(".git/info/milestone", "42")
        write_to_file(".git/info/reviewers", "foo\n\nbar")
        template = "# MR title\n## Summary\n## Test plan\n\n<!-- start git-machete generated -->\n<!-- end git-machete generated -->\n"
        write_to_file(".gitlab/merge_request_templates/Default.md", template)
        assert_success(
            ["gitlab", "create-mr", "--draft"],
            """
            Push untracked branch chore/fields to origin? (y, Q)

              master
              |
              o-hotfix/add-trigger (diverged from origin)
                |
                o-ignore-trailing  MR !3 (diverged from & older than origin)
                  |
                  o-chore/fields *

              develop
              |
              x-allow-ownership-link (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              o-call-ws  MR !4 (some_other_user)
                |
                x-drop-constraint (untracked)

            Checking if target branch ignore-trailing exists in origin remote... YES
            Creating a draft MR from chore/fields to ignore-trailing... OK, see www.gitlab.com
            Checking for open GitLab MRs... OK
            Updating description of MR !5 to include the chain of MRs... OK
            Setting milestone of MR !5 to 42... OK
            Adding gitlab_user as assignee to MR !5... OK
            Adding foo, bar as reviewers to MR !5... OK
            """
        )
        pr = gitlab_api_state.get_mr_by_number(5)
        assert pr is not None
        assert pr['title'] == 'Draft: remove outdated fields'
        assert pr['description'] == textwrap.dedent('''
            # MR title
            ## Summary
            ## Test plan

            <!-- start git-machete generated -->

            # Based on MR !3

            ## Chain of upstream MRs as of 2023-12-31

            * MR !3 _MR title_: <br>
              `hotfix/add-trigger` ← `ignore-trailing`

              * **MR !5 _Draft: remove outdated fields_ (THIS ONE)**: <br>
                `ignore-trailing` ← `chore/fields`

            <!-- end git-machete generated -->
        ''')[1:]
        assert pr['milestone_id'] == '42'
        assert pr['assignee_ids'] == [123456]
        assert pr['reviewer_ids'] == [123, 456]

        assert_success(
            ['status'],
            """
            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing  MR !3 (diverged from & older than origin)
                |
                o-chore/fields *  MR !5 (some_other_user)

            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws  MR !4 (some_other_user)
              |
              x-drop-constraint (untracked)
            """,
        )

        check_out('hotfix/add-trigger')
        commit('trigger released')
        commit('minor changes applied')

        # diverged from and newer than origin
        assert_success(
            ["gitlab", "create-mr", "--update-related-descriptions"],
            """
            Branch hotfix/add-trigger diverged from (and has newer commits than) its remote counterpart origin/hotfix/add-trigger.
            Push hotfix/add-trigger with force-with-lease to origin? (y, N, q)

              master
              |
              o-hotfix/add-trigger *
                |
                x-ignore-trailing  MR !3 (diverged from & older than origin)
                  |
                  o-chore/fields  MR !5 (some_other_user)

              develop
              |
              x-allow-ownership-link (ahead of origin)
              | |
              | x-build-chain (untracked)
              |
              o-call-ws  MR !4 (some_other_user)
                |
                x-drop-constraint (untracked)

            Checking if target branch master exists in origin remote... YES
            Creating a MR from hotfix/add-trigger to master... OK, see www.gitlab.com
            Updating description of MR !6 to include the chain of MRs... OK
            Setting milestone of MR !6 to 42... OK
            Adding gitlab_user as assignee to MR !6... OK
            Adding foo, bar as reviewers to MR !6... OK
            Updating descriptions of other MRs...
            Checking for open GitLab MRs... OK
            Description of MR !3 (ignore-trailing -> hotfix/add-trigger) has been updated
            Description of MR !5 (chore/fields -> ignore-trailing) has been updated
        """)
        mr5 = gitlab_api_state.get_mr_by_number(5)
        assert mr5 is not None
        assert mr5["description"] == textwrap.dedent("""
            # MR title
            ## Summary
            ## Test plan

            <!-- start git-machete generated -->

            # Based on MR !3

            ## Chain of upstream MRs as of 2023-12-31

            * MR !6 _HOTFIX Add the trigger (amended)_: <br>
              `master` ← `hotfix/add-trigger`

              * MR !3 _MR title_: <br>
                `hotfix/add-trigger` ← `ignore-trailing`

                * **MR !5 _Draft: remove outdated fields_ (THIS ONE)**: <br>
                  `ignore-trailing` ← `chore/fields`

            <!-- end git-machete generated -->
        """)[1:]

        expected_error_message = "Another open merge request already exists for this source branch: !6"
        assert_failure(["gitlab", "create-mr"], expected_error_message)

        # check against source branch is ancestor or equal to target branch
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
                                 "Cannot create merge request."
        assert_failure(["gitlab", "create-mr"], expected_error_message)

        check_out('develop')
        expected_error_message = "Branch develop does not have a parent branch (it is a root), " \
                                 "target branch for the MR cannot be established."
        assert_failure(["gitlab", "create-mr"], expected_error_message)

        write_to_file(".git/info/reviewers", "invalid-user")
        write_to_file(".git/info/description", "# MR title\n")
        check_out("allow-ownership-link")
        assert_success(
            ["gitlab", "create-mr", "--title=MR title set explicitly"],
            """
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

            Checking if target branch develop exists in origin remote... YES
            Creating a MR from allow-ownership-link to develop... OK, see www.gitlab.com
            Setting milestone of MR !7 to 42... OK
            Adding gitlab_user as assignee to MR !7... OK
            Adding invalid-user as reviewer to MR !7... OK
            """
        )

        pr = gitlab_api_state.get_mr_by_number(7)
        assert pr is not None
        assert pr['title'] == 'MR title set explicitly'

    def test_gitlab_create_mr_for_root_branch(self) -> None:
        create_repo()
        new_branch("master")
        commit()

        rewrite_branch_layout_file("master")
        assert_failure(
            ["gitlab", "create-mr"],
            "Branch master does not have a parent branch (it is a root), target branch for the MR cannot be established."
        )

    @staticmethod
    def gitlab_api_state_for_test_create_mr_for_chain_in_description() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='allow-ownership-link', base='develop', number=1),
            mock_mr_json(head='build-chain', base='allow-ownership-link', number=2)
        )

    def test_gitlab_create_mr_for_chain_in_description(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        gitlab_api_state = self.gitlab_api_state_for_test_create_mr_for_chain_in_description()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')

        create_repo_with_remote()
        new_branch("develop")
        commit("first commit")
        new_branch("allow-ownership-link")
        commit("Enable ownership links")
        push()
        new_branch("build-chain")
        commit("Build arbitrarily long chains of MRs")
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
                allow-ownership-link  MR !1
                    build-chain  MR !2
                        call-ws
                            drop-constraint
            """
        rewrite_branch_layout_file(body)

        check_out("drop-constraint")
        launch_command("gitlab", "create-mr", "--yes")
        pr = gitlab_api_state.get_mr_by_number(3)
        assert pr is not None
        assert pr['description'] == ''  # no chain at this moment

        write_to_file(".gitlab/merge_request_templates/Default.md", "# MR title\n## Summary\n## Test plan\n")
        set_git_config_key("machete.gitlab.mrDescriptionIntroStyle", "full")

        check_out("call-ws")
        launch_command("gitlab", "create-mr")
        pr = gitlab_api_state.get_mr_by_number(4)
        assert pr is not None
        assert pr['description'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on MR !2

            ## Chain of upstream MRs & tree of downstream MRs as of 2023-12-31

            * MR !1 _MR title_: <br>
              `develop` ← `allow-ownership-link`

              * MR !2 _MR title_: <br>
                `allow-ownership-link` ← `build-chain`

                * **MR !4 _Call web service_ (THIS ONE)**: <br>
                  `build-chain` ← `call-ws`

                    * MR !3 _Drop unneeded SQL constraints_: <br>
                      `call-ws` ← `drop-constraint`

            <!-- end git-machete generated -->

            # MR title
            ## Summary
            ## Test plan
        ''')[1:]

    @staticmethod
    def gitlab_api_state_for_test_create_mr_missing_base_branch_on_remote() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='chore/redundant_checks', base='restrict_access', number=18)
        )

    def test_gitlab_create_mr_missing_base_branch_on_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)
        gitlab_api_state = self.gitlab_api_state_for_test_create_mr_missing_base_branch_on_remote()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

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

        expected_msg = ("Checking if target branch feature/api_handling exists in origin remote... NO\n"
                        "Pushing untracked branch feature/api_handling to origin...\n"
                        "Creating a MR from feature/api_exception_handling to feature/api_handling... OK, see www.gitlab.com\n")

        set_git_config_key("machete.gitlab.annotateWithUrls", "true")
        assert_success(['gitlab', 'create-mr', '--yes'], expected_msg)
        assert_success(
            ['status'],
            """
            develop
            |
            o-feature/api_handling
              |
              o-feature/api_exception_handling *  MR !19 (some_other_user) www.gitlab.com
            """,
        )
        pr = gitlab_api_state.get_mr_by_number(19)
        assert pr is not None
        assert pr['description'] == 'commit body\nanother line'

    @staticmethod
    def gitlab_api_state_for_test_gitlab_create_mr_with_multiple_non_origin_remotes() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='branch-1', base='root', number=15)
        )

    def test_gitlab_create_mr_with_multiple_non_origin_remotes(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')
        gitlab_api_state = self.gitlab_api_state_for_test_gitlab_create_mr_with_multiple_non_origin_remotes()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

        (_, remote_path) = create_repo_with_remote()
        origin_1_remote_path = create_repo("remote-1", bare=True, switch_dir_to_new_repo=False)
        origin_2_remote_path = create_repo("remote-2", bare=True, switch_dir_to_new_repo=False)

        # branch feature present in each of the remotes, no branch tracking data, remote origin_1 picked manually
        remove_remote()
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
            ['gitlab', 'create-mr'],
            expected_result
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('3'))
        assert_failure(
            ['gitlab', 'create-mr'],
            "Invalid index: 3"
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('xd'))
        assert_failure(
            ['gitlab', 'create-mr'],
            "Could not establish remote repository, operation interrupted."
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('1', 'n'))
        assert_failure(
            ['gitlab', 'create-mr'],
            "Multiple non-origin remotes correspond to GitLab in this repository: origin_1, origin_2 -> aborting.\n"
            "You can select the project by providing some or all of git config keys:\n"
            "machete.gitlab.domain, machete.gitlab.namespace, machete.gitlab.project, machete.gitlab.remote\n"
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
            ['gitlab', 'create-mr'],
            expected_result
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('1', 'yq'))
        assert_success(
            ['gitlab', 'create-mr'],
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

        Warn: Target branch branch-1 lives in example-org/example-repo-2 project,
        while source branch feature lives in example-org/example-repo-1 project.
        git-machete will now attempt to create an MR in example-org/example-repo-2.

        Note that due to the limitations of GitLab's MR model, it is not possible to cleanly create stacked MRs from forks.
        For example, in a hypothetical chain some-other-branch -> feature -> branch-1, an MR from some-other-branch to feature
        could not be created in example-org/example-repo-2, since its source branch feature lives in example-org/example-repo-1.
        Generally, MRs need to be created in whatever project the target branch lives.

        Checking if target branch branch-1 exists in origin_2 remote... YES
        Creating a MR from feature to branch-1... OK, see www.gitlab.com
        Checking for open GitLab MRs... OK
        Updating description of MR !16 to include the chain of MRs... OK
        """  # noqa: E501

        write_to_file(".git/info/description", "overridden description")
        set_git_config_key("machete.gitlab.forceDescriptionFromCommitMessage", "true")
        assert_success(
            ['gitlab', 'create-mr'],
            expected_result
        )
        pr = gitlab_api_state.get_mr_by_number(16)
        assert pr is not None
        assert pr['description'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on MR !15

            ## Chain of upstream MRs as of 2023-12-31

            * MR !15 _MR title_: <br>
              `root` ← `branch-1`

              * **MR !16 _introduce feature_ (THIS ONE)**: <br>
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
            ['gitlab', 'create-mr'],
            "Subcommand create-mr can NOT be executed on the branch that is not managed by git machete"
            " (is not present in branch layout file).\n"
            "To successfully execute this command either add current branch to the file "
            "via commands add, discover or edit or agree on adding the branch to the branch layout file "
            "during the execution of create-mr subcommand."
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y'))
        expected_result = """
        Add feature_1 onto the inferred upstream (parent) branch feature? (y, N)
        Added branch feature_1 onto feature
        Warn: Target branch feature lives in example-org/example-repo-1 project,
        while source branch feature_1 lives in example-org/example-repo-2 project.
        git-machete will now attempt to create an MR in example-org/example-repo-1.

        Note that due to the limitations of GitLab's MR model, it is not possible to cleanly create stacked MRs from forks.
        For example, in a hypothetical chain some-other-branch -> feature_1 -> feature, an MR from some-other-branch to feature_1
        could not be created in example-org/example-repo-1, since its source branch feature_1 lives in example-org/example-repo-2.
        Generally, MRs need to be created in whatever project the target branch lives.

        Checking if target branch feature exists in origin_1 remote... YES
        Creating a MR from feature_1 to feature... OK, see www.gitlab.com
        Checking for open GitLab MRs... OK
        Updating description of MR !17 to include the chain of MRs... OK
        """
        assert_success(
            ['gitlab', 'create-mr'],
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
            o-feature  MR !16 (some_other_user)
              |
              o-feature_1  MR !17 (some_other_user)
              |
              o-feature_2 *

        Checking if target branch feature exists in origin_1 remote... YES
        Creating a MR from feature_2 to feature... OK, see www.gitlab.com
        Checking for open GitLab MRs... OK
        Updating description of MR !18 to include the chain of MRs... OK
        """
        assert_success(
            ['gitlab', 'create-mr'],
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
        Checking if target branch feature_2 exists in origin_1 remote... YES
        Creating a MR from feature_3 to feature_2... OK, see www.gitlab.com
        Checking for open GitLab MRs... OK
        Updating description of MR !19 to include the chain of MRs... OK
        """  # noqa: E501
        assert_success(
            ['gitlab', 'create-mr'],
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
        Warn: Target branch feature_3 lives in example-org/example-repo-1 project,
        while source branch feature_4 lives in example-org/example-repo-2 project.
        git-machete will now attempt to create an MR in example-org/example-repo-1.

        Note that due to the limitations of GitLab's MR model, it is not possible to cleanly create stacked MRs from forks.
        For example, in a hypothetical chain some-other-branch -> feature_4 -> feature_3, an MR from some-other-branch to feature_4
        could not be created in example-org/example-repo-1, since its source branch feature_4 lives in example-org/example-repo-2.
        Generally, MRs need to be created in whatever project the target branch lives.

        Checking if target branch feature_3 exists in origin_1 remote... YES
        Creating a MR from feature_4 to feature_3... OK, see www.gitlab.com
        Checking for open GitLab MRs... OK
        Updating description of MR !20 to include the chain of MRs... OK
        """
        assert_success(
            ['gitlab', 'create-mr'],
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
        Warn: Target branch feature_3 lives in example-org/example-repo-1 project,
        while source branch feature_5 lives in example-org/example-repo-2 project.
        git-machete will now attempt to create an MR in example-org/example-repo-1.

        Note that due to the limitations of GitLab's MR model, it is not possible to cleanly create stacked MRs from forks.
        For example, in a hypothetical chain some-other-branch -> feature_5 -> feature_3, an MR from some-other-branch to feature_5
        could not be created in example-org/example-repo-1, since its source branch feature_5 lives in example-org/example-repo-2.
        Generally, MRs need to be created in whatever project the target branch lives.

        Checking if target branch feature_3 exists in origin_1 remote... YES
        Creating a MR from feature_5 to feature_3... OK, see www.gitlab.com
        Checking for open GitLab MRs... OK
        Updating description of MR !21 to include the chain of MRs... OK
        """
        assert_success(
            ['gitlab', 'create-mr'],
            expected_result
        )

    def test_gitlab_create_mr_for_no_push_qualifier(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitLabAPIState.with_mrs()))

        create_repo_with_remote()

        new_branch("master")
        commit()
        push()

        new_branch("develop")
        commit()

        rewrite_branch_layout_file("master\n\tdevelop push=no")

        assert_success(
            ['gitlab', 'create-mr'],
            """
            Checking if target branch master exists in origin remote... YES
            Creating a MR from develop to master... OK, see www.gitlab.com
            """
        )

    def test_gitlab_create_mr_for_no_remotes(self) -> None:
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()

        rewrite_branch_layout_file("master\n\tdevelop")

        assert_failure(
            ['gitlab', 'create-mr'],
            "Could not create merge request - there are no remote repositories!"
        )

    def test_gitlab_create_mr_for_branch_behind_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitLabAPIState.with_mrs()))

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
            ['gitlab', 'create-mr'],
            "Interrupted creating merge request."
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y'))
        assert_success(
            ['gitlab', 'create-mr'],
            """
            Warn: Branch develop is behind its remote counterpart. Consider using git pull.
            Proceed with creating merge request? (y, Q)
            Checking if target branch master exists in origin remote... YES
            Creating a MR from develop to master... OK, see www.gitlab.com
            """
        )

    def test_gitlab_create_mr_for_untracked_branch(self, mocker: MockerFixture) -> None:
        create_repo_with_remote()

        new_branch("master")
        commit()
        push()

        new_branch("develop")
        commit()

        rewrite_branch_layout_file("master\n\tdevelop")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('q'))
        assert_success(
            ['gitlab', 'create-mr'],
            "Push untracked branch develop to origin? (y, Q)\n"
        )

    def test_gitlab_create_mr_for_branch_diverged_from_and_newer_than_remote(self, mocker: MockerFixture) -> None:
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
            ['gitlab', 'create-mr'],
            """
            Branch develop diverged from (and has newer commits than) its remote counterpart origin/develop.
            Push develop with force-with-lease to origin? (y, N, q)
            """
        )

    def test_gitlab_create_mr_for_branch_diverged_from_and_older_than_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitLabAPIState.with_mrs()))

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
            ['gitlab', 'create-mr'],
            """
            Warn: Branch develop is diverged from and older than its remote counterpart. Consider using git reset --keep.
            Proceed with creating merge request? (y, Q)
            Checking if target branch master exists in origin remote... YES
            Creating a MR from develop to master... OK, see www.gitlab.com
            """
        )

    def test_gitlab_create_mr_when_target_branch_disappeared_from_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitLabAPIState.with_mrs()))

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
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning('y'))
        assert_success(
            ['gitlab', 'create-mr'],
            """
            Checking if target branch develop exists in origin remote... NO
            Push untracked branch develop to origin? (y, Q)
            Creating a MR from feature to develop... OK, see www.gitlab.com
            """
        )

    def test_gitlab_create_mr_when_target_branch_appeared_on_remote(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(MockGitLabAPIState.with_mrs()))

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
            ['gitlab', 'create-mr'],
            """
            Checking if target branch develop exists in origin remote... YES
            Creating a MR from feature to develop... OK, see www.gitlab.com
            """
        )

    def test_gitlab_create_mr_with_title_from_file(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_none)
        gitlab_api_state = MockGitLabAPIState.with_mrs()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

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

        launch_command("gitlab", "create-mr")

        pr = gitlab_api_state.get_mr_by_number(1)
        assert pr is not None
        assert pr['title'] == pr_title

        assert_success(
            ['status'],
            """
            develop
            |
            o-feature *  MR !1 (some_other_user)
            """,
        )
