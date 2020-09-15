Parcels
=======

Conda-pack has recently been enhanced with the ability to generate
`parcels <https://docs.cloudera.com/documentation/enterprise/latest/topics/cm_ig_parcels.html>`_
for use on Cloudera Hadoop clusters. The file formats for parcels and
conda-packs are nearly identical. In fact, it was possible even with
older versions of conda-pack to build parcels as follows:

1. Add two unmanaged files to the environment:

   - ``meta/parcel.json``:, a file of parcel-specific metadata
   - ``meta/conda_env.sh``: a simple activation script. The filename
     is flexible, and is recorded in the metadata file.

2. Pack the environment with specifically chosen values of
   ``--arcroot``, ``--dest-prefix``, and ``--output``.

The latest version of conda-pack has been enhanced to eliminate the manual
aspects of this work. The key is the introduction of a ``--format parcel``
option and four parcel-specific options:

- ``--parcel-name``: the base name of the parcel

  By default, this value will be taken from the basename of the selected environment
  directory. Parcel names may not have dashes ``-``, however, so if the name of the
  environment contains a dash, use this option to provide a compliant alternative.
- ``--parcel-version``: the version of the parcel

  This is generally expected to follow a standard `semver <https://semver.org/>`_
  format. If not supplied, conda-pack will autogenerate one from today's date in
  ``YYYY.MM.DD`` format.
- ``--parcel-distribution``: the target distribution for the parcel. 

  This is an abbreviation describing the specific operating system on which
  your Cloudera clsuter runs. Its default value is ``el7``, corresponding
  to RHEL7/CentOS7. Other common values include ``el6``, ``sles12``, ``bionic``,
  and ``xenial``.

- ``--parcel-root``: the location where parcels are unpacked on the cluster

  The default value of this location is ``/opt/cloudera/parcels``. Unless your
  cluster manager has modified this default, there should be no need to change
  this, but it is essential that this matches your configuration.

In many cases, it will not be necessary to override any of these options,
because conda-pack provides sensible defaults. Given these values, conda-pack
generates values for the following internal options:

- ``arcroot``: ``{parcel_name}-{parcel_version}``
- ``dest_prefix``: ``{parcel_root}/{parcel_name}-{parcel_version}``
- ``output`` (filename): ``{parcel_name}-{parcel_version}-{parcel_distro}.parcel``

Conda-pack will exit with an error if you attempt to override the ``dest-prefix``
or ``arcroot`` options. We recommend against overriding the ``output`` option,
but conda-pack does not prevent this.

Example
-------

Create an environment:

.. code-block:: bash

    $ conda create -y -n example python=3.5 numpy pandas scikit-learn


Package the environment into a parcel:

.. code-block:: bash

    $ conda pack -n example --format parcel --parcel-name=sklearn
    Collecting packages...
    Packing environment at '/Users/mgrant/miniconda3/envs/example' to 'sklearn-2020.09.15-el7.parcel'
    [########################################] | 100% Completed |  9.8s

