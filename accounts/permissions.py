from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

MANAGER_GROUP_NAME = "Менеджеры"


def is_manager(user):
    """Проверяет права менеджера."""

    if not user.is_authenticated:
        return False

    return user.is_superuser or user.groups.filter(name=MANAGER_GROUP_NAME).exists()


def manager_required(view_func):
    """Разрешает доступ только менеджерам и суперпользователям."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_manager(request.user):
            raise PermissionDenied("У вас нет прав для доступа к панели менеджера.")

        return view_func(request, *args, **kwargs)

    return wrapper
