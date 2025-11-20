import os

import pexpect

from .mockers import rewrite_branch_layout_file
from .mockers_git_repository import commit, create_repo, new_branch


class TestGoInteractive:
    """Tests for the interactive branch selection interface."""

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
        child = pexpect.spawn("git machete go", timeout=5)

        try:
            # Wait for the interface to appear
            child.expect("Select branch")

            # develop should be initially selected (marked with *)
            child.expect(r"\* develop")

            # Press down arrow to select feature-1
            child.send("\x1b[B")  # Down arrow
            child.expect(r"\* feature-1")

            # Press up arrow to go back to develop
            child.send("\x1b[A")  # Up arrow
            child.expect(r"\* develop")

            # Press q to quit
            child.send("q")
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

        child = pexpect.spawn("git machete go", timeout=5)

        try:
            child.expect("Select branch")
            child.expect(r"\* feature-1")

            # Press left arrow to go to parent (develop)
            child.send("\x1b[D")  # Left arrow
            child.expect(r"\* develop")

            # Press q to quit
            child.send("q")
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

        child = pexpect.spawn("git machete go", timeout=5)

        try:
            child.expect("Select branch")
            child.expect(r"\* develop")

            # Press right arrow to go to first child (feature-1)
            child.send("\x1b[C")  # Right arrow
            child.expect(r"\* feature-1")

            # Press q to quit
            child.send("q")
            child.expect(pexpect.EOF)
        finally:
            child.close()

    def test_go_interactive_enter_checkout(self) -> None:
        """Test that pressing Enter checks out the selected branch."""
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

        child = pexpect.spawn("git machete go", timeout=5)

        try:
            child.expect("Select branch")
            child.expect(r"\* develop")

            # Press down arrow to select feature-1
            child.send("\x1b[B")  # Down arrow
            child.expect(r"\* feature-1")

            # Press Enter to checkout
            child.send("\r")
            child.expect(pexpect.EOF)

            # Verify we're now on feature-1
            current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
            assert current_branch == "feature-1"
        finally:
            child.close()

    def test_go_interactive_quit_with_q(self) -> None:
        """Test that pressing 'q' quits without checking out."""
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

        child = pexpect.spawn("git machete go", timeout=5)

        try:
            child.expect("Select branch")

            # Press down to select develop
            child.send("\x1b[B")  # Down arrow

            # Press q to quit without checking out
            child.send("q")
            child.expect(pexpect.EOF)

            # Verify we're still on the initial branch
            current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
            assert current_branch == initial_branch
        finally:
            child.close()
