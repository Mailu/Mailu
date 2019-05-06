#!/usr/bin/env python

from distutils.core import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="socrate",
    version="0.1",
    description="Socrate daemon utilities",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Pierre Jaury",
    author_email="pierre@jaury.eu",
    url="https://github.com/mailu/socrate.git",
    packages=["socrate"],
    include_package_data=True,
    install_requires=[
        "jinja2",
        "importlib",
        "tenacity"
    ]
)
