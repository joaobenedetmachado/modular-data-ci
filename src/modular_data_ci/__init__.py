"""Modular Data CI: configuration-driven data quality checks for CI."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("modular-data-ci")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
