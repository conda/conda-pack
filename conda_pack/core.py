from __future__ import absolute_import, print_function

import glob
import json
import os
import pkg_resources
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import warnings
from contextlib import contextmanager
from fnmatch import fnmatch

from .compat import on_win, default_encoding, find_py_source
from .prefixes import SHEBANG_REGEX, replace_prefix
from ._progress import progressbar


__all__ = ('CondaPackException', 'CondaEnv', 'File', 'pack')


class CondaPackException(Exception):
    """Internal exception to report to user"""
    pass


# String is split so as not to appear in the file bytes unintentionally
PREFIX_PLACEHOLDER = ('/opt/anaconda1anaconda2'
                      'anaconda3')

BIN_DIR = 'Scripts' if on_win else 'bin'

_current_dir = os.path.dirname(__file__)
if on_win:
    _scripts = [(os.path.join(_current_dir, 'scripts', 'windows', 'activate.bat'),
                 os.path.join(BIN_DIR, 'activate.bat')),
                (os.path.join(_current_dir, 'scripts', 'windows', 'deactivate.bat'),
                 os.path.join(BIN_DIR, 'deactivate.bat'))]
else:
    _scripts = [(os.path.join(_current_dir, 'scripts', 'posix', 'activate'),
                 os.path.join(BIN_DIR, 'activate')),
                (os.path.join(_current_dir, 'scripts', 'posix', 'deactivate'),
                 os.path.join(BIN_DIR, 'deactivate'))]


class _Context(object):
    def __init__(self):
        self.is_cli = False

    def warn(self, msg):
        if self.is_cli:
            print(msg + "\n", file=sys.stderr)
        else:
            warnings.warn(msg)

    @contextmanager
    def set_cli(self):
        old = self.is_cli
        try:
            self.is_cli = True
            yield
        finally:
            self.is_cli = old


context = _Context()


