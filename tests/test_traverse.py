import os

from pytest_mock import MockerFixture

from git_machete.exceptions import UnderlyingGitException

from .base_test import BaseTest, GitRepositorySandbox
from .mockers import (assert_failure, assert_success,
                      fixed_author_and_committer_date_in_past, launch_command,
                      mock_input_returning, mock_input_returning_y,
                      overridden_environment, rewrite_branch_layout_file)


class TestTraverse(BaseTest):

    def setup_standard_tree(self, repo_sandbox: GitRepositorySandbox) -> None:
        (
            repo_sandbox.new_branch("root")
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
        )

        body: str = \
            """
            develop
                allow-ownership-link
                    build-chain
                call-ws
                    drop-constraint
            master
                hotfix/add-trigger
                    ignore-trailing
            """
        rewrite_branch_layout_file(body)

    def test_traverse_slide_out(self, mocker: MockerFixture) -> None:
        repo_sandbox = GitRepositorySandbox()
        (
            repo_sandbox
            .remove_remote()
            .new_branch("master")
            .commit()
            .new_branch("develop")
            .commit()
            .new_branch("feature")
            .commit()
            .check_out("master")
            .merge("develop")
            .check_out("develop")
        )
        body: str = \
            """
            master
                develop  PR #123
                    feature
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n"))
        assert_success(
            ["traverse"],
            """
            Branch develop is merged into master. Slide develop out of the tree of branch dependencies? (y, N, q, yq)

              master
              |
              m-develop *  PR #123
                |
                o-feature

            No successor of develop needs to be slid out or synced with upstream branch or remote; nothing left to update
            """
        )
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))
        assert_success(
            ["traverse"],
            "Branch develop is merged into master. Slide develop out of the tree of branch dependencies? (y, N, q, yq)\n"
        )
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("yq"))
        assert_success(
            ["traverse"],
            "Branch develop is merged into master. Slide develop out of the tree of branch dependencies? (y, N, q, yq)\n"
        )
        assert_success(
            ["status", "-l"],
            """
            master
            |
            | Some commit message.
            o-feature
            """
        )

        repo_sandbox.check_out("master").merge("feature").check_out("feature")
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("y"))
        assert_success(
            ["traverse"],
            """
            Branch feature is merged into master. Slide feature out of the tree of branch dependencies? (y, N, q, yq)

              master

            Reached branch feature which has no successor; nothing left to update
            """
        )

    def test_traverse_no_remotes(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        self.setup_standard_tree(repo_sandbox)
        repo_sandbox.remove_remote()

        launch_command("traverse", "-Wy")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link
            | |
            | | Build arbitrarily long chains
            | o-build-chain
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws
              |
              | Drop unneeded SQL constraints
              o-drop-constraint

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger
              |
              | Ignore trailing data
              o-ignore-trailing *
            """
        )

    def test_traverse_no_push(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        self.setup_standard_tree(repo_sandbox)

        launch_command("traverse", "-Wy", "--no-push")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link (diverged from origin)
            | |
            | | Build arbitrarily long chains
            | o-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws (ahead of origin)
              |
              | Drop unneeded SQL constraints
              o-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger (diverged from origin)
              |
              | Ignore trailing data (amended)
              o-ignore-trailing *
            """,
        )

    def test_traverse_no_push_override(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        self.setup_standard_tree(repo_sandbox)
        repo_sandbox.check_out("hotfix/add-trigger")
        launch_command("t", "-Wy", "--no-push", "--push", "--start-from=here")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            x-allow-ownership-link (ahead of origin)
            | |
            | | Build arbitrarily long chains
            | x-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws (ahead of origin)
              |
              | Drop unneeded SQL constraints
              x-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger *
              |
              | Ignore trailing data (amended)
              o-ignore-trailing
            """,
        )
        repo_sandbox.check_out("ignore-trailing")
        repo_sandbox.set_git_config_key("machete.traverse.push", "false")
        launch_command("t", "-Wy")
        assert_success(
            ["status"],
            """
            develop
            |
            o-allow-ownership-link (diverged from origin)
            | |
            | o-build-chain (untracked)
            |
            o-call-ws (ahead of origin)
              |
              o-drop-constraint (untracked)

            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing *
            """,
        )

        launch_command("t", "-Wy", "--push-untracked")
        assert_success(
            ["status"],
            """
            develop
            |
            o-allow-ownership-link (diverged from origin)
            | |
            | o-build-chain
            |
            o-call-ws (ahead of origin)
              |
              o-drop-constraint

            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing *
            """,
        )

        repo_sandbox.set_git_config_key("machete.traverse.push", "true")
        launch_command("t", "-Wy", "--no-push-untracked")
        assert_success(
            ["status"],
            """
            develop
            |
            o-allow-ownership-link
            | |
            | o-build-chain
            |
            o-call-ws
              |
              o-drop-constraint

            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing *
            """,
        )

    def test_traverse_ahead_of_remote_responses(self, mocker: MockerFixture) -> None:
        GitRepositorySandbox().new_branch("master").commit().push().commit()
        rewrite_branch_layout_file("master")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))
        assert_success(["traverse"], "Push master to origin? (y, N, q, yq)\n")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n"))
        assert_success(
            ["traverse"],
            """
            Push master to origin? (y, N, q, yq)

              master * (ahead of origin)

            Reached branch master which has no successor; nothing left to update
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("yq"))
        assert_success(["traverse"], "Push master to origin? (y, N, q, yq)\n")

    def test_traverse_behind_remote_responses(self, mocker: MockerFixture) -> None:
        GitRepositorySandbox().new_branch("master")\
            .commit().commit().push()\
            .reset_to("HEAD~")
        rewrite_branch_layout_file("master")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))
        assert_success(
            ["traverse"],
            """
            Branch master is behind its remote counterpart origin/master.
            Pull master (fast-forward only) from origin? (y, N, q, yq)
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n"))
        assert_success(
            ["traverse"],
            """
            Branch master is behind its remote counterpart origin/master.
            Pull master (fast-forward only) from origin? (y, N, q, yq)

              master * (behind origin)

            Reached branch master which has no successor; nothing left to update
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("yq"))
        assert_success(
            ["traverse"],
            """
            Branch master is behind its remote counterpart origin/master.
            Pull master (fast-forward only) from origin? (y, N, q, yq)
            """
        )

    def test_traverse_diverged_from_and_newer_responses(self, mocker: MockerFixture) -> None:
        GitRepositorySandbox().new_branch("master").commit().push().amend_commit("Different commit message")
        rewrite_branch_layout_file("master")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))
        assert_success(
            ["traverse"],
            """
            Branch master diverged from (and has newer commits than) its remote counterpart origin/master.
            Push master with force-with-lease to origin? (y, N, q, yq)
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n"))
        assert_success(
            ["traverse"],
            """
            Branch master diverged from (and has newer commits than) its remote counterpart origin/master.
            Push master with force-with-lease to origin? (y, N, q, yq)

              master * (diverged from origin)

            Reached branch master which has no successor; nothing left to update
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("yq"))
        assert_success(
            ["traverse"],
            """
            Branch master diverged from (and has newer commits than) its remote counterpart origin/master.
            Push master with force-with-lease to origin? (y, N, q, yq)
            """
        )

    def test_traverse_diverged_from_and_older_responses(self, mocker: MockerFixture) -> None:
        repo_sandbox = GitRepositorySandbox()
        repo_sandbox.new_branch("master").commit().push()
        with fixed_author_and_committer_date_in_past():
            repo_sandbox.amend_commit()
        rewrite_branch_layout_file("master")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))
        assert_success(
            ["traverse"],
            """
            Branch master diverged from (and has older commits than) its remote counterpart origin/master.
            Reset branch master to the commit pointed by origin/master? (y, N, q, yq)
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n"))
        assert_success(
            ["traverse"],
            """
            Branch master diverged from (and has older commits than) its remote counterpart origin/master.
            Reset branch master to the commit pointed by origin/master? (y, N, q, yq)

              master * (diverged from & older than origin)

            Reached branch master which has no successor; nothing left to update
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("yq"))
        assert_success(
            ["traverse"],
            """
            Branch master diverged from (and has older commits than) its remote counterpart origin/master.
            Reset branch master to the commit pointed by origin/master? (y, N, q, yq)
            """
        )

    def test_traverse_no_push_untracked(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        self.setup_standard_tree(repo_sandbox)

        launch_command("traverse", "-Wy", "--no-push-untracked")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link
            | |
            | | Build arbitrarily long chains
            | o-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws
              |
              | Drop unneeded SQL constraints
              o-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger
              |
              | Ignore trailing data (amended)
              o-ignore-trailing *
            """,
        )

    def test_traverse_push_config_key(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        self.setup_standard_tree(repo_sandbox)
        repo_sandbox.set_git_config_key('machete.traverse.push', 'false')
        launch_command("traverse", "-Wy")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link (diverged from origin)
            | |
            | | Build arbitrarily long chains
            | o-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws (ahead of origin)
              |
              | Drop unneeded SQL constraints
              o-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger (diverged from origin)
              |
              | Ignore trailing data (amended)
              o-ignore-trailing *
            """,
        )

    def test_traverse_no_push_no_checkout(self) -> None:
        (
            GitRepositorySandbox()
            .new_branch("root")
            .commit("root")
            .new_branch("develop")
            .commit("develop commit")
            .commit("Other develop commit")
            .push()
            .new_branch("allow-ownership-link")
            .commit("Allow ownership links")
            .push()
            .check_out("allow-ownership-link")
            .commit("1st round of fixes")
            .new_branch("build-chain")
            .commit("Build arbitrarily long chains")
            .check_out("root")
            .new_branch("master")
            .commit("Master commit")
            .push()
            .new_branch("hotfix/add-trigger")
            .commit("HOTFIX Add the trigger")
            .push()
            .amend_commit("HOTFIX Add the trigger (amended)")
            .delete_branch("root")
        )

        body: str = \
            """
            develop
                allow-ownership-link
                    build-chain
            master
                hotfix/add-trigger
            """
        rewrite_branch_layout_file(body)
        assert_success(
            ["status"],
            """
            develop
            |
            o-allow-ownership-link (ahead of origin)
              |
              o-build-chain (untracked)

            master
            |
            o-hotfix/add-trigger * (diverged from origin)
            """
        )

        expected_result = '''
        Fetching origin...

        Checking out the first root branch (develop)

          develop
          |
          o-allow-ownership-link (ahead of origin)
            |
            o-build-chain (untracked)

          master
          |
          o-hotfix/add-trigger * (diverged from origin)

        No successor of develop needs to be slid out or synced with upstream branch or remote; nothing left to update
        Tip: traverse by default starts from the current branch, use flags (--start-from=, --whole or -w, -W) to change this behavior.
        Further info under git machete traverse --help.
        Returned to the initial branch hotfix/add-trigger
        '''
        assert_success(["traverse", "-Wy", "--no-push"],
                       expected_result)

    def test_traverse_and_squash(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        self.setup_standard_tree(repo_sandbox)

        repo_sandbox.check_out("hotfix/add-trigger")
        launch_command("traverse", "--fetch", "--start-from=root", "--return-to=here", "-y")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            x-allow-ownership-link (ahead of origin)
            | |
            | | Build arbitrarily long chains
            | x-build-chain (untracked)
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws (ahead of origin)
              |
              | Drop unneeded SQL constraints
              x-drop-constraint (untracked)

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger *
              |
              | Ignore trailing data (amended)
              o-ignore-trailing
            """,
        )
        assert repo_sandbox.get_current_branch() == "hotfix/add-trigger"

        launch_command("traverse", "-wy")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link
            | |
            | | Build arbitrarily long chains
            | o-build-chain
            |
            | Call web service
            | 1st round of fixes
            | 2nd round of fixes
            o-call-ws
              |
              | Drop unneeded SQL constraints
              o-drop-constraint

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger *
              |
              | Ignore trailing data (amended)
              o-ignore-trailing
            """,
        )

        # Go from hotfix/add-trigger to call-ws which has >1 commit to be squashed
        for _ in range(3):
            launch_command("go", "prev")
        launch_command("squash")
        assert_success(
            ["status", "-l"],
            """
            develop
            |
            | Allow ownership links
            | 1st round of fixes
            o-allow-ownership-link
            | |
            | | Build arbitrarily long chains
            | o-build-chain
            |
            | Call web service
            o-call-ws * (diverged from origin)
              |
              | Drop unneeded SQL constraints
              x-drop-constraint

            master
            |
            | HOTFIX Add the trigger (amended)
            o-hotfix/add-trigger
              |
              | Ignore trailing data (amended)
              o-ignore-trailing
            """,
        )

    def test_traverse_with_merge(self, mocker: MockerFixture) -> None:
        (
            GitRepositorySandbox()
            .remove_remote()
            .new_branch("develop")
            .commit()
            .new_branch('mars')
            .commit()
            .new_branch('snickers')
            .commit()
            .check_out('mars')
            .commit()
            .check_out('develop')
            .commit()
        )

        body: str = \
            """
            develop
                mars
                    snickers
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("q"))
        launch_command("traverse", "-M")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n", "q"))
        launch_command("traverse", "-M")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("yq"))
        assert_success(
            ["traverse", "--start-from=root", "-M", "--no-edit-merge"],
            """
            Checking out the root branch (develop)

            Checking out mars

              develop
              |
              x-mars *
                |
                x-snickers

            Merge develop into mars? (y, N, q, yq)
            """
        )

    def test_traverse_with_merge_annotation(self, mocker: MockerFixture) -> None:
        (
            GitRepositorySandbox()
            .remove_remote()
            .new_branch("develop")
            .commit()
            .new_branch("mars")
            .commit()
            .new_branch("snickers")
            .commit()
            .check_out("mars")
            .commit()
            .check_out("develop")
            .commit()
        )

        body: str = """
            develop
                mars update=merge
                    snickers
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, "builtins.input", mock_input_returning("q"))
        launch_command("traverse")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("n", "q"))
        launch_command("traverse")
        self.patch_symbol(mocker, "builtins.input", mock_input_returning("yq"))
        assert_success(
            ["traverse", "--start-from=root", "--no-edit-merge"],
            """
            Checking out the root branch (develop)

            Checking out mars

              develop
              |
              x-mars *  update=merge
                |
                x-snickers

            Merge develop into mars? (y, N, q, yq)
            """,
        )

    def test_traverse_with_merge_annotation_and_yes_option(self) -> None:
        (
            GitRepositorySandbox()
            .remove_remote()
            .new_branch("develop")
            .commit()
            .new_branch("mars")
            .commit()
            .new_branch("snickers")
            .commit()
            .check_out("mars")
            .commit()
            .check_out("develop")
            .commit()
        )

        body: str = """
            develop
                mars update=merge
                    snickers
            """
        rewrite_branch_layout_file(body)

        with overridden_environment(GIT_EDITOR='false'):
            # --yes should imply --no-edit-merge, if it doesn't then the command will fail due to a non-zero exit code from the editor
            launch_command("traverse", "--start-from=root", "--yes"),

        assert_success(
            ["status"],
            """
            develop
            |
            o-mars  update=merge
              |
              o-snickers *
            """,
        )

    def test_traverse_qualifiers_no_push(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        self.setup_standard_tree(repo_sandbox)

        body: str = \
            """
            develop
            \tallow-ownership-link push=no
            \t\tbuild-chain push=no
            \tcall-ws push=no
            \t\tdrop-constraint push=no
            master
            \thotfix/add-trigger push=no
            \t\tignore-trailing
            """
        rewrite_branch_layout_file(body)

        launch_command("traverse", "-Wy", "--no-push-untracked", "--push-untracked")
        assert_success(
            ["status"],
            """
            develop
            |
            o-allow-ownership-link  push=no (diverged from origin)
            | |
            | o-build-chain  push=no (untracked)
            |
            o-call-ws  push=no (ahead of origin)
              |
              o-drop-constraint  push=no (untracked)

            master
            |
            o-hotfix/add-trigger  push=no (diverged from origin)
              |
              o-ignore-trailing *
            """,
        )

    def test_traverse_qualifiers_no_rebase(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        self.setup_standard_tree(repo_sandbox)

        body: str = \
            """
            develop
            \tallow-ownership-link rebase=no
            \t\tbuild-chain rebase=no
            \tcall-ws rebase=no
            \t\tdrop-constraint
            master
            \thotfix/add-trigger
            \t\tignore-trailing
            """
        rewrite_branch_layout_file(body)

        launch_command("traverse", "-Wy")
        assert_success(
            ["status"],
            """
            develop
            |
            x-allow-ownership-link  rebase=no
            | |
            | x-build-chain  rebase=no
            |
            o-call-ws  rebase=no
              |
              o-drop-constraint

            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing *
            """,
        )

    def test_traverse_qualifiers_no_rebase_no_push(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        self.setup_standard_tree(repo_sandbox)

        body: str = \
            """
            develop
            \tallow-ownership-link rebase=no push=no
            \t\tbuild-chain rebase=no push=no
            \tcall-ws
            \t\tdrop-constraint rebase=no push=no
            master
            \thotfix/add-trigger
            \t\tignore-trailing
            """
        rewrite_branch_layout_file(body)

        launch_command("traverse", "-Wy")
        assert_success(
            ["status"],
            """
            develop
            |
            x-allow-ownership-link  rebase=no push=no (ahead of origin)
            | |
            | x-build-chain  rebase=no push=no (untracked)
            |
            o-call-ws
              |
              x-drop-constraint  rebase=no push=no (untracked)

            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing *
            """,
        )

    def test_traverse_qualifiers_no_slide_out(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        self.setup_standard_tree(repo_sandbox)

        body: str = \
            """
            develop
            \tallow-ownership-link
            \t\tbuild-chain
            \tcall-ws slide-out=no
            \t\tdrop-constraint
            master
            \thotfix/add-trigger
            \t\tignore-trailing
            """
        rewrite_branch_layout_file(body)
        repo_sandbox.check_out('develop').merge('call-ws')

        launch_command("traverse", "-Wy")
        assert_success(
            ["status"],
            """
            develop *
            |
            o-allow-ownership-link
            | |
            | o-build-chain
            |
            m-call-ws  slide-out=no
              |
              o-drop-constraint

            master
            |
            o-hotfix/add-trigger
              |
              o-ignore-trailing
            """,
        )

    def test_traverse_no_managed_branches(self) -> None:
        _ = GitRepositorySandbox()

        expected_error_message = """
          No branches listed in .git/machete. Consider one of:
          * git machete discover
          * git machete edit or edit .git/machete manually
          * git machete github checkout-prs --mine
          * git machete gitlab checkout-mrs --mine"""
        assert_failure(["traverse"], expected_error_message)

    def test_traverse_invalid_flag_values(self) -> None:
        assert_failure(["traverse", "--return-to=dunno-where"],
                       "Invalid value for --return-to flag: dunno-where. Valid values are here, nearest-remaining, stay")
        assert_failure(["traverse", "--squash-merge-detection=lolxd"],
                       "Invalid value for --squash-merge-detection flag: lolxd. Valid values are none, simple, exact")
        assert_failure(["traverse", "--start-from=nowhere"],
                       "Invalid value for --start-from flag: nowhere. Valid values are here, root, first-root")

    def test_traverse_removes_current_directory(self) -> None:
        repo_sandbox = GitRepositorySandbox()
        (
            repo_sandbox
            .new_branch("master")
            .commit()
            .new_branch("with-directory")
            .add_file_and_commit(file_path="directory/file.txt")
            .check_out("master")
            .new_branch("without-directory")
            .commit()
            .check_out("master")
            .commit()
            .check_out("with-directory")
        )

        body: str = \
            """
            master
              with-directory
              without-directory
            """
        rewrite_branch_layout_file(body)

        os.chdir("directory")

        common_expected_output = """
            Rebasing with-directory onto master...

            Pushing untracked branch with-directory to origin...

            Checking out without-directory

              master (untracked)
              |
              o-with-directory
              |
              x-without-directory * (untracked)

            Rebasing without-directory onto master...

            Pushing untracked branch without-directory to origin...

              master (untracked)
              |
              o-with-directory
              |
              o-without-directory *

            Reached branch without-directory which has no successor; nothing left to update
            """
        if repo_sandbox.get_git_version() >= (2, 35, 0):
            # See https://github.com/git/git/blob/master/Documentation/RelNotes/2.35.0.txt#L81 for the fix
            assert_success(
                ["traverse", "-y"],
                common_expected_output
            )
            assert os.path.split(os.getcwd())[-1] == "directory"
        else:
            assert_success(
                ["traverse", "-y"],
                common_expected_output +
                f"Warn: current directory {repo_sandbox.local_path}/directory no longer exists, " +
                f"the nearest existing parent directory is {repo_sandbox.local_path}\n"
            )
            assert os.path.split(os.getcwd())[-1] != "directory"

    def test_traverse_reset_keep_failing(self) -> None:
        (
            GitRepositorySandbox()
            .new_branch("master")
            .add_file_and_commit(file_path="foo.txt", file_content="1")
            .sleep(1)
            .write_to_file(file_path="foo.txt", file_content="2")
            .amend_commit()
            .push()
            .reset_to("HEAD@{1}")  # noqa: FS003
            .write_to_file(file_path="foo.txt", file_content="3")
        )

        rewrite_branch_layout_file("master")

        assert_failure(
            ["traverse", "--fetch", "-y", "--debug"],
            "Cannot perform git reset --keep origin/master. This is most likely caused by local uncommitted changes.",
            expected_type=UnderlyingGitException
        )

    def test_traverse_with_stop_for_edit(self, mocker: MockerFixture) -> None:

        (
            GitRepositorySandbox()
            .remove_remote()
            .new_branch("branch-0")
            .commit()
            .new_branch("branch-1")
            .commit()
            .check_out("branch-0")
            .commit()
        )
        rewrite_branch_layout_file("branch-0\n\tbranch-1")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning_y)
        with overridden_environment(GIT_SEQUENCE_EDITOR="sed -i.bak '1s/^pick /edit /'"):
            launch_command("traverse")

        assert_success(
            ["status"],
            """
            branch-0
            |
            x-REBASING branch-1 *
            """
        )

    def test_reset_to_remote_after_rebase(self) -> None:
        """Very unlikely case; can happen only in case of divergence of clocks between local and remote
        (which is simulated in this test)."""
        (
            GitRepositorySandbox()
            .new_branch("branch-0")
            .commit()
            .push()
            .new_branch("branch-1")
            .commit()
            .push()
            .check_out("branch-0")
            .commit()
        )
        rewrite_branch_layout_file("branch-0\n\tbranch-1")

        with fixed_author_and_committer_date_in_past():
            assert_success(
                ["traverse", "-y"],
                """
                Pushing branch-0 to origin...

                Checking out branch-1

                  branch-0
                  |
                  x-branch-1 *

                Rebasing branch-1 onto branch-0...

                Branch branch-1 diverged from (and has older commits than) its remote counterpart origin/branch-1.
                Resetting branch branch-1 to the commit pointed by origin/branch-1...

                  branch-0
                  |
                  x-branch-1 *

                Reached branch branch-1 which has no successor; nothing left to update
                """
            )

    def test_traverse_quit_on_pushing_untracked(self, mocker: MockerFixture) -> None:
        GitRepositorySandbox().new_branch("master").commit()
        rewrite_branch_layout_file("master")
        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("q"))
        assert_success(
            ["traverse"],
            "Push untracked branch master to origin? (y, N, q, yq)\n"
        )

    def test_traverse_multiple_remotes(self, mocker: MockerFixture) -> None:
        repo_sandbox = GitRepositorySandbox()
        origin_1_remote_path = repo_sandbox.create_repo("remote-1", bare=True)
        origin_2_remote_path = repo_sandbox.create_repo("remote-2", bare=True)
        (
            repo_sandbox
            .remove_remote("origin")
            .add_remote("origin-1", origin_1_remote_path)
            .add_remote("origin-2", origin_2_remote_path)
        )

        repo_sandbox.new_branch("master").commit()
        rewrite_branch_layout_file("master")

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("xd"))
        assert_success(
            ["traverse", "--fetch"],
            """
            Fetching origin-1...
            Fetching origin-2...

            Branch master is untracked and there's no origin remote.
            [1] origin-1
            [2] origin-2
            Select number 1..2 to specify the destination remote repository, or 'n' to skip this branch, or 'q' to quit the traverse:

              master * (untracked)

            Reached branch master which has no successor; nothing left to update
            """
        )

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("1", "o", "2", "yq"))
        repo_sandbox.set_git_config_key("machete.traverse.fetch.origin-2", "false")
        assert_success(
            ["traverse", "--fetch"],
            """
            Fetching origin-1...

            Branch master is untracked and there's no origin remote.
            [1] origin-1
            [2] origin-2
            Select number 1..2 to specify the destination remote repository, or 'n' to skip this branch, or 'q' to quit the traverse:
            Push untracked branch master to origin-1? (y, N, q, yq, o[ther-remote])
            [1] origin-1
            [2] origin-2
            Select number 1..2 to specify the destination remote repository, or 'n' to skip this branch, or 'q' to quit the traverse:
            Push untracked branch master to origin-2? (y, N, q, yq, o[ther-remote])
            """
        )

    def test_traverse_yellow_edges(self, mocker: MockerFixture) -> None:
        (
            GitRepositorySandbox()
            .remove_remote()
            .new_branch("master")
            .commit()
            .new_branch("develop")
            .commit()
            .new_branch("feature-1")
            .commit()
            .check_out("develop")
            .new_branch("feature-2")
            .commit()
        )
        body: str = \
            """
            master
                feature-1
                feature-2
            """
        rewrite_branch_layout_file(body)

        self.patch_symbol(mocker, 'builtins.input', mock_input_returning("n", "n"))
        assert_success(
            ["traverse", "-w"],
            """
            Checking out the first root branch (master)

            Checking out feature-1

              master
              |
              ?-feature-1 *
              |
              ?-feature-2

            Warn: yellow edges indicate that fork points for feature-1, feature-2 are probably incorrectly inferred,
            or that some extra branch should be added between each of these branches and its parent.

            Run git machete status --list-commits or git machete status --list-commits-with-hashes to see more details.

            Rebase feature-1 onto master? (y, N, q, yq)

            Checking out feature-2

              master
              |
              ?-feature-1
              |
              ?-feature-2 *


            Rebase feature-2 onto master? (y, N, q, yq)

              master
              |
              ?-feature-1
              |
              ?-feature-2 *


            Reached branch feature-2 which has no successor; nothing left to update
            Returned to the initial branch feature-2
            """
        )
