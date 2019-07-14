#!/usr/bin/env python

from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="podop",
    version="0.2.5",
    description="Postfix and Dovecot proxy",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Pierre Jaury",
    author_email="pierre@jaury.eu",
    url="https://github.com/mailu/podop.git",
    packages=["podop"],
    include_package_data=True,
    scripts=["scripts/podop"],
    install_requires=[
        "aiohttp"
    ]
)
