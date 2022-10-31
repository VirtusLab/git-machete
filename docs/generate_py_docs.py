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


def html2txt(html_: str):
    html_elements = BeautifulSoup(html_, features="html.parser")

    # remove style tags
    for tag in html_elements.select('style'):
        tag.decompose()

    # remove non-breaking spaces
    for tag in html_elements.select('td'):
        if tag.text == u'\xa0':
            tag.decompose()

    # substitute double backticks with a single backtick
    for tag in html_elements.select('tt'):
        tag.insert_before('`')
        tag.insert_after('`')

    # format cite's tag text with single backticks
    for tag in html_elements.select('cite'):
        tag.insert_before('`')
        tag.insert_after('`')

    # format colors
    for tag in html_elements.select('span'):
        if 'class' in tag.attrs:
            color = ' '.join(tag.attrs['class']).replace('gray', 'dim')
            if color in ['green', 'yellow', 'red', 'dim']:
                tag.insert_before(f'<{color}>')
                tag.insert_after(f'</{color}>')

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
            if 'admonition-title' in ' '.join(tag.attrs['class']):
                tag.decompose()
            else:
                tag.insert_before('\n')
        else:
            tag.insert_before('\n\n')

    # add indent and bullet points to the nested bulleted list
    for tag in html_elements.select('li'):
        if tag.parent.parent is not None:
            if tag.parent.parent.name == 'li':
                lines = tag.text.splitlines()
                tag.string = f' - {lines[0]}'
                if len(lines) > 1:
                    tag.string += indent('\n' + '\n'.join(lines[1:]), INDENT_LEN_3)

    # add indent and bullet points to the bulleted list
    for tag in html_elements.select('li'):
        if tag.parent.parent is not None:
            if tag.parent.parent.name != 'li':
                lines = tag.text.splitlines()
                tag.string = f'\n{INDENT_LEN_3}* {lines[0]}'
                if len(lines) > 1:
                    tag.string += indent('\n' + '\n'.join(lines[1:]), INDENT_LEN_3 + '  ')

    # format elements in the `Option:` section by adding new line and indent
    for tag in html_elements.select('kbd'):
        tag.insert_before(f'\n{INDENT_LEN_3}')

    # add indent to the description list
    for tag in html_elements.select('dt'):
        tag.string = '\n' + indent(tag.text.strip(), INDENT_LEN_3)

    # add indent to the nested description list
    for tag in html_elements.select('dd'):
        tag.string = '\n' + indent(tag.text, 2 * INDENT_LEN_3) + '\n'

    # add new line and indent for the cells inside a table (e.g. options inside **Options:** section)
    for tag in html_elements.select('td'):
        if 'class' not in tag.attrs:
            tag.string = indent(f'\n{tag.text}', 2 * INDENT_LEN_3)

    # format code examples
    for tag in html_elements.select('pre'):
        if 'class' in tag.attrs:
            if ' '.join(tag.attrs['class']).replace('first', '').replace('last', '').replace('  ', ' ') == 'code literal-block':
                tag.string = '\n<dim>' + indent(tag.text, '  ') + '</dim>'
            elif 'literal-block' in ' '.join(tag.attrs['class']):
                tag.string = '<b>' + indent(tag.text.rstrip('\n'), INDENT_LEN_3) + '</b>'

    # build python docs string out of the previously formatted html tags
    text: str = ''
    for html_element in html_elements.descendants:
        if isinstance(html_element, str):
            if html_element != '\n':
                new_text = html_element
            else:
                new_text = ''

            # keep exactly one line gap between points in bulleted list
            if f'{INDENT_LEN_3}- ' in html_element and f'{INDENT_LEN_3}* ' in html_element:
                new_text = html_element.rstrip()

            text += new_text
    return text


def skip_or_replace_unparseable_directives(rst_: str) -> str:
    rst_ = rst_.replace(':ref:', '')
    return rst_


def resolve_includes(rst_: str, docs_source_path_: str) -> str:
    # matches = re.findall(r'(.*)\.\. include:: (.*)', rst_)
    matches = re.findall(r'(.*)\.\. include:: (.*)\n(.* :(.*): ([0-9]*)\n)?(.* :(.*): ([0-9]*)\n)?', rst_)
    matches2 = re.findall(r'(.*) :start-line: ([0-9]*)', rst_)
    for indent_, match, start_line, end_line in matches:
        with open(f'{docs_source_path_}/{match}', 'r') as handle:
            include_text = handle.read()
        rst_ = rst_.replace(f'{indent_}.. include:: {match}', indent(dedent(include_text), indent_))
    return rst_


def skip_prefix_new_lines(txt: str) -> str:
    txt = re.sub(r'\A[\n]+', '', txt)
    return txt


def replace_3_newlines_and_more_with_2_newlines(txt: str) -> str:
    for i in range(10, 2, -1):
        txt = txt.replace(i * '\n', '\n\n')
    return txt


if __name__ == '__main__':
    INDENT_LEN_3 = 3 * ' '
    INDENT_LEN_4 = 4 * ' '
    docs_source_path = 'source'
    # docs_source_path = 'docs/source'
    warning_text = '# ---------------------------------------------------------------------------------------------------------\n' \
                   '# Warning: This file is NOT supposed to be edited directly, ' \
                   'but instead regenerated via `tox -e py-docs`\n' \
                   '# ---------------------------------------------------------------------------------------------------------\n'
    output_text = 'from typing import Dict\n\n' + warning_text

    # build short docs
    output_text += '\nshort_docs: Dict[str, str] = {\n'
    short_docs_rst_file = docs_source_path + '/short_docs.rst'
    with open(short_docs_rst_file, 'r') as f:
        rst = f.read()
    rst = skip_or_replace_unparseable_directives(rst)
    html = rst2html(rst)
    plain_text = html2txt(html)
    plain_text = skip_prefix_new_lines(plain_text)
    command_and_short_docs = re.findall(r'\* `([a-z-]*)`.*-- (.*)', plain_text)
    for command, short_doc in command_and_short_docs:
        output_text += f'{INDENT_LEN_4}"{command}": "{short_doc}",\n'
    output_text += '}'

    # build long docs
    output_text += '\n\nlong_docs: Dict[str, str] = {\n'
    path = docs_source_path + '/cli_help'
    commands_and_file_paths = {f.split('.')[0]: join(path, f) for f in sorted(os.listdir(path)) if isfile(join(path, f))}

    command = 'github'
    commands_and_file_paths = {command: path + f'/{command}.rst'}
    for command, file in commands_and_file_paths.items():
        with open(file, 'r') as f:
            rst = f.read()

        rst = skip_or_replace_unparseable_directives(rst)
        rst = resolve_includes(rst_=rst, docs_source_path_=docs_source_path)

        html = rst2html(rst)

        plain_text = html2txt(html)
        plain_text = skip_prefix_new_lines(plain_text)
        plain_text = plain_text.replace('---', '—')

        output_text += f'{INDENT_LEN_4}"{command}": """\n' + indent(plain_text, 2 * INDENT_LEN_4) + '\n   """,\n'
        output_text = replace_3_newlines_and_more_with_2_newlines(output_text)

    output_text += '}'
    print(output_text)
