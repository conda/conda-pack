from __future__ import print_function, absolute_import

import json
import os
import sys
import zipfile
from subprocess import check_output

__all__ = ('pack',)

__version__ = '0.0.1'


_ENCODING = sys.getdefaultencoding()


class CondaPackException(Exception):
    """Internal exception to report to user"""
    pass


def zip_dir(directory, fname, prefix):
    # The top-level folder in the zipfile
    zFile = zipfile.ZipFile(fname, "w", allowZip64=True,
                            compression=zipfile.ZIP_DEFLATED)
    try:
        for root, dirs, files in os.walk(directory, followlinks=True):
            to_root = os.path.join(prefix, os.path.relpath(root, directory))
            for f in files:
                from_path = os.path.join(root, f)
                to_path = os.path.join(to_root, f)
                zFile.write(from_path, to_path)
    finally:
        zFile.close()


def pack(name=None, prefix=None, output=None, packed_prefix=None):
    """Package an existing conda environment into a zip file

    Parameters
    ----------
    name : str, optional
        The name of the conda environment to pack.
    prefix : str, optional
        A path to a conda environment to pack.
    output : str, optional
        The path of the output file. Defaults to the environment name with a
        ``.zip`` suffix (e.g. ``my_env.zip``).
    packed_prefix : str, optional
        Once unpacked, the relative path to the conda environment. By default
        this is a single directory with the same name as the environment (e.g.
        ``my_env``).

    Returns
    -------
    out_path : str
        The path to the zipped environment.
    """
    if name and prefix:
        raise CondaPackException("Cannot specify both ``name`` and ``prefix``")
    elif prefix:
        env_dir = prefix
        if not os.path.exists(env_dir):
            raise CondaPackException("Environment path %r doesn't "
                                     "exist" % env_dir)
    else:
        info = check_output("conda info --json", shell=True).decode(_ENCODING)
        info2 = json.loads(info)

        if name:
            env_lk = {os.path.basename(e): e for e in info2['envs']}
            try:
                env_dir = env_lk[name]
            except KeyError:
                raise CondaPackException("Environment name %r doesn't "
                                         "exist" % name)
        else:
            env_dir = info2['default_prefix']

    # The name of the environment
    env_name = os.path.basename(env_dir)

    if not output:
        output = os.extsep.join([env_name, 'zip'])

    if not packed_prefix:
        packed_prefix = env_name
    else:
        # Ensure the prefix is a relative path
        packed_prefix = packed_prefix.strip(os.path.sep)

    if os.path.exists(output):
        raise CondaPackException("File %r already exists" % output)

    zip_dir(env_dir, output, packed_prefix)
    return output
