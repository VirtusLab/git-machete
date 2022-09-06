import re
import sys
from textwrap import dedent, indent
from os import listdir
from os.path import isfile, join
from bs4 import BeautifulSoup
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
    # html_elements.replace(u'\xa0', ' ')

    for tag in html_elements.select('style'):
        tag.decompose()

    for tag in html_elements.select('td'):
        if tag.text == u'\xa0':
            tag.decompose()
        else:
            if 'class' not in tag.attrs:
                new_tag = html_elements.new_tag('td')
                new_tag.string = '\n      ' + tag.text
                tag.replace_with(new_tag)

    for tag in html_elements.select('tt'):
        new_tag = html_elements.new_tag('cite')
        new_tag.string = '`' + tag.text + '`'
        tag.replace_with(new_tag)

    for tag in html_elements.select('span'):
        if 'class' in tag.attrs:
            if ' '.join(tag.attrs['class']) == 'option':
                new_tag = html_elements.new_tag('strong')
                new_tag.string = tag.text
                tag.replace_with(new_tag)

    for tag in html_elements.select('strong'):
        new_tag = html_elements.new_tag('strong')
        new_tag.string = '<b>' + tag.text + '</b>'
        tag.replace_with(new_tag)

    for tag in html_elements.select('kbd'):
        new_tag = html_elements.new_tag('kbd')
        new_tag.string = '\n   ' + tag.text.strip()
        tag.replace_with(new_tag)

    for tag in html_elements.select('dt'):
        new_tag = html_elements.new_tag('dt')
        new_tag.string = '   ' + tag.text.strip()
        tag.replace_with(new_tag)

    # for tag in html_elements.select('div'):
    #     if 'class' in tag.attrs:
    #         if 'admonition note' in ' '.join(tag.attrs['class']):
    #             new_tag = html_elements.new_tag('div')
    #             # new_tag.string = '\n' + indent(tag.text, '   ')
    #             new_tag.string = '\n' + tag.text
    #             tag.replace_with(new_tag)

    for tag in html_elements.select('pre'):
        if 'class' in tag.attrs:
            if ' '.join(tag.attrs['class']) == 'code shell literal-block':
                new_tag = html_elements.new_tag('pre', attrs={"class": "code shell literal-block"})
                new_tag.string = '<b>' + indent(tag.text, '  ') + '</b>'
                tag.replace_with(new_tag)
            elif 'literal-block' in ' '.join(tag.attrs['class']):
                new_tag = html_elements.new_tag('pre', attrs={"class": "code literal-block"})
                new_tag.string = '\n<dim>' + indent(tag.text, '  ') + '</dim>'
                tag.replace_with(new_tag)

    for tag in html_elements.select('span'):
        new_tag = None
        if 'class' in tag.attrs:
            if ' '.join(tag.attrs['class']) == 'green':
                new_tag = html_elements.new_tag('span', attrs={"class": "green"})
                new_tag.string = AnsiEscapeCodes.GREEN + tag.text + AnsiEscapeCodes.ENDC
            elif ' '.join(tag.attrs['class']) == 'yellow':
                new_tag = html_elements.new_tag('span', attrs={"class": "yellow"})
                new_tag.string = AnsiEscapeCodes.YELLOW + tag.text + AnsiEscapeCodes.ENDC
            elif ' '.join(tag.attrs['class']) == 'red':
                new_tag = html_elements.new_tag('span', attrs={"class": "red"})
                new_tag.string = AnsiEscapeCodes.RED + tag.text + AnsiEscapeCodes.ENDC
            elif ' '.join(tag.attrs['class']) == 'gray':
                new_tag = html_elements.new_tag('span', attrs={"class": "gray"})
                new_tag.string = AnsiEscapeCodes.DIM + tag.text + AnsiEscapeCodes.ENDC
            if new_tag:
                tag.replace_with(new_tag)

    text: str = ''
    for html_element in html_elements.descendants:
        if isinstance(html_element, str):
            # if len(html_element) > 1:
            #     if '\n\n' in html_element:
            #         new_text = html_element.replace('\n\n', '\n')
            #     else:
            #         new_text = html_element.replace('\n', '')
            # else:
            #     new_text = html_element

            # if html_element != '\n' and '\n' in html_element:
            #     new_text = html_element
            # else:
            #     new_text = html_element.replace('\n', '')

            # if html_element == '\n':
            #     new_text = ''

            # if inside_code:
            #     new_text = html_element
            # else:
            #     new_text = html_element.replace('\n', '')

            # new_text = html_element.replace('\n', '')

            # if prev_tag is None:
            #     new_text = html_element.replace('\n', '')
            # else:
            #     new_text = html_element

            if html_element != '\n':
                new_text = html_element
            else:
                new_text = html_element.replace('\n', '')

            # if prev_tag == 'code':
            #     new_text = indent(html_element, '  ')
            # if prev_tag == 'code_shell':
            #     new_text = html_element

            text += new_text

            # if prev_tag == 'kbd':
            #     text += '\n'

            # prev_tag = None
            # append at the end of the tag's value
            # if prev_tag == 'strong':
            #     text += '</b>'
            #     prev_tag = None
        #     elif prev_tag == 'cite':
        #         text += ''
        #     elif prev_tag == 'code':
        #         text += '</dim>'
        #         prev_tag = None

        # append at the beginning of the tag's value
        # elif html_element.name in ['kbd']:
        #     text += '\n   '
        #     prev_tag = 'kbd'
        # elif html_element.name in ['td']:
        #     text += '   '  # not sure if its possible to even them out
        elif html_element.name in ['p']:
            if 'class' in html_element.attrs:
                if ' '.join(html_element.attrs['class']) == 'first':
                    text += ' '
                else:
                    text += '\n'
            else:
                text += '\n\n'
        # elif html_element.name in ['dl']:
        #     text += '\n'
        elif html_element.name in ['dt']:
            text += '\n'
            # text += '\n   '
        elif html_element.name in ['dd']:
            text += '\n      '
        elif html_element.name == 'li':
            if html_element.parent.parent.name == 'li':  # deal with nested lists
                text += '\n   - '
            else:
                text += '\n* '

        # # another approach
        # elif html_element.name in ['kbd']:
        #     text += '   '
        #     prev_tag = 'kbd'
        # # elif html_element.name in ['td']:
        # #     text += '   '  # not sure if its possible to even them out
        # elif html_element.name in ['p']:
        #     if 'class' in html_element.attrs:
        #         if ' '.join(html_element.attrs['class']) == 'first':
        #             text += ' '
        #         else:
        #             text += ''
        #     else:
        #         text += ''
        #     prev_tag = 'p'
        # elif html_element.name in ['dt']:
        #     prev_tag = 'dt'
        #     text += '   '
        # elif html_element.name in ['table']:
        #     prev_tag = 'table'
        # elif html_element.name in ['tt']:
        #     prev_tag = 'tt'
        #     text += ''
        # elif html_element.name in ['dd']:
        #     text += '      '
        #     prev_tag = 'dd'
        # elif html_element.name == 'ul':
        #     prev_tag = 'ul'
        # elif html_element.name == 'li':
        #     if html_element.parent.parent.name == 'li':  # deal with nested lists
        #         text += '      - '
        #     else:
        #         text += '   * '
        #     prev_tag = 'li'
        # elif html_element.name == 'ol':
        #     prev_tag = 'ol'

        # elif html_element.name == 'strong':
        #     prev_tag = 'strong'
        #     text += '<b>'
        # elif html_element.name == 'pre':
        #     if 'literal-block' in ' '.join(html_element.attrs['class']):
        #         if 'shell' in ' '.join(html_element.attrs['class']):
        #             text += ' '
        #             prev_tag = 'code_shell'
                # else:
                #     text += '\n<dim>'
                #     prev_tag = 'code'
        # elif html_element.name == 'cite':
        #     text += ''
        #     prev_tag = 'cite'
        # elif html_element.name == 'div':
        #     if ' '.join(html_element.attrs['class']) == 'admonition note':
        #         prev_tag = 'note'
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


