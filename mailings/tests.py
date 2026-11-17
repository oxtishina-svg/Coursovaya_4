from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import MailingForm
from .models import Mailing, MailingAttempt, Message, Recipient
from .views import HOME_STATS_CACHE_KEY, invalidate_home_stats_cache

User = get_user_model()


class MailingTestData(TestCase):
    """Общие тестовые данные для проверки рассылок."""

    def setUp(self):
        cache.clear()

        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            email="otheruser@example.com",
            password="TestPassword123!",
        )

        self.message = Message.objects.create(
            subject="Тестовое письмо",
            body="Содержимое тестового письма",
            owner=self.user,
        )

        self.recipient = Recipient.objects.create(
            email="recipient@example.com",
            full_name="Тестовый Получатель",
            comment="Тест",
            owner=self.user,
        )

        now = timezone.now()

        self.mailing = Mailing.objects.create(
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=2),
            message=self.message,
            owner=self.user,
            is_enabled=True,
        )

        self.mailing.recipients.add(self.recipient)


class MailingModelTests(MailingTestData):
    """Проверяет модели рассылок."""

    def test_recipient_string_representation(self):
        self.assertEqual(
            str(self.recipient),
            "Тестовый Получатель (recipient@example.com)",
        )

    def test_message_string_representation(self):
        self.assertEqual(
            str(self.message),
            "Тестовое письмо",
        )

    def test_mailing_string_representation(self):
        self.assertIn(
            "Тестовое письмо",
            str(self.mailing),
        )

    def test_future_mailing_status(self):
        self.assertEqual(
            self.mailing.status,
            "Создана",
        )

    def test_active_mailing_status(self):
        now = timezone.now()

        self.mailing.start_time = now - timedelta(hours=1)
        self.mailing.end_time = now + timedelta(hours=1)

        self.assertEqual(
            self.mailing.status,
            "Запущена",
        )

    def test_finished_mailing_status(self):
        now = timezone.now()

        self.mailing.start_time = now - timedelta(days=2)
        self.mailing.end_time = now - timedelta(days=1)

        self.assertEqual(
            self.mailing.status,
            "Завершена",
        )

    def test_valid_mailing_dates(self):
        self.mailing.full_clean()

    def test_end_time_before_start_time_is_invalid(self):
        self.mailing.end_time = self.mailing.start_time - timedelta(hours=1)

        with self.assertRaises(ValidationError):
            self.mailing.full_clean()

    def test_new_mailing_cannot_start_in_past(self):
        mailing = Mailing(
            start_time=timezone.now() - timedelta(days=2),
            end_time=timezone.now() + timedelta(days=1),
            message=self.message,
            owner=self.user,
        )

        with self.assertRaises(ValidationError):
            mailing.full_clean()

    def test_mailing_attempt_status(self):
        attempt = MailingAttempt.objects.create(
            mailing=self.mailing,
            status=MailingAttempt.STATUS_SUCCESS,
            server_response="OK",
        )

        self.assertEqual(
            attempt.status,
            "success",
        )

        self.assertEqual(
            attempt.get_status_display(),
            "Успешно",
        )


