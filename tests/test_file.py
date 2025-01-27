import os
from pathlib import Path
from tempfile import mkdtemp

from git_machete.exceptions import UnderlyingGitException

from .base_test import BaseTest
from .mockers import assert_failure, execute, launch_command
from .mockers_git_repository import (commit, create_repo, get_git_version,
                                     new_branch, set_git_config_key)


class TestFile(BaseTest):

    def test_file(self) -> None:
        """
        Verify behaviour of a 'git machete file' command.
        """

        create_repo()
        new_branch("master")
        commit("master commit.")
        new_branch("develop")
        commit("develop commit.")
        new_branch("feature")
        commit("feature commit.")

        # check branch layout file path when inside a normal directory
        branch_layout_file_full_path = launch_command("file")
        branch_layout_file_path = Path(branch_layout_file_full_path).parts
        branch_layout_file_path_relative_to_git_dir = '/'.join(branch_layout_file_path[-2:]).rstrip('\n')
        assert branch_layout_file_path_relative_to_git_dir == '.git/machete'

        if get_git_version() >= (2, 5):  # `git worktree` command was introduced in git version 2.5
            # check branch layout file path when inside a worktree using the default `True` value
            # for the `machete.worktree.useTopLevelMacheteFile` key
            execute("git worktree add -f -b snickers_feature snickers_worktree develop")
            os.chdir('snickers_worktree')
            branch_layout_file_full_path = launch_command("file")
            branch_layout_file_path = Path(branch_layout_file_full_path).parts
            branch_layout_file_path_relative_to_git_dir = '/'.join(branch_layout_file_path[-2:]).rstrip('\n')
            assert branch_layout_file_path_relative_to_git_dir == '.git/machete'

            # check branch layout file path when inside a worktree
            # but with the `machete.worktree.useTopLevelMacheteFile` key set to `False`
            set_git_config_key('machete.worktree.useTopLevelMacheteFile', 'false')
            execute("git worktree add -f -b mars_feature mars_worktree develop")
            os.chdir('mars_worktree')
            branch_layout_file_full_path = launch_command("file")
            branch_layout_file_path = Path(branch_layout_file_full_path).parts
            branch_layout_file_path_relative_to_git_dir = '/'.join(branch_layout_file_path[-4:]).rstrip('\n')
            assert branch_layout_file_path_relative_to_git_dir == '.git/worktrees/mars_worktree/machete'

    def test_file_outside_git_repo(self) -> None:
        os.chdir(mkdtemp())
        assert_failure(["file", "--debug"], "Not a git repository", expected_type=UnderlyingGitException)

    def test_file_when_git_machete_is_a_directory(self) -> None:
        create_repo()
        execute(f"mkdir .git{os.path.sep}machete")
        assert_failure(["file"], ".git/machete is a directory rather than a regular file, aborting")
