from django import forms
from django.utils import timezone

from .models import Mailing, Message, Recipient


class RecipientForm(forms.ModelForm):
    """Форма создания и редактирования получателя."""

    class Meta:
        model = Recipient

        fields = [
            "email",
            "full_name",
            "comment",
        ]

        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "example@mail.ru",
                }
            ),
            "full_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Иванов Иван Иванович",
                }
            ),
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Дополнительная информация о клиенте",
                    "rows": 4,
                }
            ),
        }


class MessageForm(forms.ModelForm):
    """Форма создания и редактирования сообщения."""

    class Meta:
        model = Message

        fields = [
            "subject",
            "body",
        ]

        widgets = {
            "subject": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Тема вашего письма",
                }
            ),
            "body": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Введите текст сообщения",
                    "rows": 10,
                }
            ),
        }


class MailingForm(forms.ModelForm):
    """Форма создания и редактирования рассылки."""

    class Meta:
        model = Mailing

        fields = [
            "start_time",
            "end_time",
            "message",
            "recipients",
            "is_enabled",
        ]

        widgets = {
            "start_time": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "end_time": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "message": forms.Select(attrs={"class": "form-control"}),
            "recipients": forms.SelectMultiple(
                attrs={
                    "class": "form-control",
                    "size": 8,
                }
            ),
            "is_enabled": forms.CheckboxInput(),
        }

    def __init__(self, *args, user=None, **kwargs):
        """Настраивает поля и права редактирования."""

        super().__init__(*args, **kwargs)

        self.fields["message"].queryset = Message.objects.none()
        self.fields["recipients"].queryset = Recipient.objects.none()

        if user is not None and user.is_authenticated:
            self.fields["message"].queryset = Message.objects.filter(owner=user)

            self.fields["recipients"].queryset = Recipient.objects.filter(owner=user)

        self.fields["start_time"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ]

        self.fields["end_time"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ]

        self.fields["recipients"].help_text = (
            "Для выбора нескольких получателей удерживайте Ctrl "
            "и нажимайте на нужные строки."
        )

        # Отключённую рассылку может повторно включить
        # только суперпользователь.
        is_existing_mailing = self.instance.pk is not None
        is_disabled = not self.instance.is_enabled

        is_superuser = user is not None and user.is_authenticated and user.is_superuser

        if is_existing_mailing and is_disabled and not is_superuser:
            self.fields["is_enabled"].disabled = True

            self.fields["is_enabled"].help_text = (
                "Рассылка отключена. "
                "Повторное включение доступно только "
                "суперпользователю."
            )

    def clean(self):
        """Проверяет корректность времени рассылки."""

        cleaned_data = super().clean()

        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if start_time and end_time:
            if start_time >= end_time:
                self.add_error(
                    "end_time",
                    "Время окончания должно быть позже начала.",
                )

        if start_time and start_time < timezone.now():
            if self.instance._state.adding:
                self.add_error(
                    "start_time",
                    "Начало новой рассылки не может быть в прошлом.",
                )
            elif "start_time" in self.changed_data:
                self.add_error(
                    "start_time",
                    "Нельзя изменять начало рассылки " "на прошедшее время.",
                )

        return cleaned_data
