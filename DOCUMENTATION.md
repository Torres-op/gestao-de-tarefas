# Grello — Documentação técnica

Documentação de arquitetura e implementação do **Grello**, sistema de gestão de tarefas
desenvolvido na disciplina de Laboratório de Programação Full Stack. A P1 entregou o MVP (CRUD,
dependências entre tarefas e a regra de bloqueio da conclusão); a P2 o transforma num mini-SaaS
com várias organizações na mesma base, perfis de acesso, sprints, API REST e dashboard.

Este arquivo concentra toda a explicação do projeto. O código-fonte não contém comentários
por decisão de projeto: o que precisa ser explicado está aqui, onde pode ser lido de forma
contínua, e não espalhado em trechos soltos dentro dos módulos. (Os arquivos de infraestrutura —
`Dockerfile`, `docker-compose.yml`, `compose.prod.yml` e os modelos `.env*.example` — têm
comentários curtos de uso, porque são lidos por quem opera o sistema, não por quem o programa.)

---

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Stack e decisões de arquitetura](#2-stack-e-decisões-de-arquitetura)
3. [Estrutura de pastas](#3-estrutura-de-pastas)
4. [Modelagem de dados](#4-modelagem-de-dados)
5. [A regra central: bloqueio da conclusão](#5-a-regra-central-bloqueio-da-conclusão)
6. [Multi-organização](#6-multi-organização)
7. [Autenticação e perfis de acesso](#7-autenticação-e-perfis-de-acesso)
8. [Sprints](#8-sprints)
9. [Telas, URLs e templates](#9-telas-urls-e-templates)
10. [API REST](#10-api-rest)
11. [Dashboard e relatórios](#11-dashboard-e-relatórios)
12. [Segurança](#12-segurança)
13. [Desempenho](#13-desempenho)
14. [Testes](#14-testes)
15. [Como rodar](#15-como-rodar)
16. [Roteiro de demonstração e teste manual](#16-roteiro-de-demonstração-e-teste-manual)
17. [Decisões de projeto e limitações conhecidas](#17-decisões-de-projeto-e-limitações-conhecidas)

---

## 1. Visão geral

### De P1 para P2

| Etapa  | O que entregou                                                                                                                                                                 |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **P1** | CRUD de projetos, membros, tarefas e subtarefas; dependências entre tarefas; bloqueio da conclusão com a explicação do motivo; detecção de ciclos; filtro de tarefas por projeto e status; validação do prazo da tarefa contra a criação do projeto. |
| **P2** | Os quatro pilares abaixo, mais sprints, paginação, testes automatizados (348), configuração segura para produção, Docker para desenvolvimento e produção.                         |

Os quatro pilares da P2:

| Pilar                 | Em uma frase                                                                                                     | Seção  |
| --------------------- | ---------------------------------------------------------------------------------------------------------------- | ------ |
| **Multi-organização** | Várias empresas usam a mesma base e cada uma enxerga apenas os próprios dados.                                   | [6](#6-multi-organização)  |
| **Perfis de acesso**  | Login obrigatório; cada usuário pertence a uma organização como **administrador** ou **operador**.              | [7](#7-autenticação-e-perfis-de-acesso)  |
| **API REST**          | Os mesmos recursos e as mesmas regras expostos em JSON com Django REST Framework.                               | [10](#10-api-rest) |
| **Dashboard**         | Métricas de fluxo (throughput, lead time, cycle time, entrega no prazo), burndown/burnup de sprint e CSV.        | [11](#11-dashboard-e-relatórios) |

E um quinto elemento que sustenta o dashboard: **sprints** ([seção 8](#8-sprints)), que agrupam
as tarefas de um projeto em janelas de tempo.

### As entidades

| Entidade                           | Papel                                                                                     |
| ---------------------------------- | ----------------------------------------------------------------------------------------- |
| **Organização** (`Organization`)   | O "cliente" do SaaS. Dona dos projetos e dos membros.                                     |
| **Perfil** (`Profile`)             | Liga um usuário do Django a uma organização e a um papel (administrador ou operador).     |
| **Projeto** (`Project`)            | Agrupa as tarefas e as sprints de uma frente de trabalho.                                 |
| **Sprint** (`Sprint`)              | Janela de tempo dentro de um projeto (no máximo 60 dias).                                 |
| **Membro** (`Member`)              | Pessoa da equipe que pode ser responsável por tarefas.                                    |
| **Tarefa** (`Task`)                | Unidade de trabalho: pertence a um projeto, pode estar numa sprint e ter um responsável.  |
| **Subtarefa** (`Subtask`)          | Item de checklist dentro de uma tarefa.                                                   |
| **Dependência** (`TaskDependency`) | Relação de pré-requisito entre duas tarefas do mesmo projeto.                             |

**Critério de aceite da P1 (continua valendo):** uma tarefa não pode ser marcada como concluída
enquanto qualquer tarefa da qual ela depende — ou qualquer subtarefa dela — não estiver
concluída. O sistema bloqueia a ação e informa exatamente quais pendências a impedem. Na P2 essa
regra passou a valer também pela API, sem nenhuma linha duplicada ([seção 10](#10-api-rest)).

`Member` continua sendo um model de domínio próprio e **não** o `User` do Django: representar a
pessoa da equipe (que pode receber tarefas sem nunca fazer login) é uma responsabilidade
diferente de representar quem acessa o sistema. Quem acessa é `User` + `Profile`.

### Marcos no histórico do Git

| Commit    | Marco                                                                          |
| --------- | ------------------------------------------------------------------------------ |
| `b0c934e` | P1: dependências entre tarefas e bloqueio de conclusão                         |
| `5be4c68` | P1: subtarefas em aberto impedem a conclusão                                   |
| `dc6bde0` | P1: validação do prazo da tarefa contra a criação do projeto (`TaskForm.clean`)|
| `aa640cc` | Início da P2: lista de melhorias da P1 (`MELHORIAS_P1.md`)                     |
| `709f907` | Ambiente de desenvolvimento com Docker Compose                                 |
| `fea4b34` | Organizações, perfis de acesso e sprints com isolamento de dados               |
| `c304da7` | API REST com DRF                                                               |
| `dd6e150` | Dashboard, burndown/burnup e exportação CSV                                    |
| `1d04c11` | Testes das regras da P1, do isolamento e dos perfis                            |
| `be8ac9f` | Desempenho: consultas repetidas eliminadas e índices em `Task` (Aula 17)       |
| `2b58458` | Número de consultas travado por testes                                         |
| `d24f9d9` | Segurança: configurações seguras, limite de login e log de segurança (Aula 18) |
| `a7ce7c4` | Segurança: limite de duração da sprint e bloqueio de mudança de projeto        |

---

## 2. Stack e decisões de arquitetura

| Item           | Escolha                                                                                  |
| -------------- | ---------------------------------------------------------------------------------------- |
| Linguagem      | Python 3.13                                                                              |
| Framework      | Django 6.0.7, padrão MVT                                                                 |
| API            | Django REST Framework 3.18.3                                                             |
| Banco          | PostgreSQL 18, acessado exclusivamente pelo ORM (nenhum SQL cru)                         |
| Driver         | `psycopg` 3.3.5 (`psycopg[binary]`)                                                      |
| Front-end      | HTML dos templates do Django + uma folha de estilo própria + Chart.js 4.6.2 servido localmente |
| Produção       | gunicorn 27.0.1 + WhiteNoise 6.12.0 (arquivos estáticos comprimidos e com hash)          |
| Configuração   | Variáveis de ambiente, lidas de um `.env` via `python-dotenv` 1.2.3                       |
| Contêineres    | Docker com dois alvos (`dev` e `prod`) e dois arquivos Compose                           |
| Testes         | `django.test` / `rest_framework.test` + `coverage` 7.17.5 (`requirements-dev.txt`)       |

### Separação de responsabilidades

O princípio que organiza o código continua o mesmo da P1: **cada regra mora em um lugar só**.

- **Model** — guarda os dados e as regras que precisam valer sempre, venha a operação de uma
  view, do admin do Django, do shell **ou da API**. É onde vivem a regra de bloqueio da conclusão
  e as regras novas da P2 (sprint do mesmo projeto, responsável da mesma organização, limite de
  duração da sprint, mudança de projeto).
- **Form / Serializer** — traduzem a entrada do usuário em dados válidos e restringem as opções
  oferecidas (só registros da organização). Não reimplementam regras do model: o `ModelForm`
  chama `full_clean()` sozinho, e os serializers chamam o mesmo `clean()` por meio do
  `ModelCleanMixin` ([seção 10](#10-api-rest)).
- **View / ViewSet** — orquestram o ciclo HTTP: buscam os dados **sempre filtrados pela
  organização**, chamam o model e traduzem sucesso ou falha em mensagem (HTML) ou status (JSON).
- **Template** — só exibe. Percentuais, contagens, estado de bloqueio e métricas chegam prontos.
- **Camada de métricas** (`dashboard/metrics.py`) — funções puras sobre querysets, usadas igualmente
  pela tela, pela API e pelo CSV.

### Divisão em apps

| App         | Pergunta do domínio           | Conteúdo                                                                                      |
| ----------- | ----------------------------- | --------------------------------------------------------------------------------------------- |
| `core`      | **quem acessa** e **de qual organização** | `Organization`, `Profile`, `OrganizationOwned`, middleware, mixins de isolamento e permissão, limite de login, log de segurança, health check, paginação |
| `members`   | **quem** faz                  | `Member`                                                                                      |
| `projects`  | **onde** e **quando**         | `Project`, `Sprint`                                                                           |
| `tasks`     | **o que** precisa ser feito   | `Task`, `Subtask`, `TaskDependency`, consultas reutilizáveis (`queries.py`), `seed_demo`      |
| `dashboard` | **como está indo**            | métricas, burndown/burnup, tela, API do dashboard e exportação CSV                            |
| `api`       | acesso programático           | serializers, viewsets, permissões e paginação da API REST                                     |

`Subtask` e `TaskDependency` continuam dentro de `tasks` pelo mesmo motivo da P1: não são
domínios independentes (uma subtarefa não existe sem a tarefa; uma dependência é uma aresta entre
duas tarefas). `Sprint` mora em `projects` porque pertence a um projeto e não tem sentido fora
dele — e porque `tasks` já depende de `projects`, então a FK `Task.sprint` não cria importação
circular.

A API ficou num app próprio (`api`) em vez de espalhada pelos apps de domínio: os serializers
compartilham peças (`OrganizationRelatedField`, `ModelCleanMixin`) e as permissões da API são
diferentes das permissões das telas. A API do dashboard é a exceção: mora em `dashboard`
(`api_views.py`), ao lado das métricas que ela devolve.

---

## 3. Estrutura de pastas

```
Gestao-de-tarefas/
├── manage.py
├── requirements.txt              # dependências de execução
├── requirements-dev.txt          # + coverage
├── .coveragerc                   # o que entra no relatório de cobertura
├── .env.example                  # modelo de variáveis (desenvolvimento / local)
├── .env.prod.example             # modelo de variáveis para o compose.prod.yml
├── Dockerfile                    # alvos dev (runserver) e prod (gunicorn + WhiteNoise)
├── docker-compose.yml            # ambiente de desenvolvimento
├── compose.prod.yml              # ambiente de produção
├── docker/entrypoint.sh          # migrate + createcachetable (+ seed opcional) ao subir
├── README.md  DOCUMENTATION.md  MELHORIAS_P1.md  RELATORIO_FEATURES.MD
│
├── config/
│   ├── settings.py               # configuração; seguro por padrão (DEBUG desligado)
│   ├── urls.py                   # roteamento raiz: admin, health, login, apps e API
│   └── wsgi.py  asgi.py
│
├── core/                         # organizações, perfis, isolamento e segurança
│   ├── models.py                 # Organization, OrganizationOwned (abstrato), Profile
│   ├── middleware.py             # OrganizationMiddleware: request.profile / request.organization
│   ├── tenancy.py                # get_profile, current_organization, is_org_admin
│   ├── permissions.py            # admin_required, AdminRequiredMixin, OrganizationScopedMixin, OrganizationFormMixin
│   ├── auth.py                   # RateLimitedModelBackend (limite de tentativas de login)
│   ├── forms.py                  # LoginForm (mostra a mensagem de bloqueio)
│   ├── signals.py                # log de segurança (grello.security)
│   ├── context_processors.py     # current_profile, current_organization, is_org_admin
│   ├── pagination.py             # LenientPaginationMixin
│   ├── views.py                  # health check (/health/)
│   ├── admin.py                  # Organization, Profile e Perfil embutido no User
│   ├── testing.py                # fábricas e cenário de contagem de consultas para os testes
│   ├── templates/core/no_profile.html
│   └── tests.py  test_queries.py  test_security.py  test_settings.py
│       test_pagination.py  test_error_pages.py  test_health.py
│
├── members/                      # Member (e-mail único por organização)
├── projects/                     # Project e Sprint
│   └── templates/projects/       # project_*, sprint_* e partials/_sprint_state_badge.html
├── tasks/                        # Task, Subtask, TaskDependency
│   ├── queries.py                # Prefetch reutilizáveis (evitam N+1)
│   ├── management/commands/seed_demo.py
│   └── templates/tasks/          # task_*, subtask_*, dependency_form e partials/
├── dashboard/                    # métricas, tela, API do dashboard e CSV
│   ├── metrics.py                # fórmulas de todas as métricas e do burndown
│   ├── services.py               # filtros + montagem do payload (tela e API)
│   ├── forms.py                  # PeriodForm / DashboardFilterForm
│   ├── exports.py                # CSV
│   ├── views.py  api_views.py  urls.py  api_urls.py
│   └── templates/dashboard/      # index.html e partials/_filters.html, _kpi.html
├── api/                          # API REST (DRF)
│   ├── serializers.py            # OrganizationRelatedField, ModelCleanMixin, serializers
│   ├── views.py                  # viewsets + ações complete / reopen / toggle
│   ├── permissions.py  pagination.py  urls.py
│   └── tests.py  test_queries.py
│
│   (members, projects e tasks têm cada um models.py, forms.py, views.py, urls.py,
│    admin.py, migrations/, templates/ e os testes tests.py, test_queries.py
│    e, em projects e tasks, test_security.py)
│
├── templates/                    # templates globais
│   ├── base.html  home.html
│   ├── 403.html  404.html  500.html
│   ├── registration/login.html
│   └── partials/_messages.html  _form.html  _confirm_delete.html  _pagination.html
│
└── static/
    ├── css/style.css
    └── js/chart.umd.js  dashboard.js # Chart.js 4.6.2 local + script dos gráficos
```

---

## 4. Modelagem de dados

```
   Organization ◄──────────── Profile ─────────── 1:1 ──── User (django.contrib.auth)
     │ 1    │ 1                (role: admin / operator)
     │      │
     │ N    │ N   (organization, PROTECT)
   Member  Project
     │ 1    │ 1  └──────────► N  Sprint            (project, CASCADE)
     │      │                     │ 1
     │ N    │ N (project, CASCADE)│ N (sprint, SET_NULL — sem sprint = backlog)
     └──►  Task  ◄────────────────┘
 (assignee, │ 1
  SET_NULL) ├──────────► N  Subtask       (CASCADE)
            │
            └──────────► N  TaskDependency
                               │
            task ──────────────┤   duas FKs para Task: relação assimétrica
            depends_on ────────┘
```

Só `Project` e `Member` têm a FK para `Organization`. Sprints, tarefas, subtarefas e
dependências **herdam** a organização pelo projeto — a [seção 6](#6-multi-organização) explica por quê.

### `core.Organization`

| Campo        | Tipo                                   | Observações                 |
| ------------ | -------------------------------------- | --------------------------- |
| `name`       | `CharField(max_length=120, unique=True)` | nome único no sistema      |
| `created_at` | `DateTimeField(auto_now_add=True)`     |                             |

### `core.OrganizationOwned` (abstrato)

Model abstrato com um único campo, `organization = ForeignKey(Organization, on_delete=PROTECT)`.
`Project` e `Member` herdam dele. O `PROTECT` impede apagar uma organização que ainda tem dados:
excluir um cliente inteiro precisa ser uma decisão explícita, não um efeito colateral de um clique
no Admin.

### `core.Profile`

| Campo          | Tipo                                                      | Observações                                    |
| -------------- | --------------------------------------------------------- | ---------------------------------------------- |
| `user`         | `OneToOneField(User, CASCADE, related_name="profile")`    | um perfil por usuário                          |
| `organization` | `ForeignKey(Organization, PROTECT, related_name="profiles")` |                                             |
| `role`         | `CharField(choices=Role.choices, default=OPERATOR)`       | `TextChoices`: `admin` / `operator`            |

Propriedade `is_admin`. O perfil é editado no Admin, embutido na tela do usuário (`ProfileInline`).

### `members.Member`

| Campo          | Tipo                                   | Observações                                  |
| -------------- | -------------------------------------- | -------------------------------------------- |
| `organization` | herdado de `OrganizationOwned`         |                                              |
| `name`         | `CharField(max_length=120)`            |                                              |
| `email`        | `EmailField()`                         | único **por organização** (ver abaixo)       |
| `role`         | `CharField(max_length=80, blank=True)` | cargo na equipe                              |
| `is_active`    | `BooleanField(default=True)`           | inativo não aparece no select de responsável |
| `created_at`   | `DateTimeField(auto_now_add=True)`     |                                              |

Restrição: `UniqueConstraint(organization, email)` (`unique_member_email_per_organization`).
Na P1 o e-mail era `unique=True` no banco inteiro — com várias organizações, a segunda empresa não
conseguiria cadastrar uma pessoa que já existisse na primeira.

### `projects.Project`

| Campo          | Tipo                               | Observações |
| -------------- | ---------------------------------- | ----------- |
| `organization` | herdado de `OrganizationOwned`     |             |
| `name`         | `CharField(max_length=120)`        |             |
| `description`  | `TextField(blank=True)`            |             |
| `start_date`   | `DateField(null=True, blank=True)` |             |
| `due_date`     | `DateField(null=True, blank=True)` |             |
| `created_at`   | `DateTimeField(auto_now_add=True)` |             |

Métodos: `task_count()`, `completed_task_count()` e `progress_percent()`. `clean()` recusa um prazo
final anterior à data de início.

### `projects.Sprint`

| Campo        | Tipo                                                     | Observações                    |
| ------------ | -------------------------------------------------------- | ------------------------------ |
| `project`    | `ForeignKey(Project, CASCADE, related_name="sprints")`   |                                |
| `name`       | `CharField(max_length=80)`                               | único dentro do projeto        |
| `goal`       | `TextField(blank=True)`                                  | objetivo da sprint             |
| `start_date` | `DateField()`                                            | obrigatório                    |
| `end_date`   | `DateField()`                                            | obrigatório                    |
| `created_at` | `DateTimeField(auto_now_add=True)`                       |                                |

Restrições no banco:

- `UniqueConstraint(project, name)` — `unique_sprint_name_per_project`;
- `CheckConstraint(end_date >= start_date)` — `sprint_end_after_start`;
- `CheckConstraint(end_date <= start_date + 59 dias)` — `sprint_max_duration` (no máximo 60 dias
  contando o primeiro e o último).

O **estado** (planejada / em andamento / encerrada) não é um campo: é calculado pelas datas em
`state()`. Detalhes na [seção 8](#8-sprints).

### `tasks.Task`

| Campo                       | Tipo                                                                        | Relacionamento / observação                                   |
| --------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `project`                   | `ForeignKey(Project, CASCADE, related_name="tasks")`                        | excluir o projeto exclui suas tarefas                         |
| `assignee`                  | `ForeignKey(Member, SET_NULL, null=True, blank=True, related_name="tasks")` | excluir o membro deixa a tarefa sem responsável               |
| `sprint`                    | `ForeignKey(Sprint, SET_NULL, null=True, blank=True, related_name="tasks")` | **P2.** Sem sprint = backlog; excluir a sprint devolve as tarefas ao backlog |
| `title`                     | `CharField(max_length=150)`                                                 |                                                               |
| `description`               | `TextField(blank=True)`                                                     |                                                               |
| `status`                    | `CharField(choices=Status.choices, default=PENDING)`                        | `pending` / `in_progress` / `done`                            |
| `due_date`                  | `DateField(null=True, blank=True)`                                          |                                                               |
| `started_at`                | `DateTimeField(null=True, blank=True)`                                      | **P2.** Preenchido pelo `save()`; base do cycle time          |
| `completed_at`              | `DateTimeField(null=True, blank=True)`                                      | preenchido pelo `save()`                                      |
| `created_at` / `updated_at` | `DateTimeField`                                                             |                                                               |

Ordenação padrão por `due_date`, depois `title`. Índices (P2, Aula 17):

| Índice                      | Campos                    | Para quê                                                         |
| --------------------------- | ------------------------- | ---------------------------------------------------------------- |
| `task_project_status_idx`   | `project`, `status`       | listagens e métricas filtradas por projeto e status              |
| `task_status_completed_idx` | `status`, `completed_at`  | throughput, lead/cycle time e burndown (concluídas num intervalo)|
| `task_created_at_idx`       | `created_at`              | série "criadas por semana/mês" e relatório CSV por período       |

### `tasks.Subtask`

| Campo        | Tipo                                                 | Relacionamento                        |
| ------------ | ---------------------------------------------------- | ------------------------------------- |
| `task`       | `ForeignKey(Task, CASCADE, related_name="subtasks")` | excluir a tarefa exclui as subtarefas |
| `title`      | `CharField(max_length=150)`                          |                                       |
| `is_done`    | `BooleanField(default=False)`                        |                                       |
| `created_at` | `DateTimeField(auto_now_add=True)`                   |                                       |

### `tasks.TaskDependency`

| Campo        | Tipo                                                     | Significado                                     |
| ------------ | -------------------------------------------------------- | ----------------------------------------------- |
| `task`       | `ForeignKey(Task, CASCADE, related_name="dependencies")` | a tarefa **dependente**, a que fica bloqueada   |
| `depends_on` | `ForeignKey(Task, CASCADE, related_name="dependents")`   | o **pré-requisito**, que precisa terminar antes |
| `created_at` | `DateTimeField(auto_now_add=True)`                       |                                                 |

Restrições no banco:

- `UniqueConstraint(task, depends_on)` — a mesma aresta não pode ser cadastrada duas vezes.
- `CheckConstraint(~Q(task=F("depends_on")))` — o PostgreSQL recusa uma tarefa que dependa
  de si mesma.

Os dois `related_name` são propositalmente opostos e legíveis a partir da tarefa:
`task.dependencies` são as arestas que **bloqueiam** esta tarefa; `task.dependents` são as arestas
das tarefas que **esta tarefa bloqueia**.

### Por que um model intermediário e não um `ManyToManyField("self")`

1. **A relação tem regras próprias.** Mesmo projeto, sem auto-referência, sem duplicata, sem
   ciclo, e sem contradizer uma conclusão já registrada — todas em `TaskDependency.clean()`. Um
   `ManyToManyField` não tem um `clean()` onde colocá-las.
2. **A dependência é uma entidade de primeira classe** na interface (URL própria para criar e
   remover, `ModelForm` próprio) e na API (`/api/dependencies/`).
3. **O grafo fica explícito.** As duas pontas e os dois sentidos de leitura têm nome.

---

## 5. A regra central: bloqueio da conclusão

Uma tarefa só pode ser concluída quando **duas** condições valem ao mesmo tempo:

> 1. Todas as tarefas das quais ela depende já estão concluídas.
> 2. Todas as suas subtarefas já estão concluídas.

### Os invariantes, enunciados por completo

> **A.** Para toda dependência (`task` → `depends_on`): se `task` está concluída, então
> `depends_on` também está concluída.
>
> **B.** Para toda subtarefa: se a tarefa dela está concluída, então a subtarefa também está.

Enunciados assim, fica claro que **seis** operações diferentes poderiam quebrá-los:

| #   | Operação                                                               | Como quebraria                                                 | Onde é barrada                         |
| --- | ---------------------------------------------------------------------- | -------------------------------------------------------------- | -------------------------------------- |
| A1  | **Concluir** uma tarefa com pré-requisito pendente                     | é o caso óbvio                                                 | `Task.complete()` e `Task.clean()`     |
| A2  | **Reabrir** uma tarefa que é pré-requisito de outra já concluída       | inverte a ordem das operações e chega ao mesmo estado inválido | `Task.reopen()` e `Task.clean()`       |
| A3  | **Criar uma dependência** de uma tarefa já concluída para uma pendente | cria a aresta depois, quando o estado já está "errado"         | `TaskDependency.clean()`               |
| B1  | **Concluir** uma tarefa com subtarefa em aberto                        | é o caso óbvio                                                 | `Task.complete()` e `Task.clean()`     |
| B2  | **Reabrir uma subtarefa** de uma tarefa já concluída                   | mesma inversão de ordem do caso A2                             | `Subtask.toggle()` e `Subtask.clean()` |
| B3  | **Adicionar uma subtarefa em aberto** a uma tarefa já concluída        | cria o item depois, quando o estado já está "errado"           | `Subtask.clean()`                      |

Os seis estão fechados — na interface, no Admin e na API — e cada um tem testes com o prefixo
correspondente (`test_a1_…`, `test_b2_…`) em `tasks/tests.py`, além dos equivalentes HTTP e da API.

Uma subtarefa já concluída **pode** ser adicionada a uma tarefa concluída (não viola nada), e
excluir uma subtarefa em aberto de uma tarefa concluída também é permitido, porque corrige o
estado em vez de quebrá-lo.

### Onde a regra é validada, e por quê

A regra é definida **uma única vez, no model**, e as outras camadas apenas a expõem.

#### Camada 1 — Model `Task`: a fonte da verdade

```python
def pending_dependencies(self):
    return [
        dependency.depends_on
        for dependency in self.dependencies.all()
        if dependency.depends_on.status != self.Status.DONE
    ]

def is_blocked(self):
    return bool(self.pending_dependencies()) or bool(self.pending_subtasks())

def complete(self):
    reason = self.blocking_reason()
    if reason:
        raise ValidationError(reason)
    self.status = self.Status.DONE
    self.save()
```

`blocking_reason()` reúne os dois motivos numa única frase, no singular ou no plural — por exemplo:
_"Ela depende das tarefas "Desenhar as telas", "Modelar o banco de dados", que ainda não foram
concluídas."_ `reopening_reason()` faz o mesmo no sentido inverso, percorrendo
`completed_dependents()`.

**Por que no model:** a proibição é uma propriedade dos dados, não uma regra de tela. Ela precisa
valer venha a operação de uma view, do Admin, do shell ou da API. Na P2 isso se pagou: a API
ganhou as ações `complete` e `reopen` chamando os mesmos métodos, e o `PATCH` de `status` passa
pelo mesmo `clean()` — nenhuma regra foi reescrita.

`pending_dependencies()` percorre `self.dependencies.all()` **em Python**, e não com um `.filter()`:
quando a view usa `prefetch_related`, a lista já está em memória e o cálculo de bloqueio de uma
listagem inteira não dispara nenhuma consulta adicional ([seção 13](#13-desempenho)).

#### Camada 2 — `Task.clean()`: fecha a porta do formulário e da API

```python
def clean(self):
    self.validate_relations()
    if not self.pk:
        return
    if self.status == self.Status.DONE:
        reason = self.blocking_reason()
    else:
        reason = self.reopening_reason()
    if reason:
        raise ValidationError({"status": reason})
```

O campo `status` do formulário de edição (e do `PATCH` da API) é um segundo caminho para concluir
uma tarefa. Como `TaskForm` é um `ModelForm`, o Django chama `full_clean()` sozinho e o erro aparece
**embaixo do campo Status**. Na API, o mesmo erro volta como `{"status": ["…"]}` com HTTP 400.
`validate_relations()` contém as regras novas da P2, descritas logo abaixo.

`Subtask.clean()` faz o mesmo do outro lado da relação (B2/B3), e `Subtask.toggle()` aplica a
checagem para o botão de marcar/desmarcar, que não passa por formulário.

#### Camada 3 — Views e ações da API: traduzem para HTTP

```python
@require_POST
def task_complete(request, pk):
    task = get_object_or_404(
        organization_tasks(request).prefetch_related("dependencies__depends_on", "subtasks"), pk=pk
    )
    try:
        task.complete()
    except ValidationError as error:
        messages.error(request, f'Não é possível concluir "{task.title}". {" ".join(error.messages)}')
    else:
        messages.success(request, f'Tarefa "{task.title}" concluída.')
    return redirect(task)
```

A view não sabe o que é uma dependência: pede ao model que conclua e traduz o resultado em
mensagem. A diferença em relação à P1 é `organization_tasks(request)`: uma tarefa de outra
organização nem é encontrada (404). A ação `POST /api/tasks/{id}/complete/` faz o mesmo e devolve
`400 {"detail": "<motivo>"}` quando a tarefa está bloqueada.

#### Camada 4 — Banco: a última linha de defesa

`UniqueConstraint` e `CheckConstraint` garantem a integridade do grafo e das sprints mesmo diante
de uma escrita feita fora da aplicação.

### Validações de `TaskDependency`

`TaskDependency.clean()` recusa, nesta ordem: (1) auto-dependência; (2) tarefas de projetos
diferentes; (3) duplicata; (4) dependência de uma tarefa concluída para uma pendente (caso A3);
(5) ciclo.

### Detecção de ciclo

Sem essa verificação, um encadeamento A → B → C → A deixaria as três tarefas travadas para sempre.

```python
def creates_cycle(self):
    visited = set()
    pending = [self.task_id]
    while pending:
        current = pending.pop()
        if current == self.depends_on_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(
            TaskDependency.objects.filter(depends_on_id=current).values_list("task_id", flat=True)
        )
    return False
```

A busca parte da tarefa dependente e sobe pelo grafo na direção "quem depende de quem". Se o
pré-requisito que se quer adicionar já depende de `task`, direta ou indiretamente, a nova aresta
fecharia o laço. O conjunto `visited` garante o término mesmo com caminhos repetidos (um "losango"
não é ciclo — há teste para isso).

### Defesa em profundidade no formulário

`TaskDependencyForm` restringe o `queryset` de `depends_on` às tarefas do mesmo projeto, excluindo
a própria tarefa e as dependências já cadastradas. Um POST forjado com um valor fora do `queryset`
é recusado antes, com _"Faça uma escolha válida"_. As validações (1) a (3) do model continuam
valendo para o Admin, o shell e a API.

### Sinalização visual do bloqueio

| Onde                | O que mostra                                                                                                                         |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Listagem de tarefas | linha destacada, etiqueta "Bloqueada", "Bloqueada por: X, Y" e a contagem "1 de 2 subtarefas concluídas" em destaque                 |
| Detalhe do projeto, da sprint e do membro | a mesma tabela (`_task_table.html`), com os mesmos indicadores                                                 |
| Detalhe da tarefa   | aviso separando "Dependências pendentes" de "Subtarefas em aberto"; cada dependência marcada como "Atendida" ou "Impede a conclusão" |
| API                 | campos `is_blocked` e `blocking_reason` em cada tarefa                                                                               |
| Dashboard           | KPI "Bloqueadas"                                                                                                                     |

O botão "Concluir" continua **clicável** quando a tarefa está bloqueada, por decisão de projeto: o
enunciado pede que o sistema _informe o motivo_, o que só acontece se a tentativa chegar ao servidor.

### `completed_at` e `started_at` são gerenciados pelo model

```python
def save(self, *args, **kwargs):
    now = timezone.now()
    if self.status == self.Status.DONE and self.completed_at is None:
        self.completed_at = now
    elif self.status != self.Status.DONE:
        self.completed_at = None
    if self.status == self.Status.PENDING:
        self.started_at = None
    elif self.started_at is None:
        self.started_at = self.completed_at or now
    super().save(*args, **kwargs)
```

Garantias, todas vindas de um único ponto: `completed_at` está preenchido **se e somente se** a
tarefa está concluída; `started_at` está vazio **se e somente se** a tarefa está pendente. Uma
tarefa criada direto como concluída recebe `started_at = completed_at` (cycle time zero, em vez de
indefinido). Reabrir limpa `completed_at` mas preserva `started_at`. Na API os dois campos são
somente leitura.

### Regras novas da P2 no model

A P2 acrescentou relações (sprint, organização) que abrem novos caminhos para dados
inconsistentes. Cada uma foi fechada no model, pelo mesmo motivo da regra central: precisa valer
também na API e no Admin.

| Regra                                                         | Onde                                                      | Mensagem / efeito                                                                            |
| ------------------------------------------------------------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| A sprint da tarefa pertence ao mesmo projeto da tarefa        | `Task.validate_relations()`                               | "A sprint precisa pertencer ao mesmo projeto da tarefa."                                     |
| O responsável pertence à mesma organização do projeto         | `Task.validate_relations()`                               | "O responsável precisa pertencer à mesma organização do projeto."                            |
| Tarefa com dependências (em qualquer sentido) não muda de projeto | `Task.validate_relations()` + `Task.changed_project()` | "Uma tarefa com dependências não pode mudar de projeto. Remova as dependências antes."       |
| Sprint com tarefas não muda de projeto                        | `Sprint.clean()` + `Sprint.changed_project()`             | "Uma sprint com tarefas não pode mudar de projeto. Mova as tarefas antes."                   |
| Sprint de no máximo 60 dias                                   | `Sprint.clean()` **e** `CheckConstraint sprint_max_duration` | "Uma sprint pode durar no máximo 60 dias."                                                 |
| Fim da sprint não anterior ao início                          | `Sprint.clean()` **e** `CheckConstraint sprint_end_after_start` | "O fim da sprint não pode ser anterior ao início."                                     |
| Nome da sprint único no projeto                               | `Sprint.clean()` **e** `UniqueConstraint`                 | "Já existe uma sprint com este nome neste projeto."                                          |
| Prazo da tarefa não anterior à criação do projeto (P1)        | **`TaskForm.clean()`** — somente no formulário HTML       | "O prazo não pode ser anterior a criação do projeto" (erro geral do formulário)              |

Por que a mudança de projeto é proibida: dependências só podem existir entre tarefas do mesmo
projeto, e as tarefas de uma sprint precisam ser do projeto da sprint. Mover uma tarefa (ou uma
sprint) de projeto quebraria essas invariantes em silêncio — e, com várias organizações, um
projeto de destino de outra organização arrastaria dados entre clientes. O formulário HTML da
sprint nem oferece o campo `project` (o projeto vem da URL), então a regra protege sobretudo a API
e o Admin. `changed_project()` compara com o `project_id` carregado do banco, guardado em
`from_db()`, para não gastar uma consulta extra a cada validação.

Por que o limite de 60 dias: foi um achado da revisão de segurança ([seção 12](#12-segurança)). O
burndown gera um ponto por dia da sprint; uma sprint de séculos travaria o servidor ao abrir o
dashboard. O `clean()` dá a mensagem amigável e o `CheckConstraint` garante o limite mesmo fora da
aplicação.

**A regra do prazo é diferente das outras.** Ela foi implementada na P1 como Feature 2 (ver
`RELATORIO_FEATURES.MD`), no `TaskForm.clean()`, e não no model. Consequência: vale para criar e
editar tarefas pelas telas, mas **não** vale na API nem no Admin. Ela está registrada como
limitação conhecida ([seção 17](#17-decisões-de-projeto-e-limitações-conhecidas)); o `seed_demo`
foi ajustado (`2035ebe`) para gerar apenas prazos que passam por ela.

---

## 6. Multi-organização

### A estratégia: coluna discriminadora

Há três formas clássicas de isolar clientes num SaaS:

| Estratégia                          | Como funciona                                     | Por que não (ou por que sim) aqui                                                                   |
| ----------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Banco por cliente                   | um banco PostgreSQL para cada organização         | isolamento máximo, mas exige roteamento de conexões, migrações N vezes e provisionamento por cliente |
| Schema por cliente                  | um schema do PostgreSQL por organização           | exige biblioteca externa (ex.: django-tenants), migrações por schema e roteamento por domínio      |
| **Coluna discriminadora** (escolhida) | todas as organizações nas mesmas tabelas, com uma FK `organization` | um banco, um conjunto de migrações, consultas comuns do ORM e relatórios globais simples          |

Para o porte do projeto (poucas organizações, mesmo esquema para todas, deploy único), a coluna
discriminadora é a opção mais simples e a que exige menos infraestrutura. O custo é conhecido:
**toda** consulta precisa filtrar pela organização, e esquecer um filtro vaza dados. A mitigação é
estrutural — o filtro fica em poucos lugares reutilizados (mixins, funções `organization_*`,
`OrganizationRelatedField`) — e verificada por testes de isolamento em cada app.

### FK só em `Project` e `Member`

Apenas os dois "pontos de entrada" do domínio têm a coluna `organization`. As demais entidades
herdam a organização pelo caminho até o projeto:

| Entidade         | Caminho até a organização              |
| ---------------- | -------------------------------------- |
| `Sprint`         | `sprint.project.organization`          |
| `Task`           | `task.project.organization`            |
| `Subtask`        | `subtask.task.project.organization`    |
| `TaskDependency` | `dependency.task.project.organization` |

Duplicar a FK em `Task` (e nas demais) abriria a possibilidade de uma tarefa dizer que pertence à
organização A enquanto seu projeto pertence à B — e cada duplicação exigiria mais uma validação
para manter as duas em acordo. Com uma única fonte, a inconsistência é impossível por construção.
O custo é um `JOIN` com `projects_project` nos filtros (`project__organization=…`), barato com a
chave estrangeira indexada. As únicas ligações que **cruzam** entidades sem passar pelo projeto
(responsável e sprint de uma tarefa, pontas de uma dependência) são justamente as validadas pelas
regras da [seção 5](#regras-novas-da-p2-no-model).

### Como o isolamento é aplicado

| Peça                                 | Onde                    | O que faz                                                                                                          |
| ------------------------------------ | ----------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `OrganizationMiddleware`             | `core/middleware.py`    | carrega o perfil (uma consulta) e define `request.profile` e `request.organization`; usuário logado sem perfil recebe a página 403 `core/no_profile.html` (exceto em `/admin/`, `/accounts/`, `/api/` e `/static/`) |
| `get_profile` / `current_organization` / `is_org_admin` | `core/tenancy.py` | ponto único para descobrir a organização e o papel; o perfil fica em cache no próprio objeto `user` |
| `OrganizationScopedMixin`            | `core/permissions.py`   | filtra o `get_queryset()` das views de classe pela organização — `get_object()` passa a dar 404 para registros de outra |
| `OrganizationFormMixin`              | `core/permissions.py`   | entrega a organização ao formulário (`organization=` no `__init__`)                                                |
| `organization_tasks`, `organization_subtasks`, `organization_sprints` | views de `tasks` e `projects` | querysets já filtrados para as views de função, usados com `get_object_or_404` |
| `OrganizationViewSet`                | `api/views.py`          | mesmo filtro para todos os viewsets, por `organization_field` (`organization`, `project__organization`, …)        |
| `OrganizationRelatedField`           | `api/serializers.py`    | campos de FK da API só aceitam IDs da organização do usuário                                                       |
| `metrics.organization_tasks`         | `dashboard/metrics.py`  | ponto de partida de todas as métricas                                                                             |
| `core.context_processors.organization` | templates             | expõe `current_organization`, `current_profile` e `is_org_admin` em todas as páginas                              |

### A organização nunca vem do formulário

Nenhum formulário e nenhum serializer tem o campo `organization`. Ela é atribuída no servidor:

- `ProjectForm` e `MemberForm` recebem `organization` no `__init__` e a atribuem à instância
  **somente se ela ainda não tiver uma** — editar nunca muda a organização de um registro.
- Na API, `perform_create()` salva com `organization=self.get_organization()`; um campo
  `organization` enviado no JSON é simplesmente ignorado (há teste injetando outra organização).
- Subtarefas recebem a tarefa pela URL; sprints recebem o projeto pela URL (já filtrado).

### Registros de outra organização: 404

Abrir, editar, excluir ou disparar uma ação (`complete`, `toggle`, remover dependência) sobre um
registro de outra organização responde **404**, como se ele não existisse — tanto nas telas quanto
na API. Responder 403 confirmaria que o ID existe. A página `templates/404.html` diz "não existe ou
não está disponível para a sua organização".

Exceção consciente: nas ações exclusivas de administrador, a checagem de papel vem antes da busca.
Um **operador** que tenta editar um projeto de outra organização recebe 403 (porque não poderia
editar projeto nenhum) — o que não revela nada sobre o registro.

### Selects filtrados

| Formulário             | Campo                          | Opções oferecidas                                                         |
| ---------------------- | ------------------------------ | ------------------------------------------------------------------------- |
| `TaskForm`             | `project`                      | projetos da organização                                                   |
| `TaskForm`             | `sprint`                       | sprints dos projetos da organização ("Sem sprint (backlog)" como vazio)   |
| `TaskForm`             | `assignee`                     | membros **ativos** da organização (+ o responsável atual, se inativo)     |
| `TaskDependencyForm`   | `depends_on`                   | tarefas do mesmo projeto, exceto a própria e as já cadastradas            |
| `DashboardFilterForm`  | `project`, `sprint`            | projetos e sprints da organização                                         |
| Filtros da listagem    | projeto, sprint, status        | projetos e sprints da organização                                         |

Um ID de outra organização enviado à força é recusado como "escolha inválida" no formulário e como
"Pk inválido … objeto não existe" na API — a mesma resposta de um ID inexistente.

### E-mail único por organização

`UniqueConstraint(organization, email)` no banco e checagem de duplicidade no
`MemberForm.clean_email()` e no `MemberSerializer.validate_email()`, porque a organização não faz
parte do formulário e a validação de unicidade automática do Django não a enxergaria. As checagens
de formulário e API são **sem diferenciar maiúsculas** (`email__iexact`); a do banco é exata. O
`seed_demo` cadastra `ana@exemplo.com` nas duas organizações para demonstrar.

### Migração dos dados da P1 em três etapas

Um banco da P1 já tinha projetos e membros sem organização. Adicionar uma FK obrigatória de uma vez
falharia. A migração foi feita em três passos, para `projects` e para `members`:

| Passo | Migração (`projects` / `members`)          | O que faz                                                                         |
| ----- | ------------------------------------------ | --------------------------------------------------------------------------------- |
| 1     | `0002_*_organization`                      | adiciona `organization` **nula**                                                  |
| 2     | `0003_default_organization`                | `RunPython`: cria "Organização padrão" (só se houver órfãos) e atribui a ela       |
| 3     | `0004_require_organization*`               | torna a FK **obrigatória** (em `projects`, cria também `Sprint`)                  |

`tasks/0003_task_sprint_started_at` adiciona `sprint` e `started_at` e preenche
`started_at = created_at` para as tarefas que já não estavam pendentes, mantendo a garantia da
[seção 5](#completed_at-e-started_at-são-gerenciados-pelo-model). O teste
`DataMigrationTests` migra um banco para o estado da P1, cria dados "legados" e confere o resultado.

---

## 7. Autenticação e perfis de acesso

### Login obrigatório

`django.contrib.auth.middleware.LoginRequiredMiddleware` (Django 5.1+) exige login em **todas** as
rotas por padrão; as exceções são declaradas, não lembradas: a tela de login, o health check
(`@login_not_required`) e a API (o DRF trata a própria autenticação e responde 403 em JSON, em vez
de redirecionar para uma página HTML). Um anônimo que acessa uma tela é redirecionado para
`/accounts/login/?next=<url>`; um POST anônimo para uma ação não altera nada. O logout é por POST
(botão "Sair" no cabeçalho), e `LoginView` usa `redirect_authenticated_user=True`.

### Perfis: administrador e operador

Cada usuário tem um `Profile` com uma organização e um papel. A divisão segue a pergunta "quem
define a estrutura" × "quem executa o trabalho":

| Ação                                                         | Administrador | Operador |
| ------------------------------------------------------------ | :-----------: | :------: |
| Ver projetos, sprints, membros, tarefas                      | sim           | sim      |
| Criar, editar e excluir **projetos**                         | sim           | não      |
| Criar, editar e excluir **sprints**                          | sim           | não      |
| Criar, editar e excluir **membros**                          | sim           | não      |
| Criar e editar **tarefas**, concluir e reabrir               | sim           | sim      |
| **Excluir** tarefas                                          | sim           | não      |
| Subtarefas: criar, editar, marcar, excluir                   | sim           | sim      |
| Dependências: criar e remover                                | sim           | sim      |
| Dashboard: KPIs, status, carga por membro, projetos, burndown | sim          | sim      |
| Dashboard: throughput, criadas × concluídas, velocity        | sim           | não      |
| Exportar CSV                                                 | sim           | não      |
| API: mesmas regras acima (escrita em projetos/sprints/membros e `DELETE` de tarefa só para admin) | sim | conforme a tabela |

Implementação: `AdminRequiredMixin` (views de classe) e `@admin_required` (funções) levantam
`PermissionDenied` com a mensagem "Somente administradores da organização podem realizar esta
ação.", exibida pela página `templates/403.html`. Os botões de ação de administrador somem da tela
para o operador (`{% if is_org_admin %}`), mas a proteção real está no servidor — esconder o botão
é conveniência, não segurança. Na API, `IsOrgAdminOrReadOnly` e `IsOrgAdminToDelete`.

### Usuário sem perfil

Um usuário (inclusive superusuário) sem `Profile` consegue fazer login, mas não pertence a nenhuma
organização. Ao acessar qualquer tela recebe a página 403 `core/no_profile.html`, que explica a
situação; se for `is_staff`, a página traz um botão para criar o perfil no Admin. O Admin
(`/admin/`) e o logout continuam acessíveis. Na API, `HasOrganizationProfile` responde 403 com
mensagem equivalente.

### Limite de tentativas de login

Achado da revisão de segurança: sem limite, a senha de qualquer usuário podia ser testada
indefinidamente.

| Item          | Como funciona                                                                                                                  |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Onde          | `core.auth.RateLimitedModelBackend`, o único `AUTHENTICATION_BACKENDS` — vale para a tela de login, o login do Admin e `/api/auth/login/` |
| Chave         | `login-attempts:<IP>:<usuário em minúsculas>` — o limite é por **usuário + IP**                                                |
| Limite        | 5 falhas (`DJANGO_LOGIN_MAX_ATTEMPTS`); depois disso, até a senha correta é recusada                                            |
| Janela        | 900 s = 15 min (`DJANGO_LOGIN_LOCKOUT_SECONDS`), contados a partir da primeira falha (ver a ressalva do cache em banco abaixo)   |
| Sucesso       | um login correto antes do limite zera o contador                                                                               |
| Mensagem      | "Muitas tentativas de login sem sucesso. Aguarde alguns minutos e tente novamente." (`LoginForm` a mostra na tela de login)    |
| Armazenamento | o cache do Django: em desenvolvimento, o cache em memória do processo (`LocMemCache`, padrão); em produção, o cache em banco (`DJANGO_DATABASE_CACHE=True`, tabela `django_cache`, criada por `createcachetable` no entrypoint) para que todos os workers do gunicorn compartilhem o contador |
| Testes        | durante os testes o limite sobe para 1000, e os testes do limite usam `override_settings`                                      |

A janela é deslizante: cada falha regrava o contador com a expiração configurada
(`LOGIN_LOCKOUT_SECONDS`, 15 minutos por padrão), então o bloqueio termina 15 minutos depois da
**última** tentativa com falha. `register_failure()` usa `cache.set()` com a expiração explícita em
vez de `cache.incr()`, porque o `incr` do `DatabaseCache` regravaria a chave com a expiração padrão
do cache (300 s) — o comportamento é o mesmo nos dois backends.

### Log de segurança

`core/signals.py` liga os sinais de autenticação do Django ao logger `grello.security`, que escreve
no console (e, portanto, em `docker compose logs`):

```
2026-11-25 10:15:02,118 INFO grello.security login ok usuario=admin.labs ip=172.18.0.1
2026-11-25 10:16:40,532 WARNING grello.security login falhou usuario=operador.acme ip=172.18.0.1
2026-11-25 10:20:11,004 INFO grello.security logout usuario=admin.labs ip=172.18.0.1
```

A senha nunca é registrada. Durante os testes o nível sobe para `CRITICAL`, para não poluir a saída.

---

## 8. Sprints

### O que é e quem gerencia

Uma sprint é uma janela de tempo (`start_date`–`end_date`, no máximo 60 dias) dentro de um
projeto, com um objetivo (`goal`). Criar, editar e excluir sprints é exclusivo de administradores;
todos veem.

| Tela / ação           | URL                                  | Observação                                                       |
| --------------------- | ------------------------------------ | ---------------------------------------------------------------- |
| Lista de sprints      | detalhe do projeto (`/projects/<pk>/`) | tabela com estado, datas, progresso                            |
| Nova sprint           | `/projects/<project_pk>/sprints/new/` | o projeto vem da URL; `SprintForm` não tem o campo `project`    |
| Detalhe               | `/projects/sprints/<pk>/`            | objetivo, estado, duração, progresso, tarefas, botão "Ver burndown" |
| Editar                | `/projects/sprints/<pk>/edit/`       |                                                                  |
| Excluir               | `/projects/sprints/<pk>/delete/`     | confirmação; as tarefas voltam para o backlog                    |

### Estados

O estado é **calculado** a partir da data de hoje (`Sprint.state()`), nunca armazenado:

| Estado         | Condição                           |
| -------------- | ---------------------------------- |
| Planejada      | hoje < início                      |
| Em andamento   | início ≤ hoje ≤ fim (inclusive)    |
| Encerrada      | hoje > fim                         |

Guardar o estado num campo exigiria alguém (ou uma tarefa agendada) para virá-lo todo dia, e um
campo esquecido mostraria uma sprint "em andamento" meses depois do fim. Com o cálculo, o estado
nunca fica desatualizado. `duration_days()` conta os dois extremos (uma sprint de um dia dura 1).

### Backlog

Uma tarefa sem sprint (`sprint = NULL`) está no **backlog** do projeto. O formulário de tarefa
oferece "Sem sprint (backlog)" como opção vazia, a listagem de tarefas filtra por sprint, e excluir
uma sprint faz `SET_NULL` nas tarefas — elas voltam ao backlog em vez de serem apagadas, porque o
trabalho continua existindo mesmo que a janela de tempo tenha sido descartada.

### Regras

Resumidas da [seção 5](#regras-novas-da-p2-no-model): nome único no projeto; fim não anterior ao
início; no máximo 60 dias (`clean()` + `CheckConstraint`); sprint com tarefas não muda de projeto;
a sprint de uma tarefa precisa ser do mesmo projeto da tarefa.

O progresso da sprint (`task_count()`, `completed_task_count()`, `progress_percent()`) segue o mesmo
padrão do projeto, sobre `self.tasks.all()` — aproveitando o `prefetch_related` das telas.

---

## 9. Telas, URLs e templates

### Mapa de URLs

Toda rota tem um `name`, e toda referência em template ou view usa `{% url %}` / `reverse()`.

| Caminho                      | Destino                                         |
| ---------------------------- | ----------------------------------------------- |
| `/admin/`                    | Django Admin                                    |
| `/health/`                   | health check (JSON, público, sem cache)         |
| `/accounts/login/`, `/accounts/logout/` | login (`LoginForm`) e logout (POST)  |
| `/`                          | página inicial                                  |
| `/dashboard/`, `/dashboard/export/` | dashboard e exportação CSV               |
| `/projects/…`                | projetos e sprints                              |
| `/members/…`                 | membros                                         |
| `/tasks/…`                   | tarefas, subtarefas e dependências              |
| `/api/auth/login/`, `/api/auth/logout/` | login de sessão do DRF               |
| `/api/dashboard/`, `/api/dashboard/burndown/` | API do dashboard              |
| `/api/…`                     | API REST ([seção 10](#10-api-rest))             |

`projects`:

| Caminho                                  | Nome                     | Quem       |
| ---------------------------------------- | ------------------------ | ---------- |
| `/projects/`                             | `projects:list`          | todos      |
| `/projects/new/`                         | `projects:create`        | admin      |
| `/projects/<pk>/`                        | `projects:detail`        | todos      |
| `/projects/<pk>/edit/`                   | `projects:update`        | admin      |
| `/projects/<pk>/delete/`                 | `projects:delete`        | admin      |
| `/projects/<project_pk>/sprints/new/`    | `projects:sprint_create` | admin      |
| `/projects/sprints/<pk>/`                | `projects:sprint_detail` | todos      |
| `/projects/sprints/<pk>/edit/`           | `projects:sprint_update` | admin      |
| `/projects/sprints/<pk>/delete/`         | `projects:sprint_delete` | admin      |

`members` tem o mesmo CRUD (`members:list`, `create`, `detail`, `update`, `delete`), com criação,
edição e exclusão restritas ao administrador.

`tasks`:

| Caminho                              | Nome                      | Método   | Quem  |
| ------------------------------------ | ------------------------- | -------- | ----- |
| `/tasks/`                            | `tasks:list`              | GET      | todos |
| `/tasks/new/`                        | `tasks:create`            | GET/POST | todos |
| `/tasks/<pk>/`                       | `tasks:detail`            | GET      | todos |
| `/tasks/<pk>/edit/`                  | `tasks:update`            | GET/POST | todos |
| `/tasks/<pk>/delete/`                | `tasks:delete`            | GET/POST | admin |
| `/tasks/<pk>/complete/`              | `tasks:complete`          | **POST** | todos |
| `/tasks/<pk>/reopen/`                | `tasks:reopen`            | **POST** | todos |
| `/tasks/<task_pk>/dependencies/new/` | `tasks:dependency_create` | GET/POST | todos |
| `/tasks/dependencies/<pk>/delete/`   | `tasks:dependency_delete` | **POST** | todos |
| `/tasks/<task_pk>/subtasks/new/`     | `tasks:subtask_create`    | GET/POST | todos |
| `/tasks/subtasks/<pk>/edit/`         | `tasks:subtask_update`    | GET/POST | todos |
| `/tasks/subtasks/<pk>/delete/`       | `tasks:subtask_delete`    | GET/POST | todos |
| `/tasks/subtasks/<pk>/toggle/`       | `tasks:subtask_toggle`    | **POST** | todos |

Toda rota marcada como **POST** altera estado e só aceita esse método (`@require_POST`). Todos os
formulários com `method="post"` incluem `{% csrf_token %}`. `/tasks/new/` aceita `?project=<id>` e
`?sprint=<id>` para já vir com os campos escolhidos (botões "Nova tarefa" do projeto e da sprint).

**Views baseadas em classe para o CRUD, funções para as ações.** As generic views eliminam a
repetição dos fluxos de CRUD; as ações que carregam regra de negócio (concluir, reabrir,
dependências, subtarefas, sprints) são funções, onde a lógica fica explícita.

### Paginação

| Listagem  | Itens por página |
| --------- | ---------------- |
| Projetos  | 12               |
| Membros   | 20               |
| Tarefas   | 25               |

`core.pagination.LenientPaginationMixin` usa `Paginator.get_page()`: uma página inválida ou fora do
intervalo mostra a primeira ou a última, em vez de responder 404 (comportamento padrão da
`ListView`). O partial `partials/_pagination.html` monta os links com a tag `{% querystring %}`, que
preserva os filtros da listagem de tarefas (projeto, sprint, status) ao trocar de página.

### Herança e partials

`templates/base.html` é o pai de **todas** as páginas (exceto `500.html`, ver abaixo): cabeçalho com
o menu (que só aparece para quem tem perfil), a área do usuário com organização e papel e o botão
"Sair", mensagens e rodapé. Blocos: `title`, `page_title`, `page_subtitle`, `page_actions`,
`content` e `extra_js` (usado pelo dashboard para carregar os scripts dos gráficos).

| Partial                                   | Onde é usado                                                          |
| ----------------------------------------- | --------------------------------------------------------------------- |
| `partials/_messages.html`                 | no `base.html`, vale para o site inteiro                              |
| `partials/_form.html`                     | todos os formulários do sistema                                       |
| `partials/_confirm_delete.html`           | todas as telas de exclusão com confirmação                            |
| `partials/_pagination.html`               | listagens de projetos, membros e tarefas                              |
| `tasks/partials/_task_table.html`         | listagem de tarefas e detalhe do projeto, da sprint e do membro       |
| `tasks/partials/_status_badge.html`       | onde quer que um status apareça                                       |
| `tasks/partials/_task_status_action.html` | botão Concluir/Reabrir na tabela e no detalhe                         |
| `projects/partials/_sprint_state_badge.html` | estado da sprint no projeto e no detalhe da sprint                 |
| `dashboard/partials/_filters.html`, `_kpi.html` | filtros e cartões de indicador do dashboard                     |

Páginas de erro: `403.html` mostra a mensagem da exceção (por exemplo, a de "somente
administradores"); `404.html` herda do `base.html`; `500.html` é **autocontido** (CSS embutido, sem
`{% url %}` nem herança), porque o handler de erro 500 do Django renderiza sem contexto e um
template que dependesse de banco ou de context processors poderia falhar justamente quando algo já
deu errado.

### O template não calcula nada

O template não compara valores de banco (`{% if task.is_done %}`, nunca
`{% if task.status == 'done' %}`), e todo número chega pronto: progresso de projeto e sprint vem do
model, contagens de subtarefas também, e todas as métricas do dashboard vêm de `metrics.py`.

---

## 10. API REST

### Visão geral

API JSON com Django REST Framework em `/api/`. Ela não é uma segunda implementação do sistema: os
viewsets usam os mesmos models, os mesmos querysets filtrados por organização e, por meio do
`ModelCleanMixin`, os mesmos `clean()`.

### Endpoints

Todos os recursos são `ModelViewSet` (`GET` lista e detalhe, `POST`, `PUT`, `PATCH`, `DELETE`).

| Recurso / ação                              | Métodos                  | Administrador | Operador                | Filtros (`?param=`)                      |
| ------------------------------------------- | ------------------------ | :-----------: | :---------------------: | ---------------------------------------- |
| `/api/`                                     | GET                      | sim           | sim                     | raiz navegável com os links              |
| `/api/projects/`, `/api/projects/{id}/`     | GET / POST PUT PATCH DELETE | tudo       | só GET                  | —                                        |
| `/api/sprints/`, `/api/sprints/{id}/`       | GET / POST PUT PATCH DELETE | tudo       | só GET                  | `project`                                |
| `/api/members/`, `/api/members/{id}/`       | GET / POST PUT PATCH DELETE | tudo       | só GET                  | —                                        |
| `/api/tasks/`, `/api/tasks/{id}/`           | GET POST PUT PATCH / DELETE | tudo       | tudo, exceto `DELETE`   | `project`, `sprint`, `assignee`, `status`|
| `/api/tasks/{id}/complete/`                 | POST                     | sim           | sim                     |                                          |
| `/api/tasks/{id}/reopen/`                   | POST                     | sim           | sim                     |                                          |
| `/api/subtasks/`, `/api/subtasks/{id}/`     | todos                    | sim           | sim                     | `task`                                   |
| `/api/subtasks/{id}/toggle/`                | POST                     | sim           | sim                     |                                          |
| `/api/dependencies/`, `/api/dependencies/{id}/` | todos                | sim           | sim                     | `task`, `depends_on`                     |
| `/api/dashboard/`                           | GET                      | completo      | sem `flow` e `velocity` | `start`, `end`, `project`, `sprint`      |
| `/api/dashboard/burndown/`                  | GET                      | sim           | sim                     | `sprint`                                 |
| `/api/auth/login/`, `/api/auth/logout/`     | GET/POST                 | —             | —                       | login de sessão do DRF                   |

Filtros com valor inválido (não numérico, status desconhecido) são ignorados.

### Autenticação

Somente **sessão** (`SessionAuthentication`), a mesma do site: quem está logado nas telas já está
logado na API, e `/api/auth/login/` oferece o formulário de login do DRF. Por ser sessão, o DRF
exige o token CSRF em `POST`, `PUT`, `PATCH` e `DELETE` (cabeçalho `X-CSRFToken`). Anônimo recebe
`403 {"detail": "As credenciais de autenticação não foram fornecidas."}`.

O navegador da API do DRF (`BrowsableAPIRenderer`) só é habilitado com `DEBUG=True`; em produção a
API responde apenas JSON.

### Permissões

`DEFAULT_PERMISSION_CLASSES` = `IsAuthenticated` + `HasOrganizationProfile` (usuário sem perfil
recebe 403). Por viewset, somam-se `IsOrgAdminOrReadOnly` (projetos, sprints, membros) e
`IsOrgAdminToDelete` (tarefas). Subtarefas e dependências seguem a mesma regra das telas: liberadas
para os dois papéis.

### Isolamento: `OrganizationRelatedField`

Todo campo de FK da API é um `OrganizationRelatedField`, um `PrimaryKeyRelatedField` cujo
`get_queryset()` filtra pela organização do usuário:

```python
class TaskSerializer(ModelCleanMixin, serializers.ModelSerializer):
    project = OrganizationRelatedField(Project, "organization")
    sprint = OrganizationRelatedField(Sprint, "project__organization", required=False, allow_null=True)
    assignee = OrganizationRelatedField(Member, "organization", required=False, allow_null=True)
```

Assim, criar uma tarefa num projeto de outra organização, ou apontar um responsável de outra
organização, responde 400 com a mesma mensagem de um ID inexistente. As listagens e os detalhes
são filtrados por `OrganizationViewSet.get_queryset()` (404 para outra organização), e
`perform_create()` define a organização no servidor.

### Reaproveitamento do `clean()` do model: `ModelCleanMixin`

O DRF, ao contrário do `ModelForm`, **não** chama `Model.clean()`. Sem cuidado, a API seria uma
porta dos fundos para todas as regras da [seção 5](#5-a-regra-central-bloqueio-da-conclusão). O
`ModelCleanMixin` fecha essa porta:

```python
def validate(self, attrs):
    attrs = super().validate(attrs)
    instance = self.build_clean_instance(attrs)
    try:
        instance.clean()
    except DjangoValidationError as error:
        raise serializers.ValidationError(django_error_detail(error))
    return attrs
```

`build_clean_instance()` monta uma instância com os dados recebidos — uma **cópia** da instância
existente no caso de edição, para não deixar o objeto alterado se a validação falhar — e, na
criação de `Project`/`Member`, já com a organização do usuário. `django_error_detail()` converte o
erro do Django para o formato do DRF (`{"campo": [...]}` ou `{"non_field_errors": [...]}`).

Resultado: `PATCH {"status": "done"}` numa tarefa bloqueada responde 400 com o motivo; sprint de
outro projeto, sprint de 61 dias, dependência que fecha ciclo, mudança de projeto com
dependências — tudo responde 400 com as mesmas mensagens das telas. Duas regras de formulário
foram replicadas explicitamente nos serializers, porque não estão no model: e-mail único por
organização (`validate_email`) e "membro inativo não pode ser escolhido como responsável"
(`validate_assignee`, que permite manter o responsável atual). A regra de prazo do `TaskForm` **não**
foi replicada (limitação conhecida).

### Ações `complete`, `reopen` e `toggle`

`@action(detail=True, methods=["post"])` chamando `task.complete()`, `task.reopen()` e
`subtask.toggle()`. Sucesso devolve o objeto atualizado (200); bloqueio devolve
`400 {"detail": "<motivo>"}`.

### Campos de leitura

As tarefas expõem `project_name`, `sprint_name`, `assignee_name`, `status_label`, `is_blocked`,
`blocking_reason`, `subtask_count` e `completed_subtask_count`; `started_at`, `completed_at`,
`created_at` e `updated_at` são somente leitura. Projetos e sprints expõem o progresso; sprints
expõem `state`, `state_label` e `duration_days`; dependências expõem `depends_on_status`.

### Paginação

`api.pagination.StandardPagination` (`PageNumberPagination`) em todas as listas:

```json
{"count": 6, "next": "http://localhost:8000/api/tasks/?page=2&page_size=2&status=pending",
 "previous": null, "results": [ ... ]}
```

50 itens por padrão; `?page_size=` até 200 (valores maiores são limitados a 200); `?page=` fora do
intervalo responde 404 (padrão do DRF). Os filtros são preservados nos links `next`/`previous`.

### API do dashboard e do burndown

- `GET /api/dashboard/?start=&end=&project=&sprint=` devolve o mesmo payload que alimenta a tela
  ([seção 11](#11-dashboard-e-relatórios)): `period`, `filters`, `kpis`, `status_distribution`,
  `workload`, `projects`, `burndown` e, só para administradores, `flow` e `velocity`. Ao contrário
  da tela (que ignora filtros inválidos), a API responde `400 {"errors": {...}}`.
- `GET /api/dashboard/burndown/?sprint=<id>` devolve o burndown/burnup de uma sprint da
  organização (404 para outra organização; 400 para um ID não numérico). Sem `?sprint=`, usa a
  sprint padrão da organização (regra na [seção 11](#burndown-e-burnup)) e responde 404 se não
  houver nenhuma.

### Exemplos com curl

Login de sessão (o token CSRF muda depois do login, por isso é lido de novo):

```bash
B=http://localhost:8000
curl -s -c jar -b jar $B/api/auth/login/ -o /dev/null
TOKEN=$(grep csrftoken jar | awk '{print $7}')
curl -s -c jar -b jar -X POST $B/api/auth/login/ -H "Referer: $B/api/auth/login/" \
     --data-urlencode "csrfmiddlewaretoken=$TOKEN" -d username=operador.labs -d password=demo1234
TOKEN=$(grep csrftoken jar | awk '{print $7}')
```

Leitura com filtro e paginação:

```bash
curl -s -b jar "$B/api/tasks/?status=pending&page_size=2"
```

Tentativa de concluir uma tarefa bloqueada (com o `id` de "Implementar o cadastro de alunos"):

```bash
curl -s -b jar -X POST $B/api/tasks/<id>/complete/ -H "X-CSRFToken: $TOKEN" -H "Referer: $B/"
# 400 {"detail":"Ela depende das tarefas \"Desenhar as telas\", \"Modelar o banco de dados\", que ainda não foram concluídas."}
```

Operador tentando excluir um projeto, e anônimo:

```bash
curl -s -b jar -X DELETE $B/api/projects/<id>/ -H "X-CSRFToken: $TOKEN" -H "Referer: $B/"
# 403 {"detail":"Somente administradores da organização podem realizar esta ação."}
curl -s $B/api/tasks/
# 403 {"detail":"As credenciais de autenticação não foram fornecidas."}
```

Sem o cabeçalho `X-CSRFToken`, qualquer escrita responde `403 {"detail":"CSRF Failed: CSRF token missing."}`.

---

## 11. Dashboard e relatórios

### Perguntas de negócio

| Pergunta                                                   | Onde no dashboard                           |
| ---------------------------------------------------------- | ------------------------------------------- |
| Como está o trabalho **agora**?                            | KPIs do "Retrato atual", distribuição por status |
| Quanto entregamos e com que velocidade, **no período**?    | throughput, lead time, cycle time           |
| Cumprimos os prazos?                                       | entrega no prazo, KPI de atrasadas          |
| A sprint vai terminar a tempo?                             | burndown / burnup e a situação da sprint    |
| A equipe está sobrecarregada? Quem tem tarefas atrasadas?  | carga por membro                            |
| Qual projeto está mais adiantado ou mais atrasado?         | projetos por progresso                      |
| A entrada de trabalho está maior que a saída?              | criadas × concluídas (admin)                |
| Quanto a equipe entrega por sprint?                        | velocity (admin)                            |

### Retrato atual × período

Os KPIs são separados em dois grupos, e a tela diz isso explicitamente:

- **Retrato atual** — situação das tarefas **hoje**; **não depende** do período (só dos filtros de
  projeto e sprint).
- **No período** — o que aconteceu entre `start` e `end`.

Misturar os dois produziria leituras erradas (por exemplo, "total de tarefas" mudando quando se
estreita o período, ou "atrasadas" calculadas para uma data passada sem histórico de status).

### Fórmulas

Todas em `dashboard/metrics.py`, calculadas no banco com `aggregate`/`annotate` (uma consulta por
bloco, independentemente do número de tarefas). "Escopo" = tarefas da organização, filtradas por
projeto e sprint quando informados. "No período" = `completed_at` entre `start` 00:00 e
`end + 1 dia` 00:00, no fuso `America/Sao_Paulo`.

| Métrica                | Fórmula                                                                                                  | Grupo     |
| ---------------------- | -------------------------------------------------------------------------------------------------------- | --------- |
| Total                  | nº de tarefas do escopo                                                                                  | atual     |
| Em andamento (WIP)     | nº com `status = in_progress`                                                                            | atual     |
| Concluídas             | nº com `status = done`                                                                                   | atual     |
| Atrasadas              | nº com `due_date < hoje` e `status ≠ done`                                                               | atual     |
| Bloqueadas             | nº com `status ≠ done` **e** (existe dependência cujo pré-requisito não está concluído **ou** existe subtarefa em aberto) — a mesma definição de `Task.is_blocked()`, em SQL com `EXISTS` | atual |
| Taxa de conclusão      | concluídas ÷ total × 100 (1 casa; "—" sem tarefas)                                                       | atual     |
| Throughput             | nº de tarefas concluídas no período                                                                      | período   |
| Lead time médio        | média de `completed_at − created_at` das concluídas no período, em dias (1 casa)                          | período   |
| Cycle time médio       | média de `completed_at − started_at` das concluídas no período que têm `started_at`, em dias              | período   |
| Entrega no prazo       | entre as concluídas no período **com prazo**, % com data de conclusão ≤ `due_date` (mostra "X de Y")     | período   |
| Distribuição por status | contagem por status (pendente, em andamento, concluída) no escopo                                       | atual     |
| Carga por membro       | por responsável (incluindo "Sem responsável"): abertas (`≠ done`), em andamento, concluídas no período, atrasadas; só aparecem linhas com abertas ou concluídas no período; ordenado por abertas, atrasadas e concluídas (decrescente) | misto |
| Progresso por projeto  | por projeto com tarefas no escopo: total, concluídas, em andamento, atrasadas e `round(concluídas ÷ total × 100)`; ordenado do mais adiantado para o menos | atual |
| Throughput / Criadas × concluídas (admin) | por semana (segunda-feira como início, `TruncWeek`) se o período tiver menos de 182 dias; por mês (`TruncMonth`) a partir disso; criadas = `created_at` no balde, concluídas = `completed_at` no balde; baldes vazios aparecem com zero | período |
| Velocity (admin)       | últimas 12 sprints já iniciadas com tarefas no escopo: **comprometidas** = tarefas atualmente na sprint; **concluídas** = dessas, as concluídas dentro da janela da sprint (data de `completed_at` entre início e fim); média = média das concluídas apenas nas sprints **encerradas** | histórico |

Lead time mede o tempo que o cliente espera (da criação à entrega); cycle time mede o tempo de
trabalho efetivo (do início à entrega). A diferença entre os dois é o tempo de fila. É por causa do
cycle time que a P2 acrescentou `started_at` a `Task`.

### Burndown e burnup

`metrics.sprint_burndown(sprint, today, queryset)` monta as duas visões a partir dos mesmos dados.
A unidade é **tarefas** e o escopo é o **conjunto atual de tarefas da sprint** (premissas
discutidas abaixo).

| Série                  | Cálculo                                                                                                            |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Eixo X                 | um ponto "Início" (antes do primeiro dia) + um ponto por dia da sprint (fim do dia)                                |
| Escopo                 | `total` = nº de tarefas atualmente na sprint, constante em todos os pontos                                        |
| Ideal (burndown)       | `total × (dias − i) ÷ dias` no ponto `i` — de `total` no início a 0 no último dia                                   |
| Restante real          | `total − concluídas acumuladas` até o fim de cada dia; concluídas **antes** do início já entram no ponto "Início"; dias futuros ficam vazios (`null`) |
| Concluído (burnup)     | `total − restante`; ideal do burnup = `total − ideal`                                                             |
| Concluídas após o fim  | informadas à parte (`completed_after_end`), sem alterar a janela                                                 |
| Dias restantes         | em andamento: `fim − hoje`; planejada: duração total; encerrada: 0                                                 |

**Situação da sprint**, comparando o restante real com o ideal no último dia com dado:

| Situação     | Condição                                                                      |
| ------------ | ----------------------------------------------------------------------------- |
| Adiantada    | restante < ideal − tolerância                                                 |
| No ritmo     | dentro da tolerância                                                          |
| Atrasada     | restante > ideal + tolerância                                                 |
| Não iniciada | sprint planejada (nenhum ponto real ainda)                                    |
| Sem tarefas  | `total = 0`                                                                   |

A tolerância é `max(0,5; total ÷ dias)` — cerca de um dia de trabalho ideal —, para que uma
diferença de uma única tarefa numa sprint pequena não alterne entre "adiantada" e "atrasada".

**Sprint mostrada por padrão** (quando nenhuma é escolhida no filtro), entre as sprints da
organização (e do projeto, se filtrado): a **em andamento** que termina primeiro; se não houver,
a **encerrada** mais recente; se não houver, a **planejada** mais próxima.

**Premissas assumidas:**

- **Unidade = tarefas**, não story points: o modelo não tem estimativa, e inventar uma tornaria o
  gráfico mais preciso na aparência do que nos dados.
- **Escopo = tarefas atuais da sprint**: não há histórico de quando uma tarefa entrou ou saiu da
  sprint. Se uma tarefa é adicionada no meio da sprint, ela aparece como se estivesse lá desde o
  início (a linha de escopo é reta). Ver [seção 17](#17-decisões-de-projeto-e-limitações-conhecidas).

### Filtros

| Filtro    | Regra                                                                                                    |
| --------- | -------------------------------------------------------------------------------------------------------- |
| `start`, `end` | datas `AAAA-MM-DD` ou `dd/mm/aaaa`, entre 2000 e 2100; `end ≥ start`                                |
| Padrão    | sem datas: últimos **90 dias** até hoje; só `start`: até hoje; só `end`: os 90 dias que terminam em `end` |
| Limite    | período de no máximo **3 anos** (1096 dias) — achado da revisão de segurança (evita gerar séries enormes) |
| `project` | projetos da organização                                                                                  |
| `sprint`  | sprints da organização; se houver projeto, precisa ser dele                                              |

Na tela, filtros inválidos são ignorados (com a mensagem de erro no campo) e a página usa o padrão —
nunca um erro 500. Os filtros vão para a querystring, então um link do dashboard filtrado pode ser
compartilhado; o detalhe da sprint tem o botão "Ver burndown", que abre `/dashboard/?sprint=<id>`.

### Visão por papel

O operador vê o retrato atual, os KPIs do período, a distribuição por status, o burndown/burnup, a
carga por membro e o progresso por projeto. O administrador vê também throughput, criadas ×
concluídas, velocity e o botão "Exportar CSV". A separação é feita no servidor:
`dashboard_payload(..., is_admin)` simplesmente não calcula `flow` e `velocity` para o operador
(a tela faz 11 consultas para o operador e 14 para o administrador).

### Exportação CSV

`/dashboard/export/` (somente administrador; operador recebe 403) exporta as tarefas do escopo
**ativas no período** — criadas até o fim do período e não concluídas antes do início —, com os
mesmos filtros da tela (o botão leva a querystring atual).

| Aspecto     | Decisão                                                                                                   |
| ----------- | --------------------------------------------------------------------------------------------------------- |
| Colunas     | Tarefa, Projeto, Sprint, Responsável, Status, Criada em, Iniciada em, Concluída em, Prazo, Lead time (dias), Cycle time (dias), No prazo |
| Codificação | UTF-8 **com BOM** — o Excel no Windows só reconhece os acentos com o BOM                                  |
| Separador   | `;` — padrão do Excel em português, onde a vírgula é separador decimal                                    |
| Formatos    | datas `dd/mm/aaaa HH:MM` no fuso local; dias com vírgula decimal (`2,5`)                                  |
| Fórmulas    | células que começam com `=`, `+`, `-`, `@`, tabulação ou `\r` recebem um `'` na frente (`safe_cell`), contra injeção de fórmulas (CSV injection) |
| Arquivo     | `grello-tarefas-AAAA-MM-DD.csv`                                                                           |
| Consultas   | 4, independentemente do número de tarefas (`select_related` + lead/cycle time anotados no banco)         |

### Gráficos: Chart.js local + `json_script`

O Chart.js 4.6.2 está em `static/js/chart.umd.js`, servido pelo próprio sistema, e não por CDN:
o dashboard funciona sem internet (inclusive na apresentação), não depende de terceiros e não
precisa liberar domínios externos. Os dados chegam ao JavaScript com o filtro `json_script`
(`{{ burndown|json_script:"burndown-data" }}`), que gera um `<script type="application/json">`
com o conteúdo escapado — nenhum dado do banco é interpolado em código JavaScript, o que elimina o
risco de XSS por um título de tarefa malicioso. `static/js/dashboard.js` lê esses blocos, aplica as
cores das variáveis CSS e alterna burndown/burnup sem recarregar. Cada gráfico tem `aria-label` e
uma tabela com os mesmos dados em `<details>`, e a página continua utilizável se o Chart.js não
carregar.

---

## 12. Segurança

Revisão feita na Aula 18 sobre o sistema completo da P2. Cada item foi verificado e, quando havia
falha, corrigido e coberto por teste.

### O que foi verificado

| Ameaça                            | Situação no Grello                                                                                                    | Teste / evidência                       |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| **IDOR** (acessar ID de outra organização) | todas as views e viewsets partem de querysets filtrados; 404 para outra organização; FKs da API com `OrganizationRelatedField` | `core/tests.py`, `api/tests.py`, testes de isolamento de cada app |
| **Escalada de papel**             | ações de administrador checadas no servidor (`AdminRequiredMixin`, `@admin_required`, permissões da API), não só escondidas | testes `*RoleTests` em todos os apps |
| **Mass assignment**               | `organization` fora de todos os formulários e serializers; `task` da subtarefa e `project` da sprint vêm da URL; `started_at`/`completed_at` somente leitura | testes de injeção de organização |
| **CSRF**                          | `CsrfViewMiddleware`; `{% csrf_token %}` em todos os formulários; ações que alteram estado só por POST; API por sessão exige `X-CSRFToken`; logout por POST | testes de método (`test_get_on_complete_or_reopen_is_not_allowed`) |
| **XSS**                           | autoescape dos templates (nenhum `|safe` com dado de usuário); dados dos gráficos via `json_script`                  | revisão dos templates                   |
| **SQL injection**                 | somente ORM, nenhum SQL cru; filtros numéricos validados com `isdigit()`                                              | revisão do código                       |
| **CSV injection**                 | `safe_cell()` neutraliza células que começam com `=`, `+`, `-`, `@`, tab ou `\r`                                      | `dashboard/tests.py` (exportação)       |
| **Open redirect**                 | o `?next=` do login é validado pelo `LoginView` do Django contra os hosts permitidos; nenhuma view própria redireciona para URL vinda do usuário | revisão do código |
| **Clickjacking**                  | `XFrameOptionsMiddleware` com `X_FRAME_OPTIONS = "DENY"`                                                              | configuração                            |
| Outros cabeçalhos                 | `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY = "same-origin"`, `SESSION_COOKIE_HTTPONLY`                    | configuração                            |

### O que foi corrigido

| Achado                                                                                   | Correção                                                                                                       | Teste                                  |
| ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| **Sprint gigante → negação de serviço**: uma sprint de séculos fazia o burndown gerar milhões de pontos | limite de 60 dias em `Sprint.clean()` + `CheckConstraint sprint_max_duration`; período do dashboard limitado a 3 anos | `projects/test_security.py`, `dashboard/test_security.py` |
| **Mudança de projeto** quebrava invariantes (tarefa com dependências, sprint com tarefas) | regras no model ([seção 5](#regras-novas-da-p2-no-model))                                                       | `tasks/test_security.py`, `projects/test_security.py` |
| **Força bruta no login**                                                                 | `RateLimitedModelBackend` (5 falhas por usuário+IP) + log `grello.security`                                    | `core/test_security.py`                |
| **`DEBUG` ligado por padrão**                                                            | `DEBUG` é `False` quando `DJANGO_DEBUG` não está definida                                                      | `core/test_settings.py`                |
| **`SECRET_KEY` conhecida por padrão**                                                    | sem `DJANGO_SECRET_KEY`, o sistema **não inicia** fora do modo de desenvolvimento (`ImproperlyConfigured`)       | `core/test_settings.py`                |
| Cookies e HTTPS                                                                          | com `DEBUG=False`: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` e `SECURE_SSL_REDIRECT` ligados por padrão (desligáveis por variável para testes locais); `/health/` isento do redirecionamento | `core/test_settings.py` |
| HSTS                                                                                     | opcional (`DJANGO_SECURE_HSTS_SECONDS`, padrão 0); `includeSubDomains` junto; **preload só por opt-in** (`DJANGO_SECURE_HSTS_PRELOAD`), porque entrar na lista de preload dos navegadores é difícil de desfazer | `core/test_settings.py` |
| `manage.py check --deploy`                                                               | passa sem avisos com a configuração de produção                                                                | `core/test_settings.py`                |
| Navegador da API exposto                                                                 | `BrowsableAPIRenderer` só com `DEBUG=True`                                                                     | `core/test_settings.py`                |
| Banco acessível pela rede local                                                          | no Compose de desenvolvimento, as portas do banco e da aplicação são publicadas só em `127.0.0.1`; no de produção, o banco não publica porta nenhuma | `docker-compose.yml`, `compose.prod.yml` |
| Usuários de demonstração em produção                                                     | `seed_demo` se recusa a rodar com `DEBUG=False`, salvo `--allow-production` (as senhas são públicas)           | `core/test_security.py`                |
| Contêiner como root                                                                      | a imagem roda com o usuário `app` (UID 1000)                                                                   | `Dockerfile`                           |

---

## 13. Desempenho

Revisão feita na Aula 17.

### N+1 evitado com `select_related` e `prefetch_related`

As regras de bloqueio e os progressos são calculados em Python sobre `.all()` justamente para
aproveitar o que já foi carregado. O risco é o inverso: uma tela que esqueça o prefetch faria uma
consulta por tarefa. Os prefetches foram centralizados em `tasks/queries.py`:

```python
def task_table_prefetches(lookup, *related):
    return [
        Prefetch(lookup, queryset=Task.objects.select_related(*related)),
        f"{lookup}__subtasks",
        dependencies_prefetch(f"{lookup}__"),
    ]
```

O detalhe do projeto, da sprint e do membro usam `task_table_prefetches("tasks", …)`; a listagem e o
detalhe de tarefa, os viewsets da API e o Admin usam os mesmos `dependencies_prefetch()` e
`dependents_prefetch()` (que já trazem a tarefa da outra ponta com `select_related`). As métricas
são agregações no banco; o CSV anota lead e cycle time no próprio `SELECT`.

### Perfil carregado numa consulta só

`core.tenancy.load_profile()` busca o perfil com `select_related("organization")` e guarda o
resultado (inclusive a **ausência** de perfil) no cache de relação do próprio objeto `user`. O
middleware, as permissões, os context processors e as views chamam `get_profile()` quantas vezes
quiserem sem nova consulta. A página inicial faz 3 consultas no total (sessão, usuário, perfil).

### Número de consultas travado por testes

Cada app tem um `test_queries.py`. O helper `assertQueriesStayAt(n, url)` (em `core/testing.py`)
mede a mesma URL com poucos dados (3) e com muitos (12 a mais) e exige o **mesmo** número `n` nos
dois casos — se uma alteração introduzir um N+1, o teste quebra. Alguns valores travados:

| Tela / endpoint                                        | Consultas |
| ------------------------------------------------------ | --------- |
| Página inicial                                         | 3         |
| Listagem de tarefas (com ou sem filtros, qualquer página) | 9      |
| Detalhe da tarefa (dependências, dependentes, subtarefas) | 7      |
| Detalhe do projeto / da sprint / do membro             | 9 / 7 / 7 |
| Dashboard (administrador / operador)                   | 14 / 11   |
| Exportação CSV                                         | 4         |
| `GET /api/tasks/` / `GET /api/tasks/{id}/`             | 8 / 7     |
| `GET /api/dashboard/` (administrador / operador)       | 12 / 9    |
| Admin: lista de tarefas / edição de tarefa             | 8 / 11    |

### Índices em `Task`

Os três índices da [seção 4](#taskstask) atendem os filtros mais frequentes: projeto + status
(listagens, progresso), status + data de conclusão (throughput, lead/cycle time, burndown) e data
de criação (série de criadas, CSV por período). A medição foi feita com `EXPLAIN ANALYZE` num banco
de teste com 60 mil tarefas em duas organizações grandes, período de 90 dias:

| Consulta                                   | Antes                                        | Depois                                                 |
| ------------------------------------------ | -------------------------------------------- | ------------------------------------------------------ |
| Concluídas no período (fluxo do dashboard) | Seq Scan com filtro `::date`, **22,7 ms**    | Bitmap Index Scan em `task_status_completed_idx`, **2,8 ms** |
| Lista filtrada por projeto e status        | índice da FK, 4930 entradas lidas, 0,83 ms   | `task_project_status_idx`, 866 entradas, 0,64 ms       |
| Criadas no período                         | 5,6 ms                                       | `task_created_at_idx`, 5,1 ms                          |

O ganho da primeira linha vem de duas mudanças juntas: o índice composto e a troca dos filtros
`__date__gte/lte` por intervalos de data e hora (`within_days()` em `dashboard/metrics.py`), que
permitem ao Postgres usar o índice. Com muitas organizações pequenas, o filtro por organização já é
seletivo o bastante e os índices pesam pouco: eles servem às organizações grandes.

---

## 14. Testes

### Números atuais

| Item                        | Valor                                                    |
| --------------------------- | -------------------------------------------------------- |
| Testes                      | **348**, todos passando                                  |
| Cobertura de linhas         | **98%** (1805 instruções, 38 não executadas)             |
| Tempo                       | cerca de 3 minutos (os testes de configuração sobem subprocessos do Django) |

A cobertura exclui migrações, os próprios testes, `core/testing.py`, `manage.py`, `asgi.py` e
`wsgi.py` (`.coveragerc`). Os trechos não cobertos são, em sua maioria, ramos de configuração de
produção em `config/settings.py` (que os testes verificam em subprocessos, fora da medição) e
ramos defensivos.

### Organização

| Arquivo              | O que cobre                                                                                         |
| -------------------- | --------------------------------------------------------------------------------------------------- |
| `tests.py`           | regras de negócio de cada app: os seis invariantes A1–A3/B1–B3, mensagens, ciclos, sprints, papéis, isolamento, API, métricas, burndown, CSV, seed, migração de dados |
| `test_queries.py`    | número fixo de consultas de cada tela e endpoint ([seção 13](#13-desempenho))                       |
| `test_security.py`   | correções da Aula 18: limite de login, log de segurança, seed em produção, sprint gigante, mudança de projeto, período do dashboard |
| `test_settings.py`   | configuração de produção, rodando o Django em subprocesso com variáveis diferentes (`DEBUG`, `SECRET_KEY`, cookies, HSTS, `check --deploy`, navegador da API) |
| `test_pagination.py` | tamanhos de página, página inválida, filtros mantidos nos links, contagem só da organização         |
| `test_error_pages.py`| páginas 404 e 500 personalizadas                                                                    |
| `test_health.py`     | health check: público, sem cache, só GET, 503 com o banco indisponível                              |

`core/testing.py` concentra as fábricas (`make_organization`, `make_admin`, `make_task`, …) e o
cenário de contagem de consultas.

### Como rodar

No host (o PostgreSQL precisa estar acessível e o usuário precisa poder criar o banco de testes):

```bash
pip install -r requirements-dev.txt
python manage.py test
coverage run manage.py test
coverage report
```

Com o banco do Docker de desenvolvimento, a partir do host no Windows:

```bash
DB_HOST=127.0.0.1 DB_PORT=5433 python manage.py test --noinput
```

`DB_TEST_NAME` define o nome do banco de testes (padrão do Django: `test_<DB_NAME>`).

Dentro do Docker:

```bash
docker compose run --rm web python manage.py test
```

(A imagem instala só o `requirements.txt`; a cobertura é medida no host.)

---

## 15. Como rodar

### Docker — desenvolvimento

Pré-requisito: Docker Desktop (ou Docker Engine com Compose v2).

```bash
cp .env.example .env                 # opcional; sem .env valem os padrões
docker compose up -d --build         # aplica as migrações ao subir
docker compose exec web python manage.py seed_demo
```

A aplicação fica em **http://localhost:8000/**. O `docker-compose.yml` usa o alvo `dev` da imagem
(`runserver` com recarga automática, código montado em `/app`), `DJANGO_DEBUG=True` por padrão e o
PostgreSQL 18 com volume `pgdata`. O serviço web sempre se conecta em `db:5432`,
independentemente do `DB_HOST`/`DB_PORT` do `.env`. Ao subir, o `docker/entrypoint.sh` roda
`migrate`, `createcachetable` e, com `SEED_DEMO=1`, o `seed_demo`.

| Ação                                     | Comando                                                    |
| ---------------------------------------- | ---------------------------------------------------------- |
| Subir já com os dados de demonstração    | `SEED_DEMO=1 docker compose up -d`                         |
| Recriar os dados de demonstração         | `docker compose exec web python manage.py seed_demo --reset` |
| Logs (inclui o log de segurança)         | `docker compose logs -f web`                               |
| Testes                                   | `docker compose run --rm web python manage.py test`        |
| Superusuário                             | `docker compose exec web python manage.py createsuperuser` |
| Parar / derrubar / apagar o banco        | `docker compose stop` / `docker compose down` / `docker compose down -v` |

O PostgreSQL fica publicado no host em **`127.0.0.1:5433`** (altere com `DB_HOST_PORT`), e só nesse
endereço — não na rede local. **No Windows, para conectar do host use `DB_HOST=127.0.0.1` e
`DB_PORT=5433`**: com `localhost`, o cliente pode tentar primeiro o IPv6 (`::1`), onde a porta não
está publicada, e travar até o tempo limite.

### Docker — produção

```bash
cp .env.prod.example .env.prod       # defina DJANGO_SECRET_KEY, DB_PASSWORD e o domínio
docker compose -f compose.prod.yml --env-file .env.prod up -d --build
docker compose -f compose.prod.yml --env-file .env.prod exec web python manage.py createsuperuser
```

| Aspecto            | Como está configurado                                                                                         |
| ------------------ | ------------------------------------------------------------------------------------------------------------- |
| Imagem             | alvo `prod`: `collectstatic` no build, usuário `app`, `gunicorn config.wsgi:application` com `WEB_CONCURRENCY` workers (padrão 3) |
| Estáticos          | WhiteNoise com `CompressedManifestStaticFilesStorage` (arquivos comprimidos e com hash no nome, cache longo)   |
| Configuração       | `DJANGO_DEBUG=False` fixo; `DJANGO_SECRET_KEY` e `DB_PASSWORD` obrigatórias (o Compose recusa subir sem elas); `DJANGO_DATABASE_CACHE=True` (limite de login compartilhado entre workers) |
| Banco              | PostgreSQL 18 com volume `pgdata_prod`, **sem porta publicada**                                               |
| Health check       | `GET /health/` → `{"status": "ok", "database": "ok"}` ou 503; público, sem cache, isento do redirecionamento HTTPS; usado pelo `healthcheck` do contêiner (mantenha `localhost` em `DJANGO_ALLOWED_HOSTS`) |
| HTTPS              | o contêiner fala HTTP na porta 8000 (`WEB_HOST_PORT`); em produção real, um proxy reverso (Nginx, Caddy, Traefik ou o balanceador do provedor) termina o HTTPS e repassa para ela, com `DJANGO_BEHIND_HTTPS_PROXY=True` para o Django confiar no `X-Forwarded-Proto` |
| Primeiro acesso    | crie o superusuário, entre no Admin, cadastre a organização e o perfil do usuário; o `seed_demo` é recusado em produção |
| Teste local sem HTTPS | em `.env.prod`, `DJANGO_SECURE_SSL_REDIRECT=False`, `DJANGO_SECURE_COOKIES=False` e `DJANGO_SECURE_HSTS_SECONDS=0` |

O `compose.prod.yml` repassa ao contêiner **apenas** as variáveis listadas no seu bloco
`environment` (não usa `env_file`, para que nada do `.env` de desenvolvimento vaze para a
produção). Todas as variáveis de produção da tabela abaixo estão nessa lista; uma variável nova
precisa ser acrescentada a ela.

### Localmente, com venv

Pré-requisitos: Python 3.13 e PostgreSQL 14 ou superior.

```bash
python -m venv .venv
.venv\Scripts\activate             # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt    # ou requirements-dev.txt, para ter o coverage
copy .env.example .env             # Linux/macOS: cp; ajuste DB_* e mantenha DJANGO_DEBUG=True
```

Crie o banco (`CREATE DATABASE gestao_tarefas;`) — ou use o PostgreSQL do Docker com
`DB_HOST=127.0.0.1` e `DB_PORT=5433` — e depois:

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

A aplicação fica em **http://127.0.0.1:8000/**. Sem `DJANGO_DEBUG=True` o sistema roda em modo de
produção e exige `DJANGO_SECRET_KEY` (e os cookies seguros impediriam o login em HTTP).

### Variáveis de ambiente

| Variável                       | Padrão                    | Uso                                                                                  |
| ------------------------------ | ------------------------- | ------------------------------------------------------------------------------------ |
| `DJANGO_SECRET_KEY`            | — (obrigatória sem DEBUG) | chave criptográfica; com `DEBUG=True` e vazia, usa uma chave de desenvolvimento      |
| `DJANGO_DEBUG`                 | `False`                   | modo de desenvolvimento (no `docker-compose.yml` o padrão é `True`)                  |
| `DJANGO_ALLOWED_HOSTS`         | `localhost,127.0.0.1`     | hosts aceitos, separados por vírgula                                                 |
| `DJANGO_CSRF_TRUSTED_ORIGINS`  | vazio                     | origens confiáveis para o CSRF (ex.: `https://grello.exemplo.com`)                   |
| `DJANGO_SECURE_COOKIES`        | `True` (sem DEBUG)        | cookies de sessão e CSRF só por HTTPS                                                |
| `DJANGO_SECURE_SSL_REDIRECT`   | `True` (sem DEBUG)        | redireciona HTTP para HTTPS (exceto `/health/`)                                      |
| `DJANGO_SECURE_HSTS_SECONDS`   | `0`                       | HSTS em segundos (0 = desligado)                                                     |
| `DJANGO_SECURE_HSTS_PRELOAD`   | `False`                   | marca o HSTS para preload (só com HSTS ligado)                                       |
| `DJANGO_BEHIND_HTTPS_PROXY`    | `False`                   | confia no `X-Forwarded-Proto: https` do proxy reverso                                |
| `DJANGO_LOGIN_MAX_ATTEMPTS`    | `5`                       | falhas de login antes do bloqueio (por usuário + IP)                                 |
| `DJANGO_LOGIN_LOCKOUT_SECONDS` | `900`                     | duração da janela de bloqueio                                                        |
| `DJANGO_DATABASE_CACHE`        | `False`                   | usa o cache em banco (`django_cache`); `True` no `compose.prod.yml`                  |
| `DB_NAME` / `DB_USER`          | `gestao_tarefas` / `postgres` | banco e usuário                                                                  |
| `DB_PASSWORD`                  | vazio (`postgres` no Compose de dev) | senha do banco                                                            |
| `DB_HOST` / `DB_PORT`          | `localhost` / `5432`      | fora do Docker; no Compose, o web sempre usa `db:5432`                               |
| `DB_TEST_NAME`                 | `test_<DB_NAME>`          | nome do banco de testes                                                              |
| `DB_HOST_PORT`                 | `5433`                    | (Compose de dev) porta do PostgreSQL publicada em `127.0.0.1`                        |
| `SEED_DEMO`                    | `0`                       | (Compose) `1` roda o `seed_demo` ao subir                                            |
| `WEB_HOST_PORT`                | `8000`                    | (Compose de produção) porta publicada da aplicação                                   |
| `WEB_CONCURRENCY`              | `3`                       | (produção) número de workers do gunicorn                                             |

---

## 16. Roteiro de demonstração e teste manual

Roteiro para a apresentação da P2, sobre os dados do `seed_demo` (rode `seed_demo --reset` antes,
para começar do estado conhecido). Todos os usuários têm a senha **`demo1234`**:

| Usuário         | Organização      | Papel         |
| --------------- | ---------------- | ------------- |
| `admin.labs`    | Grello Labs      | Administrador |
| `operador.labs` | Grello Labs      | Operador      |
| `admin.acme`    | Acme Consultoria | Administrador |
| `operador.acme` | Acme Consultoria | Operador      |

O seed cria, na **Grello Labs**, o projeto "Sistema de Matrículas" com 4 membros, 3 sprints (as
duas primeiras encerradas, a "Sprint 3" em andamento), 24 tarefas com histórico de datas e quatro
tarefas bloqueadas; na **Acme Consultoria**, o projeto "Portal do Cliente" com 2 membros, 2 sprints
(a "Sprint 2" em andamento) e 7 tarefas. As datas são relativas ao dia em que o seed roda.

### Parte A — Isolamento entre organizações

1. Entre como `admin.labs` e abra **Projetos → Sistema de Matrículas**. Anote o número na URL
   (`/projects/<id>/`) e, numa tarefa qualquer, o número em `/tasks/<id>/`.
   **Esperado:** o cabeçalho mostra "Grello Labs · Administrador".
2. Saia e entre como `admin.acme`. **Esperado:** listas de projetos, tarefas e membros mostram só
   "Portal do Cliente" e seus dados.
3. Acesse diretamente `/projects/<id da Labs>/` e `/tasks/<id da Labs>/edit/`.
   **Esperado:** página 404 "não existe ou não está disponível para a sua organização".
4. Em **Membros**, observe "Ana Pereira" com `ana@exemplo.com` — o mesmo e-mail de "Ana Souza" na
   Labs. Tente cadastrar outro membro com `ANA@exemplo.com`.
   **Esperado:** "Já existe um membro com este e-mail na sua organização."
5. Em **Tarefas → Nova tarefa**, abra os selects. **Esperado:** só projeto, sprints e membros da Acme.

### Parte B — Perfis de acesso

6. Entre como `operador.labs`. **Esperado:** sem botões "Novo projeto", "Novo membro", "Nova
   sprint", "Editar"/"Excluir" de projeto e "Excluir" de tarefa.
7. Acesse `/projects/new/` diretamente. **Esperado:** 403 "Somente administradores da organização
   podem realizar esta ação."
8. Crie uma tarefa no "Sistema de Matrículas", na "Sprint 3", com prazo daqui a uma semana.
   **Esperado:** criada (operador pode criar e editar tarefas).
9. Acesse `/tasks/<id da tarefa criada>/delete/`. **Esperado:** 403.
10. Abra o **Dashboard**. **Esperado:** sem throughput, criadas × concluídas, velocity e sem o botão
    "Exportar CSV"; acessar `/dashboard/export/` responde 403.
11. Crie um usuário sem perfil no Admin (como superusuário) e entre com ele.
    **Esperado:** página "Seu usuário não pertence a nenhuma organização".

### Parte C — Regra de bloqueio sobre o seed

Ainda como `operador.labs`, em **Tarefas**:

12. **Esperado:** quatro linhas com a etiqueta "Bloqueada": "Modelar o banco de dados" e "Desenhar
    as telas" (subtarefas em aberto), "Implementar o cadastro de alunos" e "Testar o fluxo de
    matrícula" (dependências pendentes).
13. Clique em **Concluir** em "Implementar o cadastro de alunos".
    **Esperado:** recusado: _"Ela depende das tarefas "Desenhar as telas", "Modelar o banco de
    dados", que ainda não foram concluídas."_
14. Abra "Modelar o banco de dados", marque a subtarefa "Revisar o modelo com o professor" e clique
    em **Concluir**. **Esperado:** sucesso.
15. Tente concluir "Implementar o cadastro de alunos" de novo.
    **Esperado:** ainda recusado, agora citando só "Desenhar as telas".
16. Em "Modelar o banco de dados" (já concluída), clique em **Reabrir** na subtarefa.
    **Esperado:** recusado — a tarefa precisa ser reaberta antes (caso B2).
17. Abra "Levantar requisitos" (concluída) e clique em **Reabrir**.
    **Esperado:** recusado: _"A tarefa "Modelar o banco de dados" depende desta e já está
    concluída."_ (caso A2).
18. Abra "Desenhar as telas" → **Adicionar dependência** → escolha "Testar o fluxo de matrícula".
    **Esperado:** _"Esta dependência criaria um ciclo entre as tarefas."_

### Parte D — Regra de bloqueio do zero (roteiro da P1, atualizado)

Entre como `admin.labs` (criar projeto exige administrador).

19. Em **Projetos → Novo projeto**, crie "Sistema Acadêmico". Em **Tarefas → Nova tarefa**, crie
    três tarefas nesse projeto, com status "Pendente": **A – Levantar requisitos**, **B – Modelar
    banco**, **C – Implementar telas**. Deixe o prazo vazio (ou a partir de amanhã — ver a
    ressalva de fuso da regra do prazo na [seção 17](#17-decisões-de-projeto-e-limitações-conhecidas)).
20. Tente criar uma quarta tarefa com prazo **ontem**. **Esperado:** o formulário volta com
    "O prazo não pode ser anterior a criação do projeto" (regra da Feature 2 da P1).
21. Abra **B** → **Adicionar dependência** → **A**. Abra **C** → **Adicionar dependência** → **B**.
22. Abra **Tarefas**. **Esperado:** **B** e **C** destacadas com "Bloqueada por: …"; **A** sem marcação.
23. Clique em **Concluir** em **C**. **Esperado:** recusado, citando "Modelar banco"; status inalterado.
24. Abra **C** → **Editar** → status "Concluída" → **Salvar**. **Esperado:** erro embaixo do campo
    **Status**, nada gravado.
25. Conclua **A**; **B** perde o bloqueio e **C** continua bloqueada, agora por **B**. Conclua **B**
    e depois **C**. **Esperado:** as três concluídas, na ordem.
26. Tente **Reabrir** **B**. **Esperado:** recusado, porque "Implementar telas" depende dela e está
    concluída. Reabra **C** e depois **B**. **Esperado:** ambas aceitas, e **C** volta a aparecer
    bloqueada.
27. Abra **A** → **Adicionar dependência**. **Esperado:** a lista não oferece a própria **A** nem
    tarefas de outros projetos. Escolha **C**. **Esperado:** erro de ciclo.
28. Com **B** pendente, abra **C** e remova a dependência de **B**. **Esperado:** **C** deixa de
    aparecer bloqueada e pode ser concluída.
29. Numa tarefa sem dependências pendentes, adicione duas subtarefas. **Esperado:** etiqueta
    "Bloqueada" e "0 de 2 subtarefas concluídas" na listagem; **Concluir** é recusado citando as
    duas; com uma marcada, cita só a que falta; com as duas, conclui.
30. Na tarefa recém-concluída, tente adicionar uma subtarefa em aberto. **Esperado:** erro no campo
    **Concluída** (caso B3). Reabra a tarefa e repita. **Esperado:** aceito, e a tarefa volta a
    aparecer bloqueada.

### Parte E — Sprints e burndown

31. Como `admin.labs`, abra o "Sistema de Matrículas". **Esperado:** "Sprint 1" e "Sprint 2"
    encerradas, "Sprint 3" em andamento, com progresso.
32. Abra a "Sprint 3" → **Ver burndown**. **Esperado:** dashboard filtrado pela sprint, com a linha
    ideal, o restante real até hoje (dias futuros vazios), a situação (adiantada / no ritmo /
    atrasada) e os dias restantes. Clique em **Burnup**: linha de escopo e concluído acumulado.
33. Em **Nova sprint**, informe início hoje e fim daqui a 61 dias.
    **Esperado:** "Uma sprint pode durar no máximo 60 dias."
34. Crie um segundo projeto com uma sprint. Edite uma tarefa do "Sistema de Matrículas" escolhendo
    essa sprint. **Esperado:** "A sprint precisa pertencer ao mesmo projeto da tarefa."
35. Crie uma tarefa no segundo projeto, dentro da sprint dele, e então exclua essa sprint.
    **Esperado:** mensagem "Suas tarefas voltaram para o backlog"; a tarefa continua existindo, sem
    sprint.
36. No dashboard, mude o período para um intervalo maior que 3 anos.
    **Esperado:** "O período pode ter no máximo 3 anos." e a página continua com o período padrão.

### Parte F — API no navegador

(`DJANGO_DEBUG=True`, como no Docker de desenvolvimento.)

37. Logado como `operador.labs`, abra `/api/`. **Esperado:** a raiz navegável com os seis recursos.
38. Abra `/api/tasks/?status=pending&page_size=2`. **Esperado:** `count`, `next`, `previous`,
    `results` com duas tarefas e os campos `is_blocked` e `blocking_reason`.
39. Abra `/api/tasks/<id de "Implementar o cadastro de alunos">/complete/`. A página responde 405
    ao GET e oferece o botão **POST**; envie. **Esperado:** 400 com o motivo do bloqueio.
40. Abra `/api/projects/<id>/` e tente `DELETE`. **Esperado:** 403 "Somente administradores…".
41. Abra `/api/tasks/<id de uma tarefa da Acme>/`. **Esperado:** 404.
42. Abra `/api/dashboard/` e compare com `admin.labs`. **Esperado:** o operador não recebe `flow`
    nem `velocity`.

### Parte G — Exportação CSV

43. Como `admin.labs`, no dashboard, clique em **Exportar CSV** e abra o arquivo no Excel.
    **Esperado:** acentos corretos, colunas separadas, datas `dd/mm/aaaa`, lead/cycle time com
    vírgula decimal, só tarefas da Grello Labs.
44. Edite uma tarefa com o título `=1+1` e exporte de novo. **Esperado:** a célula mostra o texto
    `=1+1` (prefixado com `'`), e não o resultado 2.

### Parte H — Bloqueio de login

45. Saia e tente entrar como `operador.acme` com senha errada **5 vezes**.
46. Entre com a senha correta `demo1234`. **Esperado:** "Muitas tentativas de login sem sucesso.
    Aguarde alguns minutos e tente novamente."
47. Entre como `admin.acme` do mesmo navegador. **Esperado:** funciona (o bloqueio é por usuário + IP).
48. Em `docker compose logs web`, **Esperado:** linhas `login falhou usuario=operador.acme ip=…`.
    Para liberar antes dos 15 minutos em desenvolvimento, reinicie o servidor
    (`docker compose restart web`), já que o contador fica na memória do processo.

---

## 17. Decisões de projeto e limitações conhecidas

### Decisões

**Coluna discriminadora, com a FK só em `Project` e `Member`.** Simplicidade operacional e uma
única fonte para a organização de cada registro ([seção 6](#6-multi-organização)).

**404, e não 403, para registros de outra organização.** Não confirma a existência do ID.

**A organização nunca vem do cliente.** Nem formulário, nem JSON: sempre do perfil do usuário logado.

**Regras no model, expostas por forms e serializers.** O `ModelCleanMixin` faz a API passar pelo
mesmo `clean()` das telas.

**Estado da sprint calculado, não armazenado.** Nunca fica desatualizado.

**Excluir uma sprint devolve as tarefas ao backlog** (`SET_NULL`); excluir um projeto apaga suas
tarefas e sprints (`CASCADE`); excluir um membro deixa as tarefas sem responsável (`SET_NULL`);
uma organização com dados não pode ser excluída (`PROTECT`).

**Membros inativos somem do select de responsável, mas não das tarefas.** Se a tarefa editada já
tem um responsável inativo, ele continua disponível, para que editar o título não force a troca. A
API aplica a mesma regra em `validate_assignee`.

**Reabrir uma tarefa a coloca em "Em andamento"**, e não em "Pendente", preservando `started_at`.

**As ações de concluir e reabrir levam ao detalhe da tarefa**, onde está o quadro completo das
pendências — a informação de que o usuário precisa quando a ação é recusada.

**O botão "Concluir" continua clicável numa tarefa bloqueada**, para que o motivo seja informado.

**Chart.js local e dados via `json_script`.** Sem dependência de CDN e sem dados interpolados em
JavaScript.

**Métricas separadas em "retrato atual" e "no período".** Evita misturar estado com fluxo.

**A página inicial é uma landing page**, com atalhos para os domínios do sistema.

### Limitações conhecidas

Resolvidas desde a P1 (e por isso fora desta lista): falta de autenticação e de controle de acesso,
e-mail de membro único no banco inteiro, ausência de testes, configuração insegura por padrão e
listagens sem paginação — ver `MELHORIAS_P1.md`.

**O Django Admin é global.** Um usuário `is_staff` com permissões no Admin vê e edita dados de
**todas** as organizações; as classes de Admin não filtram por organização. O Admin é tratado como
ferramenta da equipe que opera o sistema, não dos clientes — os administradores de organização
usam as telas do Grello.

**A regra do prazo só vale no formulário HTML.** `TaskForm.clean()` recusa um prazo anterior à
criação do projeto, mas a API e o Admin aceitam, porque a regra não está no model. O erro aparece
no topo do formulário, e não no campo Prazo. A comparação usa a data **local** de criação do
projeto (`timezone.localdate`), coberta por `tasks/test_due_date.py`, inclusive para um projeto
criado às 23h30.

**O burndown não tem histórico de escopo.** O escopo é o conjunto **atual** de tarefas da sprint:
uma tarefa incluída ou retirada no meio da sprint altera o gráfico inteiro, retroativamente. O mesmo
vale para o "comprometido" da velocity. Registrar a entrada e a saída de tarefas da sprint
resolveria.

**A contagem é por tarefas, não por story points.** Tarefas grandes e pequenas pesam igual no
burndown e na velocity.

**O limite de login depende do cache.** Em desenvolvimento, o contador fica na memória de cada
processo (`LocMemCache`): com vários processos ele não é compartilhado, e reiniciar o servidor o
zera. Em produção, o cache em banco resolve os dois pontos. O IP vem de `REMOTE_ADDR`: atrás de um proxy reverso, todos os acessos chegam
com o IP do proxy e o limite passa a valer, na prática, por usuário — quem errar 5 vezes a senha de
alguém bloqueia temporariamente o login dessa pessoa.

**A detecção de ciclo ainda é iterativa.** `creates_cycle()` faz uma consulta por tarefa visitada.
Para os tamanhos do projeto é irrelevante; um grafo com milhares de dependências encadeadas se
beneficiaria de uma única consulta recursiva (`WITH RECURSIVE`).

**A API só aceita sessão.** Não há autenticação por token, então clientes externos (scripts,
aplicativos) precisam fazer o login de sessão e lidar com o CSRF.

**Usuários são criados pelo Admin.** Não há cadastro, convite nem recuperação de senha pelas telas;
o administrador da organização não gerencia usuários, só membros.

**O papel vale para a organização inteira.** Não há permissão por projeto.

**O campo de data depende do navegador.** `<input type="date">` tem aparência diferente em cada
navegador; o valor é sempre normalizado para `AAAA-MM-DD` e exibido como `dd/mm/aaaa` nas telas de
leitura.
