#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

extensions = ['sphinx.ext.imgmath',
    'sphinx.ext.viewcode']
templates_path = []
source_suffix = '.rst'
master_doc = 'index'
project = 'Mailu'
copyright = '2017, Mailu authors'
author = 'Mailu authors'
version = release = 'latest'
language = None
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
pygments_style = 'sphinx'
todo_include_todos = False
html_theme = 'sphinx_rtd_theme'
html_static_path = []
htmlhelp_basename = 'Mailudoc'

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
html_sidebars = {
    '**': [
        'relations.html',  # needs 'show_related': True theme option to display
        'searchbox.html',
    ]
}
