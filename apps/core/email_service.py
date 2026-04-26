"""
邮件发送服务
"""
import logging
import re
from email.utils import formataddr
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from apps.core.mail_templates import (
    DEFAULT_PASSWORD_RESET_HTML,
    DEFAULT_PASSWORD_RESET_SUBJECT,
    DEFAULT_PASSWORD_RESET_TEXT,
    DEFAULT_VERIFICATION_HTML,
    DEFAULT_VERIFICATION_SUBJECT,
    DEFAULT_VERIFICATION_TEXT,
)
from apps.core.mail_drivers import can_mail_driver_send, normalize_mail_driver
from apps.core.settings_service import BASIC_SETTINGS_DEFAULTS, get_mail_settings, get_setting_group

logger = logging.getLogger(__name__)


class EmailService:
    """邮件发送服务"""

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
    def send_verification_email(user_email: str, username: str, token: str) -> bool:
        """
        发送邮箱验证邮件

        Args:
            user_email: 用户邮箱
            username: 用户名
            token: 验证令牌

        Returns:
            bool: 是否发送成功
        """
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        mail_settings = EmailService.get_runtime_mail_settings()
        context = EmailService.build_mail_context(
            username=username,
            verification_url=verification_url,
            expires_in="24小时",
        )
        subject = EmailService.resolve_mail_template(
            mail_settings,
            "mail_verification_subject",
            DEFAULT_VERIFICATION_SUBJECT,
            context,
        )
        text_content = EmailService.resolve_mail_template(
            mail_settings,
            "mail_verification_text",
            DEFAULT_VERIFICATION_TEXT,
            context,
        )
        html_content = EmailService.resolve_mail_template(
            mail_settings,
            "mail_verification_html",
            DEFAULT_VERIFICATION_HTML,
            context,
        )

        return EmailService._send_email(
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            to_email=user_email
        )

    @staticmethod
    def send_password_reset_email(user_email: str, username: str, token: str) -> bool:
        """
        发送密码重置邮件

        Args:
            user_email: 用户邮箱
            username: 用户名
            token: 重置令牌

        Returns:
            bool: 是否发送成功
        """
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        mail_settings = EmailService.get_runtime_mail_settings()
        context = EmailService.build_mail_context(
            username=username,
            reset_url=reset_url,
            expires_in="1小时",
        )
        subject = EmailService.resolve_mail_template(
            mail_settings,
            "mail_password_reset_subject",
            DEFAULT_PASSWORD_RESET_SUBJECT,
            context,
        )
        text_content = EmailService.resolve_mail_template(
            mail_settings,
            "mail_password_reset_text",
            DEFAULT_PASSWORD_RESET_TEXT,
            context,
        )
        html_content = EmailService.resolve_mail_template(
            mail_settings,
            "mail_password_reset_html",
            DEFAULT_PASSWORD_RESET_HTML,
            context,
        )

        return EmailService._send_email(
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            to_email=user_email
        )

    @staticmethod
    def send_notification_email(
        user_email: str,
        username: str,
        notification_type: str,
        notification_data: dict
    ) -> bool:
        """
        发送通知邮件

        Args:
            user_email: 用户邮箱
            username: 用户名
            notification_type: 通知类型
            notification_data: 通知数据

        Returns:
            bool: 是否发送成功
        """
        # 根据通知类型生成邮件内容
        if notification_type == 'discussionReply':
            subject = f'您的讨论有新回复 - Bias'
            discussion_title = notification_data.get('discussion_title', '')
            discussion_url = f"{settings.FRONTEND_URL}/d/{notification_data.get('discussion_id')}"

            text_content = f"""
            您好 {username}，

            您的讨论 "{discussion_title}" 有新回复。

            查看详情：{discussion_url}

            ---
            Bias 团队
            """

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: #2ecc71; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background: #f9f9f9; }}
                    .button {{ display: inline-block; padding: 12px 24px; background: #2ecc71; color: white; text-decoration: none; border-radius: 4px; margin: 20px 0; }}
                    .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Bias</h1>
                    </div>
                    <div class="content">
                        <h2>您好 {username}，</h2>
                        <p>您的讨论 <strong>"{discussion_title}"</strong> 有新回复。</p>
                        <a href="{discussion_url}" class="button">查看详情</a>
                    </div>
                    <div class="footer">
                        <p>Bias 团队</p>
                        <p><a href="{settings.FRONTEND_URL}/settings/notifications">管理通知设置</a></p>
                    </div>
                </div>
            </body>
            </html>
            """

        elif notification_type == 'postLiked':
            subject = f'您的帖子被点赞 - Bias'
            discussion_title = notification_data.get('discussion_title', '')
            discussion_url = f"{settings.FRONTEND_URL}/d/{notification_data.get('discussion_id')}"

            text_content = f"""
            您好 {username}，

            您在 "{discussion_title}" 中的帖子被点赞了。

            查看详情：{discussion_url}

            ---
            Bias 团队
            """

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: #f39c12; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background: #f9f9f9; }}
                    .button {{ display: inline-block; padding: 12px 24px; background: #f39c12; color: white; text-decoration: none; border-radius: 4px; margin: 20px 0; }}
                    .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Bias</h1>
                    </div>
                    <div class="content">
                        <h2>您好 {username}，</h2>
                        <p>您在 <strong>"{discussion_title}"</strong> 中的帖子被点赞了。</p>
                        <a href="{discussion_url}" class="button">查看详情</a>
                    </div>
                    <div class="footer">
                        <p>Bias 团队</p>
                        <p><a href="{settings.FRONTEND_URL}/settings/notifications">管理通知设置</a></p>
                    </div>
                </div>
            </body>
            </html>
            """

        else:
            # 默认通知邮件
            subject = f'您有新通知 - Bias'
            text_content = f"您好 {username}，\n\n您有新通知。\n\n---\nBias 团队"
            html_content = f"<p>您好 {username}，</p><p>您有新通知。</p>"

        return EmailService._send_email(
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            to_email=user_email
        )

    @staticmethod
    def _send_email(
        subject: str,
        text_content: str,
        html_content: str,
        to_email: str,
        from_email: Optional[str] = None
    ) -> bool:
        """
        发送邮件（内部方法）

        Args:
            subject: 邮件主题
            text_content: 纯文本内容
            html_content: HTML内容
            to_email: 收件人邮箱
            from_email: 发件人邮箱（可选）

        Returns:
            bool: 是否发送成功
        """
        try:
            mail_settings = EmailService.get_runtime_mail_settings()
            if not can_mail_driver_send(mail_settings):
                logger.warning("邮件发送被跳过，当前邮件驱动不可发送")
                return False
            connection = EmailService.build_connection()
            mail_format = EmailService.get_mail_format(mail_settings)

            if from_email is None:
                from_email = EmailService.build_from_email(
                    mail_settings.get("mail_from_address") or settings.DEFAULT_FROM_EMAIL,
                    mail_settings.get("mail_from_name") or "",
                )

            # 创建邮件
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

            # 发送邮件
            email.send()

            logger.info(f"邮件发送成功: {to_email} - {subject}")
            return True

        except Exception as e:
            logger.error(f"邮件发送失败: {to_email} - {subject} - {str(e)}")
            return False

    @staticmethod
    def send_test_email(to_email: str) -> int:
        mail_settings = EmailService.get_runtime_mail_settings()
        if not can_mail_driver_send(mail_settings):
            raise ValueError("当前邮件配置不可发送，请先完成邮件设置")
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
