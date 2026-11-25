from io import StringIO

from django.contrib.auth.models import AnonymousUser, User
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from members.models import Member
from projects.models import Project, Sprint
from tasks.forms import TaskForm
from tasks.models import Subtask, Task, TaskDependency

from .context_processors import organization as organization_context
from .models import Organization, Profile
from .tenancy import get_profile, is_org_admin
from .testing import (
    PASSWORD,
    make_admin,
    make_dependency,
    make_member,
    make_operator,
    make_organization,
    make_project,
    make_sprint,
    make_subtask,
    make_task,
    make_user,
)


class TwoOrganizationsMixin:
    @classmethod
    def setUpTestData(cls):
        cls.org_a = make_organization("Organização A")
        cls.admin_a = make_admin("admin.a", cls.org_a)
        cls.operator_a = make_operator("operador.a", cls.org_a)
        cls.project_a = make_project(cls.org_a, "Projeto A")
        cls.sprint_a = make_sprint(cls.project_a, "Sprint A")
        cls.member_a = make_member(cls.org_a, "Ana A", email="ana@exemplo.com")
        cls.task_a = make_task(cls.project_a, "Tarefa A", assignee=cls.member_a, sprint=cls.sprint_a)

        cls.org_b = make_organization("Organização B")
        cls.admin_b = make_admin("admin.b", cls.org_b)
        cls.project_b = make_project(cls.org_b, "Projeto B")
        cls.sprint_b = make_sprint(cls.project_b, "Sprint B")
        cls.member_b = make_member(cls.org_b, "Bruno B", email="bruno@exemplo.com")
        cls.task_b = make_task(cls.project_b, "Tarefa B", assignee=cls.member_b, sprint=cls.sprint_b)
        cls.subtask_b = make_subtask(cls.task_b, "Subtarefa B")
        cls.dependency_b = make_dependency(cls.task_b, make_task(cls.project_b, "Pré-requisito B"))


