import textwrap

from pytest_mock import MockerFixture

from .base_test import BaseTest
from .mockers import (assert_failure, assert_success, mock_input_returning,
                      rewrite_branch_layout_file)
from .mockers_code_hosting import mock_from_url
from .mockers_git_repository import (check_out, commit,
                                     create_repo_with_remote, new_branch, push)
from .mockers_gitlab import (MockGitLabAPIState,
                             mock_gitlab_token_for_domain_fake, mock_mr_json,
                             mock_urlopen)


class TestTraverseGitLab(BaseTest):

    @staticmethod
    def gitlab_api_state_for_test_traverse_sync_gitlab_mrs_multiple_same_source() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='build-chain', base='develop', number=1),
            mock_mr_json(head='build-chain', base='allow-ownership-link', number=2),
        )

    def test_traverse_sync_gitlab_mrs_multiple_same_source(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(
            self.gitlab_api_state_for_test_traverse_sync_gitlab_mrs_multiple_same_source()))

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
            ["traverse", "--sync-gitlab-mrs"],
            "Multiple MRs have build-chain as its source branch: !1, !2"
        )

    @staticmethod
    def gitlab_api_state_for_test_traverse_sync_gitlab_mrs() -> MockGitLabAPIState:
        return MockGitLabAPIState.with_mrs(
            mock_mr_json(head='allow-ownership-link', base='develop', number=1),
            mock_mr_json(head='build-chain', base='develop', number=2),
            mock_mr_json(head='call-ws', base='build-chain', number=3),
        )

    def test_traverse_sync_gitlab_mrs(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, 'git_machete.code_hosting.OrganizationAndRepository.from_url', mock_from_url)
        self.patch_symbol(mocker, 'git_machete.gitlab.GitLabToken.for_domain', mock_gitlab_token_for_domain_fake)
        self.patch_symbol(mocker, 'git_machete.utils.get_current_date', lambda: '2023-12-31')
        gitlab_api_state = self.gitlab_api_state_for_test_traverse_sync_gitlab_mrs()
        self.patch_symbol(mocker, 'urllib.request.urlopen', mock_urlopen(gitlab_api_state))

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
            ["traverse", "--sync-gitlab-mrs"],
            """
            Checking for open GitLab MRs... OK
            Branch build-chain has a different MR target (develop) in GitLab than in machete file (allow-ownership-link).
            Retarget MR !2 to allow-ownership-link? (y, N, q, yq)
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n"))
        assert_success(
            ["traverse", "--sync-gitlab-mrs"],
            """
            Checking for open GitLab MRs... OK
            Branch build-chain has a different MR target (develop) in GitLab than in machete file (allow-ownership-link).
            Retarget MR !2 to allow-ownership-link? (y, N, q, yq)

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
            ["traverse", "--sync-gitlab-mrs", "-Wy"],
            """
            Fetching origin...

            Checking out the first root branch (develop)
            Checking for open GitLab MRs... OK

            Checking out build-chain

              develop
              |
              o-allow-ownership-link
                |
                o-build-chain *
                  |
                  o-call-ws

            Branch build-chain has a different MR target (develop) in GitLab than in machete file (allow-ownership-link).
            Retargeting MR !2 to allow-ownership-link...
            Target branch of MR !2 has been switched to allow-ownership-link
            Description of MR !2 has been updated
            Description of MR !3 (call-ws -> build-chain) has been updated

              develop
              |
              o-allow-ownership-link
                |
                o-build-chain *  MR !2 (some_other_user)
                  |
                  o-call-ws

            No successor of build-chain needs to be slid out or synced with upstream branch or remote; nothing left to update
            Returned to the initial branch build-chain
            """)

        mr2 = gitlab_api_state.get_mr_by_number(2)
        assert mr2 is not None
        assert mr2['description'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on MR !1

            ## Chain of upstream MRs as of 2023-12-31

            * MR !1 _MR title_: <br>
              `develop` ← `allow-ownership-link`

              * **MR !2 _MR title_ (THIS ONE)**: <br>
                `allow-ownership-link` ← `build-chain`

            <!-- end git-machete generated -->

            # Summary''')[1:]

        mr3 = gitlab_api_state.get_mr_by_number(3)
        assert mr3 is not None
        assert mr3['description'] == textwrap.dedent('''
            <!-- start git-machete generated -->

            # Based on MR !2

            ## Chain of upstream MRs as of 2023-12-31

            * MR !1 _MR title_: <br>
              `develop` ← `allow-ownership-link`

              * MR !2 _MR title_: <br>
                `allow-ownership-link` ← `build-chain`

                * **MR !3 _MR title_ (THIS ONE)**: <br>
                  `build-chain` ← `call-ws`

            <!-- end git-machete generated -->

            # Summary''')[1:]

        # Let's cover the case where the descriptions don't need to be updated after retargeting.

        mr2['target_branch'] = 'develop'
        check_out("build-chain")
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("yq"))
        assert_success(
            ["traverse", "-LW"],
            """
            Fetching origin...

            Checking out the first root branch (develop)
            Checking for open GitLab MRs... OK

            Checking out build-chain

              develop
              |
              o-allow-ownership-link
                |
                o-build-chain *  MR !2 (some_other_user)
                  |
                  o-call-ws

            Branch build-chain has a different MR target (develop) in GitLab than in machete file (allow-ownership-link).
            Retarget MR !2 to allow-ownership-link? (y, N, q, yq)
            Target branch of MR !2 has been switched to allow-ownership-link
            """)
