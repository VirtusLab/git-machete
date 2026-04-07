import os
import re
import sys
import tempfile

import pytest
from pytest_mock import MockerFixture

from git_machete import utils
from git_machete.utils import SimpleAnsiEscapeCodes

from .base_test import BaseTest


class TestUtils(BaseTest):

    def test_debug_doesnt_overwrite_local_vars(self) -> None:
        foo = {"foo": 1}
        try:
            utils.debug_mode = True
            utils.debug("")
        finally:
            utils.debug_mode = False
        assert foo["foo"] == 1  # and not string "1"

    def test_fmt(self, mocker: MockerFixture) -> None:
        # Force printing ANSI escape sequences even though the terminal is NOT a TTY
        self.patch_symbol(mocker, 'git_machete.utils.ascii_only_stdout', False)
        # Use the palette of ANSI escape code that does NOT depend on the underlying terminal properties
        E = SimpleAnsiEscapeCodes()
        self.patch_symbol(mocker, 'git_machete.utils.AE', E)

        input_string = '<red> red <yellow>yellow <b>yellow_bold</b> `yellow_underlined` yellow <green>green </green> default' \
                       ' <dim> dimmed </dim></yellow> <green>green `green_underlined`</green> default</red>'

        expected_ansi_string = (
            E.RED + ' red ' + E.YELLOW + 'yellow ' + E.BOLD + 'yellow_bold' + E.ENDC_BOLD_DIM + ' ' +
            E.UNDERLINE + 'yellow_underlined' + E.ENDC_UNDERLINE + ' yellow ' + E.GREEN + 'green ' + E.ENDC +
            ' default ' + E.DIM + ' dimmed ' + E.ENDC_BOLD_DIM + E.ENDC + ' ' + E.GREEN + 'green ' +
            E.UNDERLINE + 'green_underlined' + E.ENDC_UNDERLINE + E.ENDC + ' default' + E.ENDC
        )
        ansi_string = utils.fmt(input_string)
        assert ansi_string == expected_ansi_string

    def test_get_current_date(self) -> None:
        assert re.fullmatch("20[0-9][0-9]-[0-1][0-9]-[0-3][0-9]", utils.get_current_date())

    def test_hex_repr(self) -> None:
        assert utils.hex_repr("Hello, world!") == "48:65:6c:6c:6f:2c:20:77:6f:72:6c:64:21"

    def test_abspath_posix_general(self) -> None:
        """Test that abspath_posix returns an absolute path with forward slashes."""
        # Create a temporary directory to ensure we're working with real paths
        with tempfile.TemporaryDirectory() as tmpdir:
            normalized = utils.abspath_posix(tmpdir)
            # Should be absolute
            assert os.path.isabs(normalized)
            # Should use forward slashes (no backslashes)
            assert '\\' not in normalized
            # Should be a valid path that exists
            assert os.path.exists(normalized)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test for backslash conversion")
    def test_abspath_posix_windows_backslashes(self) -> None:
        """Test that backslashes are converted to forward slashes on Windows."""
        # On Windows, Path.resolve() returns paths with backslashes
        with tempfile.TemporaryDirectory() as tmpdir:
            # tmpdir will have backslashes on Windows (e.g., C:\Users\...)
            # Verify it contains backslashes before normalization
            assert '\\' in tmpdir or '/' in tmpdir  # Windows paths have one or the other

            normalized = utils.abspath_posix(tmpdir)

            # After normalization, should have forward slashes only
            assert '\\' not in normalized
            assert '/' in normalized
            # Should still start with drive letter (e.g., C:/)
            assert normalized[1:3] == ':/'

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test for /private prefix")
    def test_abspath_posix_macos_private_prefix(self) -> None:
        """Test that /private prefix is consistently added on macOS for /tmp and /var paths."""
        # On macOS, /tmp and /var are symlinks to /private/tmp and /private/var
        # tempfile.mkdtemp() may return paths with or without /private prefix
        with tempfile.TemporaryDirectory() as tmpdir:
            # tmpdir is in /tmp or /var on macOS
            # It might be returned as /var/folders/... or /private/var/folders/...

            normalized = utils.abspath_posix(tmpdir)

            # After normalization with resolve(), should have /private prefix if in /var or /tmp
            # (resolve resolves the symlink)
            if '/tmp' in tmpdir or '/var' in tmpdir:
                # Should start with /private after normalization
                assert normalized.startswith('/private/') or normalized.startswith('/nix/'), \
                    f"Expected path to start with /private/ or /nix/ (for Nix builds), got: {normalized}"

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test for absolute paths")
    def test_abspath_posix_unix_absolute_paths(self) -> None:
        """Test that paths start with / on Unix systems."""
        with tempfile.TemporaryDirectory() as tmpdir:
            normalized = utils.abspath_posix(tmpdir)
            # Should start with / on Unix
            assert normalized.startswith('/')
            # Should not contain backslashes
            assert '\\' not in normalized
