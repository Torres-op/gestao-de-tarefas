from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .auth import LOCKED_MESSAGE, is_locked


class LoginForm(AuthenticationForm):
    def clean(self):
        if is_locked(self.request, self.cleaned_data.get("username")):
            raise forms.ValidationError(LOCKED_MESSAGE, code="locked")
        return super().clean()
