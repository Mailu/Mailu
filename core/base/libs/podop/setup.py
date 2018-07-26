#!/usr/bin/env python

from distutils.core import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="podop",
    version="0.2",
    description="Postfix and Dovecot proxy",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Pierre Jaury",
    author_email="pierre@jaury.eu",
    url="https://github.com/mailu/podop.git",
    packages=["podop"],
    scripts=["scripts/podop"],
    install_requires=[
        "aiohttp"
    ]
)
