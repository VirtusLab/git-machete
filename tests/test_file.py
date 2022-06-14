from typing import Any

from .mockers import (GitRepositorySandbox, assert_command, launch_command, mock_run_cmd)


class TestFile:

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

    def test_file(self, mocker: Any) -> None:
        """
        Verify behaviour of a 'git machete file' command.
        """
        # mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("master")
                .commit("master commit.")
                .new_branch("develop")
                .commit("develop commit.")
                .new_branch("feature")
                .commit("feature commit.")
        )
        launch_command("discover", "-y")

        # sprawdzam dal normanego folderu
        x = launch_command("file")
        print()

        # sprawdzam dla worktree
        self.repo_sandbox.execute(f"git worktree add test -b new_feature")
        # ustawienie klucza machete.worktree.useTopLevelMacheteFile na false
        launch_command("discover", "-y")
        y_1 = self.repo_sandbox.execute('pwd')
        self.repo_sandbox.execute('cd ../test')
        y_2 = self.repo_sandbox.execute('pwd')
        x_2 = launch_command("file")
        print()



        assert_command(
            ['add', '--onto=feature'],
            'Added branch `chore/remove_indentation` onto `feature`\n',
            strip_indentation=False
        )
