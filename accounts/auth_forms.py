from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm


class CustomAuthenticationForm(AuthenticationForm):
    """Форма входа с уведомлением о блокировке."""

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and password:
            User = get_user_model()

            try:
                user = User._default_manager.get_by_natural_key(username)
            except User.DoesNotExist:
                pass
            else:
                if not user.is_active and user.check_password(password):
                    raise forms.ValidationError(
                        "Ваш аккаунт заблокирован. " "Обратитесь к администратору.",
                        code="inactive",
                    )

        return super().clean()
