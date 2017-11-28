from __future__ import absolute_import

import glob
import json
import os
import shlex
import tarfile
import warnings
import zipfile
from contextlib import closing
from fnmatch import fnmatch
from functools import partial
from subprocess import check_output

from .compat import on_win, default_encoding, find_py_source
from ._progress import progressbar


__all__ = ('CondaPackException', 'CondaEnv', 'pack')


class CondaPackException(Exception):
    """Internal exception to report to user"""
    pass


class CondaEnv(object):
    def __init__(self, prefix, files):
        self.prefix = prefix
        self.files = files

    def __repr__(self):
        return 'CondaEnv<%r, %d files>' % (self.prefix, len(self))

    def __len__(self):
        return len(self.files)

    def __iter__(self):
        return iter(self.files)

    @property
    def name(self):
        """The name of the environment"""
        return os.path.basename(self.prefix)

    @classmethod
    def from_prefix(cls, prefix, **kwargs):
        files = load_environment(prefix, **kwargs)
        return cls(prefix, files)

    @classmethod
    def from_name(cls, name, **kwargs):
        return cls.from_prefix(name_to_prefix(name), **kwargs)

    @classmethod
    def from_default(cls, **kwargs):
        return cls.from_prefix(name_to_prefix(), **kwargs)

    def _filter(self, pred, inverse=False):
        if isinstance(pred, str):
            def func(f):
                return fnmatch(f.target, pred)
        elif callable(pred):
            func = pred
        else:
            raise TypeError("pred must be callable or a filepattern")

        if inverse:
            files = [f for f in self.files if not func(f)]
        else:
            files = [f for f in self.files if func(f)]

        return CondaEnv(self.prefix, files)

    def filter(self, pred):
        """Keep all files that match ``pred``"""
        return self._filter(pred)

    def remove(self, pred):
        """Remove all files that match ``pred``"""
        return self._filter(pred, inverse=True)

    def _output_and_format(self, output, format='infer'):
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
            output = os.extsep.join([self.name, format])

        return output, format

    def pack(self, output=None, format='infer', packed_prefix=None,
             verbose=False, record=None):
        """Package the conda environment into an archive file.

        Parameters
        ----------
        output : str, optional
            The path of the output file. Defaults to the environment name with a
            ``.zip`` suffix (e.g. ``my_env.zip``).
        format : {'infer', 'zip', 'tar.gz', 'tgz', 'tar.bz2', 'tbz2', 'tar'}
            The archival format to use. By default this is inferred by the
            output file extension, falling back to `zip` if a non-standard
            extension.
        packed_prefix : str, optional
            Once unpacked, the relative path to the conda environment. By
            default this is a single directory with the same name as the
            environment (e.g.  ``my_env``).
        verbose : bool, optional
            If True, progress is reported to stdout. Default is False.
        record : str, optional
            File path. If provided, a detailed log is written here.

        Returns
        -------
        out_path : str
            The path to the zipped environment.
        """
        if not packed_prefix:
            packed_prefix = self.name
        else:
            # Ensure the prefix is a relative path
            packed_prefix = packed_prefix.strip(os.path.sep)

        # The output path and archive format
        output, format = self._output_and_format(output, format)

        if os.path.exists(output):
            raise CondaPackException("File %r already exists" % output)

        if record is not None and os.path.exists(record):
            raise CondaPackException("record file %r already exists" % record)

        if verbose:
            print("Packing environment at %r to %r" % (self.prefix, output))

        if format == 'zip':
            archive = zipfile.ZipFile(output, "w", allowZip64=True,
                                      compression=zipfile.ZIP_DEFLATED)

            def add(f):
                target = os.path.join(packed_prefix, f.target)
                archive.write(f.source, os.path.join(packed_prefix, f.target))
                return f.source, target

        else:
            archive = tarfile.open(name=output, mode=_tar_mode[format],
                                   dereference=False)

            def add(f):
                target = os.path.join(packed_prefix, f.target)
                archive.add(f.source, target, recursive=False)
                return f.source, target

        with closing(archive), progressbar(self.files, enabled=verbose) as files:
            records = [add(f) for f in files]

        if record is not None:
            with open(record, 'w') as f:
                template = "%s -> %s" + os.linesep
                f.writelines(template % r for r in records)

        return output


class File(object):
    """A single archive record.

    Parameters
    ----------
    source : str
        Absolute path to the source.
    target : str
        Relative path from the target prefix (e.g. ``lib/foo/bar.py``).
    prefix_info : PrefixInfo or None, optional
        Information about any prefixes that may need replacement.
    is_symlink : bool, optional
        Whether the file is a symlink to another file in the environment. If
        True, will be archived as a symlink (if the storage allows it), if
        False (default) file will be copied.
    """
    __slots__ = ('source', 'target', 'prefix_info', 'is_symlink')

    def __init__(self, source, target, prefix_info=None, is_symlink=False):
        self.source = source
        self.target = target
        self.prefix_info = prefix_info
        self.is_symlink = is_symlink

    @property
    def is_unmanaged(self):
        return self.prefix_info and self.prefix_info.mode == 'unmanaged'

    @property
    def kind(self):
        return 'unmanaged' if self.is_unmanaged else 'managed'

    def __repr__(self):
        return 'File<%r, %r>' % (self.target, self.kind)


