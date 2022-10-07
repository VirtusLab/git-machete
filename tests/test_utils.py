from git_machete.utils import fmt


class TestUtils:
    def test_fmt(self) -> None:
        """
        Verify behaviour of a Utils fmt() function
        """
        input_string = '<yellow>It <b>all</b> `xd` <red>red</red> should be yellow </yellow>'
        expected_ansi_string = '[33mIt [1mall[22m [4mxd[24m [91mred[0m should be yellow [0m'
        assert fmt(input_string) == expected_ansi_string
