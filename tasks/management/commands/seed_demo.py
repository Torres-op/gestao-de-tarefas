from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Organization, Profile
from members.models import Member
from projects.models import Project, Sprint
from tasks.models import Subtask, Task, TaskDependency

LABS = "Grello Labs"
ACME = "Acme Consultoria"
DEMO_PASSWORD = "demo1234"
DEMO_USERS = [
    ("admin.labs", "Alice", LABS, Profile.Role.ADMIN),
    ("operador.labs", "Otávio", LABS, Profile.Role.OPERATOR),
    ("admin.acme", "Amanda", ACME, Profile.Role.ADMIN),
    ("operador.acme", "Oscar", ACME, Profile.Role.OPERATOR),
]

DONE = Task.Status.DONE
DOING = Task.Status.IN_PROGRESS
TODO = Task.Status.PENDING


class Command(BaseCommand):
    help = (
        "Cria duas organizações de demonstração, com usuários, projetos, sprints, tarefas, "
        "subtarefas e dependências, com datas relativas ao dia de hoje."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Apaga as organizações de demonstração e seus dados antes de criar tudo de novo.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self.reset()

        if Organization.objects.filter(name__in=[LABS, ACME]).exists():
            self.stdout.write(
                self.style.WARNING("As organizações de demonstração já existem. Use --reset para recriá-las.")
            )
            return

        self.today = timezone.localdate()
        labs = Organization.objects.create(name=LABS)
        acme = Organization.objects.create(name=ACME)
        organizations = {LABS: labs, ACME: acme}

        for username, first_name, organization_name, role in DEMO_USERS:
            user = User.objects.create_user(username=username, password=DEMO_PASSWORD, first_name=first_name)
            Profile.objects.create(user=user, organization=organizations[organization_name], role=role)

        self.seed_labs(labs)
        self.seed_acme(acme)

        self.stdout.write(self.style.SUCCESS("Dados de demonstração criados."))
        self.stdout.write(f"Usuários (senha: {DEMO_PASSWORD}):")
        for username, _, organization_name, role in DEMO_USERS:
            self.stdout.write(f"  {username:<15} {organization_name:<18} {Profile.Role(role).label}")
        self.stdout.write("Na Grello Labs, o projeto Sistema de Matrículas tem 3 sprints (a última em andamento).")
        self.stdout.write("Ficam bloqueadas:")
        self.stdout.write('  por subtarefas em aberto: "Modelar o banco de dados" e "Desenhar as telas"')
        self.stdout.write('  por dependências pendentes: "Implementar o cadastro de alunos" e "Testar o fluxo de matrícula"')

    def reset(self):
        organizations = Organization.objects.filter(name__in=[LABS, ACME])
        Project.objects.filter(organization__in=organizations).delete()
        Member.objects.filter(organization__in=organizations).delete()
        User.objects.filter(profile__organization__in=organizations).delete()
        User.objects.filter(username__in=[username for username, *_ in DEMO_USERS]).delete()
        organizations.delete()

    def day(self, offset):
        return self.today + timedelta(days=offset)

    def moment(self, offset, hour):
        return timezone.make_aware(datetime.combine(self.day(offset), time(hour)))

    def sprint(self, project, name, start, end, goal):
        return Sprint.objects.create(
            project=project, name=name, goal=goal, start_date=self.day(start), end_date=self.day(end)
        )

    def task(self, project, title, assignee, status, created, started=None, completed=None, due=None, sprint=None):
        task = Task.objects.create(
            project=project,
            sprint=sprint,
            assignee=assignee,
            title=title,
            status=status,
            due_date=self.day(due) if due is not None else None,
        )
        Task.objects.filter(pk=task.pk).update(
            created_at=self.moment(created, 9),
            started_at=self.moment(started, 10) if started is not None else None,
            completed_at=self.moment(completed, 17) if completed is not None else None,
        )
        return task

    def seed_labs(self, organization):
        ana = Member.objects.create(organization=organization, name="Ana Souza", email="ana@exemplo.com", role="Analista de requisitos")
        bruno = Member.objects.create(organization=organization, name="Bruno Lima", email="bruno@exemplo.com", role="Desenvolvedor")
        carla = Member.objects.create(organization=organization, name="Carla Dias", email="carla@exemplo.com", role="Designer")
        diego = Member.objects.create(organization=organization, name="Diego Alves", email="diego@exemplo.com", role="Desenvolvedor")

        project = Project.objects.create(
            organization=organization,
            name="Sistema de Matrículas",
            description="Portal de matrículas online para a secretaria acadêmica.",
            start_date=self.day(-35),
            due_date=self.day(60),
        )
        s1 = self.sprint(project, "Sprint 1", -35, -22, "Preparar a base do projeto e o ambiente.")
        s2 = self.sprint(project, "Sprint 2", -21, -8, "Fechar requisitos e a arquitetura.")
        s3 = self.sprint(project, "Sprint 3", -7, 6, "Modelagem do banco, telas e início do cadastro.")

        t = self.task
        t(project, "Definir o escopo do MVP", ana, DONE, -38, -35, -33, due=-32, sprint=s1)
        t(project, "Criar o repositório e o ambiente", bruno, DONE, -38, -34, -31, due=-30, sprint=s1)
        t(project, "Escolher a stack do projeto", diego, DONE, -38, -34, -30, due=-30, sprint=s1)
        t(project, "Guia visual da secretaria", carla, DONE, -37, -33, -27, due=-28, sprint=s1)
        t(project, "Mapear os perfis de usuário", ana, DONE, -37, -30, -25, due=-24, sprint=s1)
        t(project, "Configurar o banco de desenvolvimento", diego, DONE, -36, -27, -23, due=-22, sprint=s1)

        requirements = t(project, "Levantar requisitos", ana, DONE, -24, -21, -17, due=-16, sprint=s2)
        t(project, "Desenhar a arquitetura", bruno, DONE, -24, -20, -19, due=-18, sprint=s2)
        t(project, "Protótipo de baixa fidelidade", carla, DONE, -23, -19, -15, due=-15, sprint=s2)
        t(project, "Política de backup", diego, DONE, -23, -18, -14, due=-15, sprint=s2)
        t(project, "Regras de negócio da matrícula", ana, DONE, -22, -16, -11, due=-12, sprint=s2)
        t(project, "Configurar a integração contínua", bruno, DONE, -22, -12, -5, due=-9, sprint=s2)
        t(project, "Documentar a API interna", diego, DOING, -22, -10, due=-8, sprint=s2)

        t(project, "Autenticação dos alunos", bruno, DONE, -9, -7, -6, due=-5, sprint=s3)
        t(project, "Tela de login", carla, DONE, -9, -6, -4, due=-3, sprint=s3)
        t(project, "Seed de cursos e turmas", diego, DONE, -9, -5, -2, due=-1, sprint=s3)
        database = t(project, "Modelar o banco de dados", bruno, DOING, -9, -6, due=1, sprint=s3)
        t(project, "Relatório de vagas por curso", diego, DOING, -8, -3, due=3, sprint=s3)
        screens = t(project, "Desenhar as telas", carla, TODO, -9, due=-1, sprint=s3)
        enrollment = t(project, "Implementar o cadastro de alunos", bruno, TODO, -8, due=5, sprint=s3)
        t(project, "Validar regras com a secretaria", ana, TODO, -8, due=6, sprint=s3)

        testing = t(project, "Testar o fluxo de matrícula", ana, TODO, -6, due=20)
        t(project, "Integração com o sistema financeiro", None, TODO, -5, due=30)
        t(project, "Notificações por e-mail", None, TODO, -3)

        Subtask.objects.create(task=database, title="Desenhar o diagrama ER", is_done=True)
        Subtask.objects.create(task=database, title="Revisar o modelo com o professor")
        Subtask.objects.create(task=screens, title="Wireframe da tela de matrícula")
        Subtask.objects.create(task=screens, title="Protótipo navegável")

        TaskDependency.objects.create(task=database, depends_on=requirements)
        TaskDependency.objects.create(task=screens, depends_on=requirements)
        TaskDependency.objects.create(task=enrollment, depends_on=database)
        TaskDependency.objects.create(task=enrollment, depends_on=screens)
        TaskDependency.objects.create(task=testing, depends_on=enrollment)

    def seed_acme(self, organization):
        ana = Member.objects.create(organization=organization, name="Ana Pereira", email="ana@exemplo.com", role="Gerente de projetos")
        eduardo = Member.objects.create(organization=organization, name="Eduardo Rocha", email="eduardo@exemplo.com", role="Desenvolvedor")

        project = Project.objects.create(
            organization=organization,
            name="Portal do Cliente",
            description="Área do cliente para acompanhar contratos e chamados.",
            start_date=self.day(-18),
            due_date=self.day(45),
        )
        s1 = self.sprint(project, "Sprint 1", -18, -5, "Login e listagem de contratos.")
        s2 = self.sprint(project, "Sprint 2", -4, 9, "Abertura e acompanhamento de chamados.")

        t = self.task
        t(project, "Login do cliente", eduardo, DONE, -19, -17, -14, due=-12, sprint=s1)
        t(project, "Listagem de contratos", eduardo, DONE, -19, -13, -8, due=-6, sprint=s1)
        t(project, "Aprovação do layout", ana, DONE, -19, -16, -10, due=-11, sprint=s1)
        t(project, "Abertura de chamado", eduardo, DONE, -5, -4, -2, due=0, sprint=s2)
        t(project, "Acompanhamento de chamados", eduardo, DOING, -5, -1, due=4, sprint=s2)
        t(project, "Notificações de status", None, TODO, -5, due=8, sprint=s2)
        t(project, "Pesquisa de satisfação", ana, TODO, -5, due=9, sprint=s2)
