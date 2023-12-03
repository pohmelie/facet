import importlib.metadata

from facet.asyncio import ServiceMixin

__all__ = ("ServiceMixin", "__version__", "version")
__version__ = importlib.metadata.version(__package__)
version = tuple(map(int, __version__.split(".")))
