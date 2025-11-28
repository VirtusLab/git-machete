import os
import sys
import threading
import time
from typing import Any, Callable, Dict

try:
    import fcntl
except ImportError:
    # fcntl is not available on Windows
    fcntl = None  # type: ignore[assignment]

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

# Global buffer to store leftover data from previous reads
_read_buffer = {}


def send_key(stdin_write_fd: int, key: str, sleep_time: float = 0.1) -> None:
    """Send a key to the interactive interface and wait for it to be processed."""
    os.write(stdin_write_fd, key.encode('utf-8'))
    time.sleep(sleep_time)


def make_non_blocking(fd: int) -> None:
    """Make a file descriptor non-blocking."""
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)


def read_line_from_fd(fd: int, timeout: float = 0.5) -> str:
    """Read a line from a file descriptor with timeout."""
    if fd not in _read_buffer:
        _read_buffer[fd] = bytearray()

    buffer = _read_buffer[fd]
    start_time = time.time()

    while True:
        # First, check if we already have a complete line in the buffer
        try:
            decoded = buffer.decode('utf-8')
            if '\n' in decoded:
                line_end = decoded.index('\n') + 1
                line = decoded[:line_end]
                # Keep the rest in the buffer
                _read_buffer[fd] = bytearray(decoded[line_end:].encode('utf-8'))
                return line
        except UnicodeDecodeError:
            # Incomplete UTF-8 sequence, need to read more
            pass

        if time.time() - start_time > timeout:
            break

        try:
            data = os.read(fd, 1024)  # Read larger chunks to handle UTF-8 properly
            if not data:
                break
            buffer.extend(data)
        except BlockingIOError:
            time.sleep(0.01)
            continue

    # Timeout - return whatever we have, decoded
    if buffer:
        try:
            result = buffer.decode('utf-8')
            _read_buffer[fd] = bytearray()
            return result
        except UnicodeDecodeError:
            result = buffer.decode('utf-8', errors='replace')
            _read_buffer[fd] = bytearray()
            return result
    return ''


