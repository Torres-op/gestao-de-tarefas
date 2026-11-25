from datetime import date, timedelta
from functools import cache

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.contrib.messages import get_messages

from members.models import Member
from projects.models import Project, Sprint
from tasks.models import Subtask, Task, TaskDependency

from .models import Organization, Profile

PASSWORD = "senha-de-teste-123"


def make_organization(name):
    return Organization.objects.create(name=name)


@cache
def password_hash():
    return make_password(PASSWORD)


def make_user(username, organization=None, role=Profile.Role.OPERATOR, **extra):
    user = User.objects.create(username=username, password=password_hash(), **extra)
    if organization is not None:
        Profile.objects.create(user=user, organization=organization, role=role)
    return user


def make_admin(username, organization):
    return make_user(username, organization, role=Profile.Role.ADMIN)


def make_operator(username, organization):
    return make_user(username, organization, role=Profile.Role.OPERATOR)


def make_project(organization, name="Projeto", **extra):
    return Project.objects.create(organization=organization, name=name, **extra)


def make_sprint(project, name="Sprint 1", start=date(2026, 3, 2), end=date(2026, 3, 15), **extra):
    return Sprint.objects.create(project=project, name=name, start_date=start, end_date=end, **extra)


def make_member(organization, name="Membro", email=None, **extra):
    email = email or f"{name.lower().replace(' ', '.')}@exemplo.com"
    return Member.objects.create(organization=organization, name=name, email=email, **extra)


def make_task(project, title="Tarefa", status=Task.Status.PENDING, **extra):
    return Task.objects.create(project=project, title=title, status=status, **extra)


def make_subtask(task, title="Subtarefa", is_done=False):
    return Subtask.objects.create(task=task, title=title, is_done=is_done)


def make_dependency(task, depends_on):
    return TaskDependency.objects.create(task=task, depends_on=depends_on)


def messages_of(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


class QueryCountScenario:
    @classmethod
    def setUpTestData(cls):
        cls.organization = make_organization("Organização Consultas")
        cls.admin = make_admin("admin.consultas", cls.organization)
        cls.operator = make_operator("operador.consultas", cls.organization)
        cls.project = make_project(cls.organization, "Projeto principal", start_date=date(2026, 1, 1))
        cls.sprint = make_sprint(cls.project, "Sprint principal", start=date(2026, 1, 1), end=date(2026, 2, 28))
        cls.member = make_member(cls.organization, "Ana Consultas")
        cls.root = make_task(cls.project, "Tarefa raiz", assignee=cls.member, sprint=cls.sprint)
        cls.subtask = make_subtask(cls.root, "Subtarefa raiz")
        other = make_organization("Outra organização")
        other_project = make_project(other, "Projeto alheio")
        make_task(other_project, "Tarefa alheia")

    def grow(self, amount):
        created = getattr(self, "grown", 0)
        previous = getattr(self, "last_grown", self.root)
        for index in range(created, created + amount):
            member = make_member(self.organization, f"Membro {index}")
            task = make_task(
                self.project,
                f"Tarefa {index}",
                status=Task.Status.IN_PROGRESS,
                sprint=self.sprint,
                assignee=member if index % 2 else self.member,
                due_date=date(2026, 6, 1) + timedelta(days=index),
            )
            make_subtask(task, f"Subtarefa {index}")
            make_subtask(task, f"Subtarefa feita {index}", is_done=True)
            make_dependency(task, previous)
            if previous != self.root:
                make_dependency(task, self.root)
            extra_project = make_project(self.organization, f"Projeto extra {index}")
            extra_sprint = make_sprint(extra_project, f"Sprint extra {index}")
            make_task(extra_project, f"Tarefa extra {index}", sprint=extra_sprint, assignee=member)
            previous = task
        self.grown = created + amount
        self.last_grown = previous

    def get_ok(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return response

    def assertQueriesStayAt(self, expected, url, user=None, small=3, large=12):
        self.client.force_login(user or self.admin)
        self.grow(small)
        with self.assertNumQueries(expected):
            self.get_ok(url)
        self.grow(large)
        with self.assertNumQueries(expected):
            self.get_ok(url)
