SquashFS
========

``conda-pack`` can package environments into
`SquashFS <https://en.wikipedia.org/wiki/SquashFS>`_, a compressed, read-only Linux filesystem.
These filesystems can then be mounted directly, without decompressing them first.
This allows benefiting from compressed storage, without the decompression step necessary for the
``zip`` and ``tar.gz`` formats.

Packing
-------
Packing environments into SquashFS works on MacOS and Linux.
You will need `squashfs-tools <https://github.com/plougher/squashfs-tools>`_, more specifically
the ``mksquashfs`` command.
``squashfs-tools`` can be installed via ``conda install -c conda-forge squashfs-tools``.

Mounting
--------
Mounting SquashFS environments is only possible on MacOS and Linux.

On Linux there are two ways:

- Mounting directly: Since SquashFS is part of the Linux kernel, it can be mounted using
  ``mount -t squashfs <filename> <mountpoint>``. This will require root or ``CAP_SYS_ADMIN``.
- Mounting as `Filesystem in Userspace (FUSE) <https://en.wikipedia.org/wiki/Filesystem_in_Userspace>`_:
  This can be done by installing `squashfuse <https://github.com/vasi/squashfuse>`_, for example through
  ``conda install -c conda-forge squashfuse``.
  It doesn't require root permissions.

On Mac only the FUSE option is available:

- First install `macFUSE <https://macfuse.io/>`_, eg via ``brew install --cask macfuse``.
- Then install `squashfuse <https://github.com/vasi/squashfuse>`_.

Python Example
--------------

Create an environment:

.. code-block:: bash

    $ conda create -y -n example python=3.9 numpy pandas scikit-learn

Pack the environment into SquashFS:

.. code-block:: bash

    $ conda pack -n example --format squashfs --n-threads 4

Create a directory to mount to:

.. code-block:: bash

    $ mkdir env_mountpoint


Option 1 (Linux + MacOS): Mount the environment using squashfuse:

.. code-block:: bash

    $ squashfuse example.squashfs env_mountpoint

Option 2 (Linux): Mount the environment using ``mount``:

.. code-block:: bash

    $ sudo mount -t squashfs example.squashfs env_mountpoint

Compression options
-------------------

Compression can be specified through ``--compress-level``.
Default is level 4, which will use ``gzip`` compression.

- 0: no compression
- <3: ``lzo``
- 4-7: ``gzip``
- >7: ``xz``