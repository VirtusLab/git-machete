import os
import re
import sys
from textwrap import indent

from os import listdir
from os.path import isfile, join
from bs4 import BeautifulSoup

# import os
# print(os.getcwd())
# sys.path.append('../../git_machete')
# print(sys.path)

from git_machete.utils import AnsiEscapeCodes
from docutils import core

# - status_extraSpaceBeforeBranchName_config_key


def rst2html(input_string: str, source_path: str = None, destination_path: str = None,
             input_encoding: str = 'unicode', doctitle: bool = True,
             initial_header_level: int = 1):
    overrides = {'input_encoding': input_encoding,
                 'doctitle_xform': doctitle,
                 'initial_header_level': initial_header_level}
    parts = core.publish_parts(
        source=input_string, source_path=source_path,
        destination_path=destination_path,
        writer_name='html', settings_overrides=overrides)
    return parts


def html2txt(html: str):
    html_elements = BeautifulSoup(html, features="html.parser")
    for data in html_elements(['style']):
        data.decompose()

    for literal in html_elements.select('tt'):
        cite = html_elements.new_tag('cite')
        cite.string = ' `' + literal.text + '` '
        literal.replace_with(cite)

    text: str = ''
    prev_tag = None

    for html_element in html_elements.descendants:
        if isinstance(html_element, str):
            new_text = html_element.strip()
            if prev_tag == 'code':
                new_text = indent(html_element.strip(), '  ')

            text += new_text

            if prev_tag == 'strong':
                text += '</b>'
            elif prev_tag == 'cite':
                text += ' '
            elif prev_tag == 'code':
                text += '\n</dim>'
            elif prev_tag == 'color':
                text += AnsiEscapeCodes.ENDC + ' '

            prev_tag = None

        elif html_element.name in ['kbd']:
            text += '\n   '
        # elif html_element.name in ['td']:
        #     text += '   '  # not sure if its possible to even them out
        elif html_element.name in ['p']:
            if 'class' in html_element.attrs:
                if ' '.join(html_element.attrs['class']) == 'first':
                    text += ' '
                else:
                    text += '\n\n'
            else:
                text += '\n\n'
        elif html_element.name in ['dt']:
            text += '\n   '
        elif html_element.name in ['dd']:
            text += '\n      '
        elif html_element.name == 'li':
            if html_element.parent.parent.name == 'li':  # deal with nested lists
                text += '\n      - '
            else:
                text += '\n\n   * '
        elif html_element.name == 'strong':
            prev_tag = 'strong'
            text += '<b>'
        elif html_element.name == 'pre':
            if ' '.join(html_element.attrs['class']) == 'code shell literal-block':
                text += ' '
            elif ' '.join(html_element.attrs['class']) == 'code literal-block':
                text += '\n<dim>\n'
                prev_tag = 'code'
        elif html_element.name == 'cite':
            text += ' '
            prev_tag = 'cite'
        elif html_element.name == 'span':
            if ' '.join(html_element.attrs['class']) == 'green':
                text += ' ' + AnsiEscapeCodes.GREEN
                prev_tag = 'color'
            if ' '.join(html_element.attrs['class']) == 'yellow':
                text += ' ' + AnsiEscapeCodes.YELLOW
                prev_tag = 'color'
            if ' '.join(html_element.attrs['class']) == 'red':
                text += ' ' + AnsiEscapeCodes.RED
                prev_tag = 'color'
            if ' '.join(html_element.attrs['class']) == 'grey':
                text += ' ' + AnsiEscapeCodes.DIM
                prev_tag = 'color'
    return text


def skip_or_replace_unparseable_directives(rst: str) -> str:
    rst = rst.replace(':ref:', '')\
             .replace('.. code-block:: ini', '.. code-block::')
    return rst


def resolve_includes(rst: str, docs_source_path: str) -> str:
    matches = re.findall(r'\.\. include:: (.*)', rst)
    for match in matches:
        with open(f'{docs_source_path}/{match}', 'r') as handle:
            include_text = handle.read()
        rst = rst.replace(f'.. include:: {match}', include_text)
    return rst


def skip_prefix_new_lines(txt: str) -> str:
    txt = re.sub(r'\A[\n]+', '', txt)
    return txt


if __name__ == '__main__':
    output_docs_path = 'git_machete/long_docs.py'
    docs_source_path = 'docs/source'
    output_text = 'from typing import Dict\n\nlong_docs: Dict[str, str] = {\n'
    path = docs_source_path + '/cli_help'
    commands_and_file_paths = {f.split('.')[0]: join(path, f) for f in sorted(listdir(path)) if isfile(join(path, f))}

    # cmd = 'traverse'
    # commands_and_file_paths = {cmd: f'source/cli_help/{cmd}.rst'}
    for command, file in commands_and_file_paths.items():
        with open(file, 'r') as f:
            rst = f.read()

        rst = skip_or_replace_unparseable_directives(rst)
        rst = resolve_includes(rst=rst, docs_source_path=docs_source_path)
        html = rst2html(rst)['body']
        # print(html)
        # print('\n\n\n)
        plain_text = html2txt(html)
        plain_text = skip_prefix_new_lines(plain_text)
        # print(plain_text)
        output_text += f'    "{command}": """\n' + indent(plain_text, '        ') + '\n   """,\n'

    with open(output_docs_path, 'w') as f:
        f.write(output_text + '}\n')


# if __name__ == '__main__':
#     from git_machete.long_docs import long_docs
#     from git_machete.docs import long_docs
#
#     for k, v in long_docs.items():
#         print(k)
#         print(v)
#         print()