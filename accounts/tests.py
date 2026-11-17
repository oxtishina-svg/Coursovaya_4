from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from mailings.models import Mailing, Message

User = get_user_model()


class AccountTests(TestCase):
    """Проверяет пользователей и подтверждение почты."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="accountuser",
            email="account@example.com",
            password="TestPassword123!",
        )

    def test_user_email_is_unique(self):
        self.assertTrue(User._meta.get_field("email").unique)

    def test_user_string_representation(self):
        self.assertEqual(
            str(self.user),
            "account@example.com",
        )

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        logged_in = self.client.login(
            username="accountuser",
            password="TestPassword123!",
        )

        self.assertFalse(logged_in)

    def test_email_confirmation_activates_user(self):
        self.user.is_active = False
        self.user.is_email_verified = False

        self.user.save(
            update_fields=[
                "is_active",
                "is_email_verified",
            ]
        )

        token = default_token_generator.make_token(self.user)

        response = self.client.get(
            reverse(
                "verify_email",
                kwargs={
                    "user_id": self.user.pk,
                    "token": token,
                },
            )
        )

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()

        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.is_email_verified)

    def test_invalid_confirmation_token(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.get(
            reverse(
                "verify_email",
                kwargs={
                    "user_id": self.user.pk,
                    "token": "invalid-token",
                },
            )
        )

        self.assertEqual(response.status_code, 400)

        self.user.refresh_from_db()

        self.assertFalse(self.user.is_active)


class ManagerTests(TestCase):
    """Проверяет полномочия менеджера рассылок."""

    def setUp(self):
        self.manager_group = Group.objects.create(name="Менеджеры")

        self.manager = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="TestPassword123!",
        )

        self.manager.groups.add(self.manager_group)

        self.regular_user = User.objects.create_user(
            username="regularuser",
            email="regular@example.com",
            password="TestPassword123!",
        )

        self.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="TestPassword123!",
        )

        self.message = Message.objects.create(
            subject="Письмо пользователя",
            body="Тестовое содержимое",
            owner=self.regular_user,
        )

        self.mailing = Mailing.objects.create(
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=2),
            message=self.message,
            owner=self.regular_user,
            is_enabled=True,
        )

    def test_manager_can_open_dashboard(self):
        self.client.force_login(self.manager)

        response = self.client.get("/manager/")

        self.assertEqual(response.status_code, 200)

    def test_regular_user_cannot_open_dashboard(self):
        self.client.force_login(self.regular_user)

        response = self.client.get("/manager/")

        self.assertEqual(response.status_code, 403)

    def test_superuser_can_open_dashboard(self):
        self.client.force_login(self.superuser)

        response = self.client.get("/manager/")

        self.assertEqual(response.status_code, 200)

    def test_staff_without_manager_role_is_denied(self):
        staff_user = User.objects.create_user(
            username="staffuser",
            email="staff@example.com",
            password="TestPassword123!",
            is_staff=True,
        )

        self.client.force_login(staff_user)

        response = self.client.get("/manager/")

        self.assertEqual(response.status_code, 403)

    def test_manager_can_disable_mailing(self):
        self.client.force_login(self.manager)

        response = self.client.post(f"/manager/mailings/{self.mailing.pk}/disable/")

        self.assertEqual(response.status_code, 302)

        self.mailing.refresh_from_db()

        self.assertFalse(self.mailing.is_enabled)

    def test_regular_user_cannot_disable_mailing_as_manager(self):
        self.client.force_login(self.regular_user)

        response = self.client.post(f"/manager/mailings/{self.mailing.pk}/disable/")

        self.assertEqual(response.status_code, 403)

        self.mailing.refresh_from_db()

        self.assertTrue(self.mailing.is_enabled)

    def test_manager_can_block_user(self):
        self.client.force_login(self.manager)

        response = self.client.post(f"/manager/users/{self.regular_user.pk}/block/")

        self.assertEqual(response.status_code, 302)

        self.regular_user.refresh_from_db()

        self.assertFalse(self.regular_user.is_active)

    def test_manager_cannot_block_self(self):
        self.client.force_login(self.manager)

        self.client.post(f"/manager/users/{self.manager.pk}/block/")

        self.manager.refresh_from_db()

        self.assertTrue(self.manager.is_active)

    def test_manager_cannot_block_superuser(self):
        self.client.force_login(self.manager)

        self.client.post(f"/manager/users/{self.superuser.pk}/block/")

        self.superuser.refresh_from_db()

        self.assertTrue(self.superuser.is_active)

    def test_manager_actions_require_post(self):
        self.client.force_login(self.manager)

        block_response = self.client.get(
            f"/manager/users/{self.regular_user.pk}/block/"
        )

        disable_response = self.client.get(
            f"/manager/mailings/{self.mailing.pk}/disable/"
        )

        self.assertEqual(
            block_response.status_code,
            405,
        )

        self.assertEqual(
            disable_response.status_code,
            405,
        )

    def test_manager_cannot_edit_foreign_mailing(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "mailing_update",
                kwargs={"pk": self.mailing.pk},
            )
        )

        self.assertEqual(response.status_code, 404)
