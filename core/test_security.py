from io import StringIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .auth import LOCKED_MESSAGE
from .testing import PASSWORD, make_operator, make_organization


@override_settings(LOGIN_MAX_ATTEMPTS=3, LOGIN_LOCKOUT_SECONDS=60)
class LoginRateLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = make_organization("Org A")
        cls.user = make_operator("ana", cls.organization)

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def post_login(self, password, username="ana", url=None):
        return self.client.post(url or reverse("login"), {"username": username, "password": password})

    def fail_until_locked(self, username="ana", url=None):
        for _ in range(3):
            self.post_login("senha-errada", username=username, url=url)

    def test_correct_password_is_refused_after_too_many_failures(self):
        self.fail_until_locked()
        response = self.post_login(PASSWORD)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, LOCKED_MESSAGE)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_failures_below_the_limit_do_not_lock(self):
        self.post_login("senha-errada")
        self.post_login("senha-errada")
        response = self.post_login(PASSWORD)
        self.assertEqual(response.status_code, 302)

    def test_successful_login_resets_the_counter(self):
        self.post_login("senha-errada")
        self.post_login("senha-errada")
        self.assertEqual(self.post_login(PASSWORD).status_code, 302)
        self.client.logout()
        self.post_login("senha-errada")
        self.post_login("senha-errada")
        self.assertEqual(self.post_login(PASSWORD).status_code, 302)

    def test_lock_is_per_username(self):
        make_operator("bruno", self.organization)
        self.fail_until_locked("ana")
        self.assertEqual(self.post_login(PASSWORD, username="bruno").status_code, 302)

    def test_lock_is_case_insensitive_on_username(self):
        self.fail_until_locked("ANA")
        self.assertContains(self.post_login(PASSWORD, username="ana"), LOCKED_MESSAGE)

    def test_admin_login_is_also_protected(self):
        User.objects.filter(pk=self.user.pk).update(is_staff=True)
        self.fail_until_locked(url=reverse("admin:login"))
        response = self.post_login(PASSWORD, url=reverse("admin:login"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_failed_and_successful_logins_are_logged(self):
        with self.assertLogs("grello.security", level="INFO") as logs:
            self.post_login("senha-errada")
            self.post_login(PASSWORD)
        self.assertTrue(any("login falhou usuario=ana" in line for line in logs.output))
        self.assertTrue(any("login ok usuario=ana" in line for line in logs.output))


class ApiProfileRequirementTests(TestCase):
    def test_api_root_requires_an_organization_profile(self):
        user = User.objects.create_user("semperfil")
        self.client.force_login(user)
        response = self.client.get("/api/")
        self.assertEqual(response.status_code, 403)


class SeedDemoProductionGuardTests(TestCase):
    @override_settings(DEBUG=False)
    def test_refuses_to_run_without_debug(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())

    @override_settings(DEBUG=False)
    def test_runs_without_debug_when_explicitly_allowed(self):
        call_command("seed_demo", "--allow-production", stdout=StringIO())
        self.assertTrue(User.objects.filter(username="admin.labs").exists())
