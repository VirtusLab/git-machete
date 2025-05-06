import ast
from typing import Optional

from flake8_plugin_utils import Visitor, Error, Plugin
from collections import Counter


class KeywordArgumentVisitor(Visitor):
    def visit_FunctionDef(self, node):
        def type_for_arg(arg: ast.arg) -> Optional[str]:
            if type(arg.annotation) is ast.Name:
                return arg.annotation.id
            if type(arg.annotation) is ast.Subscript:
                return arg.annotation.value
            return None
        arguments = {arg.arg: type_for_arg(arg) for arg in node.args.args}
        for name, typ in arguments.items():
            if name.startswith("opt_"):
                self.error_from_node(ArgumentShouldBeKeyword, node, function_name=node.name, argument_name=name, reason="an 'opt_...'")
            if typ == 'bool':
                self.error_from_node(ArgumentShouldBeKeyword, node, function_name=node.name, argument_name=name, reason="a bool")

        #def normalize(orig: str) -> str:
        #    return orig
        #argument_types = [normalize(arg) for arg in arguments.values()]

        for typ, count in dict(Counter(arguments.values())).items():
            if count > 1:
                self.error_from_node(RepeatedArgumentType, node, function_name=node.name, repeated_type=typ)


class ArgumentShouldBeKeyword(Error):
    code = "KW100"
    message = ("'{argument_name}' argument in function '{function_name}' should be a keyword argument (since it's {reason}). "  # noqa: FS003
               "Enforce keyword-only arguments with bare '*' in argument list.")


class RepeatedArgumentType(Error):
    code = "KW101"
    message = ("Multiple non-keyword arguments of the same effective type '{repeated_type}' in function '{function_name}'. "  # noqa: FS003
              "Enforce keyword-only arguments with bare '*' in argument list.")


class KeywordArgumentChecker(Plugin):
    name = "KeywordArgumentChecker"
    visitors = [KeywordArgumentVisitor]
