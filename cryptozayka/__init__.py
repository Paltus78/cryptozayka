"""CryptoZayka – async airdrop automation framework."""
from importlib.metadata import version as _pkg_version

__all__: list[str] = ["__version__"]

try:
    __version__: str = _pkg_version("cryptozayka")
except Exception:  # pragma: no cover – during local dev the dist metadata may be missing
    __version__ = "0.0.0"