class PrefixInfo(object):
    """Information on prefix replacement"""
    __slots__ = ('placeholder', 'mode')

    def __init__(self, placeholder, mode):
        self.placeholder = placeholder
        self.mode = mode

    def __repr__(self):
        return 'PrefixInfo<%s>' % self.mode


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
        env = CondaEnv.from_prefix(prefix)
    elif name:
        env = CondaEnv.from_name(name)
    else:
        env = CondaEnv.from_default()

    return env.pack(output=output, format=format, packed_prefix=packed_prefix,
                    verbose=verbose, record=record)


def find_site_packages(prefix):
    # Ensure there is exactly one version of python installed
    pythons = []
    for fn in glob.glob(os.path.join(prefix, 'conda-meta', 'python-*.json')):
        with open(fn) as fil:
            meta = json.load(fil)
        if meta['name'] == 'python':
            pythons.append(meta)

    if len(pythons) > 1:
        raise CondaPackException("Unexpected failure, multiple versions of "
                                 "python found in prefix %r" % prefix)

    elif not pythons:
        raise CondaPackException("Unexpected failure, no version of python "
                                 "found in prefix %r" % prefix)

    # Only a single version of python installed in this environment
    if on_win:
        return 'Lib/site-packages'

    python_version = pythons[0]['version']
    major_minor = python_version[:3]  # e.g. '3.5.1'[:3]

    return 'lib/python%s/site-packages' % major_minor


def check_no_editable_packages(prefix, site_packages):
    pth_files = glob.glob(os.path.join(prefix, site_packages, '*.pth'))
    editable_packages = set()
    for pth_fil in pth_files:
        dirname = os.path.dirname(pth_fil)
        with open(pth_fil) as pth:
            for line in pth:
                if line.startswith('#'):
                    continue
                line = line.rstrip()
                if line:
                    location = os.path.normpath(os.path.join(dirname, line))
                    if not location.startswith(prefix):
                        editable_packages.add(line)
    if editable_packages:
        msg = ("Cannot pack an environment with editable packages\n"
               "installed (e.g. from `python setup.py develop` or\n "
               "`pip install -e`). Editable packages found:\n\n"
               "%s") % '\n'.join('- %s' % p for p in sorted(editable_packages))
        raise CondaPackException(msg)


def name_to_prefix(name=None):
    info = check_output("conda info --json", shell=True).decode(default_encoding)
    info2 = json.loads(info)

    if name:
        env_lk = {os.path.basename(e): e for e in info2['envs']}
        try:
            prefix = env_lk[name]
        except KeyError:
            raise CondaPackException("Environment name %r doesn't exist" % name)
    else:
        prefix = info2['default_prefix']

    return prefix


def read_noarch_type(pkg):
    for file_name in ['link.json', 'package_metadata.json']:
        path = os.path.join(pkg, 'info', file_name)
        if os.path.exists(path):
            with open(path) as fil:
                info = json.load(fil)
            try:
                return info['noarch']['type']
            except KeyError:
                return None
    return None


# String is split so as not to appear in the file bytes unintentionally
PREFIX_PLACEHOLDER = ('/opt/anaconda1anaconda2'
                      'anaconda3')


def read_has_prefix(path):
    out = {}
    with open(path) as fil:
        for line in fil:
            rec = tuple(x.strip('"\'') for x in shlex.split(line, posix=False))
            if len(rec) == 1:
                out[rec[0]] = (PREFIX_PLACEHOLDER, 'text')
            elif len(rec) == 3:
                out[rec[2]] = rec[:2]
            else:
                raise ValueError("Failed to parse has_prefix file")
    return out


def collect_unmanaged(prefix, managed):
    from os.path import relpath, join, isfile, islink

    remove = {join('bin', f) for f in ['conda', 'activate', 'deactivate']}

    ignore = {'pkgs', 'envs', 'conda-bld', 'conda-meta', '.conda_lock',
              'users', 'LICENSE.txt', 'info', 'conda-recipes', '.index',
              '.unionfs', '.nonadmin', 'python.app', 'Launcher.app'}

    res = set()

    for fn in os.listdir(prefix):
        if fn in ignore:
            continue
        elif isfile(join(prefix, fn)):
            res.add(fn)
        else:
            for root, dirs, files in os.walk(join(prefix, fn)):
                root2 = relpath(root, prefix)
                res.update(join(root2, fn2) for fn2 in files)

                for d in dirs:
                    if islink(join(root, d)):
                        dirs.remove(d)
                        res.add(join(root2, d))

    managed = {i.target for i in managed}
    res -= managed
    res -= remove

    return [make_unmanaged(prefix, p) for p in res
            if not (p.endswith('~') or
                    p.endswith('.DS_Store') or
                    (find_py_source(p) in managed))]


