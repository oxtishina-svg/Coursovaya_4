from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import MailingForm, MessageForm, RecipientForm
from .models import Mailing, Message, Recipient
from .services import MailingSendError, send_mailing

HOME_STATS_CACHE_KEY = "mailflow:home:stats:v1"
HOME_STATS_CACHE_TIMEOUT = 60


def invalidate_home_stats_cache():
    """Удаляет устаревшую статистику главной страницы."""
    cache.delete(HOME_STATS_CACHE_KEY)


def get_home_statistics():
    """Получает статистику из кеша или базы данных."""

    statistics = cache.get(HOME_STATS_CACHE_KEY)

    if statistics is not None:
        return statistics

    now = timezone.now()

    statistics = {
        "total_mailings": Mailing.objects.count(),
        "active_mailings": Mailing.objects.filter(
            start_time__lte=now,
            end_time__gte=now,
            is_enabled=True,
        ).count(),
        "total_recipients": Recipient.objects.count(),
    }

    cache.set(
        HOME_STATS_CACHE_KEY,
        statistics,
        timeout=HOME_STATS_CACHE_TIMEOUT,
    )

    return statistics


def home(request):
    """Главная страница с кешированной статистикой."""

    statistics = get_home_statistics()

    return render(
        request,
        "mailings/home.html",
        statistics,
    )


@login_required
def recipient_list(request):
    """Показывает получателей текущего пользователя."""

    recipients = Recipient.objects.filter(owner=request.user).order_by("full_name")

    query = request.GET.get("q", "").strip()

    if query:
        recipients = recipients.filter(
            Q(full_name__icontains=query) | Q(email__icontains=query)
        )

    return render(
        request,
        "mailings/recipient_list.html",
        {
            "recipients": recipients,
            "query": query,
        },
    )


@login_required
def recipient_create(request):
    """Создаёт получателя."""

    if request.method == "POST":
        form = RecipientForm(request.POST)

        if form.is_valid():
            recipient = form.save(commit=False)
            recipient.owner = request.user
            recipient.save()

            invalidate_home_stats_cache()

            return redirect("recipient_list")
    else:
        form = RecipientForm()

    return render(
        request,
        "mailings/recipient_form.html",
        {
            "form": form,
            "page_title": "Добавить получателя",
            "button_text": "Сохранить получателя",
        },
    )


@login_required
def recipient_update(request, pk):
    """Редактирует собственного получателя."""

    recipient = get_object_or_404(
        Recipient,
        pk=pk,
        owner=request.user,
    )

    if request.method == "POST":
        form = RecipientForm(
            request.POST,
            instance=recipient,
        )

        if form.is_valid():
            form.save()
            return redirect("recipient_list")
    else:
        form = RecipientForm(instance=recipient)

    return render(
        request,
        "mailings/recipient_form.html",
        {
            "form": form,
            "recipient": recipient,
            "page_title": "Редактировать получателя",
            "button_text": "Сохранить изменения",
        },
    )


@login_required
def recipient_delete(request, pk):
    """Удаляет собственного получателя после подтверждения."""

    recipient = get_object_or_404(
        Recipient,
        pk=pk,
        owner=request.user,
    )

    if request.method == "POST":
        recipient.delete()

        invalidate_home_stats_cache()

        return redirect("recipient_list")

    return render(
        request,
        "mailings/recipient_confirm_delete.html",
        {"recipient": recipient},
    )


@login_required
def message_list(request):
    """Показывает сообщения текущего пользователя."""

    messages = Message.objects.filter(owner=request.user).order_by("subject")

    query = request.GET.get("q", "").strip()

    if query:
        messages = messages.filter(
            Q(subject__icontains=query) | Q(body__icontains=query)
        )

    return render(
        request,
        "mailings/message_list.html",
        {
            "messages_list": messages,
            "query": query,
        },
    )


@login_required
def message_detail(request, pk):
    """Показывает своё сообщение."""

    message = get_object_or_404(
        Message,
        pk=pk,
        owner=request.user,
    )

    return render(
        request,
        "mailings/message_detail.html",
        {"message": message},
    )


@login_required
def message_create(request):
    """Создаёт сообщение."""

    if request.method == "POST":
        form = MessageForm(request.POST)

        if form.is_valid():
            message = form.save(commit=False)
            message.owner = request.user
            message.save()

            return redirect("message_list")
    else:
        form = MessageForm()

    return render(
        request,
        "mailings/message_form.html",
        {
            "form": form,
            "page_title": "Создать сообщение",
            "button_text": "Сохранить сообщение",
        },
    )


