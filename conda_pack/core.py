import glob
import json
import os
import shlex
import sys


on_win = sys.platform == 'win32'


class CondaPackException(Exception):
    """Internal exception to report to user"""
    pass


def find_site_packages(prefix):
    # Ensure there is at most one version of python installed
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
        return None

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


class Record(object):
    __slots__ = ('source', 'target', 'link_type',
                 'prefix_placeholder', 'file_mode')

    def __init__(self, source, target, link_type=None, prefix_placeholder=None,
                 file_mode=None):
        self.source = source
        self.target = target
        self.link_type = link_type
        self.prefix_placeholder = prefix_placeholder
        self.file_mode = file_mode

    def __repr__(self):
        return 'Record<%r>' % self.target


def load_package(site_packages, meta_json):
    with open(meta_json) as fil:
        info = json.load(fil)
    pkg = info['link']['source']

    noarch_type = read_noarch_type(pkg)

    if noarch_type == 'python':
        def record(_path, path_type=None, prefix_placeholder=None,
                   file_mode=None, **ignored):
            if _path.startswith('site-packages/'):
                target = site_packages + _path[13:]
            elif _path.startswith('python-scripts/'):
                bin_dir = 'Scripts' if on_win else 'bin'
                target = bin_dir + _path[14:]
            else:
                target = _path
            return Record(os.path.join(pkg, _path), target, path_type,
                          prefix_placeholder, file_mode)
    else:
        def record(_path, path_type=None, prefix_placeholder=None,
                   file_mode=None, **ignored):
            return Record(os.path.join(pkg, _path), _path, path_type,
                          prefix_placeholder, file_mode)

    paths_json = os.path.join(pkg, 'info', 'paths.json')
    if os.path.exists(paths_json):
        with open(paths_json) as fil:
            paths = json.load(fil)

        files = [record(**r) for r in paths['paths']]
    else:
        with open(os.path.join(pkg, 'info', 'files')) as fil:
            paths = [f.strip() for f in fil]

        has_prefix = os.path.join(pkg, 'info', 'has_prefix')

        if os.path.exists(has_prefix):
            prefixes = read_has_prefix(has_prefix)
            files = [record(p, None, *prefixes.get(p, ())) for p in paths]
        else:
            files = [record(p) for p in paths]

    if noarch_type == 'python':
        seen = {i.target for i in files}
        files.extend(Record(fil, fil, None) for fil in info['files']
                     if fil not in seen)

    return files


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

    return [p for p in res
            if not (p.endswith('~') or
                    p.endswith('.DS_Store') or
                    (p.endswith('.pyc') and p[:-1] in managed))]


def load_environment(prefix, unmanaged=True):
    conda_meta = os.path.join(prefix, 'conda-meta')
    if not os.path.exists(conda_meta):
        raise CondaPackException("Path %r is not a conda environment" % prefix)

    site_packages = find_site_packages(prefix)

    managed_files = []
    for path in os.listdir(conda_meta):
        if path.endswith('.json'):
            managed_files.extend(load_package(site_packages,
                                              os.path.join(conda_meta, path)))

    if unmanaged:
        unmanaged_files = collect_unmanaged(prefix, managed_files)
    else:
        unmanaged_files = None

    return managed_files, unmanaged_files
