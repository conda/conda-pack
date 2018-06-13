from __future__ import print_function, absolute_import

from .core import CondaEnv, File, CondaPackException, pack

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
