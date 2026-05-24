class ExtensionError(Exception):
    """Base exception for extension system errors."""


class ExtensionManifestError(ExtensionError):
    """Raised when an extension manifest is invalid."""


class ExtensionNotFoundError(ExtensionError):
    """Raised when an extension cannot be found in the registry."""


class ExtensionStateError(ExtensionError):
    """Raised when an extension cannot transition to the requested state."""

    def __init__(self, message: str, *, code: str = "extension_state_error", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}
