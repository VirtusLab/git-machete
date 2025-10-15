import ast
import re
from collections import Counter
from typing import Optional

from flake8_plugin_utils import Error, Plugin, Visitor


class KeywordArgumentVisitor(Visitor):
    def visit_FunctionDef(self, node):
        def type_for_arg(arg: ast.arg) -> Optional[str]:
            if type(arg.annotation) is ast.Name:
                if re.search('Branch.*Name|Hash$|Revision$', arg.annotation.id):
                    return 'str'
                return arg.annotation.id
            if type(arg.annotation) is ast.Subscript:
                return arg.annotation.value
            return None

        arguments = {arg.arg: type_for_arg(arg) for arg in node.args.args}
        for name, typ in arguments.items():
            if name.startswith("opt_"):
                self.error_from_node(ArgumentShouldBeKeyword, node, function_name=node.name, argument_name=name, reason="an 'opt_...'")
            elif typ == 'bool':
                self.error_from_node(ArgumentShouldBeKeyword, node, function_name=node.name, argument_name=name, reason="a bool")
        for typ, count in Counter(filter(None, arguments.values())).items():
            if count > 1:
                self.error_from_node(RepeatedArgumentType, node, function_name=node.name, repeated_type=typ)


class ArgumentShouldBeKeyword(Error):
    code = "KW100"
    message = ("Argument '{argument_name}' in function '{function_name}' "  # noqa: FS003
               "should be a keyword argument (since it's {reason}). "  # noqa: FS003
               "Enforce keyword-only arguments with bare '*' in argument list.")


class RepeatedArgumentType(Error):
    code = "KW101"
    message = ("Multiple non-keyword arguments of the same effective type "
               "'{repeated_type}' in function '{function_name}'. "  # noqa: FS003
               "Enforce keyword-only arguments with bare '*' in argument list.")


class KeywordArgumentChecker(Plugin):
    name = "KeywordArgumentChecker"
    visitors = [KeywordArgumentVisitor]
