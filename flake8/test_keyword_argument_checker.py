from flake8_plugin_utils import assert_error, assert_not_error
from keyword_argument_checker import ArgumentShouldBeKeyword, KeywordArgumentVisitor, RepeatedArgumentType


def test_opt_prefix_must_be_keyword_only() -> None:
    assert_error(
        KeywordArgumentVisitor,
        "def discover(self, opt_yes: str) -> None: ...",
        ArgumentShouldBeKeyword,
        function_name="discover",
        argument_name="opt_yes",
        reason="an 'opt_...'",
    )


def test_bool_must_be_keyword_only() -> None:
    assert_error(
        KeywordArgumentVisitor,
        "def go(self, recache: bool) -> None: ...",
        ArgumentShouldBeKeyword,
        function_name="go",
        argument_name="recache",
        reason="a bool",
    )


def test_repeated_effective_str_types_must_be_keyword_only() -> None:
    assert_error(
        KeywordArgumentVisitor,
        "def pair(self, left: str, right: str) -> None: ...",
        RepeatedArgumentType,
        function_name="pair",
        repeated_type="str",
    )


def test_branch_name_annotations_count_as_str() -> None:
    assert_error(
        KeywordArgumentVisitor,
        "def wire(self, parent: LocalBranchShortName, child: LocalBranchShortName) -> None: ...",
        RepeatedArgumentType,
        function_name="wire",
        repeated_type="str",
    )


def test_keyword_only_opt_and_bool_are_ok() -> None:
    assert_not_error(
        KeywordArgumentVisitor,
        "def discover(self, *, opt_yes: bool) -> None: ...",
    )


def test_distinct_positional_types_are_ok() -> None:
    assert_not_error(
        KeywordArgumentVisitor,
        "def pair(self, left: str, right: int) -> None: ...",
    )
