from .base_test import BaseTest
from .mockers import assert_success, launch_command, overridden_environment

dummy_editor = "sh -c 'echo foo > $1' 'ignored_$0'"


class TestEdit(BaseTest):

    def test_edit_git_machete_editor(self) -> None:
        with overridden_environment(GIT_MACHETE_EDITOR=dummy_editor):
            launch_command("edit")
        assert self.repo_sandbox.read_file(".git/machete").strip() == "foo"

    def test_edit_git_editor(self) -> None:
        self.repo_sandbox.set_git_config_key("advice.macheteEditorSelection", "true")

        with overridden_environment(GIT_EDITOR=dummy_editor):
            assert_success(
                ["edit"],
                """
                Opening '$GIT_EDITOR' (sh -c 'echo foo > $1' 'ignored_$0').
                To override this choice, use GIT_MACHETE_EDITOR env var, e.g. export GIT_MACHETE_EDITOR=vi.

                See git machete help edit and git machete edit --debug for more details.

                Use git config --global advice.macheteEditorSelection false to suppress this message.
                """
            )
        assert self.repo_sandbox.read_file(".git/machete").strip() == "foo"

    def test_edit_git_config_core_editor(self) -> None:
        self.repo_sandbox.set_git_config_key("advice.macheteEditorSelection", "false")

        with overridden_environment(GIT_MACHETE_EDITOR="  ", GIT_EDITOR="lolxd-this-doesnt-exist", VISUAL="", EDITOR=dummy_editor):
            assert_success(["edit"], "")
        assert self.repo_sandbox.read_file(".git/machete").strip() == "foo"
