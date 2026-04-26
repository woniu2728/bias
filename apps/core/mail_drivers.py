"""
邮件驱动定义与后台配置元数据
"""
from copy import deepcopy
from email.utils import formataddr, parseaddr

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


MAIL_DRIVER_DEFINITIONS = {
    "smtp": {
        "label": "SMTP",
        "description": "通过 SMTP 服务器直接发送邮件。",
        "fields": [
            {
                "key": "mail_host",
                "type": "text",
                "label": "主机",
                "placeholder": "smtp.gmail.com",
            },
            {
                "key": "mail_port",
                "type": "number",
                "label": "端口",
                "placeholder": "587",
            },
            {
                "key": "mail_encryption",
                "type": "select",
                "label": "加密方式",
                "help": "TLS 常用 587，SSL 常用 465，无加密仅建议在受信网络中使用。",
                "options": [
                    {"value": "", "label": "无"},
                    {"value": "tls", "label": "TLS"},
                    {"value": "ssl", "label": "SSL"},
                ],
            },
            {
                "key": "mail_username",
                "type": "text",
                "label": "用户名",
                "placeholder": "your@gmail.com",
            },
            {
                "key": "mail_password",
                "type": "password",
                "label": "密码",
                "placeholder": "应用专用密码",
            },
        ],
    },
}

def normalize_mail_driver(driver: str | None) -> str:
    normalized = str(driver or "").strip().lower()
    return normalized if normalized in MAIL_DRIVER_DEFINITIONS else "smtp"


def build_mail_from(address: str | None, name: str | None) -> str:
    mail_address = str(address or "").strip()
    mail_name = str(name or "").strip()
    if not mail_address:
        return ""
    return formataddr((mail_name, mail_address)) if mail_name else mail_address


def parse_mail_from(value: str | None) -> tuple[str, str]:
    raw = str(value or "").strip()
    if not raw:
        return "", ""

    display_name, address = parseaddr(raw)
    address = address.strip()
    if not address and "@" in raw and "<" not in raw and ">" not in raw:
        address = raw
        display_name = ""

    return address, display_name.strip()


def get_driver_definitions() -> dict:
    return deepcopy(MAIL_DRIVER_DEFINITIONS)


def serialize_mail_settings(settings_data: dict) -> dict:
    payload = dict(settings_data)
    payload["mail_driver"] = normalize_mail_driver(payload.get("mail_driver"))
    payload["mail_from"] = build_mail_from(
        payload.get("mail_from_address"),
        payload.get("mail_from_name"),
    )
    return payload


def validate_mail_settings(settings_data: dict) -> dict[str, list[str]]:
    values = serialize_mail_settings(settings_data)
    errors: dict[str, list[str]] = {}

    driver = normalize_mail_driver(values.get("mail_driver"))
    mail_from = str(values.get("mail_from") or "").strip()

    if not mail_from:
        errors.setdefault("mail_from", []).append("发件地址不能为空")
    else:
        address, _ = parse_mail_from(mail_from)
        try:
            validate_email(address)
        except ValidationError:
            errors.setdefault("mail_from", []).append("发件地址格式无效")

    mail_format = str(values.get("mail_format") or "multipart").strip().lower()
    if mail_format not in {"multipart", "plain", "html"}:
        errors.setdefault("mail_format", []).append("邮件格式无效")

    if driver == "smtp":
        host = str(values.get("mail_host") or "").strip()
        if not host:
            errors.setdefault("mail_host", []).append("SMTP 主机不能为空")

        port = str(values.get("mail_port") or "").strip()
        if port:
            try:
                parsed_port = int(port)
            except (TypeError, ValueError):
                parsed_port = 0
            if parsed_port <= 0:
                errors.setdefault("mail_port", []).append("SMTP 端口必须是正整数")

        encryption = str(values.get("mail_encryption") or "").strip().lower()
        if encryption not in {"", "tls", "ssl"}:
            errors.setdefault("mail_encryption", []).append("加密方式无效")

    return errors


def can_mail_driver_send(settings_data: dict, errors: dict | None = None) -> bool:
    values = serialize_mail_settings(settings_data)
    return not bool(errors or validate_mail_settings(values))
