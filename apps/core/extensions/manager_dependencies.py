from __future__ import annotations

from apps.core.extensions.extension_runtime import Extension


def get_core_satisfied_dependency_ids() -> set[str]:
    try:
        from apps.core.forum_registry import get_core_module_ids

        return set(get_core_module_ids())
    except Exception:
        return {"core"}


def resolve_extension_order(extensions: list[Extension], *, satisfied_dependency_ids: set[str] | None = None) -> dict:
    satisfied_dependency_ids = set(satisfied_dependency_ids or set())
    extension_map = {extension.id: extension for extension in extensions}
    sorted_extensions = sorted(extensions, key=lambda item: item.id)
    graph: dict[str, list[str]] = {}
    in_degree: dict[str, int] = {extension.id: 0 for extension in sorted_extensions}
    missing_dependencies: dict[str, list[str]] = {}

    for extension in sorted_extensions:
        dependencies = list(extension.manifest.dependencies)
        optional_dependencies = [
            dependency_id
            for dependency_id in extension.manifest.optional_dependencies
            if dependency_id in extension_map
        ]
        graph.setdefault(extension.id, [])
        for dependency_id in [*dependencies, *optional_dependencies]:
            if dependency_id in satisfied_dependency_ids:
                continue
            if dependency_id not in extension_map:
                if dependency_id in dependencies:
                    missing_dependencies.setdefault(extension.id, []).append(dependency_id)
                continue
            graph.setdefault(dependency_id, [])
            graph[dependency_id].append(extension.id)
            in_degree[extension.id] = in_degree.get(extension.id, 0) + 1

    pending = sorted([extension_id for extension_id, count in in_degree.items() if count == 0])
    output: list[str] = []
    while pending:
        active = pending.pop(0)
        output.append(active)
        for dependent_id in sorted(graph.get(active, [])):
            in_degree[dependent_id] -= 1
            if in_degree[dependent_id] == 0:
                pending.append(dependent_id)

    circular_dependencies = sorted([
        extension_id
        for extension_id, count in in_degree.items()
        if count > 0
    ])
    valid_ids = [
        extension_id
        for extension_id in output
        if extension_id not in missing_dependencies
    ]

    return {
        "valid": [extension_map[extension_id] for extension_id in valid_ids],
        "order": valid_ids,
        "graph": graph,
        "missing_dependencies": missing_dependencies,
        "circular_dependencies": circular_dependencies,
    }


def build_dependency_resolution_payload(extensions: list[Extension]) -> dict:
    resolved = resolve_extension_order(
        extensions,
        satisfied_dependency_ids=get_core_satisfied_dependency_ids(),
    )
    dependents: dict[str, list[str]] = {extension.id: [] for extension in extensions}
    for dependency_id, dependent_ids in dict(resolved.get("graph") or {}).items():
        for dependent_id in dependent_ids:
            dependents.setdefault(dependency_id, [])
            if dependent_id not in dependents[dependency_id]:
                dependents[dependency_id].append(dependent_id)
    extension_map = {extension.id: extension for extension in extensions}
    graph = {}
    for extension in sorted(extensions, key=lambda item: item.id):
        optional_dependencies = [
            dependency_id
            for dependency_id in extension.manifest.optional_dependencies
            if dependency_id in extension_map
        ]
        graph[extension.id] = {
            "dependencies": list(extension.manifest.dependencies),
            "optional_dependencies": optional_dependencies,
            "dependents": sorted(dependents.get(extension.id, [])),
        }
    return {
        "boot_order": list(resolved.get("order") or []),
        "graph": graph,
        "missing_dependencies": dict(resolved.get("missing_dependencies") or {}),
        "circular_dependencies": list(resolved.get("circular_dependencies") or []),
    }
