from unittest import mock

from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    def test_anonymous_request_gets_ok_without_redirect_to_login(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_response_is_not_cached(self):
        response = self.client.get(reverse("health"))
        self.assertIn("no-cache", response["Cache-Control"])

    def test_only_get_is_allowed(self):
        self.assertEqual(self.client.post(reverse("health")).status_code, 405)

    def test_database_failure_returns_503(self):
        with mock.patch("core.views.connection.ensure_connection", side_effect=DatabaseError):
            response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "erro")
