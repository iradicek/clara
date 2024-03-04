#!/usr/bin/env python

from Cython.Build import cythonize
from setuptools import setup
from setuptools.extension import Extension

extensions = Extension('clara.pylpsolve', ['clara/pylpsolve.pyx'],
                       libraries=['lpsolve55'], library_dirs=['/usr/lib/lp_solve'])

setup(name='clara',
      version='1.0',
      description='CLuster And RepAir tool for introductory \
programming assignments',
      author='Ivan Radicek',
      author_email='radicek@forsyte.at',
      url='https://github.com/iradicek/clara',
      packages=['clara'],
      ext_modules=cythonize(extensions, compiler_directives={'language_level' : "3"}),
      install_requires=['pycparser', 'zss'],
      scripts=['bin/clara']
      )