def skip_holes(txt: str) -> str:
    txt = txt.replace(5 * '\n', '\n\n')\
        .replace(4 * '\n', '\n\n')\
        .replace(3 * '\n', '\n\n')
    return txt


# def random_character_fixes(txt: str) -> str:
#     txt = txt.replace('---', '-')
#     return txt


if __name__ == '__main__':
    if len(sys.argv) == 2:
        save_regenerated_docs = False if sys.argv[1] == 'dont_save' else True
    else:
        save_regenerated_docs = True
    verbose = False
    output_docs_path = 'git_machete/docs.py'
    docs_source_path = 'docs/source'
    short_docs_path = 'git_machete/short_docs.py'
    with open(short_docs_path, 'r') as f:
        short_docs = f.read()
    warning_text = '# ---------------------------------------------------------------------------------------------------------\n' \
                   '# Warning: This file is NOT supposed to be edited directly, ' \
                   'but instead regenerated via tox -e docs\n' \
                   '# ---------------------------------------------------------------------------------------------------------\n'
    output_text = short_docs + '\n' + warning_text + '\n\nlong_docs: Dict[str, str] = {\n'
    path = docs_source_path + '/cli_help'
    commands_and_file_paths = {f.split('.')[0]: join(path, f) for f in sorted(listdir(path)) if isfile(join(path, f))}

    # # NOTE: run generation for single command
    # cmd = 'anno'
    # commands_and_file_paths = {cmd: f'docs/source/cli_help/{cmd}.rst'}
    for command, file in commands_and_file_paths.items():
        with open(file, 'r') as f:
            rst = f.read()

        rst = skip_or_replace_unparseable_directives(rst)
        rst = resolve_includes(rst=rst, docs_source_path=docs_source_path)
        if verbose:
            print(rst)
        html = rst2html(rst)['body']
        if verbose:
            print(html)
        # print('\n\n\n)
        plain_text = html2txt(html)
        # plain_text = plain_text.replace(20*' ', '\n'+20*' ')
        plain_text = skip_holes(plain_text)
        plain_text = skip_prefix_new_lines(plain_text)
        plain_text = plain_text.replace('---', '-')
        # plain_text = random_character_fixes(plain_text)
        # print(plain_text)
        output_text += f'    "{command}": """\n' + indent(plain_text, '        ') + '\n   """,\n'

    output_text += '}\n'
    if save_regenerated_docs:
        with open(output_docs_path, 'w') as f:
            f.write(output_text)

    print(output_text)

#   TO REVIEW / FIX:
#   - github


# if __name__ == '__main__':
#     from git_machete.long_docs import long_docs
#     from git_machete.docs import long_docs
#
#     for k, v in long_docs.items():
#         print(k)
#         print(v)
#         print()
