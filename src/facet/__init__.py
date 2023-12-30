import importlib.metadata

from facet.asyncio import AsyncioServiceMixin
from facet.asyncio import AsyncioServiceMixin as ServiceMixin
from facet.blocking import BlockingServiceMixin

__all__ = ("AsyncioServiceMixin", "ServiceMixin", "BlockingServiceMixin", "__version__", "version")
__version__ = importlib.metadata.version(__package__)
version = tuple(map(int, __version__.split(".")))
