import curses
import os
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

    def _draw_screen(self, stdscr: 'curses.window', flat_nodes: List[BranchNode],
                    selected_idx: int, current_branch: str, scroll_offset: int) -> None:
        """Draw the branch selection screen."""
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Header
        header = "git machete go - Interactive Branch Selection"
        stdscr.addstr(0, 0, header[:width-1], curses.A_BOLD)
        stdscr.addstr(1, 0, "=" * min(len(header), width-1))

        # Help text
        help_text = "↑/↓: navigate  ←: parent  Enter: checkout  q/Esc: quit"
        if len(help_text) < width:
            stdscr.addstr(2, 0, help_text, curses.A_DIM)

        # Adjust scroll offset if needed
        visible_lines = height - 5  # Reserve space for header and footer
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
            y_pos = 4 + i

            if node_idx == selected_idx:
                # Highlight selected line
                stdscr.addstr(y_pos, 0, line[:width-1], curses.A_REVERSE)
            else:
                stdscr.addstr(y_pos, 0, line[:width-1])

        # Footer with status
        selected_node = flat_nodes[selected_idx]
        footer = f"Selected: {selected_node.name}"
        if height > 4:
            stdscr.addstr(height - 1, 0, footer[:width-1], curses.A_BOLD)

        stdscr.refresh()
        return scroll_offset

    def _run_curses_interface(self, stdscr: 'curses.window', flat_nodes: List[BranchNode],
                              current_branch: str, node_by_name: Dict[str, BranchNode]) -> Optional[str]:
        """Run the curses interface and return the selected branch or None."""
        # Find initial selection (current branch)
        selected_idx = 0
        for i, node in enumerate(flat_nodes):
            if node.name == current_branch:
                selected_idx = i
                break

        scroll_offset = 0
        curses.curs_set(0)  # Hide cursor

        # Initialize colors if available
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()

        while True:
            scroll_offset = self._draw_screen(stdscr, flat_nodes, selected_idx, current_branch, scroll_offset)

            key = stdscr.getch()

            if key == curses.KEY_UP and selected_idx > 0:
                selected_idx -= 1
            elif key == curses.KEY_DOWN and selected_idx < len(flat_nodes) - 1:
                selected_idx += 1
            elif key == curses.KEY_LEFT:
                # Go to parent
                current_node = flat_nodes[selected_idx]
                if current_node.parent:
                    # Find parent in flat list
                    for i, node in enumerate(flat_nodes):
                        if node.name == current_node.parent.name:
                            selected_idx = i
                            break
            elif key in (ord('\n'), ord('\r'), curses.KEY_ENTER):
                # Select branch
                return flat_nodes[selected_idx].name
            elif key in (ord('q'), ord('Q'), 27):  # q, Q, or Escape
                return None
            elif key == 3:  # Ctrl+C
                return None

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
            selected_branch = curses.wrapper(
                lambda stdscr: self._run_curses_interface(stdscr, flat_nodes, current_branch, node_by_name)
            )

            if selected_branch:
                return LocalBranchShortName.of(selected_branch)
            return None
        except KeyboardInterrupt:
            return None