class MailingPermissionTests(MailingTestData):
    """Проверяет права доступа пользователей."""

    def test_anonymous_user_cannot_open_recipient_list(self):
        response = self.client.get(reverse("recipient_list"))

        self.assertEqual(response.status_code, 302)

    def test_anonymous_user_cannot_open_mailing_list(self):
        response = self.client.get(reverse("mailing_list"))

        self.assertEqual(response.status_code, 302)

    def test_anonymous_user_cannot_open_statistics(self):
        response = self.client.get(reverse("mailing_statistics"))

        self.assertEqual(response.status_code, 302)

    def test_user_sees_only_own_recipients(self):
        Recipient.objects.create(
            email="private@example.com",
            full_name="Чужой получатель",
            owner=self.other_user,
        )

        self.client.force_login(self.user)

        response = self.client.get(reverse("recipient_list"))

        self.assertEqual(response.status_code, 200)

        recipients = list(response.context["recipients"])

        self.assertIn(self.recipient, recipients)

        self.assertTrue(
            all(recipient.owner_id == self.user.pk for recipient in recipients)
        )

    def test_user_sees_only_own_messages(self):
        Message.objects.create(
            subject="Чужое сообщение",
            body="Секретный текст",
            owner=self.other_user,
        )

        self.client.force_login(self.user)

        response = self.client.get(reverse("message_list"))

        self.assertEqual(response.status_code, 200)

        messages = list(response.context["messages_list"])

        self.assertIn(self.message, messages)

        self.assertTrue(all(message.owner_id == self.user.pk for message in messages))

    def test_user_cannot_open_foreign_mailing(self):
        self.client.force_login(self.other_user)

        response = self.client.get(
            reverse(
                "mailing_detail",
                kwargs={"pk": self.mailing.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_edit_foreign_mailing(self):
        self.client.force_login(self.other_user)

        response = self.client.get(
            reverse(
                "mailing_update",
                kwargs={"pk": self.mailing.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_delete_foreign_mailing(self):
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse(
                "mailing_delete",
                kwargs={"pk": self.mailing.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

        self.assertTrue(Mailing.objects.filter(pk=self.mailing.pk).exists())

    def test_user_cannot_send_foreign_mailing(self):
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse(
                "mailing_send",
                kwargs={"pk": self.mailing.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

        self.assertEqual(
            MailingAttempt.objects.count(),
            0,
        )

    def test_mailing_send_requires_post(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "mailing_send",
                kwargs={"pk": self.mailing.pk},
            )
        )

        self.assertEqual(response.status_code, 405)

    def test_mailing_form_hides_foreign_messages(self):
        foreign_message = Message.objects.create(
            subject="Чужое письмо",
            body="Чужой текст",
            owner=self.other_user,
        )

        form = MailingForm(user=self.user)

        queryset = form.fields["message"].queryset

        self.assertIn(self.message, queryset)

        self.assertNotIn(foreign_message, queryset)

    def test_mailing_form_hides_foreign_recipients(self):
        foreign_recipient = Recipient.objects.create(
            email="foreign@example.com",
            full_name="Чужой адресат",
            owner=self.other_user,
        )

        form = MailingForm(user=self.user)

        queryset = form.fields["recipients"].queryset

        self.assertIn(self.recipient, queryset)

        self.assertNotIn(foreign_recipient, queryset)


class MailingStatisticsTests(MailingTestData):
    """Проверяет статистику отправок."""

    def test_statistics_page_opens(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("mailing_statistics"))

        self.assertEqual(response.status_code, 200)

    def test_statistics_counts_attempts(self):
        MailingAttempt.objects.create(
            mailing=self.mailing,
            status=MailingAttempt.STATUS_SUCCESS,
            server_response="OK",
        )

        MailingAttempt.objects.create(
            mailing=self.mailing,
            status=MailingAttempt.STATUS_FAILED,
            server_response="Ошибка",
        )

        self.client.force_login(self.user)

        response = self.client.get(reverse("mailing_statistics"))

        self.assertEqual(
            response.context["total_mailings"],
            1,
        )

        self.assertEqual(
            response.context["total_attempts"],
            2,
        )

        self.assertEqual(
            response.context["successful_attempts"],
            1,
        )

        self.assertEqual(
            response.context["failed_attempts"],
            1,
        )

    def test_statistics_excludes_foreign_attempts(self):
        other_message = Message.objects.create(
            subject="Чужое письмо",
            body="Текст",
            owner=self.other_user,
        )

        other_mailing = Mailing.objects.create(
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=2),
            message=other_message,
            owner=self.other_user,
        )

        MailingAttempt.objects.create(
            mailing=other_mailing,
            status=MailingAttempt.STATUS_SUCCESS,
        )

        self.client.force_login(self.user)

        response = self.client.get(reverse("mailing_statistics"))

        self.assertEqual(
            response.context["total_mailings"],
            1,
        )

        self.assertEqual(
            response.context["total_attempts"],
            0,
        )


class MailingCacheTests(MailingTestData):
    """Проверяет серверное кеширование главной страницы."""

    def test_home_page_opens(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)

    def test_home_statistics_are_cached(self):
        self.client.get(reverse("home"))

        statistics = cache.get(HOME_STATS_CACHE_KEY)

        self.assertIsNotNone(statistics)

        self.assertEqual(
            statistics["total_mailings"],
            1,
        )

        self.assertEqual(
            statistics["total_recipients"],
            1,
        )

    def test_cache_can_be_invalidated(self):
        self.client.get(reverse("home"))

        self.assertIsNotNone(cache.get(HOME_STATS_CACHE_KEY))

        invalidate_home_stats_cache()

        self.assertIsNone(cache.get(HOME_STATS_CACHE_KEY))

    def test_recipient_creation_invalidates_cache(self):
        self.client.get(reverse("home"))

        self.client.force_login(self.user)

        response = self.client.post(
            reverse("recipient_create"),
            {
                "email": "newrecipient@example.com",
                "full_name": "Новый получатель",
                "comment": "",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.assertTrue(
            Recipient.objects.filter(email="newrecipient@example.com").exists()
        )

        self.assertIsNone(cache.get(HOME_STATS_CACHE_KEY))

        self.client.get(reverse("home"))

        statistics = cache.get(HOME_STATS_CACHE_KEY)

        self.assertEqual(
            statistics["total_recipients"],
            2,
        )