class CondaEnv(object):
    """A Conda Environment for packaging.

    Use :func:`CondaEnv.from_prefix`, :func:`CondaEnv.from_name`, or
    :func:`CondaEnv.from_default` instead of the default constructor.

    Examples
    --------

    Package the current environment, excluding all ``*.pyc`` and ``*.pyx``
    files, into a ``tar.gz`` archive:

    >>> (CondaEnv.from_default()
    ...          .exclude("*.pyc")
    ...          .exclude("*.pyx")
    ...          .pack(output="output.tar.gz"))
    "/full/path/to/output.tar.gz"

    Package the environment ``foo`` into a zip archive:

    >>> (CondaEnv.from_name("foo")
    ...          .pack(output="foo.zip"))
    "/full/path/to/foo.zip"

    Attributes
    ----------
    prefix : str
        The path to the conda environment.
    files : list of File
        A list of :class:`File` objects representing all files in conda
        environment.
    name : str
        The name of the conda environment.
    """
    def __init__(self, prefix, files, excluded_files=None):
        self.prefix = prefix
        self.files = files
        self._excluded_files = excluded_files or []

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
        """Create a ``CondaEnv`` from a given prefix.

        Parameters
        ----------
        prefix : str
            The path to the conda environment.

        Returns
        -------
        env : CondaEnv
        """
        prefix = os.path.abspath(prefix)
        files = load_environment(prefix, **kwargs)
        return cls(prefix, files)

    @classmethod
    def from_name(cls, name, **kwargs):
        """Create a ``CondaEnv`` from a named environment.

        Parameters
        ----------
        name : str
            The name of the conda environment.

        Returns
        -------
        env : CondaEnv
        """
        return cls.from_prefix(name_to_prefix(name), **kwargs)

    @classmethod
    def from_default(cls, **kwargs):
        """Create a ``CondaEnv`` from the current environment.

        Returns
        -------
        env : CondaEnv
        """
        return cls.from_prefix(name_to_prefix(), **kwargs)

    def exclude(self, pattern):
        """Exclude all files that match ``pattern`` from being packaged.

        This can be useful to remove functionality that isn't needed in the
        archive but is part of the original conda package.

        Parameters
        ----------
        pattern : str
            A file pattern. May include shell-style wildcards a-la ``glob``.

        Returns
        -------
        env : CondaEnv
            A new env with any matching files excluded.

        Examples
        --------

        Exclude all ``*.pyx`` files, except those from ``cytoolz``.

        >>> env = (CondaEnv.from_default()
        ...                .exclude("*.pyx")
        ...                .include("lib/python3.6/site-packages/cytoolz/*.pyx"))
        CondaEnv<'~/miniconda/envs/example', 1234 files>

        See Also
        --------
        include
        """
        files = []
        excluded = list(self._excluded_files)  # copy
        include = files.append
        exclude = excluded.append
        for f in self.files:
            if fnmatch(f.target, pattern):
                exclude(f)
            else:
                include(f)
        return CondaEnv(self.prefix, files, excluded)

    def include(self, pattern):
        """Re-add all excluded files that match ``pattern``

        Parameters
        ----------
        pattern : str
            A file pattern. May include shell-style wildcards a-la ``glob``.

        Returns
        -------
        env : CondaEnv
            A new env with any matching files that were previously excluded
            re-included.

        See Also
        --------
        exclude
        """
        files = list(self.files)  # copy
        excluded = []
        include = files.append
        exclude = excluded.append
        for f in self._excluded_files:
            if fnmatch(f.target, pattern):
                include(f)
            else:
                exclude(f)
        return CondaEnv(self.prefix, files, excluded)

    def _output_and_format(self, output=None, format='infer'):
        if output is None and format == 'infer':
            format = 'tar.gz'
        elif format == 'infer':
            if output.endswith('.zip'):
                format = 'zip'
            elif output.endswith('.tar.gz') or output.endswith('.tgz'):
                format = 'tar.gz'
            elif output.endswith('.tar.bz2') or output.endswith('.tbz2'):
                format = 'tar.bz2'
            elif output.endswith('.tar'):
                format = 'tar'
            else:
                raise CondaPackException("Unknown file extension %r" % output)
        elif format not in {'zip', 'tar.gz', 'tgz', 'tar.bz2', 'tbz2', 'tar'}:
            raise CondaPackException("Unknown format %r" % format)

        if output is None:
            output = os.extsep.join([self.name, format])

        return output, format

    def pack(self, output=None, format='infer', arcroot='', dest_prefix=None,
             verbose=False, force=False, compress_level=4, n_threads=1,
             zip_symlinks=False, zip_64=True):
        """Package the conda environment into an archive file.

        Parameters
        ----------
        output : str, optional
            The path of the output file. Defaults to the environment name with a
            ``.tar.gz`` suffix (e.g. ``my_env.tar.gz``).
        format : {'infer', 'zip', 'tar.gz', 'tgz', 'tar.bz2', 'tbz2', 'tar'}
            The archival format to use. By default this is inferred by the
            output file extension.
        arcroot : str, optional
            The relative path in the archive to the conda environment.
            Defaults to ''.
        dest_prefix : str, optional
            If present, prefixes will be rewritten to this path before
            packaging. In this case the ``conda-unpack`` script will not be
            generated.
        verbose : bool, optional
            If True, progress is reported to stdout. Default is False.
        force : bool, optional
            Whether to overwrite any existing archive at the output path.
            Default is False.
        compress_level : int, optional
            The compression level to use, from 0 to 9. Higher numbers decrease
            output file size at the expense of compression time. Ignored for
            ``format='zip'``. Default is 4.
        n_threads : int, optional
            The number of threads to use. Set to -1 to use the number of cpus
            on this machine. If a file format doesn't support threaded
            packaging, this option will be ignored. Default is 1.
        zip_symlinks : bool, optional
            Symbolic links aren't supported by the Zip standard, but are
            supported by *many* common Zip implementations. If True, store
            symbolic links in the archive, instead of the file referred to
            by the link. This can avoid storing multiple copies of the same
            files. *Note that the resulting archive may silently fail on
            decompression if the ``unzip`` implementation doesn't support
            symlinks*. Default is False. Ignored if format isn't ``zip``.
        zip_64 : bool, optional
            Whether to enable ZIP64 extensions. Default is True.

        Returns
        -------
        out_path : str
            The path to the archived environment.
        """
        from .formats import archive
        # Ensure the prefix is a relative path
        arcroot = arcroot.strip(os.path.sep)

        # The output path and archive format
        output, format = self._output_and_format(output, format)

        if os.path.exists(output) and not force:
            raise CondaPackException("File %r already exists" % output)

        if verbose:
            print("Packing environment at %r to %r" % (self.prefix, output))

        fd, temp_path = tempfile.mkstemp()

        try:
            with os.fdopen(fd, 'wb') as temp_file:
                with progressbar(self.files, enabled=verbose) as files:
                    with archive(temp_file, arcroot, format,
                                 compress_level=compress_level,
                                 zip_symlinks=zip_symlinks,
                                 zip_64=zip_64,
                                 n_threads=n_threads) as arc:
                        packer = Packer(self.prefix, arc, dest_prefix=dest_prefix)
                        for f in files:
                            packer.add(f)
                        packer.finish()

        except Exception:
            # Writing failed, remove tempfile
            os.remove(temp_path)
            raise
        else:
            # Writing succeeded, move archive to desired location
            shutil.move(temp_path, output)

        return output


