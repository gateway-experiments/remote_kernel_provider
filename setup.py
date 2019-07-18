#!/usr/bin/env python
# coding: utf-8

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from __future__ import print_function

# the name of the project
name = 'remote_kernel_provider'

import os
import sys
from setuptools import setup
from setuptools.command.bdist_egg import bdist_egg
from setuptools.command.test import test as TestCommand

v = sys.version_info
if v[:2] < (3, 4):
    error = "ERROR: %s requires Python version 3.4 or above." % name
    print(error, file=sys.stderr)
    sys.exit(1)

pjoin = os.path.join
here = os.path.abspath(os.path.dirname(__file__))
pkg_root = pjoin(here, name)

packages = []
for d, _, _ in os.walk(pjoin(here, name)):
    if os.path.exists(pjoin(d, '__init__.py')):
        packages.append(d[len(here) + 1:].replace(os.path.sep, '.'))

version_ns = {}
with open(pjoin(here, name, '_version.py')) as f:
    exec(f.read(), {}, version_ns)


class bdist_egg_disabled(bdist_egg):
    """Disabled version of bdist_egg

    Prevents setup.py install from performing setuptools' default easy_install,
    which it should never ever do.
    """
    def run(self):
        sys.exit("Aborting implicit building of eggs. Use `pip install .` to install from source.")


# From https://pytest.readthedocs.io/en/2.7.3/goodpractises.html
class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # use import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main([self.pytest_args])
        sys.exit(errno)


setup_args = dict(
    name             = name,
    version          = version_ns['__version__'],
    packages         = packages,
    description      = "Jupyter protocol implementation and client libraries",
    author           = 'Jupyter Development Team',
    author_email     = 'jupyter@googlegroups.com',
    url              = 'https://jupyter.org',
    license          = 'BSD',
    classifiers      = [
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],
    install_requires = [
        'ipython_genutils>=0.2.0',
        'jupyter_core>=4.4.0',
        'jupyter_kernel_mgmt>=0.3.0',
        'paramiko>=2.4.0',
        'pexpect>=4.2.0',
        'pycrypto>=2.6.1',
        'tornado>=5.1',
        'traitlets>=4.3.2',
    ],
    tests_require    = [
        'mock',
        'pytest'
    ],
    python_requires  = ">=3.4",
    cmdclass         = {
        'bdist_egg': bdist_egg if 'bdist_egg' in sys.argv else bdist_egg_disabled,
        'test': PyTest,
    },
    include_package_data = True,
)


if __name__ == '__main__':
    setup(**setup_args)
