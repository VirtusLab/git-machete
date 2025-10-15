# mypy: ignore-errors


import pytest

OPTION = 'full-operands'


def pytest_addoption(parser):
    parser.getgroup(OPTION).addoption(
        f'--{OPTION}',
        action='store_true',
        dest=OPTION,
        default=False,
        help='Always show full operands on `assert x == y` failures'
    )


@pytest.hookimpl(tryfirst=True)
def pytest_assertrepr_compare(config, op: str, left, right):
    if op == "==" and config.getoption(OPTION):
        def lines_for(arg):
            return [''] + ['    ' + x for x in arg.splitlines()] + ['']
        return [
            'Comparing values:',
            'LEFT (typically means actual):', *lines_for(left),
            'RIGHT (typically means expected):', *lines_for(right)
        ]
    return None


def pytest_configure(config):
    if config.getoption(OPTION):
        # Set verbosity level to the equivalent of '-vv'
        config.option.verbose = 2
