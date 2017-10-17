Conda-Pack
==========

``conda-pack`` is a command line tool for creating relocatable conda
environments. This is useful for deploying code in a consistent environment,
potentially in a location where python/conda isn't already installed.

Usage
-----

On the source machine

.. code:: bash

    # Pack environment my_env into my_env.zip
    $ conda-pack -n my_env

    # Pack environment my_env into out_name.zip
    $ conda-pack -n my_env -o new_name.zip

    # Pack environment located at an explicit path into
    # my_env.zip
    $ conda-pack -p /explicit/path/to/my_env

On the target machine

.. code:: bash

    # Unpack environment
    $ unzip my_env.zip

    # If conda is installed, you can just `source activate` the path
    # (or `activate` on windows)
    $ source activate ./my_env

    # If conda is not installed, you can run python at ./my_env/bin/python
    # All imports will be contained in the packed repos
    $ ./my_env/bin/python

Caveats
-------

This tool is extremely new, and has a few (sometimes fixable) caveats.

- Conda must be installed and be on your path.

- The os *type* where the environment was built must match the os *type* of the
  target. This means that environments built on windows can't be relocated to
  linux.

- Shebang headers (e.g. ``#! /home/ubuntu/dev/bin/python``) aren't rewritten,
  meaning certain *scripts* won't relocate well. Since the primary intention of
  this is relocating python libraries this caveat shouldn't be an issue. This
  is fixable, but isn't high priority.
