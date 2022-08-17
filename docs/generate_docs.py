

# def parse_rst(file: str):
#     with open(file)

import re
from textwrap import indent

import docutils.nodes
import docutils.parsers.rst
import docutils.utils
import docutils.frontend

from bs4 import BeautifulSoup


from utils import AnsiEscapeCodes

from docutils import core, io


# TODO
# - colors
# - include
# - status_extraSpaceBeforeBranchName_config_key
# - kolory i inne rzeczy przed **YSAGE

def html_parts(input_string, source_path=None, destination_path=None,
               input_encoding='unicode', doctitle=True,
               initial_header_level=1):
    """
    Given an input string, returns a dictionary of HTML document parts.

    Dictionary keys are the names of parts, and values are Unicode strings;
    encoding is up to the client.

    Parameters:

    - `input_string`: A multi-line text string; required.
    - `source_path`: Path to the source file or object.  Optional, but useful
      for diagnostic output (system messages).
    - `destination_path`: Path to the file or object which will receive the
      output; optional.  Used for determining relative paths (stylesheets,
      source links, etc.).
    - `input_encoding`: The encoding of `input_string`.  If it is an encoded
      8-bit string, provide the correct encoding.  If it is a Unicode string,
      use "unicode", the default.
    - `doctitle`: Disable the promotion of a lone top-level section title to
      document title (and subsequent section title to document subtitle
      promotion); enabled by default.
    - `initial_header_level`: The initial level for header elements (e.g. 1
      for "<h1>").
    """
    overrides = {'input_encoding': input_encoding,
                 'doctitle_xform': doctitle,
                 'initial_header_level': initial_header_level}
    parts = core.publish_parts(
        source=input_string, source_path=source_path,
        destination_path=destination_path,
        writer_name='html', settings_overrides=overrides)
    return parts


def parse_html(html):


    elem = BeautifulSoup(html, features="html.parser")
    text = ''
    prev_tag = None
    for e in elem.descendants:
        if isinstance(e, str):
            new_text = e.strip()
            if prev_tag == 'code':
                new_text = indent(e.strip(), '  ')

            text += new_text

            if prev_tag == 'strong':
                text += '</b>'
            elif prev_tag == 'tt':
                text += '` '
            elif prev_tag == 'cite':
                text += ' '
            elif prev_tag == 'code':
                text += '\n</dim>'
            elif prev_tag == 'color':
                text += AnsiEscapeCodes.ENDC + ' '

            prev_tag = None

        elif e.name in ['kbd']:
            text += '\n\t'
        elif e.name in ['td']:
            text += '\t'  # not sure if its possible to even them out
        elif e.name in ['p']:
            text += '\n\n'
        elif e.name in ['dt']:
            text += '\n\t'
        elif e.name in ['dd']:
            text += '\n\t\t'
        elif e.name == 'li':
            text += '\n\t* '
        elif e.name == 'strong':
            prev_tag = 'strong'
            text += '<b>'
        elif e.name == 'pre':
            if ' '.join(e.attrs['class']) == 'code shell literal-block':
                text += ' '
            elif ' '.join(e.attrs['class']) == 'code literal-block':
                text += '\n<dim>\n'
                prev_tag = 'code'
        elif e.name == 'cite':
            text += ' '
            prev_tag = 'cite'
        elif e.name == 'tt':
            text += ' `'
            prev_tag = 'tt'
        elif e.name == 'span':
            if ' '.join(e.attrs['class']) == 'green':
                text += ' ' + AnsiEscapeCodes.GREEN
                prev_tag = 'color'
            if ' '.join(e.attrs['class']) == 'yellow':
                text += ' ' + AnsiEscapeCodes.YELLOW
                prev_tag = 'color'
            if ' '.join(e.attrs['class']) == 'red':
                text += ' ' + AnsiEscapeCodes.RED
                prev_tag = 'color'
            if ' '.join(e.attrs['class']) == 'grey':
                text += ' ' + AnsiEscapeCodes.DIM
                prev_tag = 'color'
    return text


if __name__ == '__main__':
    from os import listdir
    from os.path import isfile, join

    output_docs_path = '../git_machete/long_docs.py'
    with open(output_docs_path, 'w') as f:
        f.write('from typing import Dict\n\n')
        f.write('long_docs: Dict[str, str] = {\n')

    path = 'source/cli_help'
    commands_and_file_paths = {f.split('.')[0]: join(path, f) for f in sorted(listdir(path)) if isfile(join(path, f))}

    # TODO REMOVE LATER
    # cmd = 'github'
    # commands_and_file_paths = {cmd: f'source/cli_help/{cmd}.rst'}
    for command, file in commands_and_file_paths.items():
        with open(file, 'r') as f:
            text = f.read()

        # skip ref
        text = text.replace(':ref:', '')

        # inlcudes
        matches = re.findall(r'\.\. include:: (.*)', text)
        for match in matches:
            with open(f'source/{match}', 'r') as handle:
                include_text = handle.read()
            text = text.replace(f'.. include:: {match}', include_text)

        parts = html_parts(text)
        html = parts['body']
        print(html)
        print()
        # print()

        output_text = parse_html(html)
        # print(output_text)
        # print()

        with open(output_docs_path, 'a') as f:
            f.write(f'\t"{command}": """')
            f.write(indent(output_text, '\t\t'))
            f.write('\t""",\n')

    with open(output_docs_path, 'a') as f:
        f.write('}\n')


if __name__ == '__main__':
    from git_machete.long_docs import long_docs

    for k, v in long_docs.items():
        print(k)
        print(v)
        print()