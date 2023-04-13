from typing import Any

from .mockers import (GitRepositorySandbox, assert_command, launch_command,
                      mock_run_cmd, rewrite_definition_file)


class TestTraverse:

    def setup_method(self) -> None:
        self.repo_sandbox = GitRepositorySandbox()

        (
            self.repo_sandbox
            # Create the remote and sandbox repos, chdir into sandbox repo
            .new_repo(self.repo_sandbox.remote_path, "--bare")
            .new_repo(self.repo_sandbox.local_path)
            .execute(f"git remote add origin {self.repo_sandbox.remote_path}")
            .execute('git config user.email "tester@test.com"')
            .execute('git config user.name "Tester Test"')
        )

    def setup_discover_standard_tree(self) -> None:
        (
            self.repo_sandbox.new_branch("root")
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
            .commit_amend("HOTFIX Add the trigger (amended)")
            .new_branch("ignore-trailing")
            .commit("Ignore trailing data")
            .sleep(1)
            .commit_amend("Ignore trailing data (amended)")
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
        rewrite_definition_file(body)
        assert_command(
            ["status"],
            """
            develop
            |
            x-allow-ownership-link (ahead of origin)
            | |
            | x-build-chain (untracked)
            |
            o-call-ws (ahead of origin)
              |
              x-drop-constraint (untracked)

            master
            |
            o-hotfix/add-trigger (diverged from origin)
              |
              o-ignore-trailing * (diverged from & older than origin)
            """
        )

    def test_traverse_no_push(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        self.setup_discover_standard_tree()

        launch_command("traverse", "-Wy", "--no-push")
        assert_command(
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

    def test_traverse_no_push_override(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        self.setup_discover_standard_tree()
        self.repo_sandbox.check_out("hotfix/add-trigger")
        launch_command("t", "-Wy", "--no-push", "--push", "--start-from=here")
        assert_command(
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
        self.repo_sandbox.check_out("ignore-trailing")
        launch_command("t", "-Wy", "--no-push", "--push")
        assert_command(
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
              | Ignore trailing data (amended)
              o-ignore-trailing *
            """,
        )

    def test_traverse_no_push_untracked(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        self.setup_discover_standard_tree()

        launch_command("traverse", "-Wy", "--no-push-untracked")
        assert_command(
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

    def test_traverse_push_config_key(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        self.setup_discover_standard_tree()
        self.repo_sandbox.add_git_config_key('machete.traverse.push', 'false')
        launch_command("traverse", "-Wy")
        assert_command(
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

    def test_discover_traverse_squash(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        self.setup_discover_standard_tree()

        launch_command("traverse", "-Wy")
        assert_command(
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
              | Ignore trailing data (amended)
              o-ignore-trailing *
            """,
        )

        # Go from ignore-trailing to call-ws which has >1 commit to be squashed
        for _ in range(4):
            launch_command("go", "prev")
        launch_command("squash")
        assert_command(
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

    def test_traverse_with_merge(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        (
            self.repo_sandbox
            .new_branch("develop")
            .commit("develop commit 1")
            .new_branch('mars')
            .commit('mars commit 1')
            .new_branch('snickers')
            .commit('snickers commit')
            .check_out('mars')
            .commit('mars commit 2')
            .check_out('develop')
            .commit('develop commit 2')
        )

        body: str = \
            """
            develop
                mars
                    snickers
            """
        rewrite_definition_file(body)
        launch_command("traverse", '-y', '-M', '-n')
        assert_command(
            ["status"],
            """
            develop
            |
            o-mars
              |
              o-snickers *
            """
        )

    def test_traverse_qualifiers_no_push(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        self.setup_discover_standard_tree()

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
        rewrite_definition_file(body)

        launch_command("traverse", "-Wy")
        assert_command(
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

    def test_traverse_qualifiers_no_rebase(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        self.setup_discover_standard_tree()

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
        rewrite_definition_file(body)

        launch_command("traverse", "-Wy")
        assert_command(
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

    def test_traverse_qualifiers_no_rebase_no_push(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        self.setup_discover_standard_tree()

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
        rewrite_definition_file(body)

        launch_command("traverse", "-Wy")
        assert_command(
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

    def test_traverse_qualifiers_no_slide_out(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests
        self.setup_discover_standard_tree()

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
        rewrite_definition_file(body)
        self.repo_sandbox.check_out('develop').merge('call-ws')

        launch_command("traverse", "-Wy")
        assert_command(
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
