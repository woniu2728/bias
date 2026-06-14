from __future__ import annotations

from pathlib import Path

from apps.core.extensions.types import ExtensionManifest
from apps.core.extensions.validation_rules import (
    EXTENSION_SOURCE_SUFFIXES,
    FORBIDDEN_CROSS_EXTENSION_INTERNAL_IMPORT_RE,
    FORBIDDEN_EXTENSION_MANIFEST_FIELD_PATTERNS,
    FORBIDDEN_EXTENSION_SOURCE_PATTERNS,
    PYTHON_EXTENSION_IMPORT_PATTERN,
    PYTHON_EXTENSION_INTERNAL_IMPORT_PATTERN,
    SKIPPED_SOURCE_DIRS,
)
from apps.core.extensions.validation_types import ExtensionValidationCollector


def validate_distribution_signature(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    base_path: Path,
) -> None:
    signature_url = str(manifest.distribution.signature_url or "").strip()
    if not signature_url or is_remote_url(signature_url):
        return

    signature_path = resolve_extension_local_path(signature_url, manifest=manifest, base_path=base_path)
    if not signature_path.exists() or not signature_path.is_file():
        collector.add_warning(
            "missing_distribution_signature_file",
            f"distribution.signature_url 指向的本地签名文件不存在: {signature_url}",
            extension_id=manifest.id,
            field="distribution.signature_url",
        )


def validate_manifest_field_contracts(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    base_path: Path,
) -> None:
    manifest_path = extension_root_path(manifest, base_path) / "extension.json"
    if not manifest_path.exists():
        return
    try:
        source = manifest_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    relative_path = manifest_path.relative_to(base_path.parent).as_posix()
    for code, pattern, message in FORBIDDEN_EXTENSION_MANIFEST_FIELD_PATTERNS:
        if pattern.search(source):
            collector.add_error(
                code,
                f"{message} 文件: {relative_path}",
                extension_id=manifest.id,
                field=relative_path,
            )


def validate_extension_source_contracts(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    base_path: Path,
) -> None:
    extension_dir = extension_root_path(manifest, base_path)
    if not extension_dir.exists():
        return

    for file_path in iter_extension_source_files(extension_dir):
        try:
            source = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        relative_path = file_path.relative_to(base_path.parent).as_posix()
        for code, pattern, message in FORBIDDEN_EXTENSION_SOURCE_PATTERNS:
            if pattern.search(source):
                collector.add_error(
                    code,
                    f"{message} 文件: {relative_path}",
                    extension_id=manifest.id,
                    field=relative_path,
                )


def validate_cross_extension_imports(
    collector: ExtensionValidationCollector,
    manifest: ExtensionManifest,
    base_path: Path,
    *,
    known_extension_ids: set[str],
) -> None:
    extension_dir = extension_root_path(manifest, base_path)
    if not extension_dir.exists():
        return

    required_dependencies = set(manifest.dependencies)
    optional_dependencies = set(manifest.optional_dependencies)
    for file_path in iter_extension_runtime_python_files(extension_dir):
        try:
            source = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        relative_path = file_path.relative_to(base_path.parent).as_posix()
        internal_import_spans: set[tuple[int, int]] = set()
        for match in PYTHON_EXTENSION_INTERNAL_IMPORT_PATTERN.finditer(source):
            imported_module = str(match.group(1) or match.group(3) or "").strip()
            imported_tail = str(match.group(2) or match.group(4) or "").strip()
            imported_extension_id = imported_module.replace("_", "-")
            if (
                not imported_extension_id
                or imported_extension_id == manifest.id
                or imported_extension_id not in known_extension_ids
                or not FORBIDDEN_CROSS_EXTENSION_INTERNAL_IMPORT_RE.match(imported_tail)
            ):
                continue
            internal_import_spans.add(match.span())
            collector.add_error(
                "forbidden_cross_extension_internal_import",
                f"扩展源码导入了 {imported_extension_id} 的内部 {imported_tail.lstrip('.')} 模块。"
                "跨扩展业务协作必须通过宿主 runtime service、事件或公开 extender capability，不能直接依赖其它扩展的内部 backend 模块。",
                extension_id=manifest.id,
                field=relative_path,
            )

        for match in PYTHON_EXTENSION_IMPORT_PATTERN.finditer(source):
            if match.span() in internal_import_spans:
                continue
            imported_module = str(match.group(1) or match.group(3) or "").strip()
            imported_extension_id = imported_module.replace("_", "-")
            if (
                not imported_extension_id
                or imported_extension_id == manifest.id
                or imported_extension_id not in known_extension_ids
            ):
                continue
            if imported_extension_id in optional_dependencies:
                collector.add_error(
                    "optional_dependency_top_level_import",
                    f"扩展源码在模块顶层导入了可选依赖 {imported_extension_id}。"
                    "可选依赖必须通过 ConditionalExtender 与函数内延迟导入表达，避免未启用扩展被硬加载。",
                    extension_id=manifest.id,
                    field=relative_path,
                )
                continue
            if imported_extension_id in required_dependencies:
                continue
            collector.add_error(
                "undeclared_cross_extension_import",
                f"扩展源码导入了 {imported_extension_id}，但未在 dependencies 或 optional_dependencies 中声明。"
                "请通过扩展依赖显式表达跨扩展耦合。",
                extension_id=manifest.id,
                field=relative_path,
            )


def iter_extension_source_files(extension_dir: Path):
    for file_path in extension_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part in SKIPPED_SOURCE_DIRS for part in file_path.parts):
            continue
        if file_path.suffix.lower() not in EXTENSION_SOURCE_SUFFIXES:
            continue
        yield file_path


def iter_extension_runtime_python_files(extension_dir: Path):
    for file_path in extension_dir.rglob("*.py"):
        if not file_path.is_file():
            continue
        if any(part in SKIPPED_SOURCE_DIRS for part in file_path.parts):
            continue
        if file_path.name == "tests.py" or file_path.name.startswith("test_") or file_path.name.endswith("_test.py"):
            continue
        yield file_path


def is_remote_url(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized.startswith(("http://", "https://"))


def resolve_extension_local_path(value: str, *, manifest: ExtensionManifest, base_path: Path) -> Path:
    normalized = str(value or "").strip()
    if normalized.startswith("file://"):
        normalized = normalized[7:]
    path = Path(normalized)
    if path.is_absolute():
        return path
    root_path = extension_root_path(manifest, base_path)
    return root_path / path


def extension_root_path(manifest: ExtensionManifest, base_path: Path) -> Path:
    manifest_path = str(getattr(manifest, "path", "") or "").strip()
    return Path(manifest_path) if manifest_path else Path(base_path) / manifest.id
