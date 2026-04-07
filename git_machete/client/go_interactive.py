import sys
from typing import Optional, Tuple

try:
    import termios
    import tty
except ImportError:  # pragma: no cover; Windows-specific
    # termios and tty are not available on Windows
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]

from git_machete import utils
from git_machete.client.status import (StatusData, StatusFlags,
                                       StatusMacheteClient)
from git_machete.git_operations import LocalBranchShortName
from git_machete.utils import (AnsiInputCodes, BasicTerminalAnsiOutputCodes,
                               FullTerminalAnsiOutputCodes, MacheteException,
                               UnexpectedMacheteException, index_or_none,
                               is_terminal_fully_fledged, print_fmt, warn)

AI = AnsiInputCodes


class GoInteractiveMacheteClient(StatusMacheteClient):
    """Client for interactive branch selection using curses-style interface (implemented without curses, just using ANSI sequences)."""

    MAX_VISIBLE_BRANCHES_DEFAULT = 20
    MAX_VISIBLE_BRANCHES_LOWER = 2
    MAX_VISIBLE_BRANCHES_UPPER = 50

    _status_data: StatusData
    _current_branch: Optional[LocalBranchShortName]
    _max_visible_branches: int
    _ansi_output_codes: FullTerminalAnsiOutputCodes

    def _get_max_visible_branches(self) -> int:
        """Get the maximum number of branches that can be displayed based on terminal height."""
        terminal_height = utils.get_terminal_height()
        if terminal_height is None:
            # Fallback if terminal size cannot be determined (e.g., not a TTY)
            return self.MAX_VISIBLE_BRANCHES_DEFAULT
        # Reserve 1 line for header, plus 1 line for padding
        max_visible_branches = terminal_height - 2
        return max(self.MAX_VISIBLE_BRANCHES_LOWER, min(max_visible_branches, self.MAX_VISIBLE_BRANCHES_UPPER))

    def _draw_screen(self, *, selected_idx: int, scroll_offset: int,
                     num_lines_drawn: int, is_first_draw: bool) -> Tuple[int, int]:
        """Draw the branch selection screen using status-style output (format_status_output).
        Returns (scroll_offset, actual_lines_drawn) so the caller can move the cursor up correctly on next redraw."""
        # Move cursor up to the start of our display area (if we've drawn before)
        if not is_first_draw and num_lines_drawn > 0:
            sys.stdout.write(self._ansi_output_codes.cursor_up(num_lines_drawn))

        # Clear from cursor to end of screen (only if not first draw)
        if not is_first_draw:
            sys.stdout.write(self._ansi_output_codes.CLEAR_TO_END)

        # Header
        header_text = ("Select branch (↑/↓: prev/next, Shift+↑/↓: first/last, ←: parent, →: child, "
                       "Enter or Space: checkout, q or Ctrl+C: quit)")
        print_fmt(f"<b>{header_text}</b>")

        branches = self._status_data.branches_in_display_order
        selected_branch = branches[selected_idx] if 0 <= selected_idx < len(branches) else None
        formatted = self.format_status_output(
            self._status_data,
            selected_branch=selected_branch,
        )
        lines = formatted.result.splitlines()
        num_lines = len(lines)
        visible_lines = min(self._max_visible_branches, num_lines)
        selected_line_idx = formatted.line_for_branch.get(selected_branch, 0) if selected_branch else 0
        if selected_line_idx < scroll_offset:
            scroll_offset = selected_line_idx
        elif selected_line_idx >= scroll_offset + visible_lines:
            scroll_offset = selected_line_idx - visible_lines + 1

        lines_drawn = 1  # header
        end = min(scroll_offset + visible_lines, num_lines)
        for line_idx in range(scroll_offset, end):
            print_fmt(lines[line_idx])
            lines_drawn += 1

        sys.stdout.flush()
        return scroll_offset, lines_drawn

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
            if ch == AI.ESCAPE:
                # Read the next character
                ch2 = self._read_stdin(1)
                if ch2 == '[':
                    ch3 = self._read_stdin(1)
                    # Check for Shift+arrow keys (e.g., \033[1;2A for Shift+Up)
                    if ch3 == '1':
                        ch4 = self._read_stdin(1)  # Should be ';'
                        ch5 = self._read_stdin(1)  # Should be '2'
                        ch6 = self._read_stdin(1)  # Should be 'A' or 'B'
                        return AI.CSI + ch3 + ch4 + ch5 + ch6
                    return AI.CSI + ch3
                return ch + ch2
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def go_interactive(self, *, current_branch: Optional[LocalBranchShortName]) -> Optional[LocalBranchShortName]:
        """
        Launch interactive branch selection interface.
        Returns the selected branch or None if cancelled.
        Status data is computed once at start; only rendering (format_status_output) runs on each redraw.
        """
        if termios is None or tty is None:
            raise UnexpectedMacheteException("Interactive mode is not supported on Windows yet")
        if not utils.is_stdout_a_tty():
            raise MacheteException("Interactive `git machete go` requires stdout to be a TTY.")

        self._current_branch = current_branch
        self._ansi_output_codes = FullTerminalAnsiOutputCodes() if is_terminal_fully_fledged() else BasicTerminalAnsiOutputCodes()
        self._max_visible_branches = self._get_max_visible_branches()

        # Compute status data once (no list-commits in TUI; config same as status)
        flags = StatusFlags(
            maybe_space_before_branch_name=(' ' if self._config.status_extra_space_before_branch_name() else ''),
            opt_list_commits=False,
            opt_list_commits_with_hashes=False,
            opt_squash_merge_detection=self._config.squash_merge_detection(),
        )
        self._status_data = self.compute_status_data(flags=flags)
        branches_ordered = self._status_data.branches_in_display_order

        # Find initial selection (current branch or first branch if detached HEAD)
        if current_branch is not None:
            selected_idx = index_or_none(branches_ordered, self._current_branch)
            if selected_idx is None:
                selected_idx = 0
                warn(f"current branch {self._current_branch} is unmanaged\n")
        else:
            selected_idx = 0

        scroll_offset = 0
        num_lines_drawn = 0
        is_first_draw = True

        # Hide cursor
        sys.stdout.write(self._ansi_output_codes.HIDE_CURSOR)
        sys.stdout.flush()

        branches = self._status_data.branches_in_display_order
        try:
            while True:
                scroll_offset, num_lines_drawn = self._draw_screen(
                    selected_idx=selected_idx,
                    scroll_offset=scroll_offset,
                    num_lines_drawn=num_lines_drawn,
                    is_first_draw=is_first_draw
                )
                is_first_draw = False

                key = self._getch()

                if key == AI.KEY_UP:
                    selected_idx = (selected_idx - 1) % len(branches)
                elif key == AI.KEY_DOWN:
                    selected_idx = (selected_idx + 1) % len(branches)
                elif key == AI.KEY_SHIFT_UP:
                    selected_idx = 0
                elif key == AI.KEY_SHIFT_DOWN:
                    selected_idx = len(branches) - 1
                elif key == AI.KEY_LEFT:
                    selected_branch = branches[selected_idx]
                    parent_branch = self.up_branch_for(selected_branch)
                    if parent_branch is not None:
                        selected_idx = branches.index(parent_branch)
                elif key == AI.KEY_RIGHT:
                    selected_branch = branches[selected_idx]
                    child_branches = self.down_branches_for(selected_branch)
                    if child_branches:
                        selected_idx = branches.index(child_branches[0])
                elif key in AI.KEYS_ENTER or key == AI.KEY_SPACE:
                    return branches[selected_idx]
                elif key in ('q', 'Q'):
                    return None
                elif key == AI.KEY_CTRL_C:
                    return None
        finally:
            # Show cursor again and move past our interface
            sys.stdout.write(self._ansi_output_codes.SHOW_CURSOR)
            sys.stdout.flush()
