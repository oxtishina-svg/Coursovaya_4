from django.contrib import admin

from .models import Mailing, MailingAttempt, Message, Recipient


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    """Административная панель получателей."""

    list_display = ("id", "full_name", "email", "owner")
    search_fields = ("full_name", "email")
    list_filter = ("owner",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Административная панель сообщений."""

    list_display = ("id", "subject", "owner")
    search_fields = ("subject",)
    list_filter = ("owner",)


@admin.register(Mailing)
class MailingAdmin(admin.ModelAdmin):
    """Административная панель рассылок."""

    list_display = (
        "id",
        "message",
        "start_time",
        "end_time",
        "current_status",
        "is_enabled",
        "owner",
    )

    list_filter = (
        "is_enabled",
        "owner",
        "start_time",
    )

    search_fields = ("message__subject",)

    filter_horizontal = ("recipients",)

    @admin.display(description="Статус")
    def current_status(self, obj: Mailing) -> str:
        return obj.status


@admin.register(MailingAttempt)
class MailingAttemptAdmin(admin.ModelAdmin):
    """Административная панель попыток отправки."""

    list_display = (
        "id",
        "mailing",
        "attempt_time",
        "status",
    )

    list_filter = ("status", "attempt_time")

    readonly_fields = ("attempt_time",)
