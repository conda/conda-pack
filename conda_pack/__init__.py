try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from .core import CondaEnv, CondaPackException, File, pack  # noqa: F401
