from django.test import TestCase
from django.urls import reverse

from core.testing import QueryCountScenario


class DashboardQueryCountTests(QueryCountScenario, TestCase):
    def test_dashboard_as_admin(self):
        self.assertQueriesStayAt(14, reverse("dashboard:index"))

    def test_dashboard_as_operator(self):
        self.assertQueriesStayAt(11, reverse("dashboard:index"), user=self.operator)

    def test_dashboard_filtered_by_sprint(self):
        self.assertQueriesStayAt(14, f"{reverse('dashboard:index')}?sprint={self.sprint.pk}")

    def test_csv_export(self):
        self.assertQueriesStayAt(4, reverse("dashboard:export_csv"))


class DashboardApiQueryCountTests(QueryCountScenario, TestCase):
    def test_summary_as_admin(self):
        self.assertQueriesStayAt(12, reverse("dashboard_api:summary"))

    def test_summary_as_operator(self):
        self.assertQueriesStayAt(9, reverse("dashboard_api:summary"), user=self.operator)

    def test_burndown_default_and_selected_sprint(self):
        urls = [reverse("dashboard_api:burndown"), f"{reverse('dashboard_api:burndown')}?sprint={self.sprint.pk}"]
        for url in urls:
            with self.subTest(url=url):
                self.assertQueriesStayAt(5, url, user=self.operator)
