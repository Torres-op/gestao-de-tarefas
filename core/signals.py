import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .auth import client_ip

logger = logging.getLogger("grello.security")


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    logger.info("login ok usuario=%s ip=%s", user.get_username(), client_ip(request))


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    username = user.get_username() if user else "-"
    logger.info("logout usuario=%s ip=%s", username, client_ip(request))


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request=None, **kwargs):
    logger.warning("login falhou usuario=%s ip=%s", credentials.get("username", "-"), client_ip(request))
