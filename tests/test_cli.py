import os
from tempfile import mkdtemp

import pytest
from pytest_mock import MockerFixture

from git_machete.cli import alias_by_command, main
from git_machete.exceptions import ExitCode

from .base_test import BaseTest


class TestCLI(BaseTest):
    def test_aliases(self) -> None:
        """
        Verify that each command alias is unique
        """
        assert len(alias_by_command.values()) == len(set(alias_by_command.values()))

    def test_main(self, mocker: MockerFixture) -> None:
        with pytest.raises(SystemExit) as e:
            self.patch_symbol(mocker, "sys.argv", ["go", "no-such-direction"])
            main()
        assert ExitCode.ARGUMENT_ERROR == e.value.code

        os.chdir(mkdtemp())

        with pytest.raises(SystemExit) as e:
            self.patch_symbol(mocker, "sys.argv", ["", "file"])
            main()
        assert ExitCode.MACHETE_EXCEPTION == e.value.code
