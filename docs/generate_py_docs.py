from bs4 import BeautifulSoup
from docutils import core
import os
from os.path import isfile, join
import re
from textwrap import dedent, indent


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
    return parts['body']


def html2txt(html: str):
    html_elements = BeautifulSoup(html, features="html.parser")

    # remove style tags
    for tag in html_elements.select('style'):
        tag.decompose()

    for tag in html_elements.select('td'):
        # remove non-breaking spaces
        if tag.text == u'\xa0':
            tag.decompose()
        else:
            # add new line and indent for the cells inside a table
            if 'class' not in tag.attrs:
                tag.insert_before('\n      ')

    # substitute double backticks with a single backtick
    for tag in html_elements.select('tt'):
        tag.insert_before('`')
        tag.insert_after('`')

    # make the option's text inside the option list bold
    for tag in html_elements.select('span'):
        if 'class' in tag.attrs:
            if ' '.join(tag.attrs['class']) == 'option':
                tag.insert_before('<b>')
                tag.insert_after('</b>')

    # keep bold text bold
    for tag in html_elements.select('strong'):
        tag.insert_before('<b>')
        tag.insert_after('</b>')

    # add new lines after the paragraph tag
    for tag in html_elements.select('p'):
        if 'class' in tag.attrs:
            if ' '.join(tag.attrs['class']) == 'first':
                tag.insert_before(' ')
            else:
                tag.insert_before('\n')
        else:
            tag.insert_before('\n\n')

    # format elements in the `Option:` section by adding new line and indent
    for tag in html_elements.select('kbd'):
        tag.insert_before('\n   ')

    # add indent to the description list
    for tag in html_elements.select('dt'):
        tag.string = '\n' + indent(tag.text.strip(), '   ')

    # add indent to the nested description list
    for tag in html_elements.select('dd'):
        tag.string = '\n' + indent(tag.text, '      ')

    # add indent and bullet points to the bulleted list
    for tag in html_elements.select('li'):
        if tag.parent.parent.name == 'li':  # deal with nested lists
            tag.insert_before('\n   - ')
        else:
            tag.insert_before('\n* ')

    # add new line before included NOTE class of rst documentation, example: github_api_access.rst
    for tag in html_elements.select('div'):
        if 'class' in tag.attrs:
            if 'admonition note' in ' '.join(tag.attrs['class']):
                tag.insert_before('\n')

    # format code examples
    for tag in html_elements.select('pre'):
        if 'class' in tag.attrs:
            if ' '.join(tag.attrs['class']) in ['code shell literal-block', 'code awk literal-block']:
                tag.string = '<b>' + indent(tag.text.rstrip('\n'), '  ') + '</b>'
            elif 'literal-block' in ' '.join(tag.attrs['class']):
                tag.string = '\n<dim>' + indent(tag.text, '  ') + '</dim>'

    # substitute color classes with respective ANSI codes
    for tag in html_elements.select('span'):
        if 'class' in tag.attrs:
            color = ' '.join(tag.attrs['class']).replace('gray', 'dim')
            if color in ['green', 'yellow', 'red', 'dim']:
                tag.insert_before(f'<{color}>')
                tag.insert_after(f'</{color}>')

    # build plain text output out of the previously formatted string elements
    text: str = ''
    for html_element in html_elements.descendants:
        if isinstance(html_element, str):
            if html_element != '\n':
                new_text = html_element
            else:
                new_text = html_element.replace('\n', '')
            text += new_text
    return text


def skip_or_replace_unparseable_directives(rst: str) -> str:
    rst = rst.replace(':ref:', '')
    return rst


def resolve_includes(rst: str, docs_source_path: str) -> str:
    matches = re.findall(r'(.*)\.\. include:: (.*)', rst)
    for indent_, match in matches:
        with open(f'{docs_source_path}/{match}', 'r') as handle:
            include_text = handle.read()
        rst = rst.replace(f'{indent_}.. include:: {match}', indent(dedent(include_text), indent_))
    return rst


def skip_prefix_new_lines(txt: str) -> str:
    txt = re.sub(r'\A[\n]+', '', txt)
    return txt


def replace_3_newlines_and_more_with_2_newlines(txt: str) -> str:
    for i in range(10, 2, -1):
        txt = txt.replace(i * '\n', '\n\n')
    return txt


if __name__ == '__main__':
    docs_source_path = 'docs/source'
    warning_text = '# ---------------------------------------------------------------------------------------------------------\n' \
                   '# Warning: This file is NOT supposed to be edited directly, ' \
                   'but instead regenerated via tox -e docs\n' \
                   '# ---------------------------------------------------------------------------------------------------------\n'
    output_text = 'from typing import Dict\n\n' + warning_text + '\nlong_docs: Dict[str, str] = {\n'
    path = docs_source_path + '/cli_help'
    commands_and_file_paths = {f.split('.')[0]: join(path, f) for f in sorted(os.listdir(path)) if isfile(join(path, f))}

    for command, file in commands_and_file_paths.items():
        with open(file, 'r') as f:
            rst = f.read()

        rst = skip_or_replace_unparseable_directives(rst)
        rst = resolve_includes(rst=rst, docs_source_path=docs_source_path)

        html = rst2html(rst)

        plain_text = html2txt(html)
        plain_text = skip_prefix_new_lines(plain_text)
        plain_text = plain_text.replace('---', '-')
        plain_text = replace_3_newlines_and_more_with_2_newlines(plain_text)

        output_text += f'    "{command}": """\n' + indent(plain_text, '        ') + '\n   """,\n'

    output_text += '}'
    print(output_text)
