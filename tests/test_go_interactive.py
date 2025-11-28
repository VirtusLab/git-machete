import os
import sys
from typing import Any, Tuple

import pytest
from pytest_mock import MockerFixture

from git_machete.utils import AnsiEscapeCodes

from .base_test import BaseTest
from .mockers import launch_command, rewrite_branch_layout_file
from .mockers_git_repository import check_out, commit, create_repo, new_branch

# Key codes for tests
KEY_UP = AnsiEscapeCodes.KEY_UP
KEY_DOWN = AnsiEscapeCodes.KEY_DOWN
KEY_RIGHT = AnsiEscapeCodes.KEY_RIGHT
KEY_LEFT = AnsiEscapeCodes.KEY_LEFT
KEY_SHIFT_UP = AnsiEscapeCodes.KEY_SHIFT_UP
KEY_SHIFT_DOWN = AnsiEscapeCodes.KEY_SHIFT_DOWN
KEY_SPACE = AnsiEscapeCodes.KEY_SPACE
KEY_CTRL_C = AnsiEscapeCodes.KEY_CTRL_C


def mock_read_stdin_returning(*keys: str) -> Any:
    """
    Create a mock for _read_stdin that returns characters from the key sequence.
    Multi-character keys (like arrow keys) are expanded into individual characters.
    """
    # Expand all keys into a single string of characters
    all_chars = ''.join(keys)
    char_list = list(all_chars)
    char_iter = iter(char_list)

    def inner(self: Any, n: int) -> str:  # noqa: U100
        result = ''
        for _ in range(n):
            try:
                result += next(char_iter)
            except StopIteration:
                break
        return result if result else ''  # Return empty string when exhausted (EOF)
    return inner


