class ExtensionError(Exception):
    """Base exception for extension system errors."""


class ExtensionManifestError(ExtensionError):
    """Raised when an extension manifest is invalid."""


class ExtensionNotFoundError(ExtensionError):
    """Raised when an extension cannot be found in the registry."""
