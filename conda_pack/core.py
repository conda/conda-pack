import json
import os
import shlex


class CondaPackException(Exception):
    """Internal exception to report to user"""
    pass


# String is split so as not to appear in the file bytes unintentionally
PREFIX_PLACEHOLDER = ('/opt/anaconda1anaconda2'
                      'anaconda3')


def noarch_type(pkg):
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


def _load_has_prefix(path):
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


class FileRecord(object):
    __slots__ = ('path', 'path_type', 'file_mode', 'prefix_placeholder')

    def __init__(self, _path, path_type, prefix_placeholder=None,
                 file_mode=None, **ignored):
        self.path = _path
        self.path_type = path_type
        self.prefix_placeholder = prefix_placeholder
        self.file_mode = file_mode

    def __repr__(self):
        return 'FileRecord<%r>' % self.path


class Package(object):
    __slots__ = ('root', 'files')

    def __init__(self, root, files):
        self.root = root
        self.files = files

    def __repr__(self):
        return 'Package<%r, %d files>' % (self.root, len(self.files))

    @classmethod
    def from_path(cls, root):
        paths_json = os.path.join(root, 'info', 'paths.json')
        if os.path.exists(paths_json):
            with open(paths_json) as fil:
                paths = json.load(fil)
            files = [FileRecord(**r) for r in paths['paths']]
        else:
            with open(os.path.join(root, 'info', 'files')) as fil:
                paths = [f.strip() for f in fil]

            has_prefix = os.path.join(root, 'info', 'has_prefix')

            if os.path.exists(has_prefix):
                prefixes = _load_has_prefix(has_prefix)
                files = [FileRecord(p, 'hardlink', *prefixes.get(p, ()))
                         for p in paths]
            else:
                files = [FileRecord(p, 'hardlink') for p in paths]

        return cls(root, files)


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

    res -= managed
    res -= remove

    return {p for p in res
            if not (p.endswith('~') or
                    p.endswith('.DS_Store') or
                    (p.endswith('.pyc') and p[:-1] in managed))}


class Environment(object):
    __slots__ = ('prefix', 'packages', 'unmanaged')

    def __init__(self, prefix, packages, unmanaged=None):
        self.prefix = prefix
        self.packages = packages
        self.unmanaged = unmanaged

    def __repr__(self):
        npackages = len(self.packages)
        nfiles = sum(len(p.files) for p in self.packages)
        return ('Environment<%r, %d packages, '
                '%d files>') % (self.prefix, npackages, nfiles)

    @classmethod
    def from_prefix(cls, prefix, unmanaged=True):
        conda_meta = os.path.join(prefix, 'conda-meta')
        if not os.path.exists(conda_meta):
            raise CondaPackException("Path %r is not a conda "
                                     "environment" % prefix)

        packages = []
        for path in os.listdir(conda_meta):
            if path.endswith('.json'):
                with open(os.path.join(conda_meta, path)) as fil:
                    info = json.load(fil)
                source = info['link']['source']
                packages.append(Package.from_path(source))

        if unmanaged:
            managed = set(f.path for p in packages for f in p.files)
            unmanaged = collect_unmanaged(prefix, managed)
        else:
            unmanaged = None

        return cls(prefix, packages, unmanaged)
