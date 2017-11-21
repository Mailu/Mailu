#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

extensions = ['sphinx.ext.imgmath', 'sphinx.ext.viewcode']
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
html_title = 'Mailu, Docker based mail server'
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
