from .base_test import BaseTest
from .mockers import launch_command, overridden_environment


class TestEdit(BaseTest):

    def test_edit_git_machete_editor(self) -> None:
        with overridden_environment(GIT_MACHETE_EDITOR="bash -c 'echo foo > $1' 'ignored_$0'"):
            launch_command("edit", "--debug")
        assert self.repo_sandbox.read_file(".git/machete") == "foo\n"
