from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Mailing, MailingAttempt


class MailingSendError(Exception):
    """Ошибка запуска рассылки."""


@dataclass
class MailingSendResult:
    """Результат запуска рассылки."""

    total: int
    successful: int
    failed: int


def send_mailing(mailing: Mailing) -> MailingSendResult:
    """Отправляет рассылку и сохраняет историю попыток."""

    now = timezone.now()

    if not mailing.is_enabled:
        raise MailingSendError("Рассылка отключена. Отправка невозможна.")

    if not mailing.start_time <= now <= mailing.end_time:
        raise MailingSendError(
            "Отправка разрешена только в период " "между началом и окончанием рассылки."
        )

    recipients = list(mailing.recipients.all())

    if not recipients:
        raise MailingSendError("У рассылки нет получателей.")

    attempts = []
    successful = 0
    failed = 0

    for recipient in recipients:
        attempt_time = timezone.now()

        try:
            sent_count = send_mail(
                subject=mailing.message.subject,
                message=mailing.message.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                fail_silently=False,
            )

            if sent_count != 1:
                raise MailingSendError("Почтовый сервер не подтвердил отправку.")

            status = "success"
            server_response = f"Письмо успешно отправлено: {recipient.email}"
            successful += 1

        except Exception as error:
            status = "failed"
            server_response = f"Получатель: {recipient.email}. " f"Ошибка: {error}"
            failed += 1

        attempts.append(
            MailingAttempt(
                mailing=mailing,
                attempt_time=attempt_time,
                status=status,
                server_response=server_response,
            )
        )

    MailingAttempt.objects.bulk_create(attempts)

    return MailingSendResult(
        total=len(recipients),
        successful=successful,
        failed=failed,
    )
