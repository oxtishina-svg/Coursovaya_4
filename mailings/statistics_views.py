from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from .models import Mailing, MailingAttempt


@login_required
def mailing_statistics(request):
    """Статистика рассылок текущего пользователя."""

    mailings = (
        Mailing.objects.filter(owner=request.user)
        .select_related("message")
        .annotate(
            success_count=Count(
                "attempts",
                filter=Q(attempts__status="success"),
            ),
            failed_count=Count(
                "attempts",
                filter=Q(attempts__status="failed"),
            ),
        )
        .order_by("-start_time")
    )

    attempts = MailingAttempt.objects.filter(mailing__owner=request.user)

    totals = attempts.aggregate(
        success_count=Count(
            "id",
            filter=Q(status="success"),
        ),
        failed_count=Count(
            "id",
            filter=Q(status="failed"),
        ),
    )

    success_count = totals["success_count"]
    failed_count = totals["failed_count"]

    context = {
        "mailings": mailings,
        "total_mailings": mailings.count(),
        "total_attempts": success_count + failed_count,
        "successful_attempts": success_count,
        "failed_attempts": failed_count,
        "sent_messages": success_count,
    }

    return render(
        request,
        "mailings/statistics.html",
        context,
    )
