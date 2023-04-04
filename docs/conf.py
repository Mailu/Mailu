#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import os

extensions = ['sphinx.ext.imgmath', 'sphinx.ext.viewcode', 'sphinx_rtd_theme']
templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
project = 'Mailu'
copyright = '2016, Mailu authors'
author = 'Mailu authors'
version = release = os.environ.get('VERSION', 'master')
language = 'en'
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', 'Dockerfile', 'docker-compose.yml']
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
    'github_version': version,
    'stable_version': '2.0',
    'versions': [
        ('1.9', '/1.9/'),
        ('2.0', '/2.0/'),
        ('master', '/master/')
    ],
    'conf_py_path': '/docs/'
}