class File(object):
    """A single archive record.

    Parameters
    ----------
    source : str
        Absolute path to the source.
    target : str
        Relative path from the target prefix (e.g. ``lib/foo/bar.py``).
    is_conda : bool, optional
        Whether the file was installed by conda, or comes from somewhere else.
    file_mode : {None, 'text', 'binary', 'unknown'}, optional
        The type of record.
    prefix_placeholder : None or str, optional
        The prefix placeholder in the file (if any)
    """
    __slots__ = ('source', 'target', 'is_conda', 'file_mode',
                 'prefix_placeholder')

    def __init__(self, source, target, is_conda=True, file_mode=None,
                 prefix_placeholder=None):
        self.source = source
        self.target = target
        self.is_conda = is_conda
        self.file_mode = file_mode
        self.prefix_placeholder = prefix_placeholder

    def __repr__(self):
        return 'File<%r, is_conda=%r>' % (self.target, self.is_conda)


def pack(name=None, prefix=None, output=None, format='infer',
         arcroot='', dest_prefix=None, verbose=False, force=False,
         compress_level=4, n_threads=1, zip_symlinks=False, zip_64=True,
         filters=None):
    """Package an existing conda environment into an archive file.

    Parameters
    ----------
    name : str, optional
        The name of the conda environment to pack.
    prefix : str, optional
        A path to a conda environment to pack.
    output : str, optional
        The path of the output file. Defaults to the environment name with a
        ``.tar.gz`` suffix (e.g. ``my_env.tar.gz``).
    format : {'infer', 'zip', 'tar.gz', 'tgz', 'tar.bz2', 'tbz2', 'tar'}, optional
        The archival format to use. By default this is inferred by the output
        file extension.
    arcroot : str, optional
        The relative path in the archive to the conda environment.
        Defaults to ''.
    dest_prefix : str, optional
        If present, prefixes will be rewritten to this path before packaging.
        In this case the ``conda-unpack`` script will not be generated.
    verbose : bool, optional
        If True, progress is reported to stdout. Default is False.
    force : bool, optional
        Whether to overwrite any existing archive at the output path. Default
        is False.
    compress_level : int, optional
        The compression level to use, from 0 to 9. Higher numbers decrease
        output file size at the expense of compression time. Ignored for
        ``format='zip'``. Default is 4.
    zip_symlinks : bool, optional
        Symbolic links aren't supported by the Zip standard, but are supported
        by *many* common Zip implementations. If True, store symbolic links in
        the archive, instead of the file referred to by the link. This can
        avoid storing multiple copies of the same files. *Note that the
        resulting archive may silently fail on decompression if the ``unzip``
        implementation doesn't support symlinks*. Default is False. Ignored if
        format isn't ``zip``.
    n_threads : int, optional
        The number of threads to use. Set to -1 to use the number of cpus on
        this machine. If a file format doesn't support threaded packaging, this
        option will be ignored. Default is 1.
    zip_64 : bool, optional
        Whether to enable ZIP64 extensions. Default is True.
    filters : list, optional
        A list of filters to apply to the files. Each filter is a tuple of
        ``(kind, pattern)``, where ``kind`` is either ``'exclude'`` or
        ``'include'`` and ``pattern`` is a file pattern. Filters are applied in
        the order specified.

    Returns
    -------
    out_path : str
        The path to the archived environment.
    """
    if name and prefix:
        raise CondaPackException("Cannot specify both ``name`` and ``prefix``")

    if verbose:
        print("Collecting packages...")

    if prefix:
        env = CondaEnv.from_prefix(prefix)
    elif name:
        env = CondaEnv.from_name(name)
    else:
        env = CondaEnv.from_default()

    if filters is not None:
        for kind, pattern in filters:
            if kind == 'exclude':
                env = env.exclude(pattern)
            elif kind == 'include':
                env = env.include(pattern)
            else:
                raise CondaPackException("Unknown filter of kind %r" % kind)

    return env.pack(output=output, format=format, arcroot=arcroot,
                    dest_prefix=dest_prefix,
                    verbose=verbose, force=force,
                    compress_level=compress_level, n_threads=n_threads,
                    zip_symlinks=zip_symlinks, zip_64=zip_64)


