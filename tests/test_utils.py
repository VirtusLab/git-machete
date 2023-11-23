from git_machete import utils
from git_machete.utils import hex_repr


class TestUtils:

    def test_fmt(self) -> None:
        utils.ascii_only = False
        utils.AnsiEscapeCodes.UNDERLINE = '\033[4m'
        utils.AnsiEscapeCodes.RED = '\033[91m'

        input_string = '<red> red <yellow>yellow <b>yellow_bold</b> `yellow_underlined` yellow <green>green </green> default' \
                       ' <dim> dimmed </dim></yellow> <green>green `green_underlined`</green> default</red>'
        expected_ansi_string = r'[91m red [33myellow [1myellow_bold[22m [4myellow_underlined[24m yellow [32mgreen ' \
                               '[0m default [2m dimmed [22m[0m [32mgreen [4mgreen_underlined[24m[0m default[0m'

        ansi_string = utils.fmt(input_string)

        assert ansi_string == expected_ansi_string

    def test_hex_repr(self) -> None:
        assert hex_repr("Hello, world!") == "48:65:6c:6c:6f:2c:20:77:6f:72:6c:64:21"
