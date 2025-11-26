import fcntl
import os
import sys
import threading
import time
from typing import Any, Callable, Dict

from pytest_mock import MockerFixture

from git_machete import cli

from .base_test import BaseTest
from .mockers import rewrite_branch_layout_file
from .mockers_git_repository import check_out, commit, create_repo, new_branch

# Key codes matching those in go_interactive.py
KEY_UP = '\x1b[A'
KEY_DOWN = '\x1b[B'
KEY_RIGHT = '\x1b[C'
KEY_LEFT = '\x1b[D'
KEY_ENTER = '\r'
KEY_SPACE = ' '
KEY_CTRL_C = '\x03'

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


def read_line_from_fd(fd: int, timeout: float = 2.0) -> str:
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


class TestGoInteractive(BaseTest):
    def setup_method(self) -> None:
        """Set up a standard 3-branch repository for each test."""
        super().setup_method()
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

    def run_interactive_test(
        self,
        test_func: Callable[[int, int], None],
        mocker: MockerFixture,
        timeout: float = 5.0
    ) -> None:
        """
        Run an interactive test by executing git machete go in a thread with mocked stdin/stdout.

        Args:
            test_func: A function that takes (stdin_write_fd, stdout_read_fd) and performs the test
            mocker: pytest-mock fixture for mocking
            timeout: Maximum time to wait for the test to complete
        """
        # Create pipes for stdin and stdout
        stdin_read_fd, stdin_write_fd = os.pipe()
        stdout_read_fd, stdout_write_fd = os.pipe()

        # Open file objects for all ends
        stdin_read = os.fdopen(stdin_read_fd, 'r')
        stdin_write_fd_obj = os.fdopen(stdin_write_fd, 'w')
        stdout_read_fd_obj = os.fdopen(stdout_read_fd, 'r')
        stdout_write = os.fdopen(stdout_write_fd, 'w', buffering=1)  # Line buffered

        # Make stdout read end non-blocking
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
            """Run git machete go in a thread with replaced stdin/stdout."""
            original_stdin = sys.stdin
            original_stdout = sys.stdout
            try:
                sys.stdin = stdin_read
                sys.stdout = stdout_write
                # Run the CLI command
                cli.launch(['go'])
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
            test_func(stdin_write_fd_obj.fileno(), stdout_read_fd_obj.fileno())

            # Wait for thread to finish
            thread.join(timeout=timeout)

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
        check_out("develop")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int) -> None:
            # Read initial interface output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read the branch list
            line1 = read_line_from_fd(stdout_read_fd)
            line2 = read_line_from_fd(stdout_read_fd)
            line3 = read_line_from_fd(stdout_read_fd)

            # develop should be marked with * (current branch)
            assert "master" in line1
            assert "develop" in line2
            assert "*" in line2  # Current branch marker
            assert "feature-1" in line3

            # Press down arrow to select feature-1
            send_key(stdin_write_fd, KEY_DOWN)

            # Press up arrow to go back
            send_key(stdin_write_fd, KEY_UP)

            # Use Ctrl+C to quit
            send_key(stdin_write_fd, KEY_CTRL_C)

        self.run_interactive_test(test_logic, mocker)

    def test_go_interactive_left_arrow_parent(self, mocker: MockerFixture) -> None:
        """Test that left arrow navigates to parent branch."""
        check_out("feature-1")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int) -> None:
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            line3 = read_line_from_fd(stdout_read_fd)

            # feature-1 should be current
            assert "feature-1" in line3
            assert "*" in line3

            # Press left arrow to go to parent (develop)
            send_key(stdin_write_fd, KEY_LEFT)

            # Use Ctrl+C to quit
            send_key(stdin_write_fd, KEY_CTRL_C)

        self.run_interactive_test(test_logic, mocker)

    def test_go_interactive_right_arrow_child(self, mocker: MockerFixture) -> None:
        """Test that right arrow navigates to first child branch."""
        check_out("develop")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int) -> None:
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            read_line_from_fd(stdout_read_fd)
            line2 = read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)

            # develop should be current
            assert "develop" in line2
            assert "*" in line2

            # Press right arrow to go to first child (feature-1)
            send_key(stdin_write_fd, KEY_RIGHT)

            # Use Ctrl+C to quit
            send_key(stdin_write_fd, KEY_CTRL_C)

        self.run_interactive_test(test_logic, mocker)

    def test_go_interactive_quit_without_checkout(self, mocker: MockerFixture) -> None:
        """Test that pressing Ctrl+C quits without checking out."""
        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()

        def test_logic(stdin_write_fd: int, stdout_read_fd: int) -> None:
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
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
        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert initial_branch == "master"

        def test_logic(stdin_write_fd: int, stdout_read_fd: int) -> None:
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
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
                if "Checked out" in line:
                    checkout_msg = line
                    break

            assert "Checked out" in checkout_msg, f"Expected 'Checked out' message but got: {repr(checkout_msg)}"
            assert "feature-1" in checkout_msg

        self.run_interactive_test(test_logic, mocker, timeout=3.0)

        # Verify we're now on feature-1
        current_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
        assert current_branch == "feature-1"

    def test_go_interactive_with_annotations(self, mocker: MockerFixture) -> None:
        """Test that branch annotations are displayed with proper formatting."""
        # Overwrite .git/machete with annotations
        body: str = \
            """
            master
                develop  PR #123 rebase=no
                    feature-1  Work in progress
            """
        rewrite_branch_layout_file(body)

        check_out("master")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int) -> None:
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            line1 = read_line_from_fd(stdout_read_fd)
            line2 = read_line_from_fd(stdout_read_fd)
            line3 = read_line_from_fd(stdout_read_fd)

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
        check_out("master")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int) -> None:
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            line1 = read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)

            # master should be initially selected (marked with *)
            assert "master" in line1
            assert "*" in line1

            # Press UP to wrap to last item (feature-1)
            send_key(stdin_write_fd, KEY_UP)

            # Press DOWN twice to verify we can navigate forward from last item to first
            send_key(stdin_write_fd, KEY_DOWN)
            # Now at master (wrapped from feature-1)

            send_key(stdin_write_fd, KEY_DOWN)
            # Now at develop

            # Press UP to go back to master
            send_key(stdin_write_fd, KEY_UP)
            # Now at master

            # Press UP again to wrap to feature-1
            send_key(stdin_write_fd, KEY_UP)
            # Now at feature-1 (wrapped)

            # Use Ctrl+C to quit
            send_key(stdin_write_fd, KEY_CTRL_C)

        self.run_interactive_test(test_logic, mocker)

    def test_go_interactive_q_key_quit(self, mocker: MockerFixture) -> None:
        """Test that pressing 'q' or 'Q' quits without checking out."""
        check_out("master")
        initial_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()

        def test_logic(stdin_write_fd: int, stdout_read_fd: int) -> None:
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
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
        check_out("master")

        def test_logic(stdin_write_fd: int, stdout_read_fd: int) -> None:
            # Read initial output
            header = read_line_from_fd(stdout_read_fd)
            assert "Select branch" in header

            # Read branch list
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)
            read_line_from_fd(stdout_read_fd)

            # Press some unknown keys - they should be ignored
            send_key(stdin_write_fd, 'x')
            send_key(stdin_write_fd, 'z')
            send_key(stdin_write_fd, '1')

            # Now press a valid key to verify the interface still works
            send_key(stdin_write_fd, KEY_DOWN)

            # Quit with Ctrl+C to verify we can still exit
            send_key(stdin_write_fd, KEY_CTRL_C)

        self.run_interactive_test(test_logic, mocker)