def find_site_packages(prefix):
    # Ensure there is at most one version of python installed
    pythons = []
    for fn in glob.glob(os.path.join(prefix, 'conda-meta', 'python-*.json')):
        with open(fn) as fil:
            meta = json.load(fil)
        if meta['name'] == 'python':
            pythons.append(meta)

    if len(pythons) > 1:  # pragma: nocover
        raise CondaPackException("Unexpected failure, multiple versions of "
                                 "python found in prefix %r" % prefix)

    elif not pythons:
        # No python installed
        return None

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
    try:
        conda_exe = os.environ.get('CONDA_EXE', 'conda')
        info = (subprocess.check_output("{} info --json".format(conda_exe),
                                        shell=True, stderr=subprocess.PIPE)
                          .decode(default_encoding))
    except subprocess.CalledProcessError as exc:
        kind = ('current environment' if name is None
                else 'environment: %r' % name)
        raise CondaPackException("Failed to determine path to %s. This may "
                                 "be due to conda not being on your PATH. The "
                                 "full error is below:\n\n"
                                 "%s" % (kind, exc.output))
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


def load_files(prefix):
    from os.path import relpath, join, isfile, islink

    ignore = {'pkgs', 'envs', 'conda-bld', '.conda_lock', 'users',
              'LICENSE.txt', 'info', 'conda-recipes', '.index', '.unionfs',
              '.nonadmin', 'python.app', 'Launcher.app'}

    res = set()

    for fn in os.listdir(prefix):
        if fn in ignore or fn.endswith('~') or fn.endswith('.DS_STORE'):
            continue
        elif isfile(join(prefix, fn)):
            res.add(fn)
        elif islink(join(prefix, fn)):
            res.add(fn)
        else:
            for root, dirs, files in os.walk(join(prefix, fn)):
                root2 = relpath(root, prefix)
                res.update(join(root2, fn2) for fn2 in files)

                for d in dirs:
                    if islink(join(root, d)):
                        # Add symbolic directory directly
                        res.add(join(root2, d))

                if not dirs and not files:
                    # root2 is an empty directory, add it
                    res.add(root2)

    return res


def managed_file(is_noarch, site_packages, pkg, _path, prefix_placeholder=None,
                 file_mode=None, **ignored):
    if is_noarch:
        if _path.startswith('site-packages/'):
            target = site_packages + _path[13:]
        elif _path.startswith('python-scripts/'):
            target = BIN_DIR + _path[14:]
        else:
            target = _path
    else:
        target = _path

    return File(os.path.join(pkg, _path),
                target,
                is_conda=True,
                prefix_placeholder=prefix_placeholder,
                file_mode=file_mode)


