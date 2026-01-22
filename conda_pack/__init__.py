from importlib.metadata import version

__version__ = version("conda-pack")

from .core import CondaEnv as CondaEnv
from .core import CondaPackException as CondaPackException
from .core import File as File
from .core import pack as pack

__all__ = ["CondaEnv", "CondaPackException", "File", "pack"]
