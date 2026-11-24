from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from expenses.forms import INPUT_CLASSES


class StyledFormMixin:
    """Apply the shared Tailwind input classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT_CLASSES)


class LoginForm(StyledFormMixin, AuthenticationForm):
    pass


class SignUpForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(required=False, help_text="Optional.")

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")
