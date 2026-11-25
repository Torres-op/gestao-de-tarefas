from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.cache import cache
from django.core.exceptions import PermissionDenied

LOCKED_MESSAGE = "Muitas tentativas de login sem sucesso. Aguarde alguns minutos e tente novamente."


def client_ip(request):
    if request is None:
        return "sem-ip"
    return request.META.get("REMOTE_ADDR") or "sem-ip"


def attempts_key(request, username):
    return f"login-attempts:{client_ip(request)}:{(username or '').strip().lower()}"


def is_locked(request, username):
    return cache.get(attempts_key(request, username), 0) >= settings.LOGIN_MAX_ATTEMPTS


def register_failure(request, username):
    key = attempts_key(request, username)
    cache.set(key, cache.get(key, 0) + 1, settings.LOGIN_LOCKOUT_SECONDS)


def clear_failures(request, username):
    cache.delete(attempts_key(request, username))


class RateLimitedModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)
        if is_locked(request, username):
            raise PermissionDenied(LOCKED_MESSAGE)
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is None:
            register_failure(request, username)
        else:
            clear_failures(request, username)
        return user
