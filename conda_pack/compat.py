import sys

default_encoding = sys.getdefaultencoding()
on_win = sys.platform == 'win32'


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
