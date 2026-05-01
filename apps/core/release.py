from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
import subprocess


SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")
TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")


@dataclass(frozen=True)
class ReleaseVersionState:
    version: str
    frontend_version: str


def get_version_file_path(base_dir: Path) -> Path:
    return base_dir / "VERSION"


def get_frontend_package_json_path(base_dir: Path) -> Path:
    return base_dir / "frontend" / "package.json"


def get_frontend_package_lock_path(base_dir: Path) -> Path:
    return base_dir / "frontend" / "package-lock.json"


def build_git_command(base_dir: Path, *args: str) -> list[str]:
    resolved_base_dir = str(base_dir.resolve())
    return ["git", "-c", f"safe.directory={resolved_base_dir}", *args]


def run_git_command(
    base_dir: Path,
    *args: str,
    capture_output: bool = True,
    text: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        build_git_command(base_dir, *args),
        cwd=str(base_dir),
        capture_output=capture_output,
        text=text,
        check=check,
    )


def load_release_version_state(base_dir: Path) -> ReleaseVersionState:
    version = get_version_file_path(base_dir).read_text(encoding="utf-8").strip()
    package = json.loads(get_frontend_package_json_path(base_dir).read_text(encoding="utf-8"))
    frontend_version = str(package.get("version", "")).strip()
    return ReleaseVersionState(version=version, frontend_version=frontend_version)


def validate_semver(value: str, *, field_name: str = "版本号") -> None:
    if not SEMVER_RE.match(value.strip()):
        raise ValueError(f"{field_name}必须是语义化版本号，例如 1.2.3")


def validate_release_tag(value: str) -> str:
    normalized = value.strip()
    if not TAG_RE.match(normalized):
        raise ValueError("Git tag 必须是 vX.Y.Z 格式，例如 v1.2.3")
    return normalized


def version_from_tag(tag: str) -> str:
    normalized = validate_release_tag(tag)
    return normalized[1:]


def ensure_release_versions_aligned(base_dir: Path) -> ReleaseVersionState:
    state = load_release_version_state(base_dir)
    validate_semver(state.version, field_name="VERSION")
    validate_semver(state.frontend_version, field_name="frontend/package.json version")
    if state.version != state.frontend_version:
        raise ValueError(
            "版本不一致：VERSION 与 frontend/package.json 的 version 必须完全一致"
        )
    return state


def update_frontend_versions(base_dir: Path, version: str) -> None:
    validate_semver(version)

    package_json_path = get_frontend_package_json_path(base_dir)
    package_lock_path = get_frontend_package_lock_path(base_dir)

    package = json.loads(package_json_path.read_text(encoding="utf-8"))
    package["version"] = version
    package_json_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    package_lock = json.loads(package_lock_path.read_text(encoding="utf-8"))
    package_lock["version"] = version
    root_package = package_lock.get("packages", {}).get("")
    if isinstance(root_package, dict):
        root_package["version"] = version
    package_lock_path.write_text(
        json.dumps(package_lock, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
