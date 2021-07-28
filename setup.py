#!/usr/bin/env python

from os import path
from setuptools import setup

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md')) as f:
    long_description = f.read()

with open(path.join(this_directory, 'VERSION')) as f:
    version_no = f.readline().strip()

setup(
    name='git-machete',
    version=version_no,
    description='Probably the sharpest git repository organizer & rebase/merge workflow automation tool you\'ve ever seen',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Pawel Lipski',
    author_email='pawel.p.lipski@gmail.com',
    url='https://github.com/VirtusLab/git-machete',
    license='MIT',
    keywords='git',
    packages=['git_machete'],
    scripts=['git-machete'],
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
    options={'bdist_wheel': {'universal': '1'}},
    package_data={'git-machete': ['VERSION']},
    include_package_data=True
)
