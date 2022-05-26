from typing import Any

from .mockers import (GitRepositorySandbox, assert_command, launch_command, mock_run_cmd)


class TestShow:

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
            .reset_to("ignore-trailing@{1}")
            .delete_branch("root")
        )

        launch_command("discover", "-y", "--roots=develop,master")
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

    def test_show(self, mocker: Any) -> None:
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        self.setup_discover_standard_tree()

        assert launch_command("show", "up").strip() == "hotfix/add-trigger"
        assert launch_command("show", "up", "call-ws").strip() == "develop"
        assert launch_command("show", "up", "refs/heads/call-ws").strip() == "develop"
        assert launch_command("show", "current").strip() == "ignore-trailing"

    def test_show_up(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete show up' command.

        Verify that 'git machete show up' displays name of a parent/upstream
        branch one above current one in the config file from within current
        root tree.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1-branch")
            .commit()
        )
        launch_command("discover", "-y")

        assert 'level-0-branch' == \
            launch_command("show", "up").strip(), \
            ("Verify that 'git machete show up' displays name of a parent/upstream "
                "branch one above current one."
             )            # check short command behaviour
        assert 'level-0-branch' == \
            launch_command("show", "u").strip(), \
            ("Verify that 'git machete show u' displays name of a parent/upstream "
             "branch one above current one."
             )

    def test_show_down(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete show down' command.

        Verify that 'git machete show down' displays name of a
        child/downstream branch one below current one.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1-branch")
            .commit()
            .check_out("level-0-branch")
        )
        launch_command("discover", "-y")

        assert 'level-1-branch' == \
            launch_command("show", "down").strip(), \
            ("Verify that 'git machete show down' displays name of "
                "a child/downstream branch one below current one."
             )            # check short command behaviour
        assert 'level-1-branch' == \
            launch_command("show", "d").strip(), \
            ("Verify that 'git machete show d' displays name of "
             "a child/downstream branch one below current one."
             )

    def test_show_first(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete show first' command.

        Verify that 'git machete show first' displays name of the first downstream
        branch of a root branch of the current branch in the config file if root
        branch has any downstream branches.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
            .new_branch("level-2b-branch")
            .commit()
            .new_branch("level-3b-branch")
            .commit()
            # a added so root will be placed in the config file after the level-0-branch
            .new_root_branch("a-additional-root")
            .commit()
            .new_branch("branch-from-a-additional-root")
            .commit()
            .check_out("level-3b-branch")
        )
        launch_command("discover", "-y")

        assert 'level-1a-branch' == \
            launch_command("show", "first").strip(), \
            ("Verify that 'git machete show first' displays name of the first downstream "
             "branch of a root branch of the current branch in the config file if root "
             "branch has any downstream branches."
             )
        assert 'level-1a-branch' == \
            launch_command("show", "f").strip(), \
            ("Verify that 'git machete show f' displays name of the first downstream "
             "branch of a root branch of the current branch in the config file if root "
             "branch has any downstream branches."
             )

    def test_show_last(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete show last' command.

        Verify that 'git machete show last' displays name of the last downstream
        branch of a root branch of the current branch in the config file if root
        branch has any downstream branches.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
            # x added so root will be placed in the config file after the level-0-branch
            .new_root_branch("x-additional-root")
            .commit()
            .new_branch("branch-from-x-additional-root")
            .commit()
            .check_out("level-1a-branch")
        )
        launch_command("discover", "-y")

        assert 'level-1b-branch' == \
            launch_command("show", "last").strip(), \
            ("Verify that 'git machete show last' displays name of the last downstream "
             "branch of a root branch of the current branch in the config file if root "
             "branch has any downstream branches."
             )
        assert 'level-1b-branch' == \
            launch_command("show", "l").strip(), \
            ("Verify that 'git machete show l' displays name of the last downstream "
             "branch of a root branch of the current branch in the config file if root "
             "branch has any downstream branches."
             )

    def test_show_next(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete show next' command.

        Verify that 'git machete show next' displays name of
        a branch right after the current one in the config file
        when successor branch exists within the root tree.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
            .check_out("level-2a-branch")
        )
        launch_command("discover", "-y")

        assert 'level-1b-branch' == \
            launch_command("show", "next").strip(), \
            ("Verify that 'git machete show next' displays name of "
             "a branch right after the current one in the config file "
             "when successor branch exists within the root tree."
             )
        assert 'level-1b-branch' == \
            launch_command("show", "n").strip(), \
            ("Verify that 'git machete show n' displays name of "
             "a branch right after the current one in the config file "
             "when successor branch exists within the root tree."
             )

    def test_show_prev(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete show prev' command.

        Verify that 'git machete show prev' displays name of
        a branch right before the current one in the config file
        when predecessor branch exists within the root tree.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
        )
        launch_command("discover", "-y")

        assert 'level-2a-branch' == \
            launch_command("show", "prev").strip(), \
            ("Verify that 'git machete show prev' displays name of "
             "a branch right before the current one in the config file "
             "when predecessor branch exists within the root tree."
             )
        assert 'level-2a-branch' == \
            launch_command("show", "p").strip(), \
            ("Verify that 'git machete show p' displays name of "
             "a branch right before the current one in the config file "
             "when predecessor branch exists within the root tree."
             )

    def test_show_root(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete show root' command.

        Verify that 'git machete show root' displays name of the root of
        the current branch.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1a-branch")
            .commit()
            .new_branch("level-2a-branch")
            .commit()
            .check_out("level-0-branch")
            .new_branch("level-1b-branch")
            .commit()
            .new_root_branch("additional-root")
            .commit()
            .new_branch("branch-from-additional-root")
            .commit()
            .check_out("level-2a-branch")
        )
        launch_command("discover", "-y")

        assert 'level-0-branch' == \
            launch_command("show", "root").strip(), \
            ("Verify that 'git machete show root' displays name of the root of "
             "the current branch."
             )
        assert 'level-0-branch' == \
            launch_command("show", "r").strip(), \
            ("Verify that 'git machete show r' displays name of the root of "
             "the current branch."
             )
