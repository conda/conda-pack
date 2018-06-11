Conda-Pack
==========

|Build Status|

``conda-pack`` is a command line tool for creating relocatable conda
environments. This is useful for deploying code in a consistent environment,
potentially in a location where python/conda isn't already installed.


Install
-------

Currently there is no release. The easiest way to install is to ``pip install``
from the git repo:

.. code:: bash

    pip install git+https://github.com/conda/conda-pack.git

It's recommended to install in your root conda environment - the ``conda-pack``
command will then be available in all sub-environments as well.

Usage
-----

On the source machine

.. code:: bash

    # Pack environment my_env into my_env.tar.gz
    $ conda-pack -n my_env

    # Pack environment my_env into out_name.tar.gz
    $ conda-pack -n my_env -o new_name.tar.gz

    # Pack environment located at an explicit path into my_env.tar.gz
    $ conda-pack -p /explicit/path/to/my_env

On the target machine

.. code:: bash

    # Unpack environment into directory `my_env`
    $ mkdir -p my_env
    $ tar -xzf my_env.tar.gz -C my_env

    # Use python without activating or fixing the prefixes. Most python
    # libraries will work fine, but things that require prefix cleanups
    # will fail.
    $ ./my_env/bin/python

    # Activate the environment. This adds `my_env/bin` to your path
    $ source my_env/bin/activate

    # Run python from in the environment
    (my_env) $ python

    # Cleanup prefixes from in the active environment.
    # Note that you can run this script without activating via
    # `$ ./my_env/bin/python my_env/bin/conda-unpack`
    (my_env) $ conda-unpack

    # At this point the environment is exactly as if you installed it here
    # using conda directly. All scripts should work fine.
    (my_env) $ ipython --version

    # Deactivate the environment to remove it from your path
    (my_env) $ source my_env/bin/deactivate

Caveats
-------

This tool is extremely new, and has a few caveats.

- Conda must be installed and be on your path.

- Windows is not currently supported (should be easy to fix, contributions
  welcome!)

- The os *type* where the environment was built must match the os *type* of the
  target. This means that environments built on windows can't be relocated to
  linux.

.. |Build Status| image:: https://travis-ci.org/conda/conda-pack.svg?branch=master
   :target: https://travis-ci.org/conda/conda-pack
