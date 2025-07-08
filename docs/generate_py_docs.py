import os
import re
from itertools import takewhile
from os.path import isfile, join
from textwrap import dedent, indent
from typing import List


def resolve_includes(rst_: str, docs_source_path_: str) -> str:
    matches = re.findall(r'(.*)\.\. include:: (.*)\n(.* :(.*): ([0-9]*)\n)?(.* :(.*): ([0-9]*)\n)?', rst_)
    # example matches:
    #     .. include:: status_extraSpaceBeforeBranchName_config_key.rst
    #
    #     .. include:: status_extraSpaceBeforeBranchName_config_key.rst
    #         :start-line: 2
    #
    #     .. include:: status_extraSpaceBeforeBranchName_config_key.rst
    #         :start-line: 2
    #         :end-line: 6
    for indent_, included_file, option_1_str, option_1, option_1_value, option_2_str, option_2, option_2_value in matches:
        with open(f'{docs_source_path_}/{included_file}', 'r') as handle:
            include_text = handle.readlines()
        replace_from = f'{indent_}.. include:: {included_file}'

        start_line, end_line = 0, len(include_text)
        if option_1 == 'start-line':
            start_line = int(option_1_value)
            replace_from += f'\n{option_1_str}'
            if option_2 == 'end-line':
                end_line = int(option_2_value)
                replace_from += option_2_str
        elif option_1 == 'end-line':
            end_line = int(option_1_value)
            replace_from += f'\n{option_1_str}'

        include_text = include_text[start_line:end_line]
        include_text = takewhile(lambda line: not line == "..\n", include_text)
        replace_to = indent(dedent(''.join(include_text)), indent_)
        rst_ = rst_.replace(replace_from, replace_to, 1)
    return rst_


HEADER = 0
USAGE = 1
NORMAL = 2
SHELL_BLOCK = 3
OPTIONS = 4
SECTION = 5


def rst2txt(rst: str) -> str:
    state = HEADER
    result = []
    indent = " " * 3

    def process_rst_formatting(lne: str) -> str:
        if '#. ' in lne:
            lne = indent + lne.replace("#. ", "* ")
        elif lne.startswith('   '):
            lne = indent + lne[1:]
        elif lne.startswith('* ') or lne.startswith('  '):
            lne = indent + lne
        lne = re.sub('---', '—', lne)
        lne = re.sub(':ref:`([^<`]+)(<[^>]+>)?`', r'`\1`', lne)
        lne = re.sub('`(.*) <.*>`_', r'\1', lne)
        lne = re.sub('``', '`', lne)
        lne = re.sub(r'\*\*(.*)\*\*', r'<b>\1</b>', lne)
        lne = re.sub(r' \*([^ ])', r' \1', lne)
        lne = re.sub(r'([^ ])\*([ .])', r'\1\2', lne)
        lne = re.sub(r':([a-z]+):`([^`]+)`', r'<\1>\2</\1>', lne)
        return lne

    def is_section_header(lne: str) -> bool:
        return "Environment variables:" in lne or "Git config keys:" in lne or "Hooks:" in lne or "Subcommands:" in lne

    def process_new_option(lne: str) -> List[str]:
        lne = process_rst_formatting(lne)
        lne = lne.replace('``', '`')
        forms = re.sub('  .*$', '', lne)
        fmt_forms = ", ".join(f"<b>{form}</b>" for form in forms.split(", "))
        def_first_line = re.sub('^.*   *', '', lne)
        return ["   " + fmt_forms, "      " + def_first_line]

    for line in rst.splitlines():
        if line.startswith('=='):
            if "**Usage:**" in rst:
                state = USAGE
            else:
                state = NORMAL
        elif state == USAGE:
            if "**Usage:**" in line:
                result += ["<b>Usage:</b><b>"]
            elif line.startswith('    '):
                result += [line[1:]]
            elif line and (line[0].isalpha() or line.startswith('**')):
                result[-1] += "</b>"
                result += [""]
                state = NORMAL
                result += [process_rst_formatting(line)]
        elif state == NORMAL:
            if ".. code-block::" in line:
                result = result[:-1]
                state = SHELL_BLOCK
                result += ["<dim>"]
            elif ".. note::" in line:
                result += ["<b>Note:</b>"]
            elif line.startswith('-'):
                state = OPTIONS
                result += process_new_option(line)
            elif is_section_header(line):
                result += [process_rst_formatting(line)]
                state = SECTION
            else:
                result += [process_rst_formatting(line)]
        elif state == SHELL_BLOCK:
            if line.startswith('    '):
                result += [line[2:]]
            elif is_section_header(line):
                result += ["</dim>"]
                state = SECTION
                result += [process_rst_formatting(line)]
            elif line:
                result += ["</dim>"]
                state = NORMAL
                result += [process_rst_formatting(line)]
        elif state == OPTIONS:
            if line.startswith('-'):
                result += process_new_option(line)
            elif is_section_header(line):
                result += [process_rst_formatting(line)]
                state = SECTION
            elif line:
                result += [indent * 2 + process_rst_formatting(line.strip())]
            else:
                result += [""]
        elif state == SECTION:
            if line.startswith('``'):
                result += [indent + process_rst_formatting(line)]
            elif ".. code-block::" in line:
                result = result[:-1]
            elif line:
                result += [process_rst_formatting(line)]
            else:
                result += [""]
    if state == SHELL_BLOCK:
        result += ["</dim>"]
    return "\n".join(result)


if __name__ == '__main__':
    docs_source_path = 'docs/source'
    output_text = 'from typing import Dict\n\n' \
        '# ---------------------------------------------------------------------------------------------------------\n' \
        '# Warning: This file is NOT supposed to be edited directly, but instead regenerated via `tox -e py-docs`\n' \
        '# ---------------------------------------------------------------------------------------------------------\n\n'

    # build short docs
    output_text += 'short_docs: Dict[str, str] = {\n'
    short_docs_rst_file = docs_source_path + '/short_docs.rst'
    with open(short_docs_rst_file, 'r') as f:
        rst = f.read()
    for line in rst.splitlines():
        if line.startswith('* :ref:'):
            output_text += re.sub(r'^\* :ref:`(.+)` +-- (.*)$', r'    "\1": "\2",', line) + "\n"
    output_text += '}\n\n'

    # build long docs
    output_text += 'long_docs: Dict[str, str] = {\n'
    path = docs_source_path + '/cli'
    commands_and_file_paths = {f.split('.')[0]: join(path, f) for f in sorted(os.listdir(path)) if isfile(join(path, f))}

    for command, file in commands_and_file_paths.items():
        with open(file, 'r') as f:
            rst = f.read()
        rst = resolve_includes(rst_=rst, docs_source_path_=docs_source_path)
        plain_text = rst2txt(rst)
        output_text += f'    "{command}": """\n' + indent(plain_text, '        ') + '\n   """,\n'
        output_text = re.sub('\n{2,}', '\n\n', output_text)  # noqa: FS003

    output_text += '}'
    print(output_text)
