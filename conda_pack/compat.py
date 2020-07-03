import os
import sys

default_encoding = sys.getdefaultencoding()
on_win = sys.platform == 'win32'
is_32bit = sys.maxsize < 2**32 or os.environ.get('CONDA_FORCE_32BIT', '0') == '1'

PY2 = sys.version_info.major == 2


if PY2:
    from imp import load_source
    from Queue import Queue

    def source_from_cache(path):
        if path.endswith('.pyc') or path.endswith('.pyo'):
            return path[:-1]
        raise ValueError("Path %s is not a python bytecode file" % path)
else:
    import importlib
    from importlib.util import source_from_cache
    from queue import Queue  # noqa

    def load_source(name, path):
        loader = importlib.machinery.SourceFileLoader(name, path)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


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
