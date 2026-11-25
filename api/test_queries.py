from django.test import TestCase

from core.testing import QueryCountScenario


class ApiQueryCountTests(QueryCountScenario, TestCase):
    def assertEndpointsStayAt(self, expected_by_url):
        for url, expected in expected_by_url.items():
            with self.subTest(url=url):
                self.assertQueriesStayAt(expected, url, user=self.operator)

    def test_projects(self):
        self.assertEndpointsStayAt({"/api/projects/": 6, f"/api/projects/{self.project.pk}/": 5})

    def test_sprints(self):
        self.assertEndpointsStayAt(
            {
                "/api/sprints/": 6,
                f"/api/sprints/?project={self.project.pk}": 6,
                f"/api/sprints/{self.sprint.pk}/": 5,
            }
        )

    def test_members(self):
        self.assertEndpointsStayAt({"/api/members/": 5, f"/api/members/{self.member.pk}/": 4})

    def test_tasks(self):
        self.assertEndpointsStayAt(
            {
                "/api/tasks/": 8,
                f"/api/tasks/?project={self.project.pk}&status=in_progress": 8,
                f"/api/tasks/{self.root.pk}/": 7,
            }
        )

    def test_subtasks(self):
        self.assertEndpointsStayAt({"/api/subtasks/": 5, f"/api/subtasks/{self.subtask.pk}/": 4})

    def test_dependencies(self):
        self.client.force_login(self.operator)
        self.grow(1)
        dependency = self.root.dependents.first()
        self.assertEndpointsStayAt({"/api/dependencies/": 5, f"/api/dependencies/{dependency.pk}/": 4})

    def test_paginated_list_stays_constant_beyond_one_page(self):
        self.assertQueriesStayAt(5, "/api/members/?page_size=5", user=self.operator)
        self.assertQueriesStayAt(5, "/api/members/?page_size=5&page=2", user=self.operator, small=0, large=1)
