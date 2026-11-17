import logging

from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .forms import RegistrationForm
from .models import User

logger = logging.getLogger(__name__)


def register(request):
    """Регистрирует пользователя и отправляет подтверждение email."""

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.is_active = False
                    user.is_email_verified = False
                    user.save()

                    token = default_token_generator.make_token(user)

                    verification_url = request.build_absolute_uri(
                        reverse(
                            "verify_email",
                            kwargs={
                                "user_id": user.pk,
                                "token": token,
                            },
                        )
                    )

                    send_mail(
                        subject="MailFlow: подтверждение почты",
                        message=(
                            f"Здравствуйте, {user.username}!\n\n"
                            "Для подтверждения электронной почты "
                            "перейдите по ссылке:\n\n"
                            f"{verification_url}\n\n"
                            "Если вы не регистрировались в MailFlow, "
                            "проигнорируйте это письмо."
                        ),
                        from_email=None,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )

            except Exception:
                logger.exception("Не удалось завершить регистрацию пользователя.")
                form.add_error(
                    None,
                    "Не удалось отправить письмо подтверждения. " "Попробуйте ещё раз.",
                )
            else:
                return render(
                    request,
                    "accounts/registration_status.html",
                    {
                        "page_title": "Проверьте почту",
                        "description": (
                            "Аккаунт создан. Мы отправили ссылку "
                            "для подтверждения электронной почты. "
                            "До подтверждения вход недоступен."
                        ),
                    },
                )

    else:
        form = RegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form},
    )


@require_GET
def verify_email(request, user_id, token):
    """Подтверждает email по одноразовой ссылке."""

    user = get_object_or_404(User, pk=user_id)

    if not user.is_email_verified and default_token_generator.check_token(user, token):
        user.is_email_verified = True
        user.is_active = True

        user.save(
            update_fields=[
                "is_email_verified",
                "is_active",
            ]
        )

        return render(
            request,
            "accounts/registration_status.html",
            {
                "page_title": "Почта подтверждена",
                "description": (
                    "Ваш аккаунт активирован. " "Теперь вы можете войти в MailFlow."
                ),
            },
        )

    return render(
        request,
        "accounts/registration_status.html",
        {
            "page_title": "Ссылка недействительна",
            "description": (
                "Ссылка подтверждения недействительна " "или уже использована."
            ),
        },
        status=400,
    )
