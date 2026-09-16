from django.core.management.base import BaseCommand
from django.db import transaction

from members.models import Member
from projects.models import Project
from tasks.models import Subtask, Task, TaskDependency

PROJECT_NAME = "Sistema de Matrículas"


class Command(BaseCommand):
    help = "Cria um projeto de demonstração com membros, tarefas, subtarefas e dependências."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Apaga o projeto de demonstração e seus membros antes de criar tudo de novo.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        emails = ["ana@exemplo.com", "bruno@exemplo.com", "carla@exemplo.com"]

        if options["reset"]:
            Project.objects.filter(name=PROJECT_NAME).delete()
            Member.objects.filter(email__in=emails).delete()

        if Project.objects.filter(name=PROJECT_NAME).exists():
            self.stdout.write(self.style.WARNING(f'O projeto "{PROJECT_NAME}" já existe. Use --reset para recriá-lo.'))
            return

        ana = Member.objects.create(name="Ana Souza", email=emails[0], role="Analista de requisitos")
        bruno = Member.objects.create(name="Bruno Lima", email=emails[1], role="Desenvolvedor")
        carla = Member.objects.create(name="Carla Dias", email=emails[2], role="Designer")

        project = Project.objects.create(
            name=PROJECT_NAME,
            description="Portal de matrículas online para a secretaria acadêmica.",
            start_date="2026-03-02",
            due_date="2026-06-30",
        )

        requirements = Task.objects.create(
            project=project,
            assignee=ana,
            title="Levantar requisitos",
            description="Entrevistar a secretaria e documentar as regras de matrícula.",
            status=Task.Status.DONE,
            due_date="2026-03-13",
        )
        database = Task.objects.create(
            project=project,
            assignee=bruno,
            title="Modelar o banco de dados",
            description="Definir entidades, relacionamentos e restrições.",
            status=Task.Status.IN_PROGRESS,
            due_date="2026-03-27",
        )
        screens = Task.objects.create(
            project=project,
            assignee=carla,
            title="Desenhar as telas",
            description="Protótipo das telas de matrícula e consulta.",
            due_date="2026-04-03",
        )
        enrollment = Task.objects.create(
            project=project,
            assignee=bruno,
            title="Implementar o cadastro de alunos",
            description="Telas e regras de cadastro ligadas ao banco.",
            due_date="2026-05-15",
        )
        testing = Task.objects.create(
            project=project,
            assignee=ana,
            title="Testar o fluxo de matrícula",
            description="Roteiro de testes de ponta a ponta com a secretaria.",
            due_date="2026-06-12",
        )

        Subtask.objects.create(task=database, title="Desenhar o diagrama ER", is_done=True)
        Subtask.objects.create(task=database, title="Revisar o modelo com o professor")
        Subtask.objects.create(task=screens, title="Wireframe da tela de matrícula")
        Subtask.objects.create(task=screens, title="Protótipo navegável")

        TaskDependency.objects.create(task=database, depends_on=requirements)
        TaskDependency.objects.create(task=screens, depends_on=requirements)
        TaskDependency.objects.create(task=enrollment, depends_on=database)
        TaskDependency.objects.create(task=enrollment, depends_on=screens)
        TaskDependency.objects.create(task=testing, depends_on=enrollment)

        self.stdout.write(self.style.SUCCESS(f'Projeto "{PROJECT_NAME}" criado com 3 membros, 5 tarefas, 4 subtarefas e 5 dependências.'))
        self.stdout.write('Tarefas bloqueadas neste cenário: "Implementar o cadastro de alunos" e "Testar o fluxo de matrícula".')
