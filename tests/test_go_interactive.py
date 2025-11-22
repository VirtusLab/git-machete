import os
import time

import pexpect
import pytest

from .mockers import rewrite_branch_layout_file
from .mockers_git_repository import commit, create_repo, new_branch

# Use git-machete from tox environment if available, otherwise fall back to PATH
# GIT_MACHETE_EXEC is set by tox.ini to point to the installed executable
GIT_MACHETE_CMD = os.environ.get('GIT_MACHETE_EXEC', 'git machete')


class TestGoInteractive:
    def test_go_interactive_navigation_up_down(self) -> None:
        """Test that up/down arrow keys navigate through branches."""
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        new_branch("feature-1")
        commit()

        body: str = \
            """
            master
                develop
                    feature-1
            """
        rewrite_branch_layout_file(body)

        # Start on develop
        os.system("git checkout develop")

        # Run git machete go interactively
        child = pexpect.spawn(f"{GIT_MACHETE_CMD} go", timeout=5)

        try:
            # Wait for the interface to appear
            child.expect("Select branch")

            # develop should be initially selected (marked with *)
            child.expect("develop")

            # Press down arrow to select feature-1 (it becomes highlighted but * stays on develop)
            child.send("\x1b[B")  # Down arrow
            # Just check that feature-1 appears (it will be highlighted with reverse video)
            child.expect("feature-1")

            # Press up arrow to go back to develop
            child.send("\x1b[A")  # Up arrow
            child.expect("develop")

            # Use Ctrl+C to quit
            child.send("\x03")  # Ctrl+C
            child.expect(pexpect.EOF)
        finally:
            child.close()

    def test_go_interactive_left_arrow_parent(self) -> None:
        """Test that left arrow navigates to parent branch."""
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        new_branch("feature-1")
        commit()

        body: str = \
            """
            master
                develop
                    feature-1
            """
        rewrite_branch_layout_file(body)

        # Start on feature-1
        os.system("git checkout feature-1")

        child = pexpect.spawn(f"{GIT_MACHETE_CMD} go", timeout=5)

        try:
            child.expect("Select branch")
            child.expect("feature-1")

            # Press left arrow to go to parent (develop)
            child.send("\x1b[D")  # Left arrow
            # develop should now be highlighted
            child.expect("develop")

            # Use Ctrl+C to quit
            child.send("\x03")  # Ctrl+C
            child.expect(pexpect.EOF)
        finally:
            child.close()

    def test_go_interactive_right_arrow_child(self) -> None:
        """Test that right arrow navigates to first child branch."""
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        new_branch("feature-1")
        commit()

        body: str = \
            """
            master
                develop
                    feature-1
            """
        rewrite_branch_layout_file(body)

        # Start on develop
        os.system("git checkout develop")

        child = pexpect.spawn(f"{GIT_MACHETE_CMD} go", timeout=5)

        try:
            child.expect("Select branch")
            child.expect("develop")

            # Press right arrow to go to first child (feature-1)
            child.send("\x1b[C")  # Right arrow
            child.expect("feature-1")

            # Use Ctrl+C to quit (more reliable than 'q' in pexpect)
            child.send("\x03")  # Ctrl+C
            child.expect(pexpect.EOF)
        finally:
            child.close()

    def test_go_interactive_quit_without_checkout(self) -> None:
        """Test that pressing Ctrl+C quits without checking out."""
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()

        body: str = \
            """
            master
                develop
            """
        rewrite_branch_layout_file(body)

        # Start on master
        os.system("git checkout master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()

        child = pexpect.spawn(f"{GIT_MACHETE_CMD} go", timeout=5)

        try:
            child.expect("Select branch")

            # Press down to select develop
            child.send("\x1b[B")  # Down arrow

            # Press Ctrl+C to quit without checking out
            child.send("\x03")  # Ctrl+C
            child.expect(pexpect.EOF)

            # Verify we're still on the initial branch
            current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
            assert current_branch == initial_branch
        finally:
            child.close()
