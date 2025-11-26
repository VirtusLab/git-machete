import sys
import termios
import tty
from typing import List, Optional, Tuple

from git_machete.client.base import MacheteClient
from git_machete.git_operations import LocalBranchShortName
from git_machete.utils import bold, index_or_none, warn

# ANSI escape sequences for terminal control
ANSI_ESCAPE = '\x1b'
ANSI_CSI = '\x1b['  # Control Sequence Introducer

# Cursor control
ANSI_HIDE_CURSOR = '\x1b[?25l'
ANSI_SHOW_CURSOR = '\x1b[?25h'
ANSI_CLEAR_TO_END = '\x1b[J'  # Clear from cursor to end of screen

# Text styling
ANSI_REVERSE_VIDEO = '\x1b[7m'
ANSI_RESET = '\x1b[0m'

# Arrow key codes
KEY_UP = '\x1b[A'
KEY_DOWN = '\x1b[B'
KEY_RIGHT = '\x1b[C'
KEY_LEFT = '\x1b[D'

# Other keys
KEY_ENTER = ('\r', '\n')
KEY_SPACE = ' '
KEY_CTRL_C = '\x03'


class GoInteractiveMacheteClient(MacheteClient):
    """Client for interactive branch selection using curses."""

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

    def _render_branch_line(self, branch: LocalBranchShortName, depth: int, *, current_branch: LocalBranchShortName) -> str:
        """Render a single branch line with indentation."""
        indent = "  " * depth
        marker = " " if branch != current_branch else "*"

        line = f"{indent}{marker} {branch}"
        annotation = self.annotations.get(branch)
        if annotation and annotation.formatted_full_text:
            line += f"  {annotation.formatted_full_text}"

        return line

    def _draw_screen(self, managed_branches_with_depths: List[Tuple[LocalBranchShortName, int]], *,
                     selected_idx: int, current_branch: LocalBranchShortName, scroll_offset: int,
                     max_visible_branches: int, num_lines_drawn: int, is_first_draw: bool) -> int:
        """Draw the branch selection screen using ANSI escape codes."""
        # Move cursor up to the start of our display area (if we've drawn before)
        if not is_first_draw and num_lines_drawn > 0:
            sys.stdout.write(f'{ANSI_CSI}{num_lines_drawn}A')

        # Clear from cursor to end of screen (only if not first draw)
        if not is_first_draw:
            sys.stdout.write(ANSI_CLEAR_TO_END)

        # Header
        header_text = "Select branch (↑/↓: prev/next, ←: parent, →: child, Enter or Space: checkout, q or Ctrl+C: quit)"
        sys.stdout.write(bold(header_text) + '\n')

        # Adjust scroll offset if needed
        visible_lines = min(max_visible_branches, len(managed_branches_with_depths))
        if selected_idx < scroll_offset:
            scroll_offset = selected_idx
        elif selected_idx >= scroll_offset + visible_lines:
            scroll_offset = selected_idx - visible_lines + 1

        # Draw branches
        for i in range(visible_lines):
            branch_idx = scroll_offset + i
            if branch_idx >= len(managed_branches_with_depths):
                break

            branch, depth = managed_branches_with_depths[branch_idx]
            line = self._render_branch_line(branch, depth, current_branch=current_branch)

            if branch_idx == selected_idx:
                # Highlight selected line (inverse video)
                sys.stdout.write(f'{ANSI_REVERSE_VIDEO}{line}{ANSI_RESET}\n')
            else:
                sys.stdout.write(f'{line}\n')

        sys.stdout.flush()
        return scroll_offset

    def _getch(self) -> str:
        """Read a single character from stdin without echo."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            # Handle escape sequences for arrow keys
            if ch == ANSI_ESCAPE:
                # Read the next two characters
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    return ANSI_CSI + ch3
                return ch + ch2
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _run_interactive_interface(self, managed_branches_with_depths: List[Tuple[LocalBranchShortName, int]],
                                   current_branch: LocalBranchShortName) -> Optional[LocalBranchShortName]:
        """Run the interactive interface and return the selected branch or None."""
        # Find initial selection (current branch)
        selected_idx = index_or_none(self.managed_branches, current_branch)
        if selected_idx is None:
            selected_idx = 0
            warn(f"current branch {current_branch} is unmanaged")

        max_visible_branches = 15  # Maximum number of branches to show at once
        scroll_offset = 0
        num_lines_drawn = 0
        is_first_draw = True

        # Hide cursor
        sys.stdout.write(ANSI_HIDE_CURSOR)
        sys.stdout.flush()

        try:
            while True:
                # Calculate how many lines we'll draw (header + visible branches)
                visible_lines = min(max_visible_branches, len(managed_branches_with_depths))
                num_lines_drawn = visible_lines + 1  # +1 for header

                scroll_offset = self._draw_screen(
                    managed_branches_with_depths,
                    selected_idx=selected_idx,
                    current_branch=current_branch,
                    scroll_offset=scroll_offset,
                    max_visible_branches=max_visible_branches,
                    num_lines_drawn=num_lines_drawn,
                    is_first_draw=is_first_draw
                )
                is_first_draw = False

                # Read key
                key = self._getch()

                if key == KEY_UP:
                    # Wrap around from first to last
                    selected_idx = (selected_idx - 1) % len(managed_branches_with_depths)
                elif key == KEY_DOWN:
                    # Wrap around from last to first
                    selected_idx = (selected_idx + 1) % len(managed_branches_with_depths)
                elif key == KEY_LEFT:
                    # Go to parent
                    selected_branch, _ = managed_branches_with_depths[selected_idx]
                    parent_branch = self.up_branch_for(selected_branch)
                    if parent_branch:
                        parent_idx = index_or_none(self.managed_branches, parent_branch)
                        if parent_idx is not None:
                            selected_idx = parent_idx
                elif key == KEY_RIGHT:
                    # Go to first child
                    selected_branch, _ = managed_branches_with_depths[selected_idx]
                    child_branches = self.down_branches_for(selected_branch)
                    if child_branches:
                        first_child = child_branches[0]
                        child_idx = index_or_none(self.managed_branches, first_child)
                        if child_idx is not None:
                            selected_idx = child_idx
                elif key in KEY_ENTER or key == KEY_SPACE:
                    selected_branch, _ = managed_branches_with_depths[selected_idx]
                    return selected_branch
                elif key in ('q', 'Q'):
                    return None
                elif key == KEY_CTRL_C:
                    return None
        finally:
            # Show cursor again and move past our interface
            sys.stdout.write(ANSI_SHOW_CURSOR)
            sys.stdout.flush()

    def go_interactive(self) -> Optional[LocalBranchShortName]:
        """
        Launch interactive branch selection interface.
        Returns the selected branch or None if cancelled.
        """
        current_branch = self._git.get_current_branch()

        # Get flat list of branches with depths from already-parsed state
        managed_branches_with_depths = self._get_branch_list_with_depths()

        try:
            selected_branch = self._run_interactive_interface(managed_branches_with_depths, current_branch)

            if selected_branch:
                return LocalBranchShortName.of(selected_branch)
            return None
        except KeyboardInterrupt:
            # Make sure cursor is visible
            sys.stdout.write(ANSI_SHOW_CURSOR)
            sys.stdout.flush()
            return None
