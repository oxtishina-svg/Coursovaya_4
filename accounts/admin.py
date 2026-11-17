from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Администрирование пользователей сервиса."""

    list_display = (
        "username",
        "email",
        "is_email_verified",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "is_email_verified",
        "is_staff",
        "is_active",
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            "Дополнительные настройки",
            {
                "fields": ("is_email_verified",),
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Дополнительные настройки",
            {
                "fields": ("email", "is_email_verified"),
            },
        ),
    )
