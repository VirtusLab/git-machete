#!/usr/bin/env python

from git_machete import __version__
import setuptools

setuptools.setup(setup_requires=['pbr'], pbr=True, version=__version__)
