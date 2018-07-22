#!/usr/bin/env python

from distutils.core import setup

setup(
    name="Podop",
    version="0.1",
    description="Postfix and Dovecot proxy",
    author="Pierre Jaury",
    author_email="pierre@jaury.eu",
    url="https://github.com/mailu/podop.git",
    packages=["podop"],
    scripts=["scripts/podop"]
)
