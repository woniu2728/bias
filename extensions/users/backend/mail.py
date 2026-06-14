from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from apps.core.extensions.platform import can_mail_driver_send, send_with_extension_mail_driver

from apps.core.extensions.platform import EmailService
from apps.core.extensions.platform import QueueService
from extensions.users.backend.mail_templates import (
    DEFAULT_PASSWORD_RESET_HTML,
    DEFAULT_PASSWORD_RESET_SUBJECT,
    DEFAULT_PASSWORD_RESET_TEXT,
    DEFAULT_VERIFICATION_HTML,
    DEFAULT_VERIFICATION_SUBJECT,
    DEFAULT_VERIFICATION_TEXT,
)


def send_verification_email(user_email: str, username: str, token: str) -> bool:
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    mail_settings = EmailService.get_runtime_mail_settings()
    context = EmailService.build_mail_context(
        username=username,
        verification_url=verification_url,
        expires_in="24小时",
    )
    return EmailService.send_email(
        subject=EmailService.resolve_mail_template(
            mail_settings,
            "mail_verification_subject",
            DEFAULT_VERIFICATION_SUBJECT,
            context,
        ),
        text_content=EmailService.resolve_mail_template(
            mail_settings,
            "mail_verification_text",
            DEFAULT_VERIFICATION_TEXT,
            context,
        ),
        html_content=EmailService.resolve_mail_template(
            mail_settings,
            "mail_verification_html",
            DEFAULT_VERIFICATION_HTML,
            context,
        ),
        to_email=user_email,
    )


def queue_verification_email(user_email: str, username: str, token: str):
    from extensions.users.backend.tasks import send_verification_email_task

    return QueueService.dispatch_celery_task(
        send_verification_email_task,
        user_email,
        username,
        token,
        fallback=lambda: send_verification_email(user_email, username, token),
    )


def send_password_reset_email(user_email: str, username: str, token: str) -> bool:
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    mail_settings = EmailService.get_runtime_mail_settings()
    context = EmailService.build_mail_context(
        username=username,
        reset_url=reset_url,
        expires_in="1小时",
    )
    return EmailService.send_email(
        subject=EmailService.resolve_mail_template(
            mail_settings,
            "mail_password_reset_subject",
            DEFAULT_PASSWORD_RESET_SUBJECT,
            context,
        ),
        text_content=EmailService.resolve_mail_template(
            mail_settings,
            "mail_password_reset_text",
            DEFAULT_PASSWORD_RESET_TEXT,
            context,
        ),
        html_content=EmailService.resolve_mail_template(
            mail_settings,
            "mail_password_reset_html",
            DEFAULT_PASSWORD_RESET_HTML,
            context,
        ),
        to_email=user_email,
    )


def queue_password_reset_email(user_email: str, username: str, token: str):
    from extensions.users.backend.tasks import send_password_reset_email_task

    return QueueService.dispatch_celery_task(
        send_password_reset_email_task,
        user_email,
        username,
        token,
        fallback=lambda: send_password_reset_email(user_email, username, token),
    )


def send_test_email(to_email: str) -> int:
    mail_settings = EmailService.get_runtime_mail_settings()
    if not can_mail_driver_send(mail_settings):
        raise ValueError("当前邮件配置不可发送，请先完成邮件设置")
    extension_result = send_with_extension_mail_driver(
        mail_settings.get("mail_driver"),
        {
            "subject": "Bias 测试邮件",
            "text_content": "如果你收到这封邮件，说明 Bias 的邮件发送链路可用。",
            "html_content": "<p>如果你收到这封邮件，说明 Bias 的邮件发送链路可用。</p>",
            "to_email": to_email,
            "from_email": None,
            "settings": mail_settings,
        },
        {"source": "test_email"},
    )
    if extension_result is not None:
        return int(bool(extension_result))
    from_email = EmailService.build_from_email(
        mail_settings.get("mail_from_address") or settings.DEFAULT_FROM_EMAIL,
        mail_settings.get("mail_from_name") or "",
    )
    mail_format = EmailService.get_mail_format(mail_settings)

    email = EmailMultiAlternatives(
        subject="Bias 测试邮件",
        body="如果你收到这封邮件，说明 Bias 的邮件发送链路可用。",
        from_email=from_email,
        to=[to_email],
        connection=EmailService.build_connection(),
    )
    if mail_format == "html":
        email.body = "<p>如果你收到这封邮件，说明 Bias 的邮件发送链路可用。</p>"
        email.content_subtype = "html"
    elif mail_format == "multipart":
        email.attach_alternative("<p>如果你收到这封邮件，说明 Bias 的邮件发送链路可用。</p>", "text/html")
    return email.send()