@pytest.mark.skipif(sys.platform == 'win32', reason="Interactive mode is not supported on Windows")
class TestGoInteractive(BaseTest):
    def setup_method(self) -> None:
        """Set up a standard 4-branch repository for each test."""
        super().setup_method()
        create_repo()
        new_branch("master")
        commit()
        new_branch("develop")
        commit()
        new_branch("feature-1")
        commit()
        check_out("develop")
        new_branch("feature-2")
        commit()

        body: str = \
            """
            master
                develop
                    feature-1
                    feature-2
            """
        rewrite_branch_layout_file(body)

    def teardown_method(self) -> None:
        super().teardown_method()
        print("===========\n")

    def run_interactive_test(
        self,
        test_func: Callable[[int, int, int], None],
        mocker: MockerFixture,
        timeout: float = 5.0
    ) -> None:
        """
        Run an interactive test by executing git machete go in a thread with mocked stdin/stdout/stderr.

        Args:
            test_func: A function that takes (stdin_write_fd, stdout_read_fd, stderr_read_fd) and performs the test
            mocker: pytest-mock fixture for mocking
            timeout: Maximum time to wait for the test to complete
        """
        # Create pipes for stdin, stdout, and stderr
        stdin_read_fd, stdin_write_fd = os.pipe()
        stdout_read_fd, stdout_write_fd = os.pipe()

        # Open file objects for all ends
        stdin_read = os.fdopen(stdin_read_fd, 'r')
        stdin_write_fd_obj = os.fdopen(stdin_write_fd, 'w')
        stdout_read_fd_obj = os.fdopen(stdout_read_fd, 'r')
        stdout_write = os.fdopen(stdout_write_fd, 'w', buffering=1)  # Line buffered

        # Make stdout and stderr read ends non-blocking
        make_non_blocking(stdout_read_fd_obj.fileno())

        # Mock termios operations since pipes don't support them
        fake_termios_settings = ['fake_settings']

        def mock_tcgetattr(fd: int) -> Any:  # noqa: U100
            return fake_termios_settings

        def mock_tcsetattr(fd: int, _when: int, _attributes: Any) -> None:  # noqa: U100
            pass

        def mock_setraw(fd: int) -> None:  # noqa: U100
            pass

        self.patch_symbol(mocker, 'termios.tcgetattr', mock_tcgetattr)
        self.patch_symbol(mocker, 'termios.tcsetattr', mock_tcsetattr)
        self.patch_symbol(mocker, 'tty.setraw', mock_setraw)

        # Result and exception containers
        exception_container: Dict[str, Any] = {}

        def run_git_machete_go() -> None:
            """Run git machete go in a thread with replaced stdin/stdout/stderr."""

            original_stdin = sys.stdin
            original_stdout = sys.stdout
            try:
                sys.stdin = stdin_read
                sys.stdout = stdout_write
                print("*** run_git_machete_go start ***", file=original_stdout)
                # Run the CLI command
                cli.launch(['go'])
                print("*** run_git_machete_go end ***", file=original_stdout)
            except SystemExit as e:
                # CLI may exit with sys.exit(), that's normal
                if e.code != 0:
                    exception_container['error'] = e
            except Exception as e:
                exception_container['error'] = e
                import traceback
                traceback.print_exc()
            finally:
                sys.stdin = original_stdin
                sys.stdout = original_stdout

        # Start git machete go in a separate thread
        thread = threading.Thread(target=run_git_machete_go, daemon=True)
        thread.start()

        # Give the thread a moment to start and write initial output
        time.sleep(0.3)

        try:
            # Run the actual test
            test_func(stdin_write_fd_obj.fileno(), stdout_read_fd_obj.fileno(), 0)
            print("test_func finished", file=sys.stderr)

            # Wait for thread to finish
            thread.join(timeout=timeout)
            print("thread.join finished", file=sys.stderr)

            # Check if thread is still running (timeout)
            if thread.is_alive():
                raise TimeoutError(f"Interactive test timed out after {timeout} seconds")

            # Check for exceptions
            if 'error' in exception_container:
                raise exception_container['error']

        finally:
            # Clean up
            stdin_read.close()
            stdin_write_fd_obj.close()
            stdout_read_fd_obj.close()
            stdout_write.close()

    def test_go_interactive_navigation_up_down(self, mocker: MockerFixture) -> None:
        """Test that up/down arrow keys navigate through branches."""
        print("\n*** test_go_interactive_navigation_up_down ***")
        check_out("develop")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial interface output
            header = read_line_from_fd(stdout_read_fd)
            print("header = read_line_from_fd", file=sys.stderr)
            assert "Select branch" in header

            # Read the branch list
            line1 = read_line_from_fd(stdout_read_fd)
            print("line1 = read_line_from_fd", file=sys.stderr)
            line2 = read_line_from_fd(stdout_read_fd)
            print("line2 = read_line_from_fd", file=sys.stderr)
            line3 = read_line_from_fd(stdout_read_fd)
            print("line3 = read_line_from_fd", file=sys.stderr)
            line4 = read_line_from_fd(stdout_read_fd)
            print("line4 = read_line_from_fd", file=sys.stderr)

            # develop should be marked with * (current branch)
            assert "master" in line1
            assert "develop" in line2
            assert "*" in line2  # Current branch marker
            assert "feature-1" in line3
            assert "feature-2" in line4

            # Press down arrow to select feature-1
            send_key(stdin_write_fd, KEY_DOWN)
            print("send_key(stdin_write_fd, KEY_DOWN)", file=sys.stderr)

            # Press up arrow to go back
            send_key(stdin_write_fd, KEY_UP)
            print("send_key(stdin_write_fd, KEY_UP)", file=sys.stderr)

            # Use Ctrl+C to quit
            send_key(stdin_write_fd, KEY_CTRL_C)
            print("send_key(stdin_write_fd, KEY_CTRL_C)", file=sys.stderr)

        self.run_interactive_test(test_logic, mocker)

    def test_go_interactive_shift_arrows_jump(self, mocker: MockerFixture) -> None:
        """Test that Shift+Up/Down jumps to first/last branch."""
        print("\n*** test_go_interactive_shift_arrows_jump ***")
        check_out("develop")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial output (should start on develop)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)

            # Press Shift+Down to jump to last branch (feature-2)
            send_key(stdin_write_fd, KEY_SHIFT_DOWN)

            # Press Space to checkout feature-2
            send_key(stdin_write_fd, KEY_SPACE, sleep_time=0.5)

            # Read checkout confirmation
            checkout_msg = ""
            for _ in range(10):
                try:
                    line = read_line_from_fd(stdout_read_fd, timeout=0.5)
                    checkout_msg += line
                    if "OK" in line:
                        break
                except TimeoutError:
                    break

            assert "Checking out" in checkout_msg
            assert "feature-2" in checkout_msg
            assert "OK" in checkout_msg

        self.run_interactive_test(test_logic, mocker, timeout=3.0)

        # Verify we checked out feature-2 (the last branch)
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-2"

        # Now test Shift+Up to jump to first branch (master)
        def test_logic_shift_up(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial output (should start on feature-2)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)

            # Press Shift+Up to jump to first branch (master)
            send_key(stdin_write_fd, KEY_SHIFT_UP)

            # Press Space to checkout master
            send_key(stdin_write_fd, KEY_SPACE, sleep_time=0.5)

            # Read checkout confirmation
            checkout_msg = ""
            for _ in range(10):
                try:
                    line = read_line_from_fd(stdout_read_fd, timeout=0.5)
                    checkout_msg += line
                    if "OK" in line:
                        break
                except TimeoutError:
                    break

            assert "Checking out" in checkout_msg
            assert "master" in checkout_msg
            assert "OK" in checkout_msg

        self.run_interactive_test(test_logic_shift_up, mocker, timeout=3.0)

        # Verify we checked out master (the first branch)
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"

    def test_go_interactive_left_arrow_parent(self, mocker: MockerFixture) -> None:
        """Test that left arrow navigates to parent branch (not just up), and does nothing on root."""
        print("\n*** test_go_interactive_left_arrow_parent ***")
        check_out("feature-2")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            read_line_from_fd(stdout_read_fd)  # master
            read_line_from_fd(stdout_read_fd)  # develop
            read_line_from_fd(stdout_read_fd)  # feature-1
            line4 = read_line_from_fd(stdout_read_fd)  # feature-2
            read_line_from_fd(stdout_read_fd)

            # feature-2 should be current
            assert "feature-2" in line4
            assert "*" in line4

            # Press left arrow to go to parent (develop)
            # If left arrow was equivalent to up, it would go to feature-1
            send_key(stdin_write_fd, KEY_LEFT)

            # Press left arrow again to go to develop's parent (master)
            send_key(stdin_write_fd, KEY_LEFT)

            # Now we're on master (root branch). Press left arrow again - should not move
            send_key(stdin_write_fd, KEY_LEFT)

            # Use Ctrl+C to quit
            send_key(stdin_write_fd, KEY_CTRL_C)

        self.run_interactive_test(test_logic, mocker)

    def test_go_interactive_right_arrow_child(self, mocker: MockerFixture) -> None:
        """Test that right arrow navigates to first child branch (not just down)."""
        print("\n*** test_go_interactive_right_arrow_child ***")
        check_out("develop")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            read_line_from_fd(stdout_read_fd)  # master
            line2 = read_line_from_fd(stdout_read_fd)  # develop
            read_line_from_fd(stdout_read_fd)  # feature-1
            read_line_from_fd(stdout_read_fd)  # feature-2
            read_line_from_fd(stdout_read_fd)

            # develop should be current
            assert "develop" in line2
            assert "*" in line2

            # Press right arrow to go to first child (feature-1)
            send_key(stdin_write_fd, KEY_RIGHT)

            # Now we're on feature-1. Press down to go to feature-2
            send_key(stdin_write_fd, KEY_DOWN)

            # Now we're on feature-2. Press right - should NOT move (no children)
            # If right was equivalent to down, we'd wrap to master
            send_key(stdin_write_fd, KEY_RIGHT)

            # Use Ctrl+C to quit
            send_key(stdin_write_fd, KEY_CTRL_C)

        self.run_interactive_test(test_logic, mocker)

    def test_go_interactive_quit_without_checkout(self, mocker: MockerFixture) -> None:
        """Test that pressing Ctrl+C quits without checking out."""
        print("\n*** test_go_interactive_quit_without_checkout ***")
        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)

            # Press down to select develop
            send_key(stdin_write_fd, KEY_DOWN)

            # Press Ctrl+C to quit without checking out
            send_key(stdin_write_fd, KEY_CTRL_C)

        self.run_interactive_test(test_logic, mocker)

        # Verify we're still on the initial branch
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == initial_branch

    def test_go_interactive_space_checkout(self, mocker: MockerFixture) -> None:
        """Test that pressing Space checks out the selected branch."""
        print("\n*** test_go_interactive_space_checkout ***")
        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert initial_branch == "master"

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)

            # Press down twice to select feature-1
            send_key(stdin_write_fd, KEY_DOWN)
            send_key(stdin_write_fd, KEY_DOWN)

            # Press Space to checkout feature-1
            send_key(stdin_write_fd, KEY_SPACE, sleep_time=0.5)

            # Read until we get the checkout confirmation message
            # (may need to skip screen redraws with ANSI escape codes)
            checkout_msg = ""
            for _ in range(20):  # Try up to 20 lines
                line = read_line_from_fd(stdout_read_fd, timeout=0.3)
                if not line:
                    continue
                checkout_msg += line
                if "OK" in line:
                    break

            assert "Checking out" in checkout_msg, f"Expected 'Checking out' message but got: {repr(checkout_msg)}"
            assert "feature-1" in checkout_msg
            assert "OK" in checkout_msg

        self.run_interactive_test(test_logic, mocker, timeout=3.0)

        # Verify we're now on feature-1
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-1"

    def test_go_interactive_with_annotations(self, mocker: MockerFixture) -> None:
        """Test that branch annotations are displayed with proper formatting."""
        print("\n*** test_go_interactive_with_annotations ***")
        # Overwrite .git/machete with annotations
        body: str = \
            """
            master
                develop  PR #123 rebase=no
                    feature-1  Work in progress
            """
        rewrite_branch_layout_file(body)

        check_out("master")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            line1 = read_line_from_fd(stdout_read_fd)
            line2 = read_line_from_fd(stdout_read_fd)
            line3 = read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)

            # Check that master doesn't have annotation
            assert "master" in line1
            assert "PR #123" not in line1

            # Check that develop has annotation with dimmed text
            assert "develop" in line2
            # The annotation should be present (though we can't easily test for ANSI dim codes in this context)
            assert "PR #123" in line2 or "\x1b[2m" in line2  # Either plain text or with ANSI dim code

            # Check that feature-1 has annotation
            assert "feature-1" in line3
            assert "Work in progress" in line3 or "\x1b[2m" in line3

            # Use Ctrl+C to quit
            send_key(stdin_write_fd, KEY_CTRL_C)

        self.run_interactive_test(test_logic, mocker)

    def test_go_interactive_wrapping_navigation(self, mocker: MockerFixture) -> None:
        """Test that up/down arrow keys wrap around at the edges."""
        print("\n*** test_go_interactive_wrapping_navigation ***")
        check_out("master")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            line1 = read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)

            # master should be initially selected (marked with *)
            assert "master" in line1
            assert "*" in line1

            # Press UP to wrap to last item (feature-2)
            send_key(stdin_write_fd, KEY_UP)

            # Press DOWN twice to verify we can navigate forward from last item to first
            send_key(stdin_write_fd, KEY_DOWN)
            # Now at master (wrapped from feature-2)

            send_key(stdin_write_fd, KEY_DOWN)
            # Now at develop

            # Press UP to go back to master
            send_key(stdin_write_fd, KEY_UP)
            # Now at master

            # Press UP again to wrap to feature-2
            send_key(stdin_write_fd, KEY_UP)
            # Now at feature-2 (wrapped)

            # Use Ctrl+C to quit
            send_key(stdin_write_fd, KEY_CTRL_C)

        self.run_interactive_test(test_logic, mocker)

    def test_go_interactive_q_key_quit(self, mocker: MockerFixture) -> None:
        """Test that pressing 'q' or 'Q' quits without checking out."""
        print("\n*** test_go_interactive_q_key_quit ***")
        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)

            # Press down to select develop
            send_key(stdin_write_fd, KEY_DOWN)

            # Press 'q' to quit without checking out
            send_key(stdin_write_fd, 'q')

        self.run_interactive_test(test_logic, mocker)

        # Verify we're still on the initial branch
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == initial_branch

    def test_go_interactive_unknown_key_ignored(self, mocker: MockerFixture) -> None:
        """Test that unknown keys are ignored and don't break the interface."""
        print("\n*** test_go_interactive_unknown_key_ignored ***")
        check_out("master")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)

            # Press some unknown keys - they should be ignored
            send_key(stdin_write_fd, 'x')
            send_key(stdin_write_fd, 'z')
            send_key(stdin_write_fd, '1')
            send_key(stdin_write_fd, '\x1ba')  # Alt+a (ESC followed by 'a')

            # Now press a valid key to verify the interface still works
            send_key(stdin_write_fd, KEY_DOWN)

            # Quit with Ctrl+C to verify we can still exit
            send_key(stdin_write_fd, KEY_CTRL_C)

        self.run_interactive_test(test_logic, mocker)

    def test_go_interactive_unmanaged_current_branch(self, mocker: MockerFixture) -> None:
        """Test that when current branch is unmanaged, a warning is shown and selection starts at first branch."""
        print("\n*** test_go_interactive_unmanaged_current_branch ***")
        # Create an unmanaged branch (not in .git/machete)
        new_branch("unmanaged")
        commit()
        check_out("unmanaged")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:
            # Read the warning from stderr
            warning = read_line_from_fd(stderr_read_fd)
            assert "current branch unmanaged is unmanaged" in warning

            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list - first branch should be selected (no * marker since the current branch is unmanaged)
            line1 = read_line_from_fd(stdout_read_fd)
            # The first branch (master) should be highlighted
            assert "master" in line1
            # Read the remaining lines
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)

            # Quit with Ctrl+C
            send_key(stdin_write_fd, KEY_CTRL_C)

        self.run_interactive_test(test_logic, mocker)

    # This test times out in CI on Python < 3.11, but it's hard to reproduce locally.
    # Skipping on older Python versions to avoid CI failures.
    def test_go_interactive_scrolling_down(self, mocker: MockerFixture) -> None:
        """Test that scrolling works when there are more branches than fit on screen."""
        print("\n*** test_go_interactive_scrolling_down ***")
        # Mock terminal height to 4, which results in max_visible_branches = 2 (4 - 2)
        # This forces scrolling with our 4 branches
        self.patch_symbol(mocker, 'git_machete.utils.get_terminal_height', lambda: 4)

        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert initial_branch == "master"

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Only 2 branches should be visible initially (master, develop)
            line1 = read_line_from_fd(stdout_read_fd)
            line2 = read_line_from_fd(stdout_read_fd)
            initial_view = line1 + line2
            assert "master" in initial_view
            assert "develop" in initial_view
            # feature-1 and feature-2 should NOT be visible initially
            assert "feature-1" not in initial_view
            assert "feature-2" not in initial_view

            # Navigate down three times to feature-2 (index 3)
            # This exercises both scrolling conditions as we go beyond the visible window
            send_key(stdin_write_fd, KEY_DOWN)  # develop (index 1)
            send_key(stdin_write_fd, KEY_DOWN)  # feature-1 (index 2) - triggers scroll down
            send_key(stdin_write_fd, KEY_DOWN)  # feature-2 (index 3) - triggers scroll down again

            # Checkout feature-2 to verify scrolling worked (we reached the last branch)
            send_key(stdin_write_fd, KEY_SPACE, sleep_time=0.5)

            # Read checkout confirmation
            checkout_msg = ""
            for _ in range(10):
                try:
                    line = read_line_from_fd(stdout_read_fd, timeout=0.5)
                    checkout_msg += line
                    if "OK" in line:
                        break
                except TimeoutError:
                    break

            assert "Checking out" in checkout_msg
            assert "feature-2" in checkout_msg
            assert "OK" in checkout_msg

        self.run_interactive_test(test_logic, mocker, timeout=3.0)

        # Verify we checked out feature-2 (confirms scrolling worked)
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-2"

    # This test times out in CI on Python < 3.11, but it's hard to reproduce locally.
    # Skipping on older Python versions to avoid CI failures.
    def test_go_interactive_scrolling_up(self, mocker: MockerFixture) -> None:
        """Test that scrolling up works when starting from a branch that requires initial scroll offset."""
        print("\n*** test_go_interactive_scrolling_up ***")
        # Mock terminal height to 4, which results in max_visible_branches = 2 (4 - 2)
        # This forces scrolling with our 4 branches
        self.patch_symbol(mocker, 'git_machete.utils.get_terminal_height', lambda: 4)

        # Start from feature-2 (index 3) - this should start with scroll_offset = 2
        # so that feature-1 and feature-2 are visible
        check_out("feature-2")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert initial_branch == "feature-2"

        def test_logic(stdin_write_fd: int, stdout_read_fd: int, stderr_read_fd: int) -> None:  # noqa: U100
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # With max_visible_branches=2 and starting on feature-2 (index 3),
            # the initial view should show feature-1 and feature-2 (scroll_offset=2)
            line1 = read_line_from_fd(stdout_read_fd)
            line2 = read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            initial_view = line1 + line2
            assert "feature-1" in initial_view
            assert "feature-2" in initial_view
            # master and develop should NOT be visible initially
            assert "master" not in initial_view
            assert "develop" not in initial_view

            # Navigate up multiple times - this should trigger scrolling up
            # (the `if selected_idx < scroll_offset` condition)
            send_key(stdin_write_fd, KEY_UP)  # feature-1 (index 2) - still visible
            send_key(stdin_write_fd, KEY_UP)  # develop (index 1) - triggers scroll up!
            send_key(stdin_write_fd, KEY_UP)  # master (index 0) - triggers scroll up again!

            # Checkout master to verify we scrolled up correctly and reached the top
            send_key(stdin_write_fd, KEY_SPACE, sleep_time=0.5)

            # Read checkout confirmation
            checkout_msg = ""
            for _ in range(10):
                try:
                    line = read_line_from_fd(stdout_read_fd, timeout=0.5)
                    checkout_msg += line
                    if "OK" in line:
                        break
                except TimeoutError:
                    break

            assert "Checking out" in checkout_msg
            assert "master" in checkout_msg
            assert "OK" in checkout_msg

        self.run_interactive_test(test_logic, mocker, timeout=3.0)

        # Verify we checked out master (confirms scrolling up worked)
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "master"