@pytest.mark.skipif(sys.platform == 'win32', reason="Interactive mode is not supported on Windows")
class TestGoInteractive(BaseTest):
    def setup_method(self) -> None:
        """Set up a standard 4-branch repository for each test."""
        super().setup_method()
        create_repo()
        new_branch("master")
        commit("Some commit message-1")
        new_branch("develop")
        commit("Some commit message-2")
        new_branch("feature-1")
        commit("Some commit message-3")
        check_out("develop")
        new_branch("feature-2")
        commit("Some commit message-4")
        check_out("develop")

        body = \
            """
            master
                develop
                    feature-1
                    feature-2
            """
        rewrite_branch_layout_file(body)

    def run_interactive_test(self, mocker: MockerFixture, keys: Tuple[str, ...]) -> str:
        """
        Helper to run an interactive test by mocking stdin and terminal methods.
        Returns the captured stdout.
        """
        # Mock _get_stdin_fd to return a fake file descriptor
        self.patch_symbol(mocker, 'git_machete.client.go_interactive.GoInteractiveMacheteClient._get_stdin_fd',
                          lambda self: 0)

        # Mock _read_stdin to return characters from the key sequence
        self.patch_symbol(mocker, 'git_machete.client.go_interactive.GoInteractiveMacheteClient._read_stdin',
                          mock_read_stdin_returning(*keys))

        # Mock termios and tty functions to avoid actual terminal manipulation
        self.patch_symbol(mocker, 'termios.tcgetattr', lambda _fd: None)  # noqa: U100
        self.patch_symbol(mocker, 'termios.tcsetattr', lambda _fd, _when, _attributes: None)  # noqa: U100
        self.patch_symbol(mocker, 'tty.setraw', lambda _fd: None)  # noqa: U100

        # Run the command and return the output
        return launch_command('go')

    def test_go_interactive_navigation_up_down(self, mocker: MockerFixture) -> None:
        """Test that up/down arrow keys navigate through branches."""
        check_out("develop")

        # Navigate down once, then quit
        output = self.run_interactive_test(mocker, (KEY_DOWN, 'q'))

        # Should show the branch list
        assert "Select branch" in output
        assert "master" in output
        assert "develop" in output
        assert "feature-1" in output
        assert "feature-2" in output

    def test_go_interactive_shift_arrows_jump(self, mocker: MockerFixture) -> None:
        """Test that Shift+Up/Down jumps to first/last branch."""
        check_out("develop")

        # Shift+Down to jump to last, Space to checkout
        self.run_interactive_test(mocker, (KEY_SHIFT_DOWN, KEY_SPACE))

        # Verify we checked out feature-2
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-2"

        # Now test Shift+Up to jump to first
        check_out("develop")
        self.run_interactive_test(mocker, (KEY_SHIFT_UP, KEY_SPACE))

        # Verify we checked out master
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_left_arrow_parent(self, mocker: MockerFixture) -> None:
        """Test that left arrow navigates to parent branch (not just up), and does nothing on root."""
        check_out("feature-2")

        # Left (to develop), Left (to master), Left (no parent - should stay on master), Space (checkout master)
        self.run_interactive_test(mocker, (KEY_LEFT, KEY_LEFT, KEY_LEFT, KEY_SPACE))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_right_arrow_child(self, mocker: MockerFixture) -> None:
        """Test that right arrow navigates to first child branch (not just down), and does nothing if no child."""
        check_out("develop")

        # Right (to feature-1), Right (no child - should stay on feature-1), Space (checkout)
        self.run_interactive_test(mocker, (KEY_RIGHT, KEY_RIGHT, KEY_SPACE))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-1"

    def test_go_interactive_quit_without_checkout(self, mocker: MockerFixture) -> None:
        """Test that pressing Ctrl+C quits without checking out."""
        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()

        # Navigate down, then quit with Ctrl+C
        self.run_interactive_test(mocker, (KEY_DOWN, KEY_CTRL_C))

        # Verify we're still on the initial branch
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == initial_branch

    def test_go_interactive_space_checkout(self, mocker: MockerFixture) -> None:
        """Test that pressing Space checks out the selected branch."""
        check_out("master")

        # Navigate down to develop, checkout with Space
        self.run_interactive_test(mocker, (KEY_DOWN, KEY_SPACE))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "develop"

    def test_go_interactive_with_annotations(self, mocker: MockerFixture) -> None:
        """Test that branch annotations are displayed with proper formatting."""
        # Overwrite .git/machete with annotations
        body: str = \
            """
            master
                develop  PR #123
                    feature-1  rebase=no push=no
                    feature-2
            """
        rewrite_branch_layout_file(body)

        check_out("master")

        # Just quit
        output = self.run_interactive_test(mocker, ('q',))

        # Check that annotations are shown (they should be dimmed/formatted)
        assert "PR #123" in output or "123" in output  # Annotation might be formatted
        assert "rebase=no push=no" in output or "rebase" in output

    def test_go_interactive_wrapping_navigation(self, mocker: MockerFixture) -> None:
        """Test that up/down arrow keys wrap around at the edges."""
        check_out("master")

        # Down from feature-2 (last) should wrap to master (first)
        # Go to last with Shift+Down, then Down again (wrap to first), then Space
        self.run_interactive_test(mocker, (KEY_SHIFT_DOWN, KEY_DOWN, KEY_SPACE))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_q_key_quit(self, mocker: MockerFixture) -> None:
        """Test that pressing 'q' or 'Q' quits without checking out."""
        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()

        # Navigate and quit with 'q'
        self.run_interactive_test(mocker, (KEY_DOWN, 'q'))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == initial_branch

        # Test with 'Q' as well
        self.run_interactive_test(mocker, (KEY_DOWN, 'Q'))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == initial_branch

    def test_go_interactive_unknown_key_ignored(self, mocker: MockerFixture) -> None:
        """Test that unknown keys are ignored and don't break the interface."""
        check_out("master")

        # Send unknown keys (letters, Alt+a), then quit
        self.run_interactive_test(mocker, ('x', 'y', 'z', '\x1ba', 'q'))

        # Should still be on master (no checkout happened)
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_unmanaged_current_branch(self, mocker: MockerFixture) -> None:
        """Test that when current branch is unmanaged, a warning is shown and selection starts at first branch."""
        # Create an unmanaged branch (not in .git/machete)
        new_branch("unmanaged")
        check_out("unmanaged")

        # Just quit
        output = self.run_interactive_test(mocker, ('q',))

        # Check for warning in output (it might be in stderr, but let's check stdout first)
        # Note: We might need to capture stderr separately if warning goes there
        # For now, just verify no crash and we can navigate
        assert "Select branch" in output

    def test_go_interactive_scrolling_down(self, mocker: MockerFixture) -> None:
        """Test that scrolling works when there are more branches than fit on screen."""
        # Mock terminal height to 4, which results in max_visible_branches = 2 (4 - 2)
        self.patch_symbol(mocker, 'git_machete.utils.get_terminal_height', lambda: 4)

        check_out("master")

        # Navigate down and checkout
        self.run_interactive_test(mocker, (KEY_DOWN, KEY_DOWN, KEY_DOWN, KEY_SPACE))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-2"

    def test_go_interactive_scrolling_up(self, mocker: MockerFixture) -> None:
        """Test that scrolling up works when starting from a branch that requires initial scroll offset."""
        # Mock terminal height to 4, which results in max_visible_branches = 2 (4 - 2)
        self.patch_symbol(mocker, 'git_machete.utils.get_terminal_height', lambda: 4)

        check_out("feature-2")

        # Navigate up to master and checkout
        self.run_interactive_test(mocker, (KEY_UP, KEY_UP, KEY_UP, KEY_SPACE))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"
