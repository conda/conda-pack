from . import _version
from .core import CondaEnv, CondaPackException, File, pack

__version__ = _version.get_versions()['version']
