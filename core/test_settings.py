import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

PRODUCTION_KEY = "chave-de-teste-" + "x" * 50


def run_django(arguments, **env):
    environment = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "PYTHONIOENCODING": "utf-8",
        **env,
    }
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=settings.BASE_DIR,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def print_setting(name, **env):
    script = f"import django; django.setup(); from django.conf import settings; print(repr(settings.{name}))"
    return run_django(["-c", script], **env)


class ProductionSettingsTests(SimpleTestCase):
    def test_production_without_secret_key_refuses_to_start(self):
        result = print_setting("DEBUG", DJANGO_DEBUG="False", DJANGO_SECRET_KEY="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_debug_is_off_when_not_configured(self):
        result = print_setting("DEBUG", DJANGO_DEBUG="", DJANGO_SECRET_KEY=PRODUCTION_KEY)
        self.assertEqual(result.stdout.strip(), "False")

    def test_development_without_secret_key_uses_insecure_fallback(self):
        result = print_setting("SECRET_KEY", DJANGO_DEBUG="True", DJANGO_SECRET_KEY="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("django-insecure", result.stdout)

    def test_production_enables_secure_cookies_and_https_redirect(self):
        for name in ("SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE", "SECURE_SSL_REDIRECT"):
            with self.subTest(setting=name):
                result = print_setting(name, DJANGO_DEBUG="False", DJANGO_SECRET_KEY=PRODUCTION_KEY)
                self.assertEqual(result.stdout.strip(), "True", result.stderr)

    def test_deploy_check_passes_with_production_configuration(self):
        result = run_django(
            ["manage.py", "check", "--deploy", "--fail-level", "WARNING"],
            DJANGO_DEBUG="False",
            DJANGO_SECRET_KEY=PRODUCTION_KEY,
            DJANGO_ALLOWED_HOSTS="grello.exemplo.com",
            DJANGO_SECURE_HSTS_SECONDS="31536000",
            DJANGO_SECURE_HSTS_PRELOAD="True",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_hsts_preload_is_opt_in(self):
        result = print_setting(
            "SECURE_HSTS_PRELOAD",
            DJANGO_DEBUG="False",
            DJANGO_SECRET_KEY=PRODUCTION_KEY,
            DJANGO_SECURE_HSTS_SECONDS="31536000",
        )
        self.assertEqual(result.stdout.strip(), "False", result.stderr)

    def test_browsable_api_is_disabled_in_production(self):
        result = print_setting(
            "REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES']",
            DJANGO_DEBUG="False",
            DJANGO_SECRET_KEY=PRODUCTION_KEY,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("BrowsableAPIRenderer", result.stdout)
