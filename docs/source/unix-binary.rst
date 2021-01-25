Bundle an Environment as a Single Executable
============================================

``conda-pack`` can be used to distribute conda environments as executable shell
scripts for Linux and macOS.


Packaging a Simple Binary
-------------------------

We will package the [normaliz](https://github.com/Normaliz/Normaliz) binary in
this example. It provides a command line tool which is compiled from C++ code.

Create an environment and `conda pack` it:

.. code-block:: bash

    $ conda create -y -n normaliz normaliz=3.8.5
    $ conda pack -n normaliz

Add an entrypoint that activates the environment and starts normaliz:

.. code-block:: bash

    $ mkdir pack
    $ tar -zxf normaliz.tar.gz -C pack
    $ cat > pack/entrypoint.sh <<- EOF
      #!/bin/sh
      source bin/activate
      conda-unpack
      exec bin/normaliz $@
      EOF
    $ chmod +x pack/entrypoint.sh

Optional: reduce the size by removing files that are not needed here:

.. code-block:: bash

    $ rm -rf pack/lib/*.a pack/usr/share pack/usr/include
    $ find pack/lib -name '*.dylib' -type f -exec strip -S \{\} \; # macOS
    $ find pack/lib -name '*.so' -type f -exec strip --strip-unneeded \{\} \; # Linux

Pack everything into a single shell script with [makeself](https://makeself.io/):

.. code-block:: bash

    $ conda install -y makeself
    $ makeself pack/ normaliz.run Normaliz ./entrypoint.sh

The shell script `normaliz.run` should now work for others on the same platform. Note that arguments to `bin/normaliz` need to be given after an initial `--` since earlier arguments are consumed by makeself:

.. code-block:: bash

    $ ./normaliz.run -- --version
    Normaliz 3.8.5


Packaging a Complex Environment
-------------------------------

Note that complex environments can be packaged in the same way. Here we package
the computer algebra system [SageMath](https://sagemath.org) which comes with a
Jupyter notebook interface:

.. code-block:: bash

    $ conda create -y -n sagemath sage=9.2
    $ conda pack -n sagemath
    $ mkdir pack
    $ tar -zxf sagemath.tar.gz -C pack
    $ cat > pack/entrypoint.sh <<- EOF
      #!/bin/sh
      source bin/activate
      conda-unpack
      exec bin/sage --notebook=jupyter $@
      EOF
    $ chmod +x pack/entrypoint.sh
    $ makeself pack/ sagemath.run SageMath ./entrypoint.sh
    $ ./sagmath.run # opens a browser with Jupyter running SageMath

The above creates a huge bundle that takes a long time to pack and unpack (and
might exceed the available space in your `/tmp`.) You can speed up the process
by reducing the level of compression and by having your users uncompress things
permanently:

.. code-block:: bash

    $ cat > pack/unpack.sh <<- EOF
      #!/bin/sh
      source bin/activate
      conda-unpack
      EOF
    $ chmod +x pack/unpack.sh
    $ cat > pack/sagemath.run <<- EOF
      dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
      cd "$dir"
      ./bin/sage --notebook=jupyter $@
      EOF
    $ chmod +x pack/sagemath.run
    $ mkdir tmp
    $ TMPDIR=tmp/ makeself --complevel 6 --target ./sagemath-9.2 pack/ sagemath.install SageMath ./unpack.sh

The resulting shell script unpacks the environment into `./sagemath-9.2`.
Users could overwrite this with the `--target` parameter:

.. code-block:: bash

    $ ./sagemath.install
    $ ./sagemath-9.2/sagemath.run # opens a browser with Jupyter running SageMath
