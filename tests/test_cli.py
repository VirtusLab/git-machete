import os
from tempfile import mkdtemp

import pytest
from pytest_mock import MockerFixture

from git_machete.cli import alias_by_command, main
from git_machete.exceptions import ExitCode

from .base_test import BaseTest
from .mockers import launch_command_capturing_output_and_exception


class TestCLI(BaseTest):
    def test_aliases_unique(self) -> None:
        assert len(alias_by_command.values()) == len(set(alias_by_command.values()))

    @pytest.mark.parametrize("flag", ["--debug", "-v", "--verbose"])
    def test_verbose_no_command(self, flag: str) -> None:
        output, e = launch_command_capturing_output_and_exception(flag)
        assert output and "Usage: git machete" in output
        assert type(e) is SystemExit
        assert e.code == ExitCode.ARGUMENT_ERROR

    def test_main(self, mocker: MockerFixture) -> None:
        self.patch_symbol(mocker, "sys.argv", ["", "show", "current"])
        main()

        with pytest.raises(SystemExit) as ei:
            self.patch_symbol(mocker, "sys.argv", ["", "go", "no-such-direction"])
            main()
        assert ExitCode.ARGUMENT_ERROR == ei.value.code

        with pytest.raises(SystemExit) as ei:
            self.patch_symbol(mocker, "sys.argv", ["", "status", "--", "--patch"])
            main()
        assert ExitCode.ARGUMENT_ERROR == ei.value.code

        os.chdir(mkdtemp())

        with pytest.raises(SystemExit) as ei:
            self.patch_symbol(mocker, "sys.argv", ["", "file"])
            main()
        assert ExitCode.MACHETE_EXCEPTION == ei.value.code
