"""Local browser player for lore2mud."""

from lore2mud.web.app import PlayerSession
from lore2mud.web.server import create_server, serve

__all__ = ["PlayerSession", "create_server", "serve"]
