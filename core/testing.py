from datetime import date
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
