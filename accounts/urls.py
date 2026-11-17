from django.urls import path

from . import manager_views, views

urlpatterns = [
    path(
        "register/",
        views.register,
        name="register",
    ),
    path(
        "verify-email/<int:user_id>/<str:token>/",
        views.verify_email,
        name="verify_email",
    ),
    path(
        "manager/",
        manager_views.manager_dashboard,
        name="manager_dashboard",
    ),
    path(
        "manager/users/<int:pk>/block/",
        manager_views.manager_block_user,
        name="manager_block_user",
    ),
    path(
        "manager/mailings/<int:pk>/disable/",
        manager_views.manager_disable_mailing,
        name="manager_disable_mailing",
    ),
]
