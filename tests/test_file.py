import os
from pathlib import Path
from typing import Any

from .mockers import (GitRepositorySandbox, launch_command, mock_run_cmd, GitContext)


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
        mocker.patch('git_machete.utils.run_cmd', mock_run_cmd)  # to hide git outputs in tests

        (
            self.repo_sandbox.new_branch("master")
                .commit("master commit.")
                .new_branch("develop")
                .commit("develop commit.")
                .new_branch("feature")
                .commit("feature commit.")
        )

        # check git machete definition file path when inside normal directory
        definition_file_full_path = launch_command("file")
        definition_file_path = Path(definition_file_full_path).parts
        definition_file_path_relative_to_git_dir = '/'.join(definition_file_path[-2:]).rstrip('\n')
        assert definition_file_path_relative_to_git_dir == '.git/machete'

        # check git machete definition file path when inside worktree
        if GitContext().get_git_version() >= (2, 5):
            self.repo_sandbox.execute("rm -rf test_worktree")
            self.repo_sandbox.add_git_config_key('machete.worktree.useTopLevelMacheteFile', 'false')
            self.repo_sandbox.execute("git worktree add -f -b new_feature test_worktree develop")
            os.chdir('test_worktree')
            definition_file_full_path = launch_command("file")
            definition_file_path = Path(definition_file_full_path).parts
            definition_file_path_relative_to_git_dir = '/'.join(definition_file_path[-4:]).rstrip('\n')
            assert definition_file_path_relative_to_git_dir == '.git/worktrees/test_worktree/machete'
