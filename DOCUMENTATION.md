# Gestão de Tarefas — Documentação técnica

Documentação de arquitetura e implementação do sistema **Gestão de Tarefas**, entrega P1 da
disciplina de Laboratório de Programação Full Stack.

Este arquivo concentra toda a explicação do projeto. O código-fonte não contém comentários
por decisão de projeto: o que precisa ser explicado está aqui, onde pode ser lido de forma
contínua, e não espalhado em trechos soltos dentro dos módulos.

---

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Stack e decisões de arquitetura](#2-stack-e-decisões-de-arquitetura)
3. [Estrutura de pastas](#3-estrutura-de-pastas)
4. [Modelagem de dados](#4-modelagem-de-dados)
5. [A regra central: bloqueio da conclusão](#5-a-regra-central-bloqueio-da-conclusão)
6. [Os apps em detalhe](#6-os-apps-em-detalhe)
7. [Mapa de URLs](#7-mapa-de-urls)
8. [Camada de templates](#8-camada-de-templates)
9. [Como rodar localmente](#9-como-rodar-localmente)
10. [Roteiro de teste manual](#10-roteiro-de-teste-manual)
11. [Decisões de projeto e limitações conhecidas](#11-decisões-de-projeto-e-limitações-conhecidas)

---

## 1. Visão geral

O sistema organiza o trabalho de uma equipe em torno de cinco entidades:

| Entidade | Papel |
| --- | --- |
| **Projeto** (`Project`) | Agrupa as tarefas de uma frente de trabalho. |
| **Membro** (`Member`) | Pessoa da equipe que pode ser responsável por tarefas. |
| **Tarefa** (`Task`) | Unidade de trabalho: pertence a um projeto, tem status e pode ter um responsável. |
| **Subtarefa** (`Subtask`) | Item de checklist dentro de uma tarefa. |
| **Dependência** (`TaskDependency`) | Relação de pré-requisito entre duas tarefas do mesmo projeto. |

**Critério de aceite do P1:** uma tarefa não pode ser marcada como concluída enquanto qualquer
tarefa da qual ela depende não estiver concluída. O sistema bloqueia a ação e informa na
interface exatamente quais dependências pendentes estão impedindo a conclusão.

A mesma proteção foi estendida às subtarefas: uma tarefa com itens em aberto na sua própria
lista também não pode ser concluída. As duas regras convivem no mesmo ponto do código e
produzem a mesma mensagem combinada — a seção 5 detalha como.

O sistema não tem autenticação nesta entrega — não faz parte do escopo do P1. `Member` é um
model de domínio próprio e **não** o `User` do Django: representar a pessoa da equipe é uma
responsabilidade diferente de representar quem faz login no sistema.

---

## 2. Stack e decisões de arquitetura

| Item | Escolha |
| --- | --- |
| Linguagem | Python 3.13 |
| Framework | Django 6.0.7 (sem Django REST Framework — não há API nesta etapa) |
| Padrão | MVT (Model, View, Template) |
| Banco | PostgreSQL 18, acessado exclusivamente pelo ORM do Django (nenhum SQL cru) |
| Driver | `psycopg` 3.3.5 |
| Front-end | Apenas HTML gerado pelos templates do Django + uma folha de estilo própria |
| Configuração | Variáveis de ambiente lidas de um arquivo `.env` via `python-dotenv` |

### Separação de responsabilidades

O princípio que organiza o código é: **cada regra mora em um lugar só**.

- **Model** — guarda os dados e as regras que precisam valer sempre, independentemente de
  quem executou a operação (uma view, o admin do Django ou o shell). É onde vive a regra de
  bloqueio da conclusão.
- **Form** — traduz a entrada do usuário em dados válidos e restringe as opções oferecidas.
  Não reimplementa regras do model: o `ModelForm` chama `full_clean()` da instância
  automaticamente e as mensagens do model aparecem nos campos certos.
- **View** — orquestra o ciclo HTTP: busca os dados, chama o model, escolhe o template e
  traduz sucesso ou falha em mensagens para o usuário. Não decide se uma operação é válida —
  pergunta ao model.
- **Template** — só exibe. Não faz cálculo nem valida nada. Percentuais, contagens e o
  estado de bloqueio chegam prontos, vindos de métodos do model.

### Divisão em apps

O projeto tem três apps de domínio: `members`, `projects` e `tasks`.

`Subtask` e `TaskDependency` vivem dentro de `tasks` e não em apps próprios porque não são
domínios independentes: uma subtarefa não existe sem sua tarefa, e uma dependência é uma
aresta *entre duas tarefas*. Separá-las criaria dependência circular de importação com
`tasks` sem nenhum ganho de organização. Os três apps representam três perguntas distintas
do domínio: **quem** faz (`members`), **onde** o trabalho acontece (`projects`) e **o que**
precisa ser feito (`tasks`).

Cada app tem seu próprio `models.py`, `forms.py`, `views.py`, `urls.py`, `admin.py` e pasta
`templates/`. O `urls.py` de cada app foi criado manualmente (o `startapp` não o gera) e é
incluído no roteamento raiz com `include()`.

---

## 3. Estrutura de pastas

```
Gestao-de-tarefas/
├── manage.py
├── requirements.txt
├── .env                          # credenciais locais (fora do controle de versão)
├── .env.example                  # modelo das variáveis necessárias
├── README.md
├── DOCUMENTATION.md
│
├── config/                       # pacote de configuração do projeto
│   ├── settings.py               # configuração geral, banco, idioma, templates
│   ├── urls.py                   # roteamento raiz: admin, home e os include() dos apps
│   ├── wsgi.py  asgi.py
│
├── templates/                    # templates globais (TEMPLATES["DIRS"])
│   ├── base.html                 # template pai de todas as páginas
│   ├── home.html                 # página inicial
│   └── partials/
│       ├── _messages.html        # mensagens de sucesso/erro
│       ├── _form.html            # formulário genérico com csrf e erros
│       └── _confirm_delete.html  # confirmação de exclusão genérica
│
├── static/css/style.css          # folha de estilo da aplicação
│
├── members/                      # app: pessoas da equipe
│   ├── models.py  forms.py  views.py  urls.py  admin.py
│   ├── migrations/
│   └── templates/members/
│       ├── member_list.html        member_detail.html
│       ├── member_form.html        member_confirm_delete.html
│
├── projects/                     # app: projetos
│   ├── models.py  forms.py  views.py  urls.py  admin.py
│   ├── migrations/
│   └── templates/projects/
│       ├── project_list.html       project_detail.html
│       ├── project_form.html       project_confirm_delete.html
│
└── tasks/                        # app: tarefas, subtarefas e dependências
    ├── models.py  forms.py  views.py  urls.py  admin.py
    ├── migrations/
    ├── management/commands/seed_demo.py    # dados de demonstração
    └── templates/tasks/
        ├── task_list.html              task_detail.html
        ├── task_form.html              task_confirm_delete.html
        ├── subtask_form.html           subtask_confirm_delete.html
        ├── dependency_form.html
        └── partials/
            ├── _task_table.html            # tabela de tarefas reutilizada em 3 telas
            ├── _status_badge.html          # etiqueta colorida de status
            └── _task_status_action.html    # botão Concluir / Reabrir
```

### Idioma

- **Código em inglês**: apps, models, campos, classes, funções, variáveis, nomes de
  templates, nomes de rotas e caminhos de URL.
- **Interface em português**: rótulos de formulário, textos dos templates, botões,
  mensagens de sucesso e erro, títulos de página.

Os dois se encontram nos `verbose_name` dos campos: o campo se chama `name` no código e
aparece como "Nome" no formulário e no admin, sem que o texto precise ser repetido em
nenhum template.

---

## 4. Modelagem de dados

```
        Member                         Project
          │ 1                             │ 1
          │                               │
          │ N (assignee, SET_NULL)        │ N (project, CASCADE)
          └──────────►  Task  ◄───────────┘
                         │ 1
                         ├──────────► N  Subtask       (CASCADE)
                         │
                         └──────────► N  TaskDependency
                                            │
                     task ──────────────────┤
                     depends_on ────────────┘
                     (duas FKs para Task: relação assimétrica)
```

### `members.Member`

| Campo | Tipo | Observações |
| --- | --- | --- |
| `name` | `CharField(max_length=120)` | |
| `email` | `EmailField(unique=True)` | identifica a pessoa |
| `role` | `CharField(max_length=80, blank=True)` | cargo na equipe |
| `is_active` | `BooleanField(default=True)` | inativo não aparece no select de responsável |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

Ordenação padrão por `name`.

### `projects.Project`

| Campo | Tipo | Observações |
| --- | --- | --- |
| `name` | `CharField(max_length=120)` | |
| `description` | `TextField(blank=True)` | |
| `start_date` | `DateField(null=True, blank=True)` | |
| `due_date` | `DateField(null=True, blank=True)` | |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

Métodos: `task_count()`, `completed_task_count()` e `progress_percent()` — é daqui que sai o
texto "3 de 5 tarefas concluídas (60%)" e a largura da barra de progresso. O template apenas
imprime o resultado.

`clean()` recusa um prazo final anterior à data de início.

### `tasks.Task`

| Campo | Tipo | Relacionamento / observação |
| --- | --- | --- |
| `project` | `ForeignKey(Project, CASCADE, related_name="tasks")` | excluir o projeto exclui suas tarefas |
| `assignee` | `ForeignKey(Member, SET_NULL, null=True, blank=True, related_name="tasks")` | excluir o membro deixa a tarefa sem responsável, sem perdê-la |
| `title` | `CharField(max_length=150)` | |
| `description` | `TextField(blank=True)` | |
| `status` | `CharField(choices=Status.choices, default=PENDING)` | `TextChoices`: `pending` / `in_progress` / `done` |
| `due_date` | `DateField(null=True, blank=True)` | |
| `completed_at` | `DateTimeField(null=True, blank=True)` | preenchido automaticamente no `save()` |
| `created_at` / `updated_at` | `DateTimeField` | |

Ordenação padrão por `due_date`, depois `title`.

### `tasks.Subtask`

| Campo | Tipo | Relacionamento |
| --- | --- | --- |
| `task` | `ForeignKey(Task, CASCADE, related_name="subtasks")` | excluir a tarefa exclui as subtarefas |
| `title` | `CharField(max_length=150)` | |
| `is_done` | `BooleanField(default=False)` | |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

### `tasks.TaskDependency`

| Campo | Tipo | Significado |
| --- | --- | --- |
| `task` | `ForeignKey(Task, CASCADE, related_name="dependencies")` | a tarefa **dependente**, a que fica bloqueada |
| `depends_on` | `ForeignKey(Task, CASCADE, related_name="dependents")` | o **pré-requisito**, que precisa terminar antes |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

Restrições no banco:

- `UniqueConstraint(task, depends_on)` — a mesma aresta não pode ser cadastrada duas vezes.
- `CheckConstraint(~Q(task=F("depends_on")))` — o PostgreSQL recusa uma tarefa que dependa
  de si mesma.

Os dois `related_name` são propositalmente opostos e legíveis a partir da tarefa:

- `task.dependencies` → as arestas que **bloqueiam** esta tarefa;
- `task.dependents` → as arestas das tarefas que **esta tarefa bloqueia**.

### Por que um model intermediário e não um `ManyToManyField("self")`

Um `ManyToManyField` simples criaria a tabela de ligação, mas deixaria a relação sem lugar
para morar. `TaskDependency` existe como model próprio por três motivos concretos:

1. **A relação tem regras próprias.** Mesmo projeto, sem auto-referência, sem duplicata, sem
   ciclo, e sem contradizer uma conclusão já registrada. Todas essas validações vivem em
   `TaskDependency.clean()`. Um `ManyToManyField` não tem um `clean()` onde colocá-las.
2. **A dependência é uma entidade de primeira classe na interface.** Cada aresta tem URL
   própria para ser criada e removida, e um `ModelForm` próprio que restringe as opções
   oferecidas às tarefas válidas do mesmo projeto.
3. **O grafo fica explícito.** As duas pontas têm nome (`task` e `depends_on`) e os dois
   sentidos de leitura têm nome (`dependencies` e `dependents`), o que torna o código de
   validação e os templates diretos de ler.

---

## 5. A regra central: bloqueio da conclusão

Uma tarefa só pode ser concluída quando **duas** condições valem ao mesmo tempo:

> 1. Todas as tarefas das quais ela depende já estão concluídas.
> 2. Todas as suas subtarefas já estão concluídas.

A primeira é o critério de aceite do P1. A segunda foi acrescentada depois, com a mesma
mecânica e no mesmo lugar do código: uma tarefa cuja lista de trabalho ainda tem itens em
aberto não está, de fato, terminada.

### Os invariantes, enunciados por completo

Escritas como propriedades dos dados, as duas regras são:

> **A.** Para toda dependência (`task` → `depends_on`): se `task` está concluída, então
> `depends_on` também está concluída.
>
> **B.** Para toda subtarefa: se a tarefa dela está concluída, então a subtarefa também está.

Enunciados assim, fica claro que **seis** operações diferentes poderiam quebrá-los — e não
apenas as duas óbvias:

| # | Operação | Como quebraria | Onde é barrada |
| --- | --- | --- | --- |
| A1 | **Concluir** uma tarefa com pré-requisito pendente | é o caso óbvio | `Task.complete()` e `Task.clean()` |
| A2 | **Reabrir** uma tarefa que é pré-requisito de outra já concluída | inverte a ordem das operações e chega ao mesmo estado inválido | `Task.reopen()` e `Task.clean()` |
| A3 | **Criar uma dependência** de uma tarefa já concluída para uma pendente | cria a aresta depois, quando o estado já está "errado" | `TaskDependency.clean()` |
| B1 | **Concluir** uma tarefa com subtarefa em aberto | é o caso óbvio | `Task.complete()` e `Task.clean()` |
| B2 | **Reabrir uma subtarefa** de uma tarefa já concluída | mesma inversão de ordem do caso A2 | `Subtask.toggle()` e `Subtask.clean()` |
| B3 | **Adicionar uma subtarefa em aberto** a uma tarefa já concluída | cria o item depois, quando o estado já está "errado" | `Subtask.clean()` |

Cobrir apenas A1 e B1 deixaria quatro caminhos abertos para produzir exatamente o estado que
as regras proíbem. Os seis estão fechados.

Uma subtarefa já marcada como concluída **pode** ser adicionada a uma tarefa concluída: isso
não viola nada. E excluir uma subtarefa em aberto de uma tarefa concluída também é permitido,
porque a operação corrige o estado em vez de quebrá-lo.

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

def pending_subtasks(self):
    return [subtask for subtask in self.subtasks.all() if not subtask.is_done]

def is_blocked(self):
    return bool(self.pending_dependencies()) or bool(self.pending_subtasks())

def complete(self):
    reason = self.blocking_reason()
    if reason:
        raise ValidationError(reason)
    self.status = self.Status.DONE
    self.save()
```

`blocking_reason()` reúne **os dois motivos possíveis** numa única frase, já no singular ou
no plural conforme o caso — por exemplo: *"Ela depende da tarefa X, que ainda não foi
concluída. A subtarefa Y ainda não foi concluída."* Se uma das causas não se aplica, o trecho
correspondente simplesmente não entra. `reopening_reason()` faz o mesmo para o sentido
inverso, percorrendo `completed_dependents()`.

Como `complete()` e `clean()` consultam apenas `blocking_reason()`, acrescentar a regra das
subtarefas não exigiu tocar em nenhuma view, em nenhum formulário e em nenhuma outra
validação: bastou incluir o segundo motivo nesse método. É o efeito prático de manter a regra
num lugar só.

**Por que no model:** a proibição é uma propriedade dos dados, não uma regra de tela. Ela
precisa valer venha a operação de uma view, do admin do Django ou do shell. O model é o
único lugar por onde todos esses caminhos passam.

Repare que `pending_dependencies()` percorre `self.dependencies.all()` **em Python**, e não
com um `.filter()` no banco. Isso é deliberado: quando a view usa
`prefetch_related("dependencies__depends_on")`, a lista já está carregada em memória e o
cálculo de bloqueio de uma listagem inteira não dispara nenhuma query adicional. A listagem
de tarefas usa um número fixo de queries, independentemente de quantas tarefas e
dependências existam.

#### Camada 2 — `Task.clean()`: fecha a porta do formulário

A ação "Concluir" não é o único caminho para marcar uma tarefa como concluída: o formulário
de edição tem um campo `status` com a opção "Concluída". Sem uma segunda checagem, bastaria
usar o formulário para furar a regra.

```python
def clean(self):
    if not self.pk:
        return
    if self.status == self.Status.DONE:
        reason = self.blocking_reason()
    else:
        reason = self.reopening_reason()
    if reason:
        raise ValidationError({"status": reason})
```

Como `TaskForm` é um `ModelForm`, o Django chama `full_clean()` da instância sozinho durante
a validação do formulário. O erro é levantado com a chave `"status"` e aparece **embaixo do
campo Status**, sem uma única linha de código no form ou na view. O mesmo `clean()` cobre os
dois sentidos: concluir bloqueado e reabrir um pré-requisito de algo já concluído.

O `if not self.pk: return` existe porque uma tarefa que ainda não foi salva não tem
dependências nem subtarefas cadastradas — não há nada a verificar.

`Subtask.clean()` faz o mesmo do outro lado da relação: uma subtarefa em aberto não pode ser
salva se a tarefa dela já estiver concluída. Como `SubtaskForm` também é um `ModelForm`, a
mensagem aparece sozinha no campo **Concluída**, tanto ao criar quanto ao editar a subtarefa.
`Subtask.toggle()` aplica a mesma checagem para o botão de marcar/desmarcar da lista, que não
passa por formulário nenhum.

#### Camada 3 — Views `task_complete` e `task_reopen`: traduzem para HTTP

```python
@require_POST
def task_complete(request, pk):
    task = get_object_or_404(Task.objects.prefetch_related("dependencies__depends_on"), pk=pk)
    try:
        task.complete()
    except ValidationError as error:
        messages.error(request, f'Não é possível concluir "{task.title}". {" ".join(error.messages)}')
    else:
        messages.success(request, f'Tarefa "{task.title}" concluída.')
    return redirect(task)
```

A view não sabe o que é uma dependência. Ela pede ao model que conclua a tarefa, e o
resultado — sucesso ou `ValidationError` — vira uma mensagem para o usuário. Uma
responsabilidade só.

O `@require_POST` garante que concluir ou reabrir uma tarefa não aconteça por um `GET`, isto
é, por alguém apenas visitando ou pré-carregando um link.

#### Camada 4 — Banco: a última linha de defesa

`UniqueConstraint` e `CheckConstraint` garantem a integridade do grafo mesmo diante de uma
escrita feita fora da aplicação.

### Validações de `TaskDependency`

`TaskDependency.clean()` recusa, nesta ordem:

1. **auto-dependência** — uma tarefa não pode depender dela mesma;
2. **projetos diferentes** — o pré-requisito precisa pertencer ao mesmo projeto;
3. **duplicata** — a aresta já existe;
4. **contradição com uma conclusão já registrada** — o caso 3 do invariante;
5. **ciclo** — a nova aresta fecharia um laço.

### Detecção de ciclo

Sem essa verificação, um encadeamento A → B → C → A deixaria as três tarefas travadas para
sempre, e sem nenhuma mensagem que explicasse o motivo: cada uma esperaria a conclusão de
outra que, por sua vez, espera a primeira.

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

A busca parte da tarefa dependente e sobe pelo grafo na direção "quem depende de quem",
montando o conjunto de todas as tarefas que dependem de `task`, direta ou indiretamente. Se
o pré-requisito que se quer adicionar (`depends_on`) estiver nesse conjunto, ele já depende
de `task` — e criar a aresta fecharia o laço. O conjunto `visited` garante que a busca
termine mesmo em grafos grandes ou com caminhos repetidos.

### Defesa em profundidade no formulário

`TaskDependencyForm` restringe o `queryset` do campo `depends_on` às tarefas do mesmo
projeto, excluindo a própria tarefa e as dependências já cadastradas. O usuário **não chega
a ver** uma opção inválida.

Isso significa que, na prática, as três primeiras validações de `TaskDependency.clean()`
raramente são acionadas pela interface: um POST forjado com um valor fora do `queryset` é
recusado antes, pela validação de escolha do próprio Django, com a mensagem padrão
*"Faça uma escolha válida"*. Elas continuam valendo para o admin, para o shell e para
qualquer código futuro que crie dependências por outro caminho — é defesa em profundidade,
não código redundante. As duas validações mais interessantes (ciclo e contradição com
conclusão já feita) envolvem tarefas que **estão** no `queryset` e, portanto, exibem as
mensagens específicas normalmente.

### Sinalização visual do bloqueio

O critério de aceite pede que o sistema informe **quais** pendências estão impedindo a
conclusão. Isso aparece em quatro lugares:

| Onde | O que mostra |
| --- | --- |
| Listagem de tarefas | linha destacada, etiqueta "Bloqueada", o texto "Bloqueada por: X, Y" para as dependências e a contagem "1 de 2 subtarefas concluídas" em destaque quando há itens em aberto |
| Detalhe do projeto | a mesma tabela, com os mesmos indicadores |
| Detalhe do membro | a mesma tabela, com os mesmos indicadores |
| Detalhe da tarefa | aviso no topo separando "Dependências pendentes" de "Subtarefas em aberto", e a tabela de dependências marcando cada uma como "Atendida" ou "Impede a conclusão" |

O botão "Concluir" continua **clicável** quando a tarefa está bloqueada, por decisão de
projeto. Um botão desabilitado esconderia a regra em vez de demonstrá-la, e o enunciado pede
que o sistema *informe o motivo* — o que só acontece se a tentativa chegar ao servidor. O
bloqueio é comunicado visualmente pelos indicadores acima; a tentativa produz a mensagem
explícita.

### `completed_at` é gerenciado pelo model

```python
def save(self, *args, **kwargs):
    if self.status == self.Status.DONE and self.completed_at is None:
        self.completed_at = timezone.now()
    elif self.status != self.Status.DONE:
        self.completed_at = None
    super().save(*args, **kwargs)
```

Concluir pela ação "Concluir" ou pelo formulário de edição produz exatamente o mesmo estado,
e reabrir sempre limpa a data. A garantia "`completed_at` está preenchido se e somente se o
status é concluída" vem de um único ponto do código.

---

## 6. Os apps em detalhe

### `members`

| Componente | Responsabilidade |
| --- | --- |
| `Member` | dados da pessoa da equipe |
| `MemberForm` | `ModelForm` com placeholders e textos de ajuda |
| `MemberListView` | lista todos os membros |
| `MemberDetailView` | dados do membro + tabela das tarefas atribuídas a ele |
| `MemberCreateView` / `MemberUpdateView` | cadastro e edição, com mensagem de sucesso |
| `MemberDeleteView` | confirmação e exclusão; avisa que as tarefas ficam sem responsável |

### `projects`

| Componente | Responsabilidade |
| --- | --- |
| `Project` | dados do projeto + métodos de progresso + validação das datas |
| `ProjectForm` | `ModelForm` com campos de data nativos do navegador |
| `ProjectListView` | grade de cartões, cada um com sua barra de progresso |
| `ProjectDetailView` | dados, progresso e a tabela de tarefas do projeto |
| `ProjectCreateView` / `ProjectUpdateView` / `ProjectDeleteView` | CRUD |

### `tasks`

| Componente | Responsabilidade |
| --- | --- |
| `Task` | dados da tarefa + **toda a regra de bloqueio da conclusão** + progresso de subtarefas |
| `Subtask` | item de checklist da tarefa |
| `TaskDependency` | aresta do grafo de pré-requisitos + suas validações |
| `TaskForm` | `ModelForm`; oferece como responsável apenas membros ativos |
| `SubtaskForm` | `ModelForm` com `title` e `is_done`; a tarefa vem da URL |
| `TaskDependencyForm` | `ModelForm` com um campo só, com o `queryset` restrito |
| `TaskListView` | listagem geral com filtros por projeto e por status |
| `TaskDetailView` | tarefa, subtarefas, dependências e quem depende dela |
| `TaskCreateView` | criação; aceita `?project=<id>` para já vir com o projeto escolhido |
| `TaskUpdateView` | edição; é aqui que `Task.clean()` barra a conclusão inválida |
| `TaskDeleteView` | exclusão; volta para o projeto ao final |
| `task_complete` | **ação com regra**: conclui ou explica por que não pode |
| `task_reopen` | **ação com regra**: reabre ou explica por que não pode |
| `dependency_create` | cria a aresta com o formulário restrito |
| `dependency_delete` | remove a aresta, podendo desbloquear a tarefa |
| `subtask_create` / `subtask_update` / `subtask_delete` | CRUD da subtarefa |
| `subtask_toggle` | **ação com regra**: alterna o estado da subtarefa, ou explica por que não pode reabri-la |

**Views baseadas em classe para o CRUD, funções para as ações.** As generic views do Django
(`ListView`, `DetailView`, `CreateView`, `UpdateView`, `DeleteView`) eliminam a repetição dos
quinze fluxos de CRUD. As quatro ações que carregam regra de negócio — concluir, reabrir,
criar e remover dependência — são funções, onde a lógica fica explícita e fácil de ler.

**A subtarefa nunca recebe sua tarefa pelo formulário.** `SubtaskForm` expõe apenas `title` e
`is_done`; a tarefa vem da URL e é entregue ao formulário no `__init__`, que a atribui à
instância antes da validação. Assim ninguém consegue reapontar uma subtarefa para outra
tarefa alterando o HTML — e `Subtask.clean()` já encontra a tarefa preenchida quando precisa
verificar se ela está concluída.

---

## 7. Mapa de URLs

Toda rota tem um `name`, e toda referência em template ou view usa `{% url %}` /
`reverse()` — nunca um caminho fixo. Cada app define `app_name`, então os nomes são
qualificados por namespace.

### Raiz (`config/urls.py`)

| Caminho | Destino | Nome |
| --- | --- | --- |
| `/admin/` | admin do Django | — |
| `/` | página inicial | `home` |
| `/projects/` | `include("projects.urls")` | — |
| `/members/` | `include("members.urls")` | — |
| `/tasks/` | `include("tasks.urls")` | — |

### `projects` e `members`

Os dois apps têm o mesmo conjunto de rotas:

| Caminho | Nome | View |
| --- | --- | --- |
| `/projects/` | `projects:list` | `ProjectListView` |
| `/projects/new/` | `projects:create` | `ProjectCreateView` |
| `/projects/<pk>/` | `projects:detail` | `ProjectDetailView` |
| `/projects/<pk>/edit/` | `projects:update` | `ProjectUpdateView` |
| `/projects/<pk>/delete/` | `projects:delete` | `ProjectDeleteView` |

O mesmo vale para `/members/…` com os nomes `members:list`, `members:create`,
`members:detail`, `members:update` e `members:delete`.

### `tasks`

| Caminho | Nome | Método | View |
| --- | --- | --- | --- |
| `/tasks/` | `tasks:list` | GET | `TaskListView` |
| `/tasks/new/` | `tasks:create` | GET/POST | `TaskCreateView` |
| `/tasks/<pk>/` | `tasks:detail` | GET | `TaskDetailView` |
| `/tasks/<pk>/edit/` | `tasks:update` | GET/POST | `TaskUpdateView` |
| `/tasks/<pk>/delete/` | `tasks:delete` | GET/POST | `TaskDeleteView` |
| `/tasks/<pk>/complete/` | `tasks:complete` | **POST** | `task_complete` |
| `/tasks/<pk>/reopen/` | `tasks:reopen` | **POST** | `task_reopen` |
| `/tasks/<task_pk>/dependencies/new/` | `tasks:dependency_create` | GET/POST | `dependency_create` |
| `/tasks/dependencies/<pk>/delete/` | `tasks:dependency_delete` | **POST** | `dependency_delete` |
| `/tasks/<task_pk>/subtasks/new/` | `tasks:subtask_create` | GET/POST | `subtask_create` |
| `/tasks/subtasks/<pk>/edit/` | `tasks:subtask_update` | GET/POST | `subtask_update` |
| `/tasks/subtasks/<pk>/delete/` | `tasks:subtask_delete` | GET/POST | `subtask_delete` |
| `/tasks/subtasks/<pk>/toggle/` | `tasks:subtask_toggle` | **POST** | `subtask_toggle` |

Toda rota marcada como **POST** altera estado e só aceita esse método. Todos os formulários
com `method="post"` incluem `{% csrf_token %}`.

---

## 8. Camada de templates

### Herança

`templates/base.html` é o template pai de **todas** as páginas. Ele concentra o cabeçalho, o
menu de navegação, a área de mensagens e o rodapé, e oferece os blocos:

| Bloco | Conteúdo |
| --- | --- |
| `title` | título da aba do navegador |
| `page_title` | título principal da página |
| `page_subtitle` | linha de apoio abaixo do título |
| `page_actions` | botões de ação do canto superior direito |
| `content` | corpo da página |

Nenhum template de app repete `<html>`, menu ou rodapé — todos começam com
`{% extends "base.html" %}`.

### Partials reutilizados

| Partial | Onde é usado |
| --- | --- |
| `partials/_messages.html` | incluído no `base.html`, vale para o site inteiro |
| `partials/_form.html` | os **cinco** formulários do sistema |
| `partials/_confirm_delete.html` | as **quatro** telas de exclusão com confirmação |
| `tasks/partials/_task_table.html` | listagem de tarefas, detalhe do projeto e detalhe do membro |
| `tasks/partials/_status_badge.html` | onde quer que um status apareça |
| `tasks/partials/_task_status_action.html` | botão Concluir/Reabrir na tabela e no detalhe |

`_form.html` e `_confirm_delete.html` são parametrizados por `{% include ... with %}`
(`submit_label`, `cancel_url`, `object_type`, `object_label`, `confirm_warning`), em vez de
receberem frases prontas. Por isso cada novo formulário do sistema não precisou de nenhum
HTML de formulário novo.

Remover uma dependência é a única exclusão sem tela de confirmação: é um botão de POST
direto, porque a ação não destrói informação de trabalho — apenas desfaz uma ligação que pode
ser recriada em dois cliques.

`_task_table.html` recebe `show_project` para decidir se a coluna "Projeto" aparece — é a
única diferença entre as três telas que a usam. Foi por causa dessa reutilização que a
sinalização de bloqueio, adicionada em um arquivo só, apareceu automaticamente nas três.

### O template não calcula nada

Duas escolhas garantem isso:

- **Nenhum valor de banco aparece no HTML.** O template não escreve
  `{% if task.status == 'done' %}`; ele pergunta `{% if task.is_done %}` ao model. Os valores
  de `status` ficam num único lugar, a classe `Task.Status`.
- **Todo número já chega pronto.** "1 de 3 tarefas concluídas (33%)" e a largura da barra de
  progresso vêm de `Project.progress_percent()`; a contagem de subtarefas vem de
  `Task.subtask_progress_percent()`; a lista de pendências vem de
  `Task.pending_dependencies()`.

---

## 9. Como rodar localmente

### Pré-requisitos

- Python 3.13
- PostgreSQL 14 ou superior em execução

### Passo a passo

**1. Clonar o repositório e entrar na pasta**

```bash
git clone <url-do-repositorio>
cd Gestao-de-tarefas
```

**2. Criar e ativar o ambiente virtual**

```bash
python -m venv .venv
```

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (cmd)
.venv\Scripts\activate.bat

# Linux / macOS
source .venv/bin/activate
```

**3. Instalar as dependências**

```bash
pip install -r requirements.txt
```

**4. Criar o banco no PostgreSQL**

```sql
CREATE DATABASE gestao_tarefas;
```

**5. Configurar as variáveis de ambiente**

Copie o modelo e edite com os dados do seu PostgreSQL:

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

O arquivo `.env` precisa conter:

```
DJANGO_SECRET_KEY=uma-chave-secreta-qualquer
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=gestao_tarefas
DB_USER=postgres
DB_PASSWORD=sua-senha
DB_HOST=localhost
DB_PORT=5432
```

O `.env` está no `.gitignore` e nunca vai para o repositório.

**6. Aplicar as migrações**

```bash
python manage.py migrate
```

**7. (Opcional) Carregar dados de demonstração**

```bash
python manage.py seed_demo
```

O comando cria o projeto "Sistema de Matrículas" com 3 membros, 5 tarefas encadeadas por
dependências, 4 subtarefas e um cenário em que duas tarefas já aparecem bloqueadas — pronto
para percorrer o roteiro de teste da seção 10. Use `--reset` para recriar os dados do zero.

**8. (Opcional) Criar um usuário administrador**

```bash
python manage.py createsuperuser
```

Dá acesso ao admin do Django em `/admin/`, útil para inspecionar os dados.

**9. Subir o servidor**

```bash
python manage.py runserver
```

A aplicação fica disponível em **http://127.0.0.1:8000/**.

---

## 10. Roteiro de teste manual

Roteiro para verificar o critério de aceite do P1 pela interface. Pode ser executado do zero
ou sobre os dados criados por `seed_demo`.

### Preparação

1. Em **Membros → Novo membro**, cadastre "Ana Souza".
2. Em **Projetos → Novo projeto**, crie "Sistema Acadêmico".
3. Em **Tarefas → Nova tarefa**, crie três tarefas nesse projeto, todas com status
   "Pendente": **A – Levantar requisitos**, **B – Modelar banco**, **C – Implementar telas**.
4. Abra a tarefa **B** → **Adicionar dependência** → escolha **A**.
5. Abra a tarefa **C** → **Adicionar dependência** → escolha **B**.

### Teste 1 — A listagem sinaliza o bloqueio

6. Abra **Tarefas**.
   **Esperado:** as linhas de **B** e **C** aparecem destacadas, com a etiqueta "Bloqueada" e
   o texto "Bloqueada por: …". A tarefa **A** não tem nenhuma marcação.

### Teste 2 — A conclusão fora de ordem é bloqueada

7. Na linha da tarefa **C**, clique em **Concluir**.
   **Esperado:** a tarefa **não** é concluída e aparece a mensagem
   *"Não é possível concluir 'Implementar telas'. Ela depende da tarefa 'Modelar banco', que
   ainda não foi concluída."* O status de **C** continua "Pendente".

### Teste 3 — O formulário de edição aplica a mesma regra

8. Abra **C** → **Editar** → mude o status para "Concluída" → **Salvar**.
   **Esperado:** o formulário volta com a mensagem de erro logo abaixo do campo **Status** e
   nada é gravado.

### Teste 4 — O desbloqueio acontece em cascata, na ordem certa

9. Conclua a tarefa **A**. **Esperado:** sucesso.
10. Volte à listagem. **Esperado:** **B** perdeu a marcação de bloqueio; **C** continua
    bloqueada, agora por **B**.
11. Tente concluir **C** novamente. **Esperado:** continua bloqueada — o desbloqueio não é
    transitivo por engano.
12. Conclua **B**. **Esperado:** sucesso, e **C** fica liberada.
13. Conclua **C**. **Esperado:** sucesso. As três aparecem como "Concluída".

### Teste 5 — A reabertura respeita a mesma ordem

14. Tente **Reabrir** a tarefa **B**.
    **Esperado:** recusado, com a mensagem de que "Implementar telas" depende dela e já está
    concluída.
15. Reabra **C** e depois **B**. **Esperado:** ambas aceitas, e **C** volta a aparecer
    bloqueada.

### Teste 6 — A integridade do grafo é preservada

16. Abra **A** → **Adicionar dependência**.
    **Esperado:** a lista não oferece a própria **A** nem tarefas de outros projetos.
17. Ainda em **A**, escolha **C** como dependência.
    **Esperado:** erro *"Esta dependência criaria um ciclo entre as tarefas."*

### Teste 7 — Remover a dependência desbloqueia

18. Com **B** pendente, abra **C** e remova a dependência de **B**.
    **Esperado:** **C** deixa de aparecer bloqueada e pode ser concluída normalmente.

### Teste 8 — Subtarefas em aberto também impedem a conclusão

19. Abra uma tarefa sem dependências pendentes e adicione duas subtarefas:
    "Levantar bibliografia" e "Revisar o texto".
20. Volte à listagem. **Esperado:** a tarefa aparece com a etiqueta "Bloqueada" e a contagem
    "0 de 2 subtarefas concluídas" em destaque.
21. Clique em **Concluir**. **Esperado:** recusado, com a mensagem
    *"…As subtarefas 'Levantar bibliografia', 'Revisar o texto' ainda não foram concluídas."*
22. Marque apenas a primeira subtarefa e tente concluir de novo.
    **Esperado:** ainda recusado, agora citando só a subtarefa que falta.
23. Marque a segunda e conclua a tarefa. **Esperado:** sucesso.

### Teste 9 — A subtarefa não reabre sozinha

24. Na tarefa recém-concluída, clique em **Reabrir** na subtarefa "Levantar bibliografia".
    **Esperado:** recusado, com a mensagem de que a tarefa já está concluída e precisa ser
    reaberta antes.
25. Tente adicionar uma subtarefa nova (em aberto) a essa mesma tarefa concluída.
    **Esperado:** o formulário volta com erro no campo **Concluída**.
26. Reabra a tarefa e repita o passo 24. **Esperado:** agora a subtarefa reabre normalmente,
    e a tarefa volta a aparecer bloqueada.

---

## 11. Decisões de projeto e limitações conhecidas

### Decisões

**A página inicial é uma landing page, não um redirecionamento.** A rota `/` serve uma página
própria com os três domínios do sistema, em vez de redirecionar para a lista de projetos.

**Membros inativos somem do select de responsável, mas não das tarefas.** `TaskForm` oferece
apenas membros ativos — com uma exceção: se a tarefa que está sendo editada já tem um
responsável que foi desativado, ele continua na lista, para que editar o título da tarefa não
force a troca do responsável.

**Excluir um membro não apaga suas tarefas.** O `on_delete=SET_NULL` deixa as tarefas sem
responsável. Excluir um projeto, ao contrário, apaga suas tarefas (`CASCADE`), porque uma
tarefa não faz sentido fora de um projeto.

**Reabrir uma tarefa a coloca em "Em andamento"**, e não em "Pendente": a tarefa já foi
trabalhada antes de ser concluída.

**As ações de concluir e reabrir sempre levam ao detalhe da tarefa**, mesmo quando disparadas
da listagem. É na página de detalhe que está o quadro completo de dependências — exatamente a
informação de que o usuário precisa quando a ação é recusada.

### Limitações conhecidas

**Não há autenticação nem controle de acesso.** Qualquer pessoa com acesso à aplicação pode
criar, editar e excluir qualquer registro. Está fora do escopo do P1.

**Não há paginação nas listagens.** Com o volume de dados de um trabalho acadêmico não faz
diferença; em produção, `ListView` já oferece `paginate_by` para resolver.

**A detecção de ciclo consulta o banco a cada nível do grafo.** Para os tamanhos previstos
aqui isso é irrelevante. Um projeto com milhares de dependências encadeadas se beneficiaria
de uma consulta recursiva única.

**O campo de data depende do navegador.** Os campos de data usam `<input type="date">`, cujo
seletor visual varia entre navegadores. O valor é sempre normalizado para o formato
`YYYY-MM-DD` na renderização, e exibido como `dd/mm/aaaa` nas telas de leitura.
