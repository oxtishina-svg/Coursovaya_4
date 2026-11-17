from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Пользователь сервиса управления рассылками."""

    email = models.EmailField(
        verbose_name="Email",
        unique=True,
    )

    is_email_verified = models.BooleanField(
        verbose_name="Email подтверждён",
        default=False,
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self) -> str:
        return self.email
