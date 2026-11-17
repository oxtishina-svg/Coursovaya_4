from datetime import timedelta
from unittest.mock import call, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from mailings.models import Mailing, MailingAttempt, Message, Recipient
from mailings.services import MailingSendError, send_mailing

User = get_user_model()


class MailingServiceTests(TestCase):
    """Тесты сервиса отправки email-рассылок."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="service_test_user",
            email="service@example.com",
            password="TestPassword123!",
        )

        self.message = Message.objects.create(
            subject="Тестовая рассылка",
            body="Проверка работы сервиса отправки писем.",
            owner=self.user,
        )

        self.recipient_1 = Recipient.objects.create(
            email="recipient1@example.com",
            full_name="Первый получатель",
            owner=self.user,
        )

        self.recipient_2 = Recipient.objects.create(
            email="recipient2@example.com",
            full_name="Второй получатель",
            owner=self.user,
        )

        now = timezone.now()

        self.mailing = Mailing.objects.create(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            message=self.message,
            owner=self.user,
            is_enabled=True,
        )

        self.mailing.recipients.add(
            self.recipient_1,
            self.recipient_2,
        )

    @patch("mailings.services.send_mail", return_value=1)
    def test_successful_mailing(self, mocked_send_mail):
        """Успешная отправка двум получателям."""

        result = send_mailing(self.mailing)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.successful, 2)
        self.assertEqual(result.failed, 0)

        self.assertEqual(mocked_send_mail.call_count, 2)

        attempts = MailingAttempt.objects.filter(mailing=self.mailing)

        self.assertEqual(attempts.count(), 2)

        self.assertTrue(
            all(attempt.status == MailingAttempt.STATUS_SUCCESS for attempt in attempts)
        )

    @patch("mailings.services.send_mail", return_value=1)
    def test_email_contains_correct_data(self, mocked_send_mail):
        """Проверка темы, текста, отправителя и адресатов."""

        send_mailing(self.mailing)

        expected_calls = [
            call(
                subject=self.message.subject,
                message=self.message.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.recipient_1.email],
                fail_silently=False,
            ),
            call(
                subject=self.message.subject,
                message=self.message.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.recipient_2.email],
                fail_silently=False,
            ),
        ]

        mocked_send_mail.assert_has_calls(
            expected_calls,
            any_order=True,
        )

        self.assertEqual(mocked_send_mail.call_count, 2)

    @patch(
        "mailings.services.send_mail",
        side_effect=ConnectionError("SMTP недоступен"),
    )
    def test_smtp_error_is_recorded(self, mocked_send_mail):
        """Ошибка SMTP сохраняется как неудачная попытка."""

        result = send_mailing(self.mailing)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.successful, 0)
        self.assertEqual(result.failed, 2)

        self.assertEqual(mocked_send_mail.call_count, 2)

        attempts = MailingAttempt.objects.filter(mailing=self.mailing)

        self.assertEqual(attempts.count(), 2)

        for attempt in attempts:
            self.assertEqual(
                attempt.status,
                MailingAttempt.STATUS_FAILED,
            )

            self.assertIn(
                "SMTP недоступен",
                attempt.server_response,
            )

    @patch("mailings.services.send_mail", return_value=0)
    def test_unconfirmed_delivery_is_failure(self, mocked_send_mail):
        """Ответ send_mail=0 считается ошибкой."""

        result = send_mailing(self.mailing)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.successful, 0)
        self.assertEqual(result.failed, 2)

        self.assertEqual(mocked_send_mail.call_count, 2)

        attempts = MailingAttempt.objects.filter(mailing=self.mailing)

        for attempt in attempts:
            self.assertEqual(
                attempt.status,
                MailingAttempt.STATUS_FAILED,
            )

            self.assertIn(
                "не подтвердил отправку",
                attempt.server_response,
            )

    @patch("mailings.services.send_mail")
    def test_partial_mailing_success(self, mocked_send_mail):
        """Одна отправка успешна, вторая завершилась ошибкой."""

        mocked_send_mail.side_effect = [
            1,
            ConnectionError("Ошибка соединения"),
        ]

        result = send_mailing(self.mailing)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.successful, 1)
        self.assertEqual(result.failed, 1)

        self.assertEqual(
            MailingAttempt.objects.filter(
                mailing=self.mailing,
                status=MailingAttempt.STATUS_SUCCESS,
            ).count(),
            1,
        )

        self.assertEqual(
            MailingAttempt.objects.filter(
                mailing=self.mailing,
                status=MailingAttempt.STATUS_FAILED,
            ).count(),
            1,
        )

    @patch("mailings.services.send_mail")
    def test_disabled_mailing_cannot_be_sent(self, mocked_send_mail):
        """Отключённая рассылка не отправляется."""

        self.mailing.is_enabled = False
        self.mailing.save(update_fields=["is_enabled"])

        with self.assertRaisesRegex(
            MailingSendError,
            "Рассылка отключена",
        ):
            send_mailing(self.mailing)

        mocked_send_mail.assert_not_called()

        self.assertEqual(
            MailingAttempt.objects.count(),
            0,
        )

    @patch("mailings.services.send_mail")
    def test_future_mailing_cannot_be_sent(self, mocked_send_mail):
        """Рассылка не отправляется до начала периода."""

        self.mailing.start_time = timezone.now() + timedelta(days=1)

        self.mailing.end_time = timezone.now() + timedelta(days=2)

        self.mailing.save(update_fields=["start_time", "end_time"])

        with self.assertRaises(MailingSendError):
            send_mailing(self.mailing)

        mocked_send_mail.assert_not_called()

        self.assertEqual(
            MailingAttempt.objects.count(),
            0,
        )

    @patch("mailings.services.send_mail")
    def test_expired_mailing_cannot_be_sent(self, mocked_send_mail):
        """Завершённая рассылка не отправляется."""

        self.mailing.start_time = timezone.now() - timedelta(days=2)

        self.mailing.end_time = timezone.now() - timedelta(days=1)

        self.mailing.save(update_fields=["start_time", "end_time"])

        with self.assertRaises(MailingSendError):
            send_mailing(self.mailing)

        mocked_send_mail.assert_not_called()

        self.assertEqual(
            MailingAttempt.objects.count(),
            0,
        )

    @patch("mailings.services.send_mail")
    def test_mailing_without_recipients(self, mocked_send_mail):
        """Рассылка без получателей не отправляется."""

        self.mailing.recipients.clear()

        with self.assertRaisesRegex(
            MailingSendError,
            "нет получателей",
        ):
            send_mailing(self.mailing)

        mocked_send_mail.assert_not_called()

        self.assertEqual(
            MailingAttempt.objects.count(),
            0,
        )

    @patch("mailings.services.send_mail", return_value=1)
    def test_repeated_sending_creates_new_attempts(
        self,
        mocked_send_mail,
    ):
        """Каждый запуск добавляет новые записи истории."""

        first_result = send_mailing(self.mailing)
        second_result = send_mailing(self.mailing)

        self.assertEqual(first_result.successful, 2)
        self.assertEqual(second_result.successful, 2)

        self.assertEqual(
            mocked_send_mail.call_count,
            4,
        )

        self.assertEqual(
            MailingAttempt.objects.filter(mailing=self.mailing).count(),
            4,
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_real_django_email_backend(self):
        """Отправка через тестовый почтовый backend Django."""

        result = send_mailing(self.mailing)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.successful, 2)
        self.assertEqual(result.failed, 0)

        self.assertEqual(len(mail.outbox), 2)

        for email_message in mail.outbox:
            self.assertEqual(
                email_message.subject,
                self.message.subject,
            )

            self.assertEqual(
                email_message.body,
                self.message.body,
            )

            self.assertEqual(
                email_message.from_email,
                settings.DEFAULT_FROM_EMAIL,
            )

        actual_recipients = [email_message.to[0] for email_message in mail.outbox]

        self.assertCountEqual(
            actual_recipients,
            [
                self.recipient_1.email,
                self.recipient_2.email,
            ],
        )