def load_managed_package(info, prefix, site_packages, all_files):
    pkg = info['link']['source']

    noarch_type = read_noarch_type(pkg)

    is_noarch = noarch_type == 'python'

    if is_noarch and site_packages is None:  # pragma: nocover
        raise CondaPackException("noarch: python package installed (%r), but "
                                 "Python not found in environment (%r)" %
                                 (info['name'], prefix))

    paths_json = os.path.join(pkg, 'info', 'paths.json')
    if os.path.exists(paths_json):
        with open(paths_json) as fil:
            paths = json.load(fil)

        files = [managed_file(is_noarch, site_packages, pkg, **r)
                 for r in paths['paths']]
    else:
        with open(os.path.join(pkg, 'info', 'files')) as fil:
            paths = [f.strip() for f in fil]

        has_prefix = os.path.join(pkg, 'info', 'has_prefix')

        if os.path.exists(has_prefix):
            prefixes = read_has_prefix(has_prefix)
            files = [managed_file(is_noarch, site_packages, pkg, p,
                                  *prefixes.get(p, ())) for p in paths]
        else:
            files = [managed_file(is_noarch, site_packages, pkg, p)
                     for p in paths]

    if is_noarch:
        seen = {os.path.normcase(i.target) for i in files}
        for fil in info['files']:
            # If the path hasn't been added yet, *and* the path isn't a pyc
            # file that failed to bytecode compile (e.g. a file that contains
            # py3 only features in a py2 env), then add the path.
            fil_normed = os.path.normcase(fil)
            if (fil_normed not in seen and not
                    (fil_normed.endswith('.pyc') and fil_normed not in all_files)):
                file_mode = 'unknown' if fil.startswith(BIN_DIR) else None
                f = File(os.path.join(prefix, fil), fil, is_conda=True,
                         prefix_placeholder=None, file_mode=file_mode)
                files.append(f)
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
prefixes aren't being handled as robustly.""".format(_uncached_error)


_missing_files_error = """
Files managed by conda were found to have been deleted/overwritten in the
following packages:

{0}

This is usually due to `pip` uninstalling or clobbering conda managed files,
resulting in an inconsistent environment. Please check your environment for
conda/pip conflicts using `conda list`, and fix the environment by ensuring
only one version of each package is installed (conda preferred)."""


def load_environment(prefix, on_missing_cache='warn'):
    # Check if it's a conda environment
    if not os.path.exists(prefix):
        raise CondaPackException("Environment path %r doesn't exist" % prefix)
    conda_meta = os.path.join(prefix, 'conda-meta')
    if not os.path.exists(conda_meta):
        raise CondaPackException("Path %r is not a conda environment" % prefix)

    # Find the environment site_packages (if any)
    site_packages = find_site_packages(prefix)

    if site_packages is not None:
        # Check that no editable packages are installed
        check_no_editable_packages(prefix, site_packages)

    # Save the unnormalized filenames here so that we can preserve the
    # case of unmanaged files. The case of managed files is dictated by
    # the conda package itself.
    all_files = {os.path.normcase(p): p for p in load_files(prefix)}

    files = []
    managed = set()
    uncached = []
    missing_files = []
    for path in os.listdir(conda_meta):
        if path.endswith('.json'):
            with open(os.path.join(conda_meta, path)) as fil:
                info = json.load(fil)

            pkg = info['link']['source']

            if not os.path.exists(pkg):
                # Package cache is cleared, set file_mode='unknown' to properly
                # handle prefix replacement ourselves later.
                new_files = [File(os.path.join(prefix, f), f, is_conda=True,
                                  prefix_placeholder=None, file_mode='unknown')
                             for f in info['files']]
                uncached.append((info['name'], info['version'], info['url']))
            else:
                new_files = load_managed_package(info, prefix, site_packages,
                                                 all_files)

            targets = {os.path.normcase(f.target) for f in new_files}

            if targets.difference(all_files):
                # Collect packages missing files as we progress to provide a
                # complete error message on failure.
                missing_files.append((info['name'], info['version']))

            managed.update(targets)
            files.extend(new_files)
            # Add conda-meta entry
            managed.add(os.path.join('conda-meta', path))
            files.append(File(os.path.join(conda_meta, path),
                              os.path.join('conda-meta', path),
                              is_conda=True,
                              prefix_placeholder=None,
                              file_mode=None))

    # Add remaining conda metadata files
    managed.add(os.path.join('conda-meta', 'history'))
    files.append(File(os.path.join(conda_meta, 'history'),
                      os.path.join('conda-meta', 'history'),
                      is_conda=True,
                      prefix_placeholder=None,
                      file_mode=None))

    if missing_files:
        packages = '\n'.join('- %s=%r' % i for i in missing_files)
        raise CondaPackException(_missing_files_error.format(packages))

    # Add unmanaged files, preserving their original case
    unmanaged = {fn for fn_l, fn in all_files.items() if fn_l not in managed}
    # Older versions of conda insert unmanaged conda, activate, and deactivate
    # scripts into child environments upon activation. Remove these
    fnames = ('conda', 'activate', 'deactivate')
    if on_win:
        # Windows includes the POSIX and .bat versions of each
        fnames = fnames + ('conda.bat', 'activate.bat', 'deactivate.bat')
    unmanaged -= {os.path.join(BIN_DIR, f) for f in fnames}

    files.extend(File(os.path.join(prefix, p),
                      p,
                      is_conda=False,
                      prefix_placeholder=None,
                      file_mode='unknown')
                 for p in unmanaged if not find_py_source(p) in managed)

    if uncached and on_missing_cache in ('warn', 'raise'):
        packages = '\n'.join('- %s=%r   %s' % i for i in uncached)
        if on_missing_cache == 'warn':
            context.warn(_uncached_warning.format(packages))
        else:
            raise CondaPackException(_uncached_error.format(packages))

    return files


