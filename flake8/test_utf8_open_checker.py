import ast

from flake8_plugin_utils import assert_error, assert_not_error
from utf8_open_checker import TextFileShouldBeOpenedAsUtf8, TextFileWriteShouldPinNewline, Utf8OpenVisitor


def test_missing_encoding_on_read() -> None:
    assert_error(Utf8OpenVisitor, 'open("layout")', TextFileShouldBeOpenedAsUtf8)


def test_write_without_encoding_or_newline_reports_both() -> None:
    visitor = Utf8OpenVisitor()
    visitor.visit(ast.parse('open(".git/machete", "w")'))
    assert [type(error) for error in visitor.errors] == [TextFileShouldBeOpenedAsUtf8, TextFileWriteShouldPinNewline]


def test_non_utf8_encoding() -> None:
    assert_error(Utf8OpenVisitor, 'open("layout", encoding="cp1252")', TextFileShouldBeOpenedAsUtf8)


def test_utf8_read_is_ok() -> None:
    assert_not_error(Utf8OpenVisitor, 'open("layout", encoding="utf-8")')


def test_utf8_alias_read_is_ok() -> None:
    assert_not_error(Utf8OpenVisitor, 'open("layout", encoding="UTF_8")')


def test_binary_write_is_ok() -> None:
    assert_not_error(Utf8OpenVisitor, 'open("layout", "wb")')


def test_write_with_utf8_but_missing_newline() -> None:
    assert_error(Utf8OpenVisitor, 'open("layout", "w", encoding="utf-8")', TextFileWriteShouldPinNewline)


def test_append_with_utf8_but_missing_newline() -> None:
    assert_error(Utf8OpenVisitor, 'open("layout", "a", encoding="utf-8")', TextFileWriteShouldPinNewline)


def test_write_with_lf_newline_is_ok() -> None:
    assert_not_error(Utf8OpenVisitor, 'open("layout", "w", encoding="utf-8", newline="\\n")')


def test_write_with_untranslated_newline_is_ok() -> None:
    assert_not_error(Utf8OpenVisitor, 'io.open("layout", "w", encoding="utf-8", newline="")')
