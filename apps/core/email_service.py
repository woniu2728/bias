"""
邮件发送宿主服务。
"""
import logging
import re
from email.utils import formataddr
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from apps.core.mail_drivers import can_mail_driver_send, normalize_mail_driver, send_with_extension_mail_driver
from apps.core.settings_service import BASIC_SETTINGS_DEFAULTS, get_mail_settings, get_setting_group

logger = logging.getLogger(__name__)


class EmailService:
    """邮件发送宿主服务"""

    @staticmethod
    def get_runtime_mail_settings() -> dict:
        mail_settings = get_mail_settings()
        if not mail_settings["mail_password"]:
            mail_settings["mail_password"] = getattr(settings, "EMAIL_HOST_PASSWORD", "")
        return mail_settings

    @staticmethod
    def get_site_name() -> str:
        forum_settings = get_setting_group("basic", BASIC_SETTINGS_DEFAULTS)
        return str(forum_settings.get("forum_title") or BASIC_SETTINGS_DEFAULTS["forum_title"]).strip()

    @staticmethod
    def render_template(template: str, context: dict) -> str:
        def replace(match):
            key = match.group(1)
            return str(context.get(key, ""))

        return re.sub(r"{{\s*([a-zA-Z0-9_]+)\s*}}", replace, template)

    @staticmethod
    def build_mail_context(**extra) -> dict:
        context = {
            "site_name": EmailService.get_site_name(),
            "site_url": getattr(settings, "FRONTEND_URL", "").rstrip("/"),
        }
        context.update({key: value for key, value in extra.items() if value is not None})
        return context

    @staticmethod
    def resolve_mail_template(mail_settings: dict, field: str, default_template: str, context: dict) -> str:
        template = str(mail_settings.get(field) or "").strip()
        if not template:
            template = default_template
        return EmailService.render_template(template, context)

    @staticmethod
    def build_from_email(from_address: str, from_name: str) -> str:
        if from_name:
            return formataddr((from_name, from_address))
        return from_address

    @staticmethod
    def build_connection():
        mail_settings = EmailService.get_runtime_mail_settings()
        mail_settings["mail_driver"] = normalize_mail_driver(mail_settings.get("mail_driver"))
        return get_connection(
            backend=getattr(settings, "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"),
            host=mail_settings.get("mail_host") or getattr(settings, "EMAIL_HOST", ""),
            port=int(mail_settings.get("mail_port") or getattr(settings, "EMAIL_PORT", 587)),
            username=mail_settings.get("mail_username") or getattr(settings, "EMAIL_HOST_USER", ""),
            password=mail_settings.get("mail_password") or getattr(settings, "EMAIL_HOST_PASSWORD", ""),
            use_tls=(mail_settings.get("mail_encryption") == "tls"),
            use_ssl=(mail_settings.get("mail_encryption") == "ssl"),
            fail_silently=False,
        )

    @staticmethod
    def get_mail_format(mail_settings: dict) -> str:
        mail_format = str(mail_settings.get("mail_format") or "multipart").strip().lower()
        return mail_format if mail_format in {"multipart", "plain", "html"} else "multipart"

    @staticmethod
    def send_email(
        subject: str,
        text_content: str,
        html_content: str,
        to_email: str,
        from_email: Optional[str] = None,
        *,
        source: str = "email_service",
    ) -> bool:
        try:
            mail_settings = EmailService.get_runtime_mail_settings()
            if not can_mail_driver_send(mail_settings):
                logger.warning("邮件发送被跳过，当前邮件驱动不可发送")
                return False
            extension_result = send_with_extension_mail_driver(
                mail_settings.get("mail_driver"),
                {
                    "subject": subject,
                    "text_content": text_content,
                    "html_content": html_content,
                    "to_email": to_email,
                    "from_email": from_email,
                    "settings": mail_settings,
                },
                {"source": source},
            )
            if extension_result is not None:
                return bool(extension_result)
            connection = EmailService.build_connection()
            mail_format = EmailService.get_mail_format(mail_settings)

            if from_email is None:
                from_email = EmailService.build_from_email(
                    mail_settings.get("mail_from_address") or settings.DEFAULT_FROM_EMAIL,
                    mail_settings.get("mail_from_name") or "",
                )

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=[to_email],
                connection=connection,
            )

            if mail_format == "html":
                email.body = html_content
                email.content_subtype = "html"
            elif mail_format == "multipart":
                email.attach_alternative(html_content, "text/html")

            email.send()

            logger.info("邮件发送成功: %s - %s", to_email, subject)
            return True

        except Exception as exc:
            logger.error("邮件发送失败: %s - %s - %s", to_email, subject, str(exc))
            return False