def rewrite_shebang(data, target, prefix):
    """Rewrite a shebang header to ``#!usr/bin/env program...``.

    Returns
    -------
    data : bytes
    fixed : bool
        Whether the file was successfully fixed in the rewrite.
    """
    shebang_match = re.match(SHEBANG_REGEX, data, re.MULTILINE)
    prefix_b = prefix.encode('utf-8')

    if shebang_match:
        if data.count(prefix_b) > 1:
            # More than one occurrence of prefix, can't fully cleanup.
            return data, False

        shebang, executable, options = shebang_match.groups()

        if executable.startswith(prefix_b):
            # shebang points inside environment, rewrite
            executable_name = executable.decode('utf-8').split('/')[-1]
            new_shebang = '#!/usr/bin/env %s%s' % (executable_name,
                                                   options.decode('utf-8'))
            data = data.replace(shebang, new_shebang.encode('utf-8'))

            return data, True

    return data, False


def rewrite_conda_meta(source):
    """Remove absolute paths in conda-meta that reference local install.

    These are unnecessary for install/uninstall on the destination machine."""
    with open(source, 'r') as f:
        original = f.read()

    data = json.loads(original)
    for field in ["extracted_package_dir", "package_tarball_full_path"]:
        if field in data:
            data[field] = ""

    if "link" in data and "source" in data["link"]:
        data["link"]["source"] = ""

    out = json.dumps(data, indent=True, sort_keys=True)
    return out.encode()


_conda_unpack_template = """\
{shebang}
{prefixes_py}

_prefix_records = [
{prefix_records}
]

if __name__ == '__main__':
    import os
    import argparse
    parser = argparse.ArgumentParser(
            prog='conda-unpack',
            description=('Finish unpacking the environment after unarchiving.'
                         'Cleans up absolute prefixes in any remaining files'))
    parser.add_argument('--version',
                        action='store_true',
                        help='Show version then exit')
    args = parser.parse_args()
    # Manually handle version printing to output to stdout in python < 3.4
    if args.version:
        print('conda-unpack {version}')
    else:
        script_dir = os.path.dirname(__file__)
        new_prefix = os.path.abspath(os.path.dirname(script_dir))
        for path, placeholder, mode in _prefix_records:
            update_prefix(os.path.join(new_prefix, path), new_prefix,
                          placeholder, mode=mode)
"""


# Deduce file type for unmanaged packages. If decoding utf-8 is
# successful, we assume text, otherwise binary.
def is_binary_file(data):
    try:
        data.decode('utf-8')
        return False
    except UnicodeDecodeError:
        return True


