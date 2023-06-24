
from .base_test import BaseTest
from .mockers import launch_command


# These are mostly smoke-tests which also provide coverage.
# The actual end-to-end tests (which run the corresponding shells) are located in completion_e2e/.
class TestCompletion(BaseTest):

    def test_bash_completion(self) -> None:
        output = launch_command("completion", "bash")
        assert '_git_machete()' in output

    def test_fish_completion(self) -> None:
        output = launch_command("completion", "fish")
        assert 'complete -c git-machete' in output

    def test_zsh_completion(self) -> None:
        output = launch_command("completion", "zsh")
        assert '_git-machete()' in output
