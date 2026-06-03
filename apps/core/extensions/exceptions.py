class ExtensionError(Exception):
    """Base exception for extension system errors."""


class ExtensionManifestError(ExtensionError):
    """Raised when an extension manifest is invalid."""


class ExtensionBootError(ExtensionError):
    """Raised when an extension extender fails during application boot."""

    def __init__(self, extension_id: str, extender: object, original: Exception):
        extender_name = extender.__class__.__name__
        super().__init__(f"扩展 {extension_id} 的 {extender_name} 启动失败: {original}")
        self.extension_id = extension_id
        self.extender = extender
        self.original = original


class ExtensionDependencyError(ExtensionError):
    """Raised when extension dependency order cannot be resolved."""

    def __init__(
        self,
        message: str,
        *,
        missing_dependencies: dict[str, list[str]] | None = None,
        circular_dependencies: list[str] | None = None,
    ):
        super().__init__(message)
        self.missing_dependencies = missing_dependencies or {}
        self.circular_dependencies = circular_dependencies or []


class ExtensionNotFoundError(ExtensionError):
    """Raised when an extension cannot be found in the registry."""


class ExtensionStateError(ExtensionError):
    """Raised when an extension cannot transition to the requested state."""

    def __init__(self, message: str, *, code: str = "extension_state_error", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}
