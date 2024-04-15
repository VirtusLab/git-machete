#!/usr/bin/env python3

import re
from os import path

from setuptools import setup

from git_machete import __version__

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), mode="r", encoding="utf-8") as f:
    # PyPI webpage seems to be always served with white background, let's remove the GitHub-specific dark variants of images.
    long_description = re.sub("(?m)^.*#gh-dark-mode-only.*\n", "", f.read())

setup(
    name='git-machete',
    version=__version__,
    description='Probably the sharpest git repository organizer & rebase/merge workflow automation tool you\'ve ever seen',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='VirtusLab',
    author_email='gitmachete@virtuslab.com',
    url='https://github.com/VirtusLab/git-machete',
    license='MIT',
    keywords='git',
    # Non-python directories are only included in `packages` for the sake of bdist_wheel;
    # they have apparently no effect on sdists (only MANIFEST.in matters).
    packages=['git_machete', 'completion', 'docs/man'],
    entry_points={
        'console_scripts': [
            'git-machete = git_machete.bin:main'
        ]
    },
    python_requires='>=3.6, <4',
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent'
    ],
    # This is a pure-Python but NOT universal wheel:
    # https://realpython.com/python-wheels/#different-types-of-wheels
    options={'bdist_wheel': {'universal': False}},
    include_package_data=True
)
