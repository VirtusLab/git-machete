from typing import Any

from .mockers import GitRepositorySandbox, launch_command, mock_run_cmd


class TestGo:

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

    def test_go_up(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete go up' command.

        Verify that 'git machete go up' performs 'git checkout' to the
        parent/upstream branch of the current branch.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1-branch")
            .commit()
        )
        launch_command("discover", "-y")
        launch_command("go", "up")

        assert 'level-0-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete go up' performs 'git checkout' to "
             "the parent/upstream branch of the current branch."
             )
        # check short command behaviour
        self.repo_sandbox.check_out("level-1-branch")
        launch_command("g", "u")

        assert 'level-0-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete g u' performs 'git checkout' to "
             "the parent/upstream branch of the current branch."
             )

    def test_go_down(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete go down' command.

        Verify that 'git machete go down' performs 'git checkout' to the
        child/downstream branch of the current branch.

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
        launch_command("go", "down")

        assert 'level-1-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete go down' performs 'git checkout' to "
             "the child/downstream branch of the current branch."
             )
        # check short command behaviour
        self.repo_sandbox.check_out("level-0-branch")
        launch_command("g", "d")

        assert 'level-1-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete g d' performs 'git checkout' to "
             "the child/downstream branch of the current branch."
             )

    def test_go_first_root_with_downstream(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete go first' command.

        Verify that 'git machete go first' performs 'git checkout' to
        the first downstream branch of a root branch in the config file
        if root branch has any downstream branches.

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
        launch_command("go", "first")

        assert 'level-1a-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete go first' performs 'git checkout' to"
             "the first downstream branch of a root branch if root branch "
             "has any downstream branches."
             )
        # check short command behaviour
        self.repo_sandbox.check_out("level-3b-branch")
        launch_command("g", "f")

        assert 'level-1a-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete g d' performs 'git checkout' to "
             "the child/downstream branch of the current branch."
             )

    def test_go_first_root_without_downstream(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete go first' command.

        Verify that 'git machete go first' set current branch to root
        if root branch has no downstream.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
        )
        launch_command("discover", "-y")
        launch_command("go", "first")

        assert 'level-0-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete go first' set current branch to root"
             "if root branch has no downstream."
             )
        # check short command behaviour
        launch_command("g", "f")

        assert 'level-0-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete g f' set current branch to root"
             "if root branch has no downstream."
             )

    def test_go_last(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete go last' command.

        Verify that 'git machete go last' performs 'git checkout' to
        the last downstream branch of a root branch if root branch
        has any downstream branches.

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
        launch_command("go", "last")

        assert 'level-1b-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete go last' performs 'git checkout' to"
             "the last downstream branch of a root branch if root branch "
             "has any downstream branches."
             )
        # check short command behaviour
        self.repo_sandbox.check_out("level-1a-branch")
        launch_command("g", "l")

        assert 'level-1b-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete g l' performs 'git checkout' to"
             "the last downstream branch of a root branch if root branch "
             "has any downstream branches."
             )

    def test_go_next_successor_exists(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete go next' command.

        Verify that 'git machete go next' performs 'git checkout' to
        the branch right after the current one in the config file
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
        launch_command("go", "next")

        assert 'level-1b-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete go next' performs 'git checkout' to"
             "the next downstream branch right after the current one in the"
             "config file if successor branch exists."
             )
        # check short command behaviour
        self.repo_sandbox.check_out("level-2a-branch")
        launch_command("g", "n")

        assert 'level-1b-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete g n' performs 'git checkout' to"
             "the next downstream branch right after the current one in the"
             "config file if successor branch exists."
             )

    def test_go_next_successor_on_another_root_tree(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete go next' command.

        Verify that 'git machete go next' can checkout to branch that doesn't
        share root with the current branch.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            .new_branch("level-1-branch")
            .commit()
            # x added so root will be placed in the config file after the level-0-branch
            .new_root_branch("x-additional-root")
            .commit()
            .check_out("level-1-branch")
        )
        launch_command("discover", "-y")
        launch_command("go", "next")

        assert 'x-additional-root' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete go next' can checkout to branch that doesn't"
             "share root with the current branch."
             )
        # check short command behaviour
        self.repo_sandbox.check_out("level-1-branch")
        launch_command("g", "n")

        assert 'x-additional-root' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete g n' can checkout to branch that doesn't"
             "share root with the current branch."
             )

    def test_go_prev_successor_exists(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete go prev' command.

        Verify that 'git machete go prev' performs 'git checkout' to
        the branch right before the current one in the config file
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
        launch_command("go", "prev")

        assert 'level-2a-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete go prev' performs 'git checkout' to"
             "the branch right before the current one in the config file"
             "when predecessor branch exists within the root tree."
             )
        # check short command behaviour
        self.repo_sandbox.check_out("level-1b-branch")
        launch_command("g", "p")

        assert 'level-2a-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete g p' performs 'git checkout' to"
             "the branch right before the current one in the config file"
             "when predecessor branch exists within the root tree."
             )

    def test_go_prev_successor_on_another_root_tree(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete go prev' command.

        Verify that 'git machete go prev' raises an error when predecessor
        branch doesn't exist.

        """
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("level-0-branch")
            .commit()
            # a added so root will be placed in the config file before the level-0-branch
            .new_root_branch("a-additional-root")
            .commit()
            .check_out("level-0-branch")
        )
        launch_command("discover", "-y")
        launch_command("go", "prev")

        assert 'a-additional-root' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete go prev' can checkout to branch that doesn't"
             "share root with the current branch."
             )
        # check short command behaviour
        self.repo_sandbox.check_out("level-0-branch")
        launch_command("g", "p")

        assert 'a-additional-root' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete g p' can checkout to branch that doesn't"
             "share root with the current branch."
             )

    def test_go_root(self, mocker: Any) -> None:
        """Verify behaviour of a 'git machete go root' command.

        Verify that 'git machete go root' performs 'git checkout' to
        the root of the current branch.

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
        launch_command("go", "root")

        assert 'level-0-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete go root' performs 'git checkout' to"
             "the root of the current branch."
             )
        # check short command behaviour
        self.repo_sandbox.check_out("level-2a-branch")
        launch_command("g", "r")

        assert 'level-0-branch' == \
            launch_command("show", "current").strip(), \
            ("Verify that 'git machete g r' performs 'git checkout' to"
             "the root of the current branch."
             )
