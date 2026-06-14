from __future__ import annotations

from dataclasses import dataclass, field

from apps.core.extensions.types import ExtensionManifest


@dataclass(frozen=True)
class ExtensionValidationIssue:
    level: str
    code: str
    message: str
    extension_id: str = ""
    field: str = ""


@dataclass(frozen=True)
class ExtensionValidationResult:
    manifests: tuple[ExtensionManifest, ...] = ()
    issues: tuple[ExtensionValidationIssue, ...] = ()

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.issues if item.level == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for item in self.issues if item.level == "warning")

    @property
    def ok(self) -> bool:
        return self.error_count == 0


@dataclass
class ExtensionValidationCollector:
    manifests: list[ExtensionManifest] = field(default_factory=list)
    issues: list[ExtensionValidationIssue] = field(default_factory=list)

    def add_error(self, code: str, message: str, *, extension_id: str = "", field: str = "") -> None:
        self.issues.append(ExtensionValidationIssue(
            level="error",
            code=code,
            message=message,
            extension_id=extension_id,
            field=field,
        ))

    def add_warning(self, code: str, message: str, *, extension_id: str = "", field: str = "") -> None:
        self.issues.append(ExtensionValidationIssue(
            level="warning",
            code=code,
            message=message,
            extension_id=extension_id,
            field=field,
        ))

    def build(self) -> ExtensionValidationResult:
        return ExtensionValidationResult(
            manifests=tuple(self.manifests),
            issues=tuple(self.issues),
        )