def make_managed(pkg, _path, path_type=None, prefix_placeholder=None,
                 file_mode=None, **ignored):
    prefix_info = (None if prefix_placeholder is None else
                   PrefixInfo(prefix_placeholder, file_mode))
    return File(os.path.join(pkg, _path),
                _path,
                prefix_info=prefix_info,
                is_symlink=(path_type == 'softlink'))


def make_unmanaged(prefix, path):
    source = os.path.join(prefix, path)
    return File(source, path, prefix_info=PrefixInfo(prefix, 'unmanaged'),
                is_symlink=os.path.islink(source))


_bin_dir = 'Scripts' if on_win else 'bin'


def make_noarch_python(site_packages, pkg, _path, path_type=None,
                       prefix_placeholder=None, file_mode=None, **ignored):
    if _path.startswith('site-packages/'):
        target = site_packages + _path[13:]
    elif _path.startswith('python-scripts/'):
        target = _bin_dir + _path[14:]
    else:
        target = _path

    prefix_info = (None if prefix_placeholder is None else
                   PrefixInfo(prefix_placeholder, file_mode))

    return File(os.path.join(pkg, _path),
                target,
                prefix_info=prefix_info,
                is_symlink=(path_type == 'softlink'))


def make_noarch_python_extra(prefix, path):
    source = os.path.join(prefix, path)
    prefix_info = (None if path.endswith('.pyc')
                   else PrefixInfo(prefix, 'text'))
    return File(source, path, prefix_info=prefix_info, is_symlink=False)


def load_managed_package(info, prefix, site_packages):
    pkg = info['link']['source']

    noarch_type = read_noarch_type(pkg)

    if noarch_type == 'python':
        make_file = partial(make_noarch_python, site_packages)
    else:
        make_file = make_managed

    paths_json = os.path.join(pkg, 'info', 'paths.json')
    if os.path.exists(paths_json):
        with open(paths_json) as fil:
            paths = json.load(fil)

        files = [make_file(pkg, **r) for r in paths['paths']]
    else:
        with open(os.path.join(pkg, 'info', 'files')) as fil:
            paths = [f.strip() for f in fil]

        has_prefix = os.path.join(pkg, 'info', 'has_prefix')

        if os.path.exists(has_prefix):
            prefixes = read_has_prefix(has_prefix)
            files = [make_file(pkg, p, None, *prefixes.get(p, ()))
                     for p in paths]
        else:
            files = [make_file(pkg, p) for p in paths]

    if noarch_type == 'python':
        seen = {i.target for i in files}
        files.extend(make_noarch_python_extra(prefix, fil)
                     for fil in info['files'] if fil not in seen)

    return files


_uncached_error = """
Conda-managed packages were found without entries in the package cache. This
is usually due to `conda clean -p` being unaware of symlinked or copied
packages. Uncached packages:

{0}"""

_uncached_warning = """\
{0}

Continuing with packing, treating these packages as if they were unmanaged
files (e.g. from `pip`). This is usually fine, but may cause issues as
prefixes aren't be handled as robustly.""".format(_uncached_error)


def load_environment(prefix, unmanaged=True, on_missing_cache='warn'):
    # Check if it's a conda environment
    if not os.path.exists(prefix):
        raise CondaPackException("Environment path %r doesn't exist" % prefix)
    conda_meta = os.path.join(prefix, 'conda-meta')
    if not os.path.exists(conda_meta):
        raise CondaPackException("Path %r is not a conda environment" % prefix)

    # Find the environment site_packages (if any)
    site_packages = find_site_packages(prefix)

    # Check that no editable packages are installed
    check_no_editable_packages(prefix, site_packages)

    files = []
    uncached = []
    for path in os.listdir(conda_meta):
        if path.endswith('.json'):
            with open(os.path.join(conda_meta, path)) as fil:
                info = json.load(fil)
            pkg = info['link']['source']

            if not os.path.exists(pkg):
                # Package cache is cleared, return list of unmanaged files
                # to properly handle prefix replacement ourselves.
                new_files = [make_unmanaged(prefix, f) for f in info['files']]
                uncached.append((info['name'], info['version'], info['url']))
            else:
                new_files = load_managed_package(info, prefix, site_packages)

            files.extend(new_files)

    if unmanaged:
        files.extend(collect_unmanaged(prefix, files))

    if uncached and on_missing_cache in ('warn', 'raise'):
        packages = '\n'.join('- %s=%r   %s' % i for i in uncached)
        if on_missing_cache == 'warn':
            warnings.warn(_uncached_warning.format(packages))
        else:
            raise CondaPackException(_uncached_error.format(packages))

    return files
