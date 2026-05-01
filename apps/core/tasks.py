from celery import shared_task

from apps.core.email_service import EmailService


@shared_task(ignore_result=True)
def send_verification_email_task(user_email: str, username: str, token: str):
    EmailService.send_verification_email(user_email=user_email, username=username, token=token)


@shared_task(ignore_result=True)
def send_password_reset_email_task(user_email: str, username: str, token: str):
    EmailService.send_password_reset_email(user_email=user_email, username=username, token=token)
