Conda-Pack
==========

``conda-pack`` is a command line tool for creating relocatable `conda
environments <https://conda.io/docs/>`_. This is useful for deploying code in a
consistent environment, potentially in a location where python/conda isn't
already installed.

.. raw:: html

    <div align="center">
      <script src="https://asciinema.org/a/186862.js" id="asciicast-186862" async data-speed="2"></script>
    </div>


Use Cases
---------

- Bundling an application with its environment for deployment

- Packaging a conda environment for usage with Apache Spark (:doc:`see here
  <spark>` for more information).

- Packaging a conda environment for deployment on Apache YARN. One way to do
  this is to use `Skein <https://jcrist.github.io/skein/>`_.

- Archiving an environment in a functioning state. Note that a more sustainable
  way to do this is to specify your environment as a `environment.yml
  <https://conda.io/docs/user-guide/tasks/manage-environments.html#sharing-an-environment>`_,
  and recreate the environment when needed.


Installation
------------

It's recommended to install in your root conda environment - the ``conda pack``
command will then be available in all sub-environments as well.

**Install from Conda-Forge:**

``conda-pack`` is available on `conda-forge <https://conda-forge.org/>`_:

.. code::

    conda install -c conda-forge conda-pack


**Install from PyPI:**

While ``conda-pack`` requires an existing ``conda`` install, it can also be
installed from PyPI:

.. code::

    pip install conda-pack


**Install from source:**

``conda-pack`` is `available on github <https://github.com/conda/conda-pack>`_
and can always be installed from source.


.. code::

    pip install git+https://github.com/conda/conda-pack.git


Commandline Usage
-----------------

``conda-pack`` is primarily a commandline tool. Full CLI docs can be found
:doc:`here <cli>`.

One common use case is packing an environment on one machine to distribute to
other machines that may not have conda/python installed.

On the source machine

.. code-block:: bash

    # Pack environment my_env into my_env.tar.gz
    $ conda pack -n my_env

    # Pack environment my_env into out_name.tar.gz
    $ conda pack -n my_env -o out_name.tar.gz

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

``conda-pack`` also provides a Python API, the full documentation of which can
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

This tool is new, and has a few caveats.

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
    spark.rst
