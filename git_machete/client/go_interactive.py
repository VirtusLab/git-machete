import sys
import termios
import tty
from typing import Dict, List, Optional, Tuple

from git_machete.client.base import MacheteClient
from git_machete.git_operations import LocalBranchShortName


class BranchNode:
    """Represents a branch node in the tree structure."""
    def __init__(self, name: str, depth: int, parent: Optional['BranchNode'] = None):
        self.name = name
        self.depth = depth
        self.parent = parent
        self.children: List['BranchNode'] = []
        self.annotation: Optional[str] = None

    def add_child(self, child: 'BranchNode') -> None:
        self.children.append(child)


class GoInteractiveMacheteClient(MacheteClient):
    """Client for interactive branch selection using curses."""

    def _parse_machete_file(self) -> Tuple[List[BranchNode], Dict[str, BranchNode]]:
        """Parse the .git/machete file and build a tree structure."""
        nodes: List[BranchNode] = []
        node_by_name: Dict[str, BranchNode] = {}
        stack: List[BranchNode] = []  # Stack to track parent nodes at each depth

        with open(self._branch_layout_file_path) as file:
            lines = [line.rstrip() for line in file.readlines()]

        indent_str: Optional[str] = None

        for line in lines:
            if not line.strip():
                continue

            # Determine indentation
            prefix = ""
            for char in line:
                if char.isspace():
                    prefix += char
                else:
                    break

            # Set indent string from first indented line
            if prefix and indent_str is None:
                indent_str = prefix

            # Calculate depth
            if indent_str:
                depth = len(prefix) // len(indent_str)
            else:
                depth = 0

            # Parse branch name and annotation
            parts = line.strip().split(" ", 1)
            branch_name = parts[0]
            annotation = parts[1] if len(parts) > 1 else None

            # Find parent node
            parent = None
            if depth > 0 and stack:
                # Pop stack until we find the parent at depth-1
                while len(stack) > depth:
                    stack.pop()
                if stack:
                    parent = stack[-1]

            # Create node
            node = BranchNode(branch_name, depth, parent)
            node.annotation = annotation
            node_by_name[branch_name] = node

            # Add to parent's children
            if parent:
                parent.add_child(node)

            # Update stack
            if depth == 0:
                stack = [node]
                nodes.append(node)  # Root nodes
            else:
                while len(stack) > depth:
                    stack.pop()
                stack.append(node)

        return nodes, node_by_name

    def _flatten_tree(self, nodes: List[BranchNode]) -> List[BranchNode]:
        """Flatten the tree structure into a displayable list."""
        result: List[BranchNode] = []

        def add_node_and_children(node: BranchNode) -> None:
            result.append(node)
            for child in node.children:
                add_node_and_children(child)

        for root in nodes:
            add_node_and_children(root)

        return result

    def _render_branch_line(self, node: BranchNode, current_branch: str) -> str:
        """Render a single branch line with indentation."""
        indent = "  " * node.depth
        marker = " " if node.name != current_branch else "*"

        line = f"{indent}{marker} {node.name}"
        if node.annotation:
            line += f" {node.annotation}"

        return line

    def _draw_screen(self, flat_nodes: List[BranchNode],
                    selected_idx: int, current_branch: str, scroll_offset: int,
                    max_visible: int, num_lines_drawn: int, is_first_draw: bool) -> int:
        """Draw the branch selection screen using ANSI escape codes."""
        # Move cursor up to the start of our display area (if we've drawn before)
        if not is_first_draw and num_lines_drawn > 0:
            sys.stdout.write(f'\033[{num_lines_drawn}A')

        # Clear from cursor to end of screen (only if not first draw)
        if not is_first_draw:
            sys.stdout.write('\033[J')

        # Header
        header = "\033[1mSelect branch (↑/↓: prev/next, ←: parent, →: child, Enter: checkout, q or Ctrl+C: quit)\033[0m"
        sys.stdout.write(header + '\n')

        # Adjust scroll offset if needed
        visible_lines = min(max_visible, len(flat_nodes))
        if selected_idx < scroll_offset:
            scroll_offset = selected_idx
        elif selected_idx >= scroll_offset + visible_lines:
            scroll_offset = selected_idx - visible_lines + 1

        # Draw branches
        for i in range(visible_lines):
            node_idx = scroll_offset + i
            if node_idx >= len(flat_nodes):
                break

            node = flat_nodes[node_idx]
            line = self._render_branch_line(node, current_branch)

            if node_idx == selected_idx:
                # Highlight selected line (inverse video)
                sys.stdout.write(f'\033[7m{line}\033[0m\n')
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
            if ch == '\x1b':  # Escape character
                # Read the next two characters
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    return '\x1b[' + ch3
                return ch + ch2
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _run_interactive_interface(self, flat_nodes: List[BranchNode],
                                   current_branch: str, node_by_name: Dict[str, BranchNode]) -> Optional[str]:
        """Run the interactive interface and return the selected branch or None."""
        # Find initial selection (current branch)
        selected_idx = 0
        for i, node in enumerate(flat_nodes):
            if node.name == current_branch:
                selected_idx = i
                break

        max_visible_branches = 15  # Maximum number of branches to show at once
        scroll_offset = 0
        num_lines_drawn = 0
        is_first_draw = True

        # Hide cursor
        sys.stdout.write('\033[?25l')
        sys.stdout.flush()

        try:
            while True:
                # Calculate how many lines we'll draw (header + visible branches)
                visible_lines = min(max_visible_branches, len(flat_nodes))
                num_lines_drawn = visible_lines + 1  # +1 for header

                scroll_offset = self._draw_screen(flat_nodes, selected_idx, current_branch,
                                                  scroll_offset, max_visible_branches,
                                                  num_lines_drawn, is_first_draw)
                is_first_draw = False

                # Read key
                key = self._getch()

                if key == '\x1b[A' and selected_idx > 0:  # Up arrow
                    selected_idx -= 1
                elif key == '\x1b[B' and selected_idx < len(flat_nodes) - 1:  # Down arrow
                    selected_idx += 1
                elif key == '\x1b[D':  # Left arrow - go to parent
                    current_node = flat_nodes[selected_idx]
                    if current_node.parent:
                        for i, node in enumerate(flat_nodes):
                            if node.name == current_node.parent.name:
                                selected_idx = i
                                break
                elif key == '\x1b[C':  # Right arrow - go to first child
                    current_node = flat_nodes[selected_idx]
                    if current_node.children:
                        # Find first child in flat list
                        first_child = current_node.children[0]
                        for i, node in enumerate(flat_nodes):
                            if node.name == first_child.name:
                                selected_idx = i
                                break
                elif key in ('\r', '\n'):  # Enter
                    return flat_nodes[selected_idx].name
                elif key in ('q', 'Q'):  # q or Q to quit
                    return None
                elif key == '\x03':  # Ctrl+C
                    return None
        finally:
            # Show cursor again and move past our interface
            sys.stdout.write('\033[?25h')
            sys.stdout.flush()

    def go_interactive(self) -> Optional[LocalBranchShortName]:
        """
        Launch interactive branch selection interface.
        Returns the selected branch or None if cancelled.
        """
        self.read_branch_layout_file()

        # Check if we have any branches
        if not self.managed_branches:
            return None

        current_branch = self._git.get_current_branch()

        # Parse the machete file
        root_nodes, node_by_name = self._parse_machete_file()
        flat_nodes = self._flatten_tree(root_nodes)

        if not flat_nodes:
            return None

        try:
            selected_branch = self._run_interactive_interface(flat_nodes, current_branch, node_by_name)

            if selected_branch:
                return LocalBranchShortName.of(selected_branch)
            return None
        except KeyboardInterrupt:
            # Make sure cursor is visible
            sys.stdout.write('\033[?25h')
            sys.stdout.flush()
            return None
        except Exception:
            # Make sure cursor is visible
            sys.stdout.write('\033[?25h')
            sys.stdout.flush()
            return None
