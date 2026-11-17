from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Recipient(models.Model):
    """Получатель рассылки."""

    email = models.EmailField(
        unique=True,
        verbose_name="Email",
    )

    full_name = models.CharField(
        max_length=255,
        verbose_name="Ф. И. О.",
    )

    comment = models.TextField(
        blank=True,
        verbose_name="Комментарий",
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recipients",
        verbose_name="Владелец",
    )

    class Meta:
        verbose_name = "Получатель"
        verbose_name_plural = "Получатели"
        ordering = ["full_name"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.email})"


class Message(models.Model):
    """Сообщение для отправки по электронной почте."""

    subject = models.CharField(
        max_length=255,
        verbose_name="Тема письма",
    )

    body = models.TextField(
        verbose_name="Тело письма",
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mailing_messages",
        verbose_name="Владелец",
    )

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        ordering = ["subject"]

    def __str__(self) -> str:
        return self.subject


class Mailing(models.Model):
    """Рассылка с заданным периодом отправки."""

    start_time = models.DateTimeField(
        verbose_name="Время начала",
    )

    end_time = models.DateTimeField(
        verbose_name="Время окончания",
    )

    message = models.ForeignKey(
        Message,
        on_delete=models.PROTECT,
        related_name="mailings",
        verbose_name="Сообщение",
    )

    recipients = models.ManyToManyField(
        Recipient,
        related_name="mailings",
        verbose_name="Получатели",
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mailings",
        verbose_name="Владелец",
    )

    is_enabled = models.BooleanField(
        default=True,
        verbose_name="Рассылка включена",
    )

    class Meta:
        verbose_name = "Рассылка"
        verbose_name_plural = "Рассылки"
        ordering = ["-start_time"]

    def __str__(self) -> str:
        return f"Рассылка №{self.pk}: {self.message.subject}"

    @property
    def status(self) -> str:
        """Вычисляет текущий статус рассылки."""
        now = timezone.now()

        if now < self.start_time:
            return "Создана"

        if now > self.end_time:
            return "Завершена"

        return "Запущена"

    def clean(self) -> None:
        """Проверяет корректность периода рассылки."""
        super().clean()

        errors = {}

        if self.start_time and self.start_time < timezone.now():
            if self._state.adding:
                errors["start_time"] = "Время начала рассылки не может быть в прошлом."

        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                errors["end_time"] = "Время окончания должно быть позже времени начала."

        if errors:
            raise ValidationError(errors)


class MailingAttempt(models.Model):
    """Результат попытки отправки сообщения."""

    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Успешно"),
        (STATUS_FAILED, "Не успешно"),
    ]

    mailing = models.ForeignKey(
        Mailing,
        on_delete=models.CASCADE,
        related_name="attempts",
        verbose_name="Рассылка",
    )

    attempt_time = models.DateTimeField(
        default=timezone.now,
        verbose_name="Время попытки",
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        verbose_name="Статус",
    )

    server_response = models.TextField(
        blank=True,
        verbose_name="Ответ почтового сервера",
    )

    class Meta:
        verbose_name = "Попытка отправки"
        verbose_name_plural = "Попытки отправки"
        ordering = ["-attempt_time"]

    def __str__(self) -> str:
        return f"Попытка №{self.pk}: {self.get_status_display()}"
