from __future__ import print_function, absolute_import

from .core import CondaEnv, File, CondaPackException, pack

from . import _version
__version__ = _version.get_versions()['version']
