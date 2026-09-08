import ast
from typing import Optional

from flake8_plugin_utils import Error, Plugin, Visitor


class TextFileShouldBeOpenedAsUtf8(Error):
    code = "UTF100"
    message = "Text files must be opened with encoding='utf-8'"


class TextFileWriteShouldPinNewline(Error):
    code = "UTF101"
    message = "Text files opened for writing must set newline='\\n' or newline=''"


class Utf8OpenVisitor(Visitor):

    @staticmethod
    def _string_value(node: Optional[ast.AST]) -> Optional[str]:
        value = getattr(node, "value", None)
        if isinstance(value, str):
            return value
        legacy_value = getattr(node, "s", None)
        return legacy_value if isinstance(legacy_value, str) else None

    @staticmethod
    def _is_open_call(node: ast.Call) -> bool:
        return (
            isinstance(node.func, ast.Name) and node.func.id == "open"
        ) or (
            isinstance(node.func, ast.Attribute) and
            isinstance(node.func.value, ast.Name) and
            node.func.value.id == "io" and
            node.func.attr == "open"
        )

    @staticmethod
    def _keyword_value(node: ast.Call, keyword_name: str) -> Optional[ast.AST]:
        return next((keyword.value for keyword in node.keywords if keyword.arg == keyword_name), None)

    @classmethod
    def _mode_value(cls, node: ast.Call) -> Optional[str]:
        mode = node.args[1] if len(node.args) > 1 else cls._keyword_value(node, "mode")
        return cls._string_value(mode)

    @classmethod
    def _is_binary_mode(cls, node: ast.Call) -> bool:
        mode_value = cls._mode_value(node)
        return mode_value is not None and "b" in mode_value

    @classmethod
    def _is_write_mode(cls, node: ast.Call) -> bool:
        mode_value = cls._mode_value(node)
        return mode_value is not None and any(flag in mode_value for flag in "wax+")

    @classmethod
    def _is_utf8_encoding(cls, node: ast.Call) -> bool:
        encoding = node.args[3] if len(node.args) > 3 else cls._keyword_value(node, "encoding")
        encoding_value = cls._string_value(encoding)
        return encoding_value is not None and encoding_value.lower().replace("_", "-") == "utf-8"

    @classmethod
    def _has_pinned_newline(cls, node: ast.Call) -> bool:
        newline = node.args[5] if len(node.args) > 5 else cls._keyword_value(node, "newline")
        newline_value = cls._string_value(newline)
        return newline_value in ("\n", "")

    def visit_Call(self, node: ast.Call) -> None:
        if self._is_open_call(node) and not self._is_binary_mode(node):
            if not self._is_utf8_encoding(node):
                self.error_from_node(TextFileShouldBeOpenedAsUtf8, node)
            if self._is_write_mode(node) and not self._has_pinned_newline(node):
                self.error_from_node(TextFileWriteShouldPinNewline, node)
        self.generic_visit(node)


class Utf8OpenChecker(Plugin):
    name = "Utf8OpenChecker"
    visitors = [Utf8OpenVisitor]
