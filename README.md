![Build and test](https://github.com/iradicek/clara/workflows/Build%20and%20test/badge.svg?branch=master)

**CL**uster **A**nd **R**ep**A**ir tool for introductory programming assignments

About
=====
This is an implementation of the clustering and repair tool for introductory
programming assignments, described in the following paper:
*Automated Clustering and Program Repair forIntroductory Programming Assignments*
(https://dl.acm.org/doi/10.1145/3192366.3192387 and https://arxiv.org/abs/1603.03165).


Dependencies
============
- C compiler
- Cython
  - `$ sudo aptitude install cython` (Debian)
  - `# dnf install Cython` (Fedora)
- lpsolve 5.5 (development files and library)
  - `$ sudo aptitude install lp-solve liblpsolve55-dev` (Debian)
  - `# dnf install lpsolve-devel` (Fedora)


Installation & running
======================
- `make` (in this directory) installs a binary file called `clara`
- Run `clara help` or see examples below.


Development
===========
- Create a new virtual environment (using `virtualenv`)
- Install `Cython` (using `pip install Cython` inside the new virtual enviroment)
- Run `python setup.py develop`


Debian note
===========
On Debian system the following is required before running the tool: `export LD_LIBRARY_PATH=/usr/lib/lp_solve/`


Examples
========
The `examples/` directory contains some example programs:
- `c1.py` and `c2.py` are the correct examples from the paper
- `i1.py` and `i2.py` are the incorrect example from the paper
- `c3.py` is a constructed example.

Matching
--------

To test matching between `examples/c1.py` and `examples/c2.py` on inputs `[4.5]` and `[1.0,3.0,5.5]` use:
```
clara match examples/c1.py examples/c2.py --entryfnc computeDeriv --args "[[[4.5]], [[1.0,3.0,5.5]]]" --ignoreio 1
```

This should output `Match!`.

To test matching between `examples/c1.py` and `examples/c3.py` on inputs `[4.5]` and `[1.0,3.0,5.5]` use:
```
clara match examples/c1.py examples/c3.py --entryfnc computeDeriv --args "[[[4.5]], [[1.0,3.0,5.5]]]" --ignoreio 1
```

This should output `No match!`.

Repair (on two programs)
------------------------

To repair `examples/i1.py` using `examples/c1.py` on the same inputs as above, use:
```
clara repair examples/c1.py examples/i1.py --entryfnc computeDeriv --args "[[[4.5]], [[1.0,3.0,5.5]]]" --ingoreio 1
```

Clustering
----------

To cluster correct programs on the same inputs as above use:
```
mkdir clusters
clara cluster examples/c*.py --clusterdir clusters --entryfnc computeDeriv --args "[[[4.5]], [[1.0,3.0,5.5]]]" --ignoreio 1
```

This should produce two clusters in the directroy `clusters/` and two `.json` files with additional experssion extracted from the clusters.

Feedback
--------

To produce feedback from the above clusters for an incorrect program, for example `examples/i1.py`, use:
```
clara feedback clusters/c*.py examples/i1.py --entryfnc computeDeriv --args "[[[4.5]], [[1.0,3.0,5.5]]]" --ignoreio 1 --feedtype python
```

Note
----

You can add `--verbose 1` to any of the examples to obtain a more verbose output.

Known issues
------------
Does not work on Python 3.8.
