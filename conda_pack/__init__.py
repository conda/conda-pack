from __future__ import print_function, absolute_import

import glob
import json
import os
import sys
import tarfile
import zipfile
from contextlib import closing
from subprocess import check_output

from ._progress import progressbar

__all__ = ('pack',)

__version__ = '0.0.1'


_ENCODING = sys.getdefaultencoding()


class CondaPackException(Exception):
    """Internal exception to report to user"""
    pass


def check_is_conda_env(path):
    if not os.path.exists(path):
        raise CondaPackException("Environment path %r doesn't exist" % path)
    top_dirs = os.listdir(path)
    if 'conda-meta' not in top_dirs:
        raise CondaPackException("Path %r is not a conda environment" % path)


def getpath(*paths):
    dir = os.path.join(*paths)
    try:
        dir = os.path.abspath(dir)
    except OSError:
        pass
    return dir


def check_no_editable_packages(path):
    pth_files = glob.glob(os.path.join(path, 'lib', 'python[0-9].[0-9]',
                                       'site-packages', '*.pth'))
    editable_packages = set()
    for pth_fil in pth_files:
        dirname = os.path.dirname(pth_fil)
        with open(pth_fil) as pth:
            for line in pth:
                if line.startswith('#'):
                    continue
                line = line.rstrip()
                if line and not getpath(dirname, line).startswith(path):
                    editable_packages.add(line)
    if editable_packages:
        msg = ("Cannot pack an environment with editable packages "
               "installed (e.g. from `python setup.py develop` or "
               "`pip install -e`). Editable packages found:\n\n"
               "%s") % '\n'.join('- %s' % p for p in sorted(editable_packages))
        raise CondaPackException(msg)


def get_output_and_format(env_name, output, format='infer'):
    if format == 'infer':
        if output is None or output.endswith('.zip'):
            format = 'zip'
        elif output.endswith('.tar.gz') or output.endswith('.tgz'):
            format = 'tar.gz'
        elif output.endswith('.tar.bz2') or output.endswith('.tbz2'):
            format = 'tar.bz2'
        elif output.endswith('.tar'):
            format = 'tar'
        else:
            # Default to zip
            format = 'zip'
    elif format not in {'zip', 'tar.gz', 'tgz', 'tar.bz2', 'tbz2', 'tar'}:
        raise CondaPackException("Unknown format %r" % format)

    if output is None:
        output = os.extsep.join([env_name, format])

    return output, format


_tar_mode = {'tar.gz': 'w:gz',
             'tgz': 'w:gz',
             'tar.bz2': 'w:bz2',
             'tbz2': 'w:bz2',
             'tar': 'w'}


def pack(name=None, prefix=None, output=None, format='infer',
         packed_prefix=None, verbose=False, record=None):
    """Package an existing conda environment into an archive file.

    Parameters
    ----------
    name : str, optional
        The name of the conda environment to pack.
    prefix : str, optional
        A path to a conda environment to pack.
    output : str, optional
        The path of the output file. Defaults to the environment name with a
        ``.zip`` suffix (e.g. ``my_env.zip``).
    format : {'infer', 'zip', 'tar.gz', 'tgz', 'tar.bz2', 'tbz2', 'tar'}, optional
        The archival format to use. By default this is inferred by the output
        file extension, falling back to `zip` if a non-standard extension.
    packed_prefix : str, optional
        Once unpacked, the relative path to the conda environment. By default
        this is a single directory with the same name as the environment (e.g.
        ``my_env``).
    verbose : bool, optional
        If True, progress is reported to stdout. Default is False.
    record : str, optional
        File path. If provided, a detailed log is written here.

    Returns
    -------
    out_path : str
        The path to the zipped environment.
    """
    if name and prefix:
        raise CondaPackException("Cannot specify both ``name`` and ``prefix``")
    elif prefix:
        env_dir = prefix
        check_is_conda_env(env_dir)
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

    # Pre-checks that environment is relocatable
    check_no_editable_packages(env_dir)

    # The name of the environment
    env_name = os.path.basename(env_dir)

    if not packed_prefix:
        packed_prefix = env_name
    else:
        # Ensure the prefix is a relative path
        packed_prefix = packed_prefix.strip(os.path.sep)

    # The output path and archive format
    output, format = get_output_and_format(env_name, output, format)

    if os.path.exists(output):
        raise CondaPackException("File %r already exists" % output)

    if record is not None and os.path.exists(record):
        raise CondaPackException("record file %r already exists" % record)

    if verbose:
        print("Packing environment at %r to %r" % (env_dir, output))

    # Collect all the paths to write
    paths = []
    for from_root, _, files in os.walk(env_dir, followlinks=True):
        to_root = os.path.join(packed_prefix,
                               os.path.relpath(from_root, env_dir))
        paths.extend((os.path.join(from_root, f), os.path.join(to_root, f))
                     for f in files)

    if format == 'zip':
        archive = zipfile.ZipFile(output, "w", allowZip64=True,
                                  compression=zipfile.ZIP_DEFLATED)
    else:
        archive = tarfile.open(name=output, mode=_tar_mode[format],
                               dereference=True)

    with closing(archive), progressbar(paths, enabled=verbose) as paths2:
        if format == 'zip':
            for from_path, to_path in paths2:
                archive.write(from_path, to_path)
        else:
            for from_path, to_path in paths2:
                archive.add(from_path, to_path, recursive=False)

    if record is not None:
        with open(record, 'w') as f:
            template = "%s -> %s" + os.linesep
            f.writelines(template % p for p in paths)

    return output
