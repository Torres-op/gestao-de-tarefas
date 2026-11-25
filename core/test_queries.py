from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .testing import QueryCountScenario, make_user
from .tenancy import current_organization, get_profile, is_org_admin


class ProfileLoadingTests(QueryCountScenario, TestCase):
    def test_profile_and_organization_come_in_a_single_query(self):
        user = User.objects.get(pk=self.admin.pk)
        with self.assertNumQueries(1):
            profile = get_profile(user)
            self.assertEqual(profile.organization.name, "Organização Consultas")
            self.assertIs(profile.user, user)
        with self.assertNumQueries(0):
            self.assertIs(get_profile(user), profile)
            self.assertTrue(is_org_admin(user))
            self.assertIs(user.profile, profile)

    def test_missing_profile_is_cached_as_absent(self):
        user = make_user("sem.perfil.consultas")
        with self.assertNumQueries(1):
            self.assertIsNone(get_profile(user))
        with self.assertNumQueries(0):
            self.assertIsNone(get_profile(user))
            self.assertFalse(is_org_admin(user))

    def test_middleware_loads_profile_once_per_request(self):
        self.client.force_login(self.admin)
        with self.assertNumQueries(3):
            response = self.get_ok(reverse("home"))
        request = response.wsgi_request
        self.assertEqual(request.organization, self.organization)
        with self.assertNumQueries(0):
            self.assertEqual(current_organization(request), self.organization)

    def test_home_query_count_does_not_grow(self):
        self.assertQueriesStayAt(3, reverse("home"), user=self.operator)

    def test_user_without_profile_gets_403_with_three_queries(self):
        self.client.force_login(make_user("sem.perfil.http"))
        with self.assertNumQueries(3):
            response = self.client.get(reverse("projects:list"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_is_redirected_without_queries(self):
        with self.assertNumQueries(0):
            response = self.client.get(reverse("projects:list"))
        self.assertEqual(response.status_code, 302)
