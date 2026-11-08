"""Source-tree ASGI entry point; the packaged adapter lives with the core."""

from terramind.api.app import app

__all__ = ["app"]
