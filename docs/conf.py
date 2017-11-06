#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import os, sys, docutils

sys.path.append(os.path.dirname(__file__))
extensions = ['sphinx.ext.imgmath', 'sphinx.ext.viewcode', 'conf']
templates_path = ['_templates']
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

# Theme options
html_context = {
    'display_github': True,
    'github_user': 'mailu',
    'github_repo': 'mailu',
    'github_version': 'master',
    'conf_py_path': '/docs/'
}


def setup(app):
    """ The conf itself is an extension for parsing rst.
    """
    def rstjinja(app, docname, source):
        """ Render our pages as a jinja template for fancy templating.
        """
        if app.builder.format != 'html':
            return
        source[0] = app.builder.templates.render_string(
            source[0], app.config.html_context)

    app.connect("source-read", rstjinja)


# Upload function when the script is called directly
if __name__ == "__main__":
    import os, sys, paramiko
    build_dir, hostname, username, password, dest_dir = sys.argv[1:]
    transport = paramiko.Transport((hostname, 22))
    transport.connect(username=username, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    os.chdir(build_dir)
    for dirpath, dirnames, filenames in os.walk("."):
        remote_path = os.path.join(dest_dir, dirpath)
        try:
            sftp.mkdir(remote_path)
        except:
            pass
        for filename in filenames:
            sftp.put(
                os.path.join(dirpath, filename),
                os.path.join(remote_path, filename)
            )
