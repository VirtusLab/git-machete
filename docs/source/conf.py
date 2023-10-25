import os
import sys

# -- Path setup --------------------------------------------------------------

sys.path.append(os.path.join(os.path.abspath('../..')))

import git_machete  # noqa: E402

# -- Project information -----------------------------------------------------

project = 'git-machete'
copyright = '2017-2023, VirtusLab'
author = 'VirtusLab'
release = git_machete.__version__

# -- General configuration ---------------------------------------------------

# We switched from sphinx_rtd_theme to sphinx_book_theme
# following https://github.com/readthedocs/sphinx_rtd_theme/issues/455#issuecomment-1462174583
extensions = ["sphinx_book_theme"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['cli']

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinx_book_theme"

html_logo = "../../graphics/logo/svg/512x512.svg"

html_theme_options = {
    "show_navbar_depth": 2,
    "logo": {
        "image_dark": "../../graphics/logo/svg/512x512-dark.svg",
        "text": "git-machete v" + release,
    },
    # See https://github.com/pydata/pydata-sphinx-theme/issues/1492.
    # Mostly added to avoid a warning coming from pydata-sphinx-theme==0.14.2.
    "navigation_with_keys": False,
}

# To make sure the dark logo is included in _static/ directory in the generated docs
html_static_path = ["../../graphics/logo/svg/"]
