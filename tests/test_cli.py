import os
from tempfile import mkdtemp

import pytest
from pytest_mock import MockerFixture

from git_machete.cli import alias_by_command, main
from git_machete.exceptions import ExitCode

from .base_test import BaseTest


class TestCLI(BaseTest):
    def test_aliases_unique(self) -> None:
        assert len(alias_by_command.values()) == len(set(alias_by_command.values()))

    def test_main(self, mocker: MockerFixture) -> None:
        with pytest.raises(SystemExit) as ei:
            self.patch_symbol(mocker, "sys.argv", ["go", "no-such-direction"])
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