@login_required
def message_update(request, pk):
    """Редактирует своё сообщение."""

    message = get_object_or_404(
        Message,
        pk=pk,
        owner=request.user,
    )

    if request.method == "POST":
        form = MessageForm(
            request.POST,
            instance=message,
        )

        if form.is_valid():
            form.save()

            return redirect("message_detail", pk=message.pk)
    else:
        form = MessageForm(instance=message)

    return render(
        request,
        "mailings/message_form.html",
        {
            "form": form,
            "page_title": "Редактировать сообщение",
            "button_text": "Сохранить изменения",
        },
    )


@login_required
def message_delete(request, pk):
    """Удаляет сообщение, не связанное с рассылками."""

    message = get_object_or_404(
        Message,
        pk=pk,
        owner=request.user,
    )

    is_used = message.mailings.exists()

    if request.method == "POST" and not is_used:
        message.delete()

        return redirect("message_list")

    return render(
        request,
        "mailings/message_confirm_delete.html",
        {
            "message": message,
            "is_used": is_used,
        },
    )


@login_required
def mailing_list(request):
    """Показывает рассылки текущего пользователя."""

    mailings = (
        Mailing.objects.filter(owner=request.user)
        .select_related("message")
        .order_by("-start_time")
    )

    return render(
        request,
        "mailings/mailing_list.html",
        {"mailings": mailings},
    )


@login_required
def mailing_detail(request, pk):
    """Показывает подробную информацию о своей рассылке."""

    mailing = get_object_or_404(
        Mailing.objects.select_related("message").prefetch_related("recipients"),
        pk=pk,
        owner=request.user,
    )

    return render(
        request,
        "mailings/mailing_detail.html",
        {"mailing": mailing},
    )


@login_required
def mailing_create(request):
    """Создаёт рассылку с выбранными получателями."""

    if request.method == "POST":
        form = MailingForm(
            request.POST,
            user=request.user,
        )

        if form.is_valid():
            mailing = form.save(commit=False)
            mailing.owner = request.user
            mailing.save()
            form.save_m2m()

            invalidate_home_stats_cache()

            return redirect("mailing_detail", pk=mailing.pk)
    else:
        form = MailingForm(user=request.user)

    return render(
        request,
        "mailings/mailing_form.html",
        {
            "form": form,
            "page_title": "Создать рассылку",
            "button_text": "Сохранить рассылку",
        },
    )


@login_required
def mailing_update(request, pk):
    """Редактирует свою рассылку."""

    mailing = get_object_or_404(
        Mailing,
        pk=pk,
        owner=request.user,
    )

    if request.method == "POST":
        form = MailingForm(
            request.POST,
            instance=mailing,
            user=request.user,
        )

        if form.is_valid():
            form.save()

            invalidate_home_stats_cache()

            return redirect("mailing_detail", pk=mailing.pk)
    else:
        form = MailingForm(
            instance=mailing,
            user=request.user,
        )

    return render(
        request,
        "mailings/mailing_form.html",
        {
            "form": form,
            "mailing": mailing,
            "page_title": "Редактировать рассылку",
            "button_text": "Сохранить изменения",
        },
    )


@login_required
def mailing_delete(request, pk):
    """Удаляет свою рассылку после подтверждения."""

    mailing = get_object_or_404(
        Mailing,
        pk=pk,
        owner=request.user,
    )

    if request.method == "POST":
        mailing.delete()

        invalidate_home_stats_cache()

        return redirect("mailing_list")

    return render(
        request,
        "mailings/mailing_confirm_delete.html",
        {"mailing": mailing},
    )


@login_required
@require_POST
def mailing_send(request, pk):
    """Запускает отправку собственной рассылки вручную."""

    mailing = get_object_or_404(
        Mailing.objects.select_related("message").prefetch_related("recipients"),
        pk=pk,
        owner=request.user,
    )

    try:
        result = send_mailing(mailing)
    except MailingSendError as error:
        messages.error(request, str(error))
    else:
        messages.success(
            request,
            (
                f"Рассылка обработана. "
                f"Всего получателей: {result.total}. "
                f"Успешно: {result.successful}. "
                f"Ошибок: {result.failed}."
            ),
        )

    return redirect("mailing_detail", pk=mailing.pk)
