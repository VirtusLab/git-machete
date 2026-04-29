# flake8: noqa: E501
import os
import sys
import textwrap
from typing import Any, Tuple, Type

import pytest
from pytest_mock import MockerFixture

from git_machete.utils import AnsiInputCodes, FullTerminalAnsiOutputCodes

from .base_test import BaseTest
from .mockers import assert_failure, launch_command, rewrite_branch_layout_file
from .mockers_git_repository import check_out, commit, create_repo, new_branch

AI = AnsiInputCodes
KEY_ENTER = '\r'

AO = FullTerminalAnsiOutputCodes

HEADER = (
    "Select branch (↑/↓: prev/next, Shift+↑/↓: first/last, ←: parent, →: child, "
    "Enter or Space: checkout, q or Ctrl+C: quit)"
)


def _redraw_sequence(ao: Type[FullTerminalAnsiOutputCodes], num_lines: int) -> str:
    """ANSI sequence to move cursor up num_lines and clear to end of screen (for TUI redraw)."""
    return ao.cursor_up(num_lines) + ao.CLEAR_TO_END


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
        self.patch_symbol(mocker, 'git_machete.utils.is_stdout_a_tty', lambda: True)
        self.patch_symbol(mocker, 'git_machete.utils.is_stderr_a_tty', lambda: True)
        self.patch_symbol(mocker, "git_machete.utils.is_terminal_fully_fledged", lambda: True)

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

        # Navigate: DOWN (to feature-1), UP (back to develop), DOWN (to feature-1 again), SPACE (checkout)
        output = self.run_interactive_test(mocker, (AI.KEY_DOWN, AI.KEY_UP, AI.KEY_DOWN, AI.KEY_SPACE))

        screen_develop_selected = textwrap.dedent(f"""\
            {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
              {AO.BOLD}master{AO.ENDC_BOLD_DIM}
              {AO.GREEN}│{AO.ENDC}
              {AO.GREEN}└─{AO.ENDC}{AO.REVERSE_VIDEO}{AO.BOLD}{AO.UNDERLINE}develop{AO.ENDC_UNDERLINE}{AO.ENDC_BOLD_DIM}{AO.ENDC}
                {AO.GREEN}│{AO.ENDC}
                {AO.GREEN}├─{AO.ENDC}{AO.BOLD}feature-1{AO.ENDC_BOLD_DIM}
                {AO.GREEN}│{AO.ENDC}
                {AO.GREEN}└─{AO.ENDC}{AO.BOLD}feature-2{AO.ENDC_BOLD_DIM}
        """)
        screen_feature1_selected = textwrap.dedent(f"""\
            {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
              {AO.BOLD}master{AO.ENDC_BOLD_DIM}
              {AO.GREEN}│{AO.ENDC}
              {AO.GREEN}└─{AO.ENDC}{AO.BOLD}{AO.UNDERLINE}develop{AO.ENDC_UNDERLINE}{AO.ENDC_BOLD_DIM}
                {AO.GREEN}│{AO.ENDC}
                {AO.GREEN}├─{AO.ENDC}{AO.REVERSE_VIDEO}{AO.BOLD}feature-1{AO.ENDC_BOLD_DIM}{AO.ENDC}
                {AO.GREEN}│{AO.ENDC}
                {AO.GREEN}└─{AO.ENDC}{AO.BOLD}feature-2{AO.ENDC_BOLD_DIM}
        """)
        redraw = _redraw_sequence(AO, 8)
        expected = (
            AO.HIDE_CURSOR +
            screen_develop_selected +
            redraw +
            screen_feature1_selected +
            redraw +
            screen_develop_selected +
            redraw +
            screen_feature1_selected +
            AO.SHOW_CURSOR +
            f"\nChecking out {AO.BOLD}feature-1{AO.ENDC_BOLD_DIM}... {AO.GREEN}{AO.BOLD}OK{AO.ENDC_BOLD_DIM}{AO.ENDC}\n"
        )
        assert output == expected

        # Verify we checked out feature-1
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-1"

    def test_go_interactive_shift_arrows_jump(self, mocker: MockerFixture) -> None:
        """Test that Shift+Up/Down jumps to first/last branch."""
        check_out("develop")

        # Shift+Down to jump to last, Space to checkout
        self.run_interactive_test(mocker, (AI.KEY_SHIFT_DOWN, AI.KEY_SPACE))

        # Verify we checked out feature-2
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-2"

        # Now test Shift+Up to jump to first branch, use Enter to checkout
        check_out("develop")
        self.run_interactive_test(mocker, (AI.KEY_SHIFT_UP, KEY_ENTER))

        # Verify we checked out master
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_left_arrow_parent(self, mocker: MockerFixture) -> None:
        """Test that left arrow navigates to parent branch (not just up), and does nothing on root."""
        check_out("feature-2")

        # Left (to develop), Left (to master), Left (no parent - should stay on master), Space (checkout master)
        self.run_interactive_test(mocker, (AI.KEY_LEFT, AI.KEY_LEFT, AI.KEY_LEFT, AI.KEY_SPACE))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_right_arrow_child(self, mocker: MockerFixture) -> None:
        """Test that right arrow navigates to first child branch (not just down), and does nothing if no child."""
        check_out("develop")

        # Right (to feature-1), Right (no child - should stay on feature-1), Space (checkout)
        self.run_interactive_test(mocker, (AI.KEY_RIGHT, AI.KEY_RIGHT, AI.KEY_SPACE))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-1"

    def test_go_interactive_quit_without_checkout(self, mocker: MockerFixture) -> None:
        """Test that pressing Ctrl+C quits without checking out."""
        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()

        # Navigate down, then quit with Ctrl+C
        self.run_interactive_test(mocker, (AI.KEY_DOWN, AI.KEY_CTRL_C))

        # Verify we're still on the initial branch
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == initial_branch

    def test_go_interactive_enter_and_space_checkout(self, mocker: MockerFixture) -> None:
        """Test that pressing Enter or Space checks out the selected branch."""
        check_out("master")

        # Navigate down to develop, checkout with Enter
        self.run_interactive_test(mocker, (AI.KEY_DOWN, KEY_ENTER))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "develop"

        # Now test Space as well
        check_out("master")
        self.run_interactive_test(mocker, (AI.KEY_DOWN, AI.KEY_SPACE))

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

        expected = (
            AO.HIDE_CURSOR +
            textwrap.dedent(f"""\
                {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
                  {AO.REVERSE_VIDEO}{AO.BOLD}{AO.UNDERLINE}master{AO.ENDC_UNDERLINE}{AO.ENDC_BOLD_DIM}{AO.ENDC}
                  {AO.GREEN}│{AO.ENDC}
                  {AO.GREEN}└─{AO.ENDC}{AO.BOLD}develop{AO.ENDC_BOLD_DIM}  {AO.DIM}PR #123{AO.ENDC_BOLD_DIM}
                    {AO.GREEN}│{AO.ENDC}
                    {AO.GREEN}├─{AO.ENDC}{AO.BOLD}feature-1{AO.ENDC_BOLD_DIM}  {AO.DIM}{AO.UNDERLINE}rebase=no push=no{AO.ENDC_UNDERLINE}{AO.ENDC_BOLD_DIM}
                    {AO.GREEN}│{AO.ENDC}
                    {AO.GREEN}└─{AO.ENDC}{AO.BOLD}feature-2{AO.ENDC_BOLD_DIM}
            """) +
            AO.SHOW_CURSOR
        )
        assert output == expected

    def test_go_interactive_wrapping_navigation(self, mocker: MockerFixture) -> None:
        """Test that up/down arrow keys wrap around at the edges."""
        check_out("master")

        # Down from feature-2 (last) should wrap to master (first)
        # Go to last with Shift+Down, then Down again (wrap to first), then Space
        self.run_interactive_test(mocker, (AI.KEY_SHIFT_DOWN, AI.KEY_DOWN, AI.KEY_SPACE))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_q_key_quit(self, mocker: MockerFixture) -> None:
        """Test that pressing 'q' or 'Q' quits without checking out."""
        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()

        # Navigate and quit with 'q'
        self.run_interactive_test(mocker, (AI.KEY_DOWN, 'q'))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == initial_branch

        # Test with 'Q' as well
        self.run_interactive_test(mocker, (AI.KEY_DOWN, 'Q'))

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

        expected = (
            AO.ORANGE + "Warn: " + AO.ENDC + "current branch unmanaged is unmanaged\n\n" +
            AO.HIDE_CURSOR +
            textwrap.dedent(f"""\
                {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
                  {AO.REVERSE_VIDEO}{AO.BOLD}master{AO.ENDC_BOLD_DIM}{AO.ENDC}
                  {AO.GREEN}│{AO.ENDC}
                  {AO.GREEN}└─{AO.ENDC}{AO.BOLD}develop{AO.ENDC_BOLD_DIM}
                    {AO.GREEN}│{AO.ENDC}
                    {AO.GREEN}├─{AO.ENDC}{AO.BOLD}feature-1{AO.ENDC_BOLD_DIM}
                    {AO.GREEN}│{AO.ENDC}
                    {AO.GREEN}└─{AO.ENDC}{AO.BOLD}feature-2{AO.ENDC_BOLD_DIM}
            """) +
            AO.SHOW_CURSOR
        )
        assert output == expected

    def test_go_interactive_scrolling_down(self, mocker: MockerFixture) -> None:
        """Test that scrolling works when there are more branches than fit on screen."""
        # Mock terminal height to 3, which results in max_visible_branches = 1 (3 - 2)
        # With only 1 branch visible, initial view shows just master; after 3x DOWN we show feature-2.
        self.patch_symbol(mocker, 'git_machete.utils.get_terminal_height', lambda: 3)

        check_out("master")

        # First, check initial output without scrolling - feature-2 should be hidden
        output_no_scroll = self.run_interactive_test(mocker, ('q',))
        expected_no_scroll = (
            AO.HIDE_CURSOR +
            textwrap.dedent(f"""\
                {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
                  {AO.REVERSE_VIDEO}{AO.BOLD}{AO.UNDERLINE}master{AO.ENDC_UNDERLINE}{AO.ENDC_BOLD_DIM}{AO.ENDC}
                  {AO.GREEN}│{AO.ENDC}
            """) +
            AO.SHOW_CURSOR
        )
        assert output_no_scroll == expected_no_scroll

        # Now navigate down to trigger scrolling and verify feature-2 becomes visible
        output_with_scroll = self.run_interactive_test(mocker, (AI.KEY_DOWN, AI.KEY_DOWN, AI.KEY_DOWN, 'q'))
        redraw = _redraw_sequence(AO, 3)
        screen_master = textwrap.dedent(f"""\
            {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
              {AO.REVERSE_VIDEO}{AO.BOLD}{AO.UNDERLINE}master{AO.ENDC_UNDERLINE}{AO.ENDC_BOLD_DIM}{AO.ENDC}
              {AO.GREEN}│{AO.ENDC}
        """)
        screen_develop = textwrap.dedent(f"""\
            {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
              {AO.GREEN}│{AO.ENDC}
              {AO.GREEN}└─{AO.ENDC}{AO.REVERSE_VIDEO}{AO.BOLD}develop{AO.ENDC_BOLD_DIM}{AO.ENDC}
        """)
        screen_feature1 = textwrap.dedent(f"""\
            {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
                {AO.GREEN}│{AO.ENDC}
                {AO.GREEN}├─{AO.ENDC}{AO.REVERSE_VIDEO}{AO.BOLD}feature-1{AO.ENDC_BOLD_DIM}{AO.ENDC}
        """)
        screen_feature2 = textwrap.dedent(f"""\
            {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
                {AO.GREEN}│{AO.ENDC}
                {AO.GREEN}└─{AO.ENDC}{AO.REVERSE_VIDEO}{AO.BOLD}feature-2{AO.ENDC_BOLD_DIM}{AO.ENDC}
        """)
        expected_with_scroll = (
            AO.HIDE_CURSOR +
            screen_master +
            redraw + screen_develop +
            redraw + screen_feature1 +
            redraw + screen_feature2 +
            AO.SHOW_CURSOR
        )
        assert output_with_scroll == expected_with_scroll

        # Finally, navigate down and checkout to verify functionality
        self.run_interactive_test(mocker, (AI.KEY_DOWN, AI.KEY_DOWN, AI.KEY_DOWN, AI.KEY_SPACE))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-2"

    def test_go_interactive_scrolling_up(self, mocker: MockerFixture) -> None:
        """Test that scrolling up works when starting from a branch that requires initial scroll offset."""
        # Mock terminal height to 3, which results in max_visible_branches = 1 (3 - 2)
        # With only 1 branch visible, initial view shows just feature-2; after 3x UP we show master.
        self.patch_symbol(mocker, 'git_machete.utils.get_terminal_height', lambda: 3)

        check_out("feature-2")

        # First, check initial output without scrolling - master should be hidden
        output_no_scroll = self.run_interactive_test(mocker, ('q',))
        expected_no_scroll = (
            AO.HIDE_CURSOR +
            textwrap.dedent(f"""\
                {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
                    {AO.GREEN}│{AO.ENDC}
                    {AO.GREEN}└─{AO.ENDC}{AO.REVERSE_VIDEO}{AO.BOLD}{AO.UNDERLINE}feature-2{AO.ENDC_UNDERLINE}{AO.ENDC_BOLD_DIM}{AO.ENDC}
            """) +
            AO.SHOW_CURSOR
        )
        assert output_no_scroll == expected_no_scroll

        # Now navigate up to trigger scrolling and verify master becomes visible
        output_with_scroll = self.run_interactive_test(mocker, (AI.KEY_UP, AI.KEY_UP, AI.KEY_UP, 'q'))
        redraw = _redraw_sequence(AO, 3)
        screen_feature2 = textwrap.dedent(f"""\
            {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
                {AO.GREEN}│{AO.ENDC}
                {AO.GREEN}└─{AO.ENDC}{AO.REVERSE_VIDEO}{AO.BOLD}{AO.UNDERLINE}feature-2{AO.ENDC_UNDERLINE}{AO.ENDC_BOLD_DIM}{AO.ENDC}
        """)
        screen_feature1 = textwrap.dedent(f"""\
            {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
                {AO.GREEN}├─{AO.ENDC}{AO.REVERSE_VIDEO}{AO.BOLD}feature-1{AO.ENDC_BOLD_DIM}{AO.ENDC}
                {AO.GREEN}│{AO.ENDC}
        """)
        screen_develop = textwrap.dedent(f"""\
            {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
              {AO.GREEN}└─{AO.ENDC}{AO.REVERSE_VIDEO}{AO.BOLD}develop{AO.ENDC_BOLD_DIM}{AO.ENDC}
                {AO.GREEN}│{AO.ENDC}
        """)
        screen_master = textwrap.dedent(f"""\
            {AO.BOLD}{HEADER}{AO.ENDC_BOLD_DIM}
              {AO.REVERSE_VIDEO}{AO.BOLD}master{AO.ENDC_BOLD_DIM}{AO.ENDC}
              {AO.GREEN}│{AO.ENDC}
        """)
        expected_with_scroll = (
            AO.HIDE_CURSOR +
            screen_feature2 +
            redraw + screen_feature1 +
            redraw + screen_develop +
            redraw + screen_master +
            AO.SHOW_CURSOR
        )
        assert output_with_scroll == expected_with_scroll

        # Finally, navigate up and checkout to verify functionality
        self.run_interactive_test(mocker, (AI.KEY_UP, AI.KEY_UP, AI.KEY_UP, AI.KEY_SPACE))

        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_when_detached_head(self, mocker: MockerFixture) -> None:
        """Test that interactive mode works when in detached HEAD mode."""
        # Detached HEAD - no current branch, so selection should start at first branch
        commit_hash = os.popen("git rev-parse develop").read().strip()
        check_out(commit_hash)

        # Simulate pressing Enter (to select the first branch which will be pre-selected at master)
        self.run_interactive_test(mocker, (KEY_ENTER,))

        # Verify we checked out master (the first branch in the layout)
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_requires_tty(self, mocker: MockerFixture) -> None:
        """Interactive `go` fails immediately when stdout is not a TTY (e.g. piped to cat)."""
        self.patch_symbol(mocker, 'git_machete.utils.is_stdout_a_tty', lambda: False)
        assert_failure(
            ['go'],
            "Interactive git machete go requires stdout to be a TTY.",
        )
