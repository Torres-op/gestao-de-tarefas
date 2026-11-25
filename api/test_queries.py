from django.test import TestCase

from core.testing import QueryCountScenario


class ApiQueryCountTests(QueryCountScenario, TestCase):
    def assertEndpointsStayAt(self, expected, urls):
        for url in urls:
            with self.subTest(url=url):
                self.assertQueriesStayAt(expected, url, user=self.operator)

    def test_projects(self):
        self.assertEndpointsStayAt(5, ["/api/projects/", f"/api/projects/{self.project.pk}/"])

    def test_sprints(self):
        self.assertEndpointsStayAt(
            5, ["/api/sprints/", f"/api/sprints/?project={self.project.pk}", f"/api/sprints/{self.sprint.pk}/"]
        )

    def test_members(self):
        self.assertEndpointsStayAt(4, ["/api/members/", f"/api/members/{self.member.pk}/"])

    def test_tasks(self):
        self.assertEndpointsStayAt(
            7,
            [
                "/api/tasks/",
                f"/api/tasks/?project={self.project.pk}&status=in_progress",
                f"/api/tasks/{self.root.pk}/",
            ],
        )

    def test_subtasks(self):
        self.assertEndpointsStayAt(4, ["/api/subtasks/", f"/api/subtasks/{self.subtask.pk}/"])

    def test_dependencies(self):
        self.client.force_login(self.operator)
        self.grow(1)
        dependency = self.root.dependents.first()
        self.assertEndpointsStayAt(4, ["/api/dependencies/", f"/api/dependencies/{dependency.pk}/"])