class Packer(object):
    def __init__(self, prefix, archive, dest_prefix=None):
        self.prefix = prefix
        self.archive = archive
        self.dest = dest_prefix
        self.has_dest = dest_prefix is not None
        self.has_conda = False
        self.prefixes = []

    def add(self, file):
        # Windows note:
        # When adding files to an archive, that archive is generally
        # case-sensitive.  The target paths can be mixed case, and that means
        # that they will be distinct directories in the archive.
        #
        # If those files are then extracted onto a case-sensitive file-system
        # (such as a network share), Windows will not be able to traverse them
        # correctly.
        #
        # The simple (undesirable) solution is to normalize (lowercase) the
        # filenames when adding them to the archive.
        #
        # A nicer solution would be to note the "canonical" capitalization of a
        # prefix when it first occurs, and use that every time the prefix
        # occurs subsequently.
        #
        # We just ignore this problem for the time being.
        if file.file_mode is None:
            if fnmatch(file.target, 'conda-meta/*.json'):
                # Detect if conda is installed
                if os.path.basename(file.target).rsplit('-', 2)[0] == 'conda':
                    self.has_conda = True
                self.archive.add_bytes(file.source,
                                       rewrite_conda_meta(file.source),
                                       file.target)
            else:
                self.archive.add(file.source, file.target)
            return

        elif file.file_mode not in ('text', 'binary', 'unknown'):
            raise ValueError("unknown file_mode: %r" % file.file_mode)  # pragma: no cover

        elif os.path.isdir(file.source) or os.path.islink(file.source):
            self.archive.add(file.source, file.target)
            return

        file_mode = file.file_mode
        placeholder = file.prefix_placeholder
        if ((self.has_dest or
             file_mode == 'unknown' or
             file_mode == 'text' and file.target.startswith(BIN_DIR))):
            # In each of these cases, we need to inspect the file contents here.
            with open(file.source, 'rb') as fil:
                data = fil.read()
        else:
            # No need to read the file; just pass the filename to the archiver.
            self.archive.add(file.source, file.target)
            self.prefixes.append((file.target, placeholder, file_mode))
            return

        if file_mode == 'unknown':
            placeholder = self.prefix
            if is_binary_file(data):
                if on_win:
                    # The only binary replacement we do on Windows is distlib
                    # shebang replacement, safe for unmanaged binaries. For
                    # Unix (and other Windows binaries), we cannot trust that
                    # binary replacement can be done safely.
                    file_mode = 'binary'
            else:
                file_mode = 'text'

        if file_mode != 'unknown':
            if self.has_dest:
                data = replace_prefix(data, file_mode, placeholder, self.dest)
            else:
                if file_mode == 'text' and file.target.startswith(BIN_DIR):
                    data, fixed = rewrite_shebang(data, file.target, placeholder)
                else:
                    fixed = False
                if not fixed:
                    self.prefixes.append((file.target, placeholder, file_mode))

        self.archive.add_bytes(file.source, data, file.target)

    def finish(self):
        from . import __version__  # local import to avoid circular imports

        # Add conda-pack's activate/deactivate scripts
        if not (self.has_dest and self.has_conda):
            for source, target in _scripts:
                self.archive.add(source, target)

        # No `conda-unpack` command if dest-prefix specified
        if self.has_dest:
            return

        if on_win:
            shebang = '#!python.exe'
            # Don't just use os.path.join here: the backslash needs
            # to be doubled up for the sake of the regex match
            python_pattern = re.compile(BIN_DIR + r'\\python\d.\d')
        else:
            shebang = '#!/usr/bin/env python'
            python_pattern = re.compile(BIN_DIR + '/python')

        # We skip prefix rewriting in python executables (if needed)
        # to avoid editing a running file.
        prefix_records = ',\n'.join(repr(p) for p in self.prefixes
                                    if not python_pattern.match(p[0]))

        with open(os.path.join(_current_dir, 'prefixes.py')) as fil:
            prefixes_py = fil.read()

        script = _conda_unpack_template.format(shebang=shebang,
                                               prefix_records=prefix_records,
                                               prefixes_py=prefixes_py,
                                               version=__version__)

        fil = tempfile.NamedTemporaryFile(mode='w', delete=False)
        try:
            fil.write(script)
            fil.close()
            st = os.stat(fil.name)
            os.chmod(fil.name, st.st_mode | 0o111)  # make executable
            script_name = 'conda-unpack-script.py' if on_win else 'conda-unpack'
            self.archive.add(fil.name, os.path.join(BIN_DIR, script_name))
        finally:
            os.unlink(fil.name)

        if on_win:
            cli_exe = pkg_resources.resource_filename('setuptools', 'cli-64.exe')
            self.archive.add(cli_exe, os.path.join(BIN_DIR, 'conda-unpack.exe'))
