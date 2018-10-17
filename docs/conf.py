#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

extensions = ['sphinx.ext.imgmath', 'sphinx.ext.viewcode']
templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
project = 'Mailu'
copyright = '2018, Mailu authors'
author = 'Mailu authors'
version = release = 'latest'
language = None
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
pygments_style = 'sphinx'
todo_include_todos = False
html_theme = 'sphinx_rtd_theme'
html_title = 'Mailu, Docker based mail server'
html_static_path = []
htmlhelp_basename = 'Mailudoc'

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
html_sidebars = {
    '**': [
        'relations.html', 
        'searchbox.html',
    ]
}

# Theme options
html_context = {
    'display_github': True,
    'github_user': 'mailu',
    'github_repo': 'mailu',
    'github_version': 'master',
    'conf_py_path': '/docs/'
}
