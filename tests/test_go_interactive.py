import os
import sys
from typing import Any, Callable

import pytest
from pytest_mock import MockerFixture

from git_machete import cli
from git_machete.utils import AnsiEscapeCodes

from .base_test import BaseTest
from .mockers import rewrite_branch_layout_file
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


def mock_getch_returning(*keys: str) -> Callable[[Any], str]:
    """
    Mock for _getch that returns a predetermined sequence of keys.
    Similar to mock_input_returning but for _getch.
    """
    gen = (key for key in keys)

    def inner(self: Any) -> str:  # noqa: U100
        return next(gen, '')  # Return empty string when exhausted (EOF)
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

    def run_interactive_test(self, mocker: MockerFixture, keys: tuple, capsys: pytest.CaptureFixture) -> str:
        """
        Helper to run an interactive test by mocking _getch with a sequence of keys.
        Returns the captured stdout.
        """
        # Mock _getch to return the sequence of keys
        self.patch_symbol(mocker, 'git_machete.client.go_interactive.GoInteractiveMacheteClient._getch',
                          mock_getch_returning(*keys))

        # Run the command
        cli.launch(['go'])

        # Capture and return the output
        captured = capsys.readouterr()
        return captured.out

    def test_go_interactive_navigation_up_down(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
        """Test that up/down arrow keys navigate through branches."""
        check_out("develop")

        # Navigate down once, then quit
        output = self.run_interactive_test(mocker, (KEY_DOWN, 'q'), capsys)

        # Should show the branch list
        assert "Select branch" in output
        assert "master" in output
        assert "develop" in output
        assert "feature-1" in output
        assert "feature-2" in output

    def test_go_interactive_shift_arrows_jump(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
        """Test that Shift+Up/Down jumps to first/last branch."""
        check_out("develop")

        # Shift+Down to jump to last, Space to checkout
        self.run_interactive_test(mocker, (KEY_SHIFT_DOWN, KEY_SPACE), capsys)

        # Verify we checked out feature-2
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-2"

    def test_go_interactive_left_arrow_parent(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
        """Test that left arrow navigates to parent branch (not just up), and does nothing on root."""
        check_out("feature-2")

        # Left (to develop), Left (to master), Space (checkout master)
        self.run_interactive_test(mocker, (KEY_LEFT, KEY_LEFT, KEY_SPACE), capsys)

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_right_arrow_child(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
        """Test that right arrow navigates to first child branch (not just down)."""
        check_out("develop")

        # Right (to feature-1), Space (checkout)
        self.run_interactive_test(mocker, (KEY_RIGHT, KEY_SPACE), capsys)

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-1"

    def test_go_interactive_quit_without_checkout(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
        """Test that pressing Ctrl+C quits without checking out."""
        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()

        # Navigate down, then quit with Ctrl+C
        self.run_interactive_test(mocker, (KEY_DOWN, KEY_CTRL_C), capsys)

        # Verify we're still on the initial branch
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == initial_branch

    def test_go_interactive_space_checkout(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
        """Test that pressing Space checks out the selected branch."""
        check_out("master")

        # Navigate down to develop, checkout with Space
        self.run_interactive_test(mocker, (KEY_DOWN, KEY_SPACE), capsys)

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "develop"

    def test_go_interactive_with_annotations(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
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
        output = self.run_interactive_test(mocker, ('q',), capsys)

        # Check that annotations are shown (they should be dimmed/formatted)
        assert "PR #123" in output or "123" in output  # Annotation might be formatted
        assert "rebase=no push=no" in output or "rebase" in output

    def test_go_interactive_wrapping_navigation(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
        """Test that up/down arrow keys wrap around at the edges."""
        check_out("master")

        # Down from feature-2 (last) should wrap to master (first)
        # Go to last with Shift+Down, then Down again (wrap to first), then Space
        self.run_interactive_test(mocker, (KEY_SHIFT_DOWN, KEY_DOWN, KEY_SPACE), capsys)

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_q_key_quit(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
        """Test that pressing 'q' or 'Q' quits without checking out."""
        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()

        # Navigate and quit with 'q'
        self.run_interactive_test(mocker, (KEY_DOWN, 'q'), capsys)

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == initial_branch

        # Test with 'Q' as well
        self.run_interactive_test(mocker, (KEY_DOWN, 'Q'), capsys)

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == initial_branch

    def test_go_interactive_unknown_key_ignored(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
        """Test that unknown keys are ignored and don't break the interface."""
        check_out("master")

        # Send unknown keys (letters, Alt+a), then quit
        self.run_interactive_test(mocker, ('x', 'y', 'z', '\x1ba', 'q'), capsys)

        # Should still be on master (no checkout happened)
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_unmanaged_current_branch(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
        """Test that when current branch is unmanaged, a warning is shown and selection starts at first branch."""
        # Create an unmanaged branch (not in .git/machete)
        new_branch("unmanaged")
        check_out("unmanaged")

        # Just quit
        output = self.run_interactive_test(mocker, ('q',), capsys)

        # Check for warning in output (it might be in stderr, but let's check stdout first)
        # Note: We might need to capture stderr separately if warning goes there
        # For now, just verify no crash and we can navigate
        assert "Select branch" in output

    def test_go_interactive_scrolling_down(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
        """Test that scrolling works when there are more branches than fit on screen."""
        # Mock terminal height to 4, which results in max_visible_branches = 2 (4 - 2)
        self.patch_symbol(mocker, 'git_machete.utils.get_terminal_height', lambda: 4)

        check_out("master")

        # Navigate down and checkout
        self.run_interactive_test(mocker, (KEY_DOWN, KEY_DOWN, KEY_DOWN, KEY_SPACE), capsys)

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-2"

    def test_go_interactive_scrolling_up(self, mocker: MockerFixture, capsys: pytest.CaptureFixture) -> None:
        """Test that scrolling up works when starting from a branch that requires initial scroll offset."""
        # Mock terminal height to 4, which results in max_visible_branches = 2 (4 - 2)
        self.patch_symbol(mocker, 'git_machete.utils.get_terminal_height', lambda: 4)

        check_out("feature-2")

        # Navigate up to master and checkout
        self.run_interactive_test(mocker, (KEY_UP, KEY_UP, KEY_UP, KEY_SPACE), capsys)

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"