class IsolationScriptTests(TwoOrganizationsMixin, TestCase):
    def test_a_lists_show_only_own_organization(self):
        self.client.force_login(self.admin_a)
        projects = self.client.get(reverse("projects:list"))
        self.assertEqual(list(projects.context["projects"]), [self.project_a])
        members = self.client.get(reverse("members:list"))
        self.assertEqual(list(members.context["members"]), [self.member_a])
        tasks = self.client.get(reverse("tasks:list"))
        self.assertEqual(list(tasks.context["tasks"]), [self.task_a])
        for response in (projects, members, tasks):
            self.assertNotContains(response, "Organização B")
            self.assertNotContains(response, " B</a>")

    def test_b_opening_or_editing_records_of_another_organization_returns_404(self):
        self.client.force_login(self.admin_a)
        urls = [
            reverse("projects:detail", args=[self.project_b.pk]),
            reverse("projects:update", args=[self.project_b.pk]),
            reverse("projects:delete", args=[self.project_b.pk]),
            reverse("projects:sprint_detail", args=[self.sprint_b.pk]),
            reverse("projects:sprint_update", args=[self.sprint_b.pk]),
            reverse("projects:sprint_create", args=[self.project_b.pk]),
            reverse("members:detail", args=[self.member_b.pk]),
            reverse("members:update", args=[self.member_b.pk]),
            reverse("tasks:detail", args=[self.task_b.pk]),
            reverse("tasks:update", args=[self.task_b.pk]),
            reverse("tasks:delete", args=[self.task_b.pk]),
            reverse("tasks:subtask_create", args=[self.task_b.pk]),
            reverse("tasks:subtask_update", args=[self.subtask_b.pk]),
            reverse("tasks:dependency_create", args=[self.task_b.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_b_actions_on_records_of_another_organization_return_404_and_change_nothing(self):
        self.client.force_login(self.operator_a)
        urls = [
            reverse("tasks:complete", args=[self.task_b.pk]),
            reverse("tasks:reopen", args=[self.task_b.pk]),
            reverse("tasks:subtask_toggle", args=[self.subtask_b.pk]),
            reverse("tasks:subtask_delete", args=[self.subtask_b.pk]),
            reverse("tasks:dependency_delete", args=[self.dependency_b.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url).status_code, 404)
        self.assertFalse(Subtask.objects.get(pk=self.subtask_b.pk).is_done)
        self.assertTrue(TaskDependency.objects.filter(pk=self.dependency_b.pk).exists())

    def test_c_created_project_belongs_to_user_organization_even_if_another_is_injected(self):
        self.client.force_login(self.admin_a)
        self.client.post(
            reverse("projects:create"),
            {"name": "Injetado", "description": "", "start_date": "", "due_date": "", "organization": self.org_b.pk},
        )
        self.assertEqual(Project.objects.get(name="Injetado").organization, self.org_a)

    def test_c_created_member_belongs_to_user_organization_even_if_another_is_injected(self):
        self.client.force_login(self.admin_a)
        self.client.post(
            reverse("members:create"),
            {"name": "Carla", "email": "carla@exemplo.com", "role": "", "is_active": "on", "organization": self.org_b.pk},
        )
        self.assertEqual(Member.objects.get(email="carla@exemplo.com").organization, self.org_a)

    def test_c_task_cannot_be_created_in_project_of_another_organization(self):
        self.client.force_login(self.operator_a)
        response = self.client.post(
            reverse("tasks:create"), {"project": self.project_b.pk, "title": "Invasora", "status": "pending"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("project", response.context["form"].errors)
        self.assertFalse(Task.objects.filter(title="Invasora").exists())

    def test_c_task_cannot_use_sprint_or_assignee_of_another_organization(self):
        self.client.force_login(self.operator_a)
        response = self.client.post(
            reverse("tasks:create"),
            {
                "project": self.project_a.pk,
                "title": "Mista",
                "status": "pending",
                "sprint": self.sprint_b.pk,
                "assignee": self.member_b.pk,
            },
        )
        errors = response.context["form"].errors
        self.assertIn("sprint", errors)
        self.assertIn("assignee", errors)
        self.assertFalse(Task.objects.filter(title="Mista").exists())

    def test_d_task_form_selects_show_only_organization_options(self):
        inactive = make_member(self.org_a, "Inativo", email="inativo@exemplo.com", is_active=False)
        self.client.force_login(self.operator_a)
        form = self.client.get(reverse("tasks:create")).context["form"]
        self.assertEqual(list(form.fields["project"].queryset), [self.project_a])
        self.assertEqual(list(form.fields["sprint"].queryset), [self.sprint_a])
        self.assertEqual(list(form.fields["assignee"].queryset), [self.member_a])
        self.assertNotIn(inactive, form.fields["assignee"].queryset)

    def test_d_edit_form_keeps_current_inactive_assignee_available(self):
        Member.objects.filter(pk=self.member_a.pk).update(is_active=False)
        self.client.force_login(self.operator_a)
        form = self.client.get(reverse("tasks:update", args=[self.task_a.pk])).context["form"]
        self.assertEqual(list(form.fields["assignee"].queryset), [self.member_a])

    def test_e_same_email_is_allowed_in_different_organizations(self):
        self.client.force_login(self.admin_b)
        response = self.client.post(
            reverse("members:create"), {"name": "Ana B", "email": "ana@exemplo.com", "role": "", "is_active": "on"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            set(Member.objects.filter(email="ana@exemplo.com").values_list("organization__name", flat=True)),
            {"Organização A", "Organização B"},
        )


class AuthenticationTests(TwoOrganizationsMixin, TestCase):
    def test_anonymous_user_is_redirected_to_login_with_next(self):
        for url in (reverse("projects:list"), reverse("tasks:detail", args=[self.task_a.pk]), reverse("members:list")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f"/accounts/login/?next={url}", fetch_redirect_response=False)

    def test_anonymous_post_to_action_is_redirected_and_changes_nothing(self):
        url = reverse("tasks:complete", args=[self.task_a.pk])
        response = self.client.post(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}", fetch_redirect_response=False)
        self.assertEqual(Task.objects.get(pk=self.task_a.pk).status, Task.Status.PENDING)

    def test_login_page_is_public(self):
        self.assertEqual(self.client.get("/accounts/login/").status_code, 200)

    def test_login_with_valid_credentials_redirects_to_next(self):
        response = self.client.post(
            "/accounts/login/?next=/projects/", {"username": "operador.a", "password": PASSWORD}
        )
        self.assertRedirects(response, "/projects/")

    def test_login_with_invalid_credentials_stays_on_page(self):
        response = self.client.post("/accounts/login/", {"username": "operador.a", "password": "errada"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_requires_post_and_logs_user_out(self):
        self.client.force_login(self.operator_a)
        self.assertEqual(self.client.get("/accounts/logout/").status_code, 405)
        response = self.client.post("/accounts/logout/")
        self.assertRedirects(response, "/accounts/login/")
        self.assertEqual(self.client.get(reverse("projects:list")).status_code, 302)

    def test_base_template_shows_organization_role_and_logout_form(self):
        self.client.force_login(self.operator_a)
        response = self.client.get(reverse("projects:list"))
        self.assertContains(response, "Organização A &middot; Operador", html=False)
        self.assertContains(response, 'action="/accounts/logout/"')


class NoProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("sem.perfil")
        cls.staff = make_user("staff.sem.perfil", is_staff=True, is_superuser=True)

    def test_user_without_profile_gets_403_with_explanation(self):
        self.client.force_login(self.user)
        for url in (reverse("projects:list"), reverse("tasks:list"), reverse("members:list")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)
                self.assertTemplateUsed(response, "core/no_profile.html")
        self.assertContains(response, "Peça ao administrador", status_code=403)

    def test_staff_without_profile_is_pointed_to_admin(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("projects:list"))
        self.assertContains(response, reverse("admin:core_profile_add"), status_code=403)

    def test_admin_site_stays_accessible_without_profile(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:core_profile_add")).status_code, 200)

    def test_logout_stays_accessible_without_profile(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.post("/accounts/logout/"), "/accounts/login/")


class TenancyAndContextProcessorTests(TwoOrganizationsMixin, TestCase):
    def test_get_profile_handles_anonymous_and_missing_profile(self):
        self.assertIsNone(get_profile(AnonymousUser()))
        self.assertIsNone(get_profile(None))
        self.assertIsNone(get_profile(make_user("sem.perfil")))
        self.assertEqual(get_profile(self.admin_a), self.admin_a.profile)

    def test_is_org_admin_depends_on_role(self):
        self.assertTrue(is_org_admin(self.admin_a))
        self.assertFalse(is_org_admin(self.operator_a))
        self.assertFalse(is_org_admin(AnonymousUser()))
        self.assertTrue(self.admin_a.profile.is_admin)
        self.assertFalse(self.operator_a.profile.is_admin)

    def test_context_processor_without_profile(self):
        request = RequestFactory().get("/")
        self.assertEqual(
            organization_context(request),
            {"current_profile": None, "current_organization": None, "is_org_admin": False},
        )

    def test_context_processor_exposes_organization_and_role_in_templates(self):
        self.client.force_login(self.admin_a)
        context = self.client.get(reverse("projects:list")).context
        self.assertEqual(context["current_organization"], self.org_a)
        self.assertEqual(context["current_profile"], self.admin_a.profile)
        self.assertTrue(context["is_org_admin"])

        self.client.force_login(self.operator_a)
        context = self.client.get(reverse("projects:list")).context
        self.assertEqual(context["current_organization"], self.org_a)
        self.assertFalse(context["is_org_admin"])

    def test_profile_str_shows_role_and_organization(self):
        self.assertEqual(str(self.admin_a.profile), "admin.a (Administrador · Organização A)")


FAST_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


def run_seed(*args):
    out = StringIO()
    with override_settings(DEBUG=True):
        call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class SeedDemoContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.output = run_seed()

    def test_creates_two_organizations_with_four_users_and_profiles(self):
        self.assertEqual(
            set(Organization.objects.values_list("name", flat=True)), {"Grello Labs", "Acme Consultoria"}
        )
        profiles = {
            profile.user.username: (profile.organization.name, profile.role)
            for profile in Profile.objects.select_related("user", "organization")
        }
        self.assertEqual(
            profiles,
            {
                "admin.labs": ("Grello Labs", Profile.Role.ADMIN),
                "operador.labs": ("Grello Labs", Profile.Role.OPERATOR),
                "admin.acme": ("Acme Consultoria", Profile.Role.ADMIN),
                "operador.acme": ("Acme Consultoria", Profile.Role.OPERATOR),
            },
        )
        self.assertTrue(User.objects.get(username="admin.labs").check_password("demo1234"))
        self.assertIn("Dados de demonstração criados.", self.output)

    def test_creates_sprints_with_expected_states(self):
        labs = Sprint.objects.filter(project__organization__name="Grello Labs").order_by("start_date")
        acme = Sprint.objects.filter(project__organization__name="Acme Consultoria")
        self.assertEqual(labs.count(), 3)
        self.assertEqual(acme.count(), 2)
        self.assertEqual(
            [sprint.state() for sprint in labs],
            [Sprint.State.FINISHED, Sprint.State.FINISHED, Sprint.State.ACTIVE],
        )

    def test_creates_expected_blocking_scenario(self):
        tasks = Task.objects.filter(project__organization__name="Grello Labs").prefetch_related(
            "subtasks", "dependencies__depends_on"
        )
        blocked_by_subtasks = {task.title for task in tasks if task.pending_subtasks()}
        blocked_by_dependencies = {task.title for task in tasks if task.pending_dependencies()}
        self.assertEqual(blocked_by_subtasks, {"Modelar o banco de dados", "Desenhar as telas"})
        self.assertEqual(
            blocked_by_dependencies, {"Implementar o cadastro de alunos", "Testar o fluxo de matrícula"}
        )

    def test_seeded_data_respects_all_invariants(self):
        for dependency in TaskDependency.objects.select_related("task", "depends_on"):
            if dependency.task.is_done():
                self.assertTrue(dependency.depends_on.is_done(), str(dependency))
            self.assertEqual(dependency.task.project_id, dependency.depends_on.project_id)
        for subtask in Subtask.objects.select_related("task"):
            if subtask.task.is_done():
                self.assertTrue(subtask.is_done, str(subtask))
        for task in Task.objects.select_related("project", "sprint", "assignee"):
            with self.subTest(task=task.title):
                task.validate_relations()
                self.assertEqual(task.completed_at is not None, task.is_done())
                self.assertEqual(task.started_at is None, task.status == Task.Status.PENDING)

    def test_every_seeded_task_can_be_edited_through_the_form(self):
        for task in Task.objects.select_related("project__organization"):
            data = {
                "project": task.project_id,
                "sprint": task.sprint_id or "",
                "title": task.title,
                "description": task.description,
                "assignee": task.assignee_id or "",
                "status": task.status,
                "due_date": task.due_date.isoformat() if task.due_date else "",
            }
            form = TaskForm(data=data, instance=task, organization=task.project.organization)
            with self.subTest(task=task.title):
                self.assertTrue(form.is_valid(), form.errors)

    def test_same_member_email_exists_in_both_organizations(self):
        self.assertEqual(Member.objects.filter(email="ana@exemplo.com").count(), 2)

    def test_demo_users_see_only_their_organization(self):
        self.client.force_login(User.objects.get(username="operador.acme"))
        response = self.client.get(reverse("projects:list"))
        self.assertEqual([project.name for project in response.context["projects"]], ["Portal do Cliente"])


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class SeedDemoRerunTests(TestCase):
    def test_running_twice_without_reset_does_not_duplicate(self):
        run_seed()
        output = run_seed()
        self.assertIn("--reset", output)
        self.assertEqual(Organization.objects.count(), 2)
        self.assertEqual(User.objects.count(), 4)

    def test_reset_recreates_demo_data_and_keeps_other_organizations(self):
        other = make_organization("Organização padrão")
        kept = make_project(other, "Projeto legado")
        run_seed()
        first_ids = set(Task.objects.values_list("pk", flat=True))
        task_count = Task.objects.count()
        run_seed("--reset")
        self.assertEqual(Task.objects.count(), task_count)
        self.assertFalse(first_ids & set(Task.objects.values_list("pk", flat=True)))
        self.assertEqual(Organization.objects.count(), 3)
        self.assertEqual(User.objects.count(), 4)
        self.assertTrue(Project.objects.filter(pk=kept.pk).exists())


class DataMigrationTests(TransactionTestCase):
    before = [
        ("core", "0001_initial"),
        ("projects", "0001_initial"),
        ("members", "0001_initial"),
        ("tasks", "0002_taskdependency"),
    ]

    def test_legacy_rows_are_assigned_to_default_organization(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old_apps = executor.loader.project_state(self.before).apps

        OldProject = old_apps.get_model("projects", "Project")
        OldMember = old_apps.get_model("members", "Member")
        OldTask = old_apps.get_model("tasks", "Task")
        project = OldProject.objects.create(name="Projeto legado")
        member = OldMember.objects.create(name="Membro legado", email="legado@exemplo.com")
        doing = OldTask.objects.create(project_id=project.pk, title="Em andamento", status="in_progress")
        pending = OldTask.objects.create(project_id=project.pk, title="Pendente", status="pending")

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

        default = Organization.objects.get(name="Organização padrão")
        self.assertEqual(Project.objects.get(pk=project.pk).organization, default)
        self.assertEqual(Member.objects.get(pk=member.pk).organization, default)
        doing = Task.objects.get(pk=doing.pk)
        self.assertEqual(doing.started_at, doing.created_at)
        self.assertIsNone(Task.objects.get(pk=pending.pk).started_at)
        self.assertIsNone(doing.sprint)
