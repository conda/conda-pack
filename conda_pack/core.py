import glob
import json
import os
import shlex
import sys
from functools import partial
from collections import namedtuple


on_win = sys.platform == 'win32'
bin_dir = 'Scripts' if on_win else 'bin'


if sys.version_info.major == 2:
    def source_from_cache(path):
        if path.endswith('.pyc') or path.endswith('.pyo'):
            return path[:-1]
        raise ValueError("Path %s is not a python bytecode file" % path)
else:
    from importlib.util import source_from_cache


def find_py_source(path, ignore=True):
    """Find the source file for a given bytecode file.

    If ignore is True, errors are swallowed and None is returned"""
    if not ignore:
        return source_from_cache(path)
    else:
        try:
            return source_from_cache(path)
        except (NotImplementedError, ValueError):
            return None


class CondaPackException(Exception):
    """Internal exception to report to user"""
    pass


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


PrefixInfo = namedtuple('PrefixInfo', ['placeholder', 'mode'],
                        module='conda_pack.core')


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


def make_noarch_python(site_packages, pkg, _path, path_type=None,
                       prefix_placeholder=None, file_mode=None, **ignored):
    if _path.startswith('site-packages/'):
        target = site_packages + _path[13:]
    elif _path.startswith('python-scripts/'):
        target = bin_dir + _path[14:]
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


def load_package(prefix, site_packages, meta_json):
    with open(meta_json) as fil:
        info = json.load(fil)
    pkg = info['link']['source']

    if not os.path.exists(pkg):
        # Package cache is cleared, return list of unmanaged files
        # to properly handle prefix replacement ourselves.
        # TODO: add optional warning when uncached files are found.
        return [make_unmanaged(prefix, f) for f in info['files']]

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


def load_environment(prefix, unmanaged=True):
    conda_meta = os.path.join(prefix, 'conda-meta')
    if not os.path.exists(conda_meta):
        raise CondaPackException("Path %r is not a conda environment" % prefix)

    site_packages = find_site_packages(prefix)

    files = []
    for path in os.listdir(conda_meta):
        if path.endswith('.json'):
            meta_json = os.path.join(conda_meta, path)
            files.extend(load_package(prefix, site_packages, meta_json))

    if unmanaged:
        files.extend(collect_unmanaged(prefix, files))

    return files
