from flake8_plugin_utils import assert_error, assert_not_error
from utf8_open_checker import TextFileShouldBeOpenedAsUtf8, Utf8OpenVisitor


def test_missing_encoding_on_read() -> None:
    assert_error(Utf8OpenVisitor, 'open("layout")', TextFileShouldBeOpenedAsUtf8)


def test_missing_encoding_on_write() -> None:
    assert_error(Utf8OpenVisitor, 'open(".git/machete", "w")', TextFileShouldBeOpenedAsUtf8)


def test_non_utf8_encoding() -> None:
    assert_error(Utf8OpenVisitor, 'open("layout", encoding="cp1252")', TextFileShouldBeOpenedAsUtf8)


def test_utf8_read_is_ok() -> None:
    assert_not_error(Utf8OpenVisitor, 'open("layout", encoding="utf-8")')


def test_utf8_alias_read_is_ok() -> None:
    assert_not_error(Utf8OpenVisitor, 'open("layout", encoding="UTF_8")')


def test_utf8_write_is_ok() -> None:
    assert_not_error(Utf8OpenVisitor, 'open("layout", "w", encoding="utf-8")')


def test_binary_write_is_ok() -> None:
    assert_not_error(Utf8OpenVisitor, 'open("layout", "wb")')


def test_utf8_via_io_open_is_ok() -> None:
    assert_not_error(Utf8OpenVisitor, 'io.open("layout", "w", encoding="utf-8")')
