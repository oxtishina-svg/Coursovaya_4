from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from mailings.models import Mailing, Recipient

from .permissions import manager_required

User = get_user_model()


@manager_required
def manager_dashboard(request):
    """Панель управления для менеджера."""

    users = User.objects.all().order_by("username")

    recipients = Recipient.objects.select_related("owner").order_by("full_name")

    mailings = Mailing.objects.select_related(
        "owner",
        "message",
    ).order_by("-start_time")

    context = {
        "users": users,
        "recipients": recipients,
        "mailings": mailings,
        "total_users": users.count(),
        "total_recipients": recipients.count(),
        "total_mailings": mailings.count(),
    }

    return render(
        request,
        "accounts/manager_dashboard.html",
        context,
    )


@manager_required
@require_POST
def manager_block_user(request, pk):
    """Блокирует пользователя, если это разрешено."""

    user_to_block = get_object_or_404(User, pk=pk)

    if user_to_block.pk == request.user.pk:
        messages.error(
            request,
            "Вы не можете заблокировать собственный аккаунт.",
        )
        return redirect("manager_dashboard")

    if user_to_block.is_superuser:
        messages.error(
            request,
            "Блокировка суперпользователя запрещена.",
        )
        return redirect("manager_dashboard")

    if not user_to_block.is_active:
        messages.info(
            request,
            "Этот пользователь уже заблокирован.",
        )
        return redirect("manager_dashboard")

    user_to_block.is_active = False
    user_to_block.save(update_fields=["is_active"])

    messages.success(
        request,
        f"Пользователь {user_to_block.username} заблокирован.",
    )

    return redirect("manager_dashboard")


@manager_required
@require_POST
def manager_disable_mailing(request, pk):
    """Отключает рассылку без изменения остальных полей."""

    mailing = get_object_or_404(Mailing, pk=pk)

    if not mailing.is_enabled:
        messages.info(
            request,
            f"Рассылка №{mailing.pk} уже отключена.",
        )
        return redirect("manager_dashboard")

    mailing.is_enabled = False
    mailing.save(update_fields=["is_enabled"])

    messages.success(
        request,
        f"Рассылка №{mailing.pk} успешно отключена.",
    )

    return redirect("manager_dashboard")
