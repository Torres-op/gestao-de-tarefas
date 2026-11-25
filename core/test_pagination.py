from django.test import TestCase
from django.urls import reverse

from members.models import Member
from projects.models import Project
from tasks.models import Task

from .testing import make_admin, make_operator, make_organization, make_project, make_sprint, make_task

NAV = 'aria-label="Paginação"'


class HtmlPaginationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = make_organization("Org Paginada")
        cls.admin = make_admin("admin.paginas", cls.organization)
        cls.operator = make_operator("operador.paginas", cls.organization)
        cls.other = make_organization("Outra Org")

    def setUp(self):
        self.client.force_login(self.admin)

    def create_projects(self, amount, organization=None):
        Project.objects.bulk_create(
            Project(organization=organization or self.organization, name=f"Projeto {index:03d}")
            for index in range(amount)
        )

    def create_members(self, amount, organization=None):
        Member.objects.bulk_create(
            Member(
                organization=organization or self.organization,
                name=f"Pessoa {index:03d}",
                email=f"pessoa{index}@exemplo.com",
            )
            for index in range(amount)
        )

    def create_tasks(self, project, amount, **extra):
        for index in range(amount):
            make_task(project, f"Tarefa {index:03d}", **extra)

    def test_page_sizes(self):
        self.create_projects(13)
        self.create_members(21)
        project = Project.objects.filter(organization=self.organization).first()
        self.create_tasks(project, 26)
        cases = [
            ("projects:list", "projects", 12, 13, "projetos"),
            ("members:list", "members", 20, 21, "membros"),
            ("tasks:list", "tasks", 25, 26, "tarefas"),
        ]
        for url_name, context_name, page_size, total, label in cases:
            with self.subTest(url=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["is_paginated"])
                self.assertEqual(len(response.context[context_name]), page_size)
                self.assertEqual(response.context["paginator"].count, total)
                self.assertContains(response, NAV)
                self.assertContains(response, "Página 1 de 2")
                self.assertContains(response, f"{total} {label} no total")
                self.assertContains(response, 'href="?page=2"')
                last = self.client.get(reverse(url_name), {"page": 2})
                self.assertEqual(len(last.context[context_name]), total - page_size)
                self.assertContains(last, "Página 2 de 2")
                self.assertContains(last, 'href="?page=1"')

    def test_short_lists_do_not_show_pagination(self):
        self.create_projects(2)
        self.create_members(2)
        for url_name in ("projects:list", "members:list", "tasks:list"):
            with self.subTest(url=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context["is_paginated"])
                self.assertNotContains(response, NAV)

    def test_invalid_page_falls_back_instead_of_failing(self):
        self.create_projects(13)
        cases = {"abc": 1, "0": 2, "-1": 2, "999": 2, "": 1}
        for page, expected in cases.items():
            with self.subTest(page=page):
                response = self.client.get(reverse("projects:list"), {"page": page})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["page_obj"].number, expected)

    def test_invalid_page_on_empty_list_shows_empty_state(self):
        response = self.client.get(reverse("members:list"), {"page": "7"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nenhum membro cadastrado ainda.")

    def test_task_filters_are_kept_in_page_links(self):
        project = make_project(self.organization, "Projeto filtrado")
        sprint = make_sprint(project, "Sprint filtrada")
        self.create_tasks(project, 27, sprint=sprint, status=Task.Status.IN_PROGRESS)
        self.create_tasks(project, 3, status=Task.Status.PENDING)
        query = {"project": project.pk, "sprint": sprint.pk, "status": "in_progress"}
        response = self.client.get(reverse("tasks:list"), query)
        self.assertEqual(response.context["paginator"].count, 27)
        expected = f"?project={project.pk}&amp;sprint={sprint.pk}&amp;status=in_progress&amp;page=2"
        self.assertContains(response, f'href="{expected}"')
        response = self.client.get(reverse("tasks:list"), {**query, "page": 2})
        self.assertEqual(len(response.context["tasks"]), 2)
        self.assertContains(response, "status=in_progress&amp;page=1")

    def test_count_only_includes_own_organization(self):
        self.create_projects(5)
        self.create_projects(20, organization=self.other)
        self.create_members(25, organization=self.other)
        response = self.client.get(reverse("projects:list"))
        self.assertEqual(response.context["paginator"].count, 5)
        self.assertFalse(response.context["is_paginated"])
        response = self.client.get(reverse("members:list"))
        self.assertEqual(response.context["paginator"].count, 0)

    def test_operator_also_sees_pagination(self):
        self.create_members(21)
        self.client.force_login(self.operator)
        response = self.client.get(reverse("members:list"), {"page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["members"]), 1)


class TaskListEmptyStateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = make_organization("Org Vazia")
        cls.admin = make_admin("admin.vazio", cls.organization)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_without_filters(self):
        response = self.client.get(reverse("tasks:list"))
        self.assertContains(response, "Nenhuma tarefa cadastrada ainda.")
        self.assertNotContains(response, "Limpar filtros")

    def test_with_filters(self):
        response = self.client.get(reverse("tasks:list"), {"status": "done"})
        self.assertContains(response, "Nenhuma tarefa encontrada com os filtros selecionados.")
        self.assertContains(response, "Limpar filtros")
