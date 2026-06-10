from celery import shared_task

from extensions.users.backend.mail import send_password_reset_email, send_verification_email


@shared_task(ignore_result=True)
def send_verification_email_task(user_email: str, username: str, token: str):
    send_verification_email(user_email=user_email, username=username, token=token)


@shared_task(ignore_result=True)
def send_password_reset_email_task(user_email: str, username: str, token: str):
    send_password_reset_email(user_email=user_email, username=username, token=token)
