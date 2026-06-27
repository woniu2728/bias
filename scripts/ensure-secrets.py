from __future__ import annotations

import base64
import os
from pathlib import Path


def new_secret() -> str:
    return base64.urlsafe_b64encode(os.urandom(48)).decode("ascii")


def is_weak(value: str) -> bool:
    normalized = (value or "").strip().lower()
    return not normalized or any(token in normalized for token in ("changeme", "default", "placeholder"))


def is_development_email_backend(value: str) -> bool:
    normalized = (value or "").strip().lower()
    return not normalized or "console" in normalized or "locmem" in normalized


def main() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    required = {
        "SECRET_KEY": new_secret(),
        "JWT_SECRET_KEY": new_secret(),
        "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    }
    seen: set[str] = set()
    output: list[str] = []

    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            output.append(line)
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in required:
            seen.add(key)
            if key == "EMAIL_BACKEND":
                output.append(f"{key}={required[key] if is_development_email_backend(value) else value.strip()}")
            else:
                output.append(f"{key}={required[key] if is_weak(value) else value.strip()}")
        else:
            output.append(line)

    for key, value in required.items():
        if key not in seen:
            output.append(f"{key}={value}")

    env_path.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"Secrets ensured in {env_path}")


if __name__ == "__main__":
    main()
