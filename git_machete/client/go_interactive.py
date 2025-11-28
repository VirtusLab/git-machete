import sys
from typing import List, Optional, Tuple

try:
    import termios
    import tty
except ImportError:  # pragma: no cover; Windows-specific
    # termios and tty are not available on Windows
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]

from git_machete import utils
from git_machete.client.base import MacheteClient
from git_machete.exceptions import UnexpectedMacheteException
from git_machete.git_operations import LocalBranchShortName
from git_machete.utils import AnsiEscapeCodes, bold, index_or_none, warn


class GoInteractiveMacheteClient(MacheteClient):
    """Client for interactive branch selection using curses-style interface (implemented without curses, just using ANSI sequences)."""

    MAX_VISIBLE_BRANCHES_DEFAULT = 20
    MAX_VISIBLE_BRANCHES_LOWER = 2
    MAX_VISIBLE_BRANCHES_UPPER = 50

    _managed_branches_with_depths: List[Tuple[LocalBranchShortName, int]]
    _current_branch: LocalBranchShortName
    _max_visible_branches: int

    def _get_max_visible_branches(self) -> int:
        """Get the maximum number of branches that can be displayed based on terminal height."""
        terminal_height = utils.get_terminal_height()
        if terminal_height is None:
            # Fallback if terminal size cannot be determined (e.g., not a TTY)
            return self.MAX_VISIBLE_BRANCHES_DEFAULT
        # Reserve 1 line for header, plus 1 line for padding
        max_visible_branches = terminal_height - 2
        return max(self.MAX_VISIBLE_BRANCHES_LOWER, min(max_visible_branches, self.MAX_VISIBLE_BRANCHES_UPPER))

    def _get_branch_list_with_depths(self) -> List[Tuple[LocalBranchShortName, int]]:
        """Get a flat list of branches with their depths using DFS traversal."""
        result: List[Tuple[LocalBranchShortName, int]] = []

        def add_branch_and_children(branch: LocalBranchShortName, depth: int) -> None:
            result.append((branch, depth))
            for child_branch in self.down_branches_for(branch) or []:
                add_branch_and_children(child_branch, depth + 1)

        for root in self._state.roots:
            add_branch_and_children(root, depth=0)

        return result

    def _render_branch_line(self, branch: LocalBranchShortName, depth: int) -> str:
        """Render a single branch line with indentation."""
        indent = "  " * depth
        marker = " " if branch != self._current_branch else "*"

        line = f"{indent}{marker} {branch}"
        annotation = self.annotations.get(branch)
        if annotation and annotation.formatted_full_text:
            line += f"  {annotation.formatted_full_text}"

        return line

    def _draw_screen(self, *, selected_idx: int, scroll_offset: int,
                     num_lines_drawn: int, is_first_draw: bool) -> int:
        """Draw the branch selection screen using ANSI escape codes."""
        # Move cursor up to the start of our display area (if we've drawn before)
        if not is_first_draw and num_lines_drawn > 0:
            sys.stdout.write(f'{AnsiEscapeCodes.CSI}{num_lines_drawn}A')

        # Clear from cursor to end of screen (only if not first draw)
        if not is_first_draw:
            sys.stdout.write(AnsiEscapeCodes.CLEAR_TO_END)

        # Header
        header_text = ("Select branch (↑/↓: prev/next, Shift+↑/↓: first/last, ←: parent, →: child, "
                       "Enter or Space: checkout, q or Ctrl+C: quit)")
        sys.stdout.write(bold(header_text) + '\n')

        # Adjust scroll offset if needed
        visible_lines = min(self._max_visible_branches, len(self._managed_branches_with_depths))
        if selected_idx < scroll_offset:
            scroll_offset = selected_idx
        elif selected_idx >= scroll_offset + visible_lines:
            scroll_offset = selected_idx - visible_lines + 1

        # Draw branches
        for i in range(visible_lines):
            branch_idx = scroll_offset + i
            branch, depth = self._managed_branches_with_depths[branch_idx]
            line = self._render_branch_line(branch, depth)

            if branch_idx == selected_idx:
                # Highlight selected line (inverse video)
                sys.stdout.write(f'{AnsiEscapeCodes.REVERSE_VIDEO}{line}{AnsiEscapeCodes.ENDC}\n')
            else:
                sys.stdout.write(f'{line}\n')

        sys.stdout.flush()
        return scroll_offset

    def _get_stdin_fd(self) -> int:  # pragma: no cover; always mocked in tests
        return sys.stdin.fileno()

    def _read_stdin(self, n: int) -> str:  # pragma: no cover; always mocked in tests
        return sys.stdin.read(n)

    def _getch(self) -> str:
        """Read a single character from stdin without echo."""
        fd = self._get_stdin_fd()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = self._read_stdin(1)
            # Handle escape sequences for arrow keys
            if ch == AnsiEscapeCodes.ESCAPE:
                # Read the next character
                ch2 = self._read_stdin(1)
                if ch2 == '[':
                    ch3 = self._read_stdin(1)
                    # Check for Shift+arrow keys (e.g., \033[1;2A for Shift+Up)
                    if ch3 == '1':
                        ch4 = self._read_stdin(1)  # Should be ';'
                        ch5 = self._read_stdin(1)  # Should be '2'
                        ch6 = self._read_stdin(1)  # Should be 'A' or 'B'
                        return AnsiEscapeCodes.CSI + ch3 + ch4 + ch5 + ch6
                    return AnsiEscapeCodes.CSI + ch3
                return ch + ch2
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def go_interactive(self) -> Optional[LocalBranchShortName]:
        """
        Launch interactive branch selection interface.
        Returns the selected branch or None if cancelled.
        """
        if termios is None or tty is None:
            raise UnexpectedMacheteException("Interactive mode is not supported on Windows yet")

        # Get flat list of branches with depths from already-parsed state
        self._managed_branches_with_depths = self._get_branch_list_with_depths()

        self._current_branch = self._git.get_current_branch()

        # Determine maximum visible branches from terminal height
        self._max_visible_branches = self._get_max_visible_branches()

        # Find initial selection (current branch)
        selected_idx = index_or_none(self.managed_branches, self._current_branch)
        if selected_idx is None:
            selected_idx = 0
            warn(f"current branch {self._current_branch} is unmanaged\n")

        scroll_offset = 0
        num_lines_drawn = 0
        is_first_draw = True

        # Hide cursor
        sys.stdout.write(AnsiEscapeCodes.HIDE_CURSOR)
        sys.stdout.flush()

        try:
            while True:
                # Calculate how many lines we'll draw (header + visible branches)
                visible_lines = min(self._max_visible_branches, len(self._managed_branches_with_depths))
                num_lines_drawn = visible_lines + 1  # +1 for header

                scroll_offset = self._draw_screen(
                    selected_idx=selected_idx,
                    scroll_offset=scroll_offset,
                    num_lines_drawn=num_lines_drawn,
                    is_first_draw=is_first_draw
                )
                is_first_draw = False

                # Read key
                key = self._getch()

                if key == AnsiEscapeCodes.KEY_UP:
                    # Wrap around from first to last
                    selected_idx = (selected_idx - 1) % len(self._managed_branches_with_depths)
                elif key == AnsiEscapeCodes.KEY_DOWN:
                    # Wrap around from last to first
                    selected_idx = (selected_idx + 1) % len(self._managed_branches_with_depths)
                elif key == AnsiEscapeCodes.KEY_SHIFT_UP:
                    # Jump to first branch
                    selected_idx = 0
                elif key == AnsiEscapeCodes.KEY_SHIFT_DOWN:
                    # Jump to last branch
                    selected_idx = len(self._managed_branches_with_depths) - 1
                elif key == AnsiEscapeCodes.KEY_LEFT:
                    # Go to parent
                    selected_branch, _ = self._managed_branches_with_depths[selected_idx]
                    parent_branch = self.up_branch_for(selected_branch)
                    if parent_branch:
                        selected_idx = self.managed_branches.index(parent_branch)
                elif key == AnsiEscapeCodes.KEY_RIGHT:
                    # Go to first child
                    selected_branch, _ = self._managed_branches_with_depths[selected_idx]
                    child_branches = self.down_branches_for(selected_branch)
                    if child_branches:
                        selected_idx = self.managed_branches.index(child_branches[0])
                elif key in AnsiEscapeCodes.KEYS_ENTER or key == AnsiEscapeCodes.KEY_SPACE:
                    selected_branch, _ = self._managed_branches_with_depths[selected_idx]
                    return selected_branch
                elif key in ('q', 'Q'):
                    return None
                elif key == AnsiEscapeCodes.KEY_CTRL_C:
                    return None
        finally:
            # Show cursor again and move past our interface
            sys.stdout.write(AnsiEscapeCodes.SHOW_CURSOR)
            sys.stdout.flush()
