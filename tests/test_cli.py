from git_machete.cli import alias_by_command


class TestCLI:
    def test_aliases(self) -> None:
        """
        Verify that each command alias is unique
        """
        assert len(alias_by_command.values()) == len(set(alias_by_command.values()))
