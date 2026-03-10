"""LiDMaS+ Python launcher package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("lidmas")
except PackageNotFoundError:
    __version__ = "0+local"

