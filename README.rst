Conda-Pack
==========

``conda-pack`` is a command line tool for creating relocatable conda
environments. This is useful for deploying code in a consistent environment,
potentially in a location where python/conda isn't already installed.


Install
-------

Currently there is no release. The easiest way to install is to ``pip install``
from the git repo:

.. code:: bash

    pip install git+https://github.com/jcrist/conda-pack.git

It's recommended to install in your root conda environment - the ``conda-pack``
command will then be available in all sub-environments as well.

Usage
-----

On the source machine

.. code:: bash

    # Pack environment my_env into my_env.zip
    $ conda-pack -n my_env

    # Pack environment my_env into out_name.zip
    $ conda-pack -n my_env -o new_name.zip

    # Pack environment located at an explicit path into my_env.zip
    $ conda-pack -p /explicit/path/to/my_env

On the target machine

.. code:: bash

    # Unpack environment
    $ unzip my_env.zip

    # Use python without activating or fixing the prefixes. Most python
    # libraries will work fine, but things that require prefix cleanups
    # will fail.
    $ ./myenv/bin/python

    # Activate the environment. This adds `myenv/bin` to your path
    $ source myenv/bin/activate

    # Run python from in the environment
    (myenv) $ python

    # Cleanup prefixes from in the active environment.
    # Note that you can run this script without activating via
    # `$ ./myenv/bin/python myenv/bin/conda-unpack`
    (myenv) $ conda-unpack

    # At this point the environment is exactly as if you installed it here
    # using conda directly. All scripts should work fine.
    (myenv) $ ipython --version

    # Deactivate the environment to remove it from your path
    (myenv) $ source myenv/bin/deactivate

Caveats
-------

This tool is extremely new, and has a few caveats.

- Conda must be installed and be on your path.

- The os *type* where the environment was built must match the os *type* of the
  target. This means that environments built on windows can't be relocated to
  linux.
