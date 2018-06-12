Conda-Pack
==========

``conda-pack`` is a command line tool for creating relocatable conda
environments. This is useful for deploying code in a consistent environment,
potentially in a location where python/conda isn't already installed.

Installation
------------

It's recommended to install in your root conda environment - the ``conda pack``
command will then be available in all sub-environments as well.

**Install from source:**

Conda-Pack is `available on github <https://github.com/conda/conda-pack>`_ and
can always be installed from source.


.. code::

    pip install git+https://github.com/conda/conda-pack.git


Commandline Usage
-----------------

Conda-Pack is primarily a commandline tool. Full CLI docs can be found
:doc:`here <cli>`.

One common use case is packing an environment on one machine to distribute to
other machines that may not have conda/python installed.

On the source machine

.. code-block:: bash

    # Pack environment my_env into my_env.tar.gz
    $ conda pack -n my_env

    # Pack environment my_env into out_name.tar.gz
    $ conda pack -n my_env -o new_name.tar.gz

    # Pack environment located at an explicit path into my_env.tar.gz
    $ conda pack -p /explicit/path/to/my_env

On the target machine

.. code-block:: bash

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


API Usage
---------

Conda-Pack is also provides a Python API, the full documentation of which can
be found :doc:`here <api>`. The API mostly mirrors that of the ``conda pack``
commandline. Repeating the examples from above:

.. code-block:: python

    import conda_pack

    # Pack environment my_env into my_env.tar.gz
    conda_pack.pack(name="my_env")

    # Pack environment my_env into out_name.tar.gz
    conda_pack.pack(name="my_env", output="out_name.tar.gz")

    # Pack environment located at an explicit path into my_env.tar.gz
    conda_pack.pack(prefix="/explicit/path/to/my_env")


Caveats
-------

This tool is extremely new, and has a few caveats.

- Conda must be installed and be on your path.

- Windows is not currently supported (should be easy to fix, contributions
  welcome!)

- The os *type* where the environment was built must match the os *type* of the
  target. This means that environments built on windows can't be relocated to
  linux.


.. toctree::
    :hidden:

    api.rst
    cli.rst
