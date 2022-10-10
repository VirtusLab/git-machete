import os


class TestUtils():
    def test_fmt(self) -> None:
        """
        Verify behaviour of a Utils fmt() function
        """
        os.environ["TERM"] = 'xterm-256color'
        from git_machete import utils
        utils.ascii_only = False
        del os.environ["TERM"]

        input_string = '<red> red <yellow>yellow <b>yellow_bold</b> `yellow_underlined` yellow <green>green </green> default' \
                       ' <dim> dimmed </dim></yellow> <green>green `green_underlined`</green> default</red>'
        expected_ansi_string = r'[31m red [33myellow [1myellow_bold[22m [36myellow_underlined[24m yellow [32mgreen ' \
                               '[0m default [2m dimmed [22m[0m [32mgreen [36mgreen_underlined[24m[0m default[0m'
        ansi_string = utils.fmt(input_string)
        utils.ascii_only = False
        assert ansi_string == expected_ansi_string
