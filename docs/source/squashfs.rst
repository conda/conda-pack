SquashFS
========

``conda-pack`` can package environments into
`SquashFS <https://en.wikipedia.org/wiki/SquashFS>`_, a compressed, read-only Linux filesystem.
These filesystems can then be mounted directly, without decompressing them first.
This allows using packed environments immediately and without consuming disk space.

Packing
-------
Packing environments into SquashFS works on MacOS and Linux.
You will need to install `squashfs-tools <https://github.com/plougher/squashfs-tools>`_, more specifically
the ``mksquashfs`` command.
On Ubuntu run ``apt-get install squashfs-tools``,
on MacOS ``brew install squashfs`` or alternatively (Linux+MacOS) install from conda-forge through
``conda install -c conda-forge squashfs-tools``.

Mounting
--------
Mounting SquashFS environments is only possible on MacOS and Linux.

On Linux there are two ways:

- Mounting directly: Since SquashFS is part of the Linux kernel, it can be mounted using
  ``mount -t squashfs <filename> <mountpoint>``. This will require root or ``CAP_SYS_ADMIN``.
- Mounting as `Filesystem in Userspace (FUSE) <https://en.wikipedia.org/wiki/Filesystem_in_Userspace>`_:
  This can be done by installing `squashfuse <https://github.com/vasi/squashfuse>`_, for example through
  ``apt-get install squashfuse`` (Ubuntu), ``conda install -c conda-forge squashfuse`` or from source.
  Contrary to the Kernel-version of SquashFS, ``squashfuse`` doesn't require root permissions to run. ``squashfuse_ll``
  comes packaged with ``squashfuse`` and is often faster.

On Mac only the FUSE option is available:

- First install `macFUSE <https://macfuse.io/>`_, eg via ``brew install --cask macfuse``.
- Then install ``squashfuse``, ideally from `source <https://github.com/vasi/squashfuse>`_.

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
Default is level 4, which will use ``zstd`` compression.

When selecting a compression option for packing, keep in mind the kernel or ``squashfuse`` version on the target system.
For older systems, make sure that SquashFS or ``squashfuse`` support ``zstd`` compression
(Linux kernel version ``>=4.14`` or ``squashfuse >= 0.1.101``).
If ``zstd`` isn't supported on the target, you can always compress with ``xz`` instead.


- 0: no compression
- 1-8: ``zstd`` with increasing compression level
- 9: ``xz``

Making the unpacked environment writeable
-----------------------------------------

SquashFS is a read-only filesystem.
Sometimes the unpacked environment needs to be writeable on the target machine, for example to install
more packages.
A good way to do this is to use `Union mounting <https://en.wikipedia.org/wiki/Union_mount>`_ to
add a writeable layer on top of the read-only SquashFS.
On Linux the most used option is `OverlayFS <https://www.kernel.org/doc/html/latest/filesystems/overlayfs.html>`_.

To set this up, we create three layers:

1. The SquashFS-packed conda env as a read-only lower layer
2. A writeable working directory, necessary for OverlayFS
3. A writeable upper directory, where all new and changed files will go

.. code-block:: bash

    $ # 1. Create read-only lower layer, consisting of squashFS-packed conda env
    $ mkdir squashFS_mountpoint
    $ sudo mount -t squashfs example.squashfs squashFS_mountpoint
    $ # 2. Create workdir & 3. Create upperdir
    $ mkdir workdir upperdir

Now we combine them into a single directory ``writeable_env``, which will contain our environment but
which will be writeable.

.. code-block:: bash

    $ mkdir writeable_env
    $ sudo mount -t overlay overlay \
        -o lowerdir=squashFS_mountpoint,upperdir=upperdir,workdir=workdir writeable_env

Any files created in the ``writeable_env`` directory will also show up in ``upperdir``.
After unmounting, delete ``upperdir`` and ``workdir`` and all changes made to the environment will be gone.
