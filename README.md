# Grello

**Grello** é um sistema de gestão de tarefas com subtarefas, dependências entre tarefas e
sprints, desenvolvido em Django (padrão MVT) com PostgreSQL, para a disciplina de Laboratório de
Programação Full Stack. A P1 entregou o MVP; a P2 o transforma num mini-SaaS com várias
organizações, perfis de acesso, API REST e dashboard.

**Regra central:** uma tarefa não pode ser concluída enquanto qualquer tarefa da qual ela
depende — ou qualquer subtarefa dela — não estiver concluída. O sistema bloqueia a ação e
mostra exatamente quais pendências estão impedindo a conclusão.

A documentação completa de arquitetura, modelagem e implementação está em
[DOCUMENTATION.md](DOCUMENTATION.md). Os pontos da P1 revisados para a P2 estão em
[MELHORIAS_P1.md](MELHORIAS_P1.md).

## Funcionalidades

- CRUD de projetos, sprints, membros, tarefas e subtarefas
- Definição de dependências entre tarefas do mesmo projeto
- Ação de concluir tarefa com validação das dependências e das subtarefas em aberto
- Ação de reabrir tarefa, respeitando a mesma ordem
- Listagem de tarefas com filtros e indicação visual das tarefas bloqueadas
- Detecção de ciclos no grafo de dependências
- Várias organizações na mesma base, cada uma vendo só os seus dados
- Login obrigatório e perfis de acesso (administrador e operador)
- API REST com Django REST Framework em `/api/`
- Dashboard com métricas de fluxo, burndown/burnup de sprint e exportação CSV

## Como rodar com Docker

Pré-requisito: Docker Desktop (ou Docker Engine com Compose v2).

1. (Opcional) Copie o modelo de configuração e ajuste os valores. Sem `.env`, são usados os
   padrões (banco `gestao_tarefas`, usuário `postgres`, senha `postgres`). Dentro do Compose, o
   serviço web sempre se conecta em `db:5432`, independentemente do `DB_HOST`/`DB_PORT` do `.env`.

   ```bash
   cp .env.example .env
   ```

2. Suba os serviços. O serviço web aplica as migrações automaticamente ao iniciar:

   ```bash
   docker compose up -d --build
   ```

3. Carregue os dados de demonstração:

   ```bash
   docker compose exec web python manage.py seed_demo
   ```

A aplicação fica disponível em http://localhost:8000/. O código é montado dentro do container,
então as alterações recarregam sozinhas.

| Ação | Comando |
| --- | --- |
| Subir já carregando os dados de demonstração | `SEED_DEMO=1 docker compose up -d` |
| Ver os logs | `docker compose logs -f web` |
| Rodar os testes | `docker compose run --rm web python manage.py test` |
| Criar um superusuário | `docker compose exec web python manage.py createsuperuser` |
| Abrir o shell do Django | `docker compose exec web python manage.py shell` |
| Parar | `docker compose stop` |
| Derrubar (mantém os dados) | `docker compose down` |
| Derrubar e apagar o banco | `docker compose down -v` |

O PostgreSQL também fica exposto no host em `localhost:5433` (altere com `DB_HOST_PORT`), para
ser usado por ferramentas locais ou por testes rodando fora do container.

## Como rodar localmente

Pré-requisitos: Python 3.13 e PostgreSQL 14 ou superior em execução.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Crie o banco no PostgreSQL:

```sql
CREATE DATABASE gestao_tarefas;
```

Copie o modelo de configuração e ajuste com as credenciais do seu PostgreSQL:

```bash
copy .env.example .env
```

Aplique as migrações e suba o servidor:

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

A aplicação fica disponível em http://127.0.0.1:8000/.

## Dados de demonstração

O comando `seed_demo` cria duas organizações, com projetos, sprints (a última em andamento),
tarefas com histórico de datas, subtarefas, dependências e tarefas bloqueadas, prontas para
percorrer o roteiro de teste da documentação e alimentar o dashboard. Use `--reset` para recriar
tudo. Todos os usuários têm a senha `demo1234`:

| Usuário | Organização | Papel |
| --- | --- | --- |
| `admin.labs` | Grello Labs | Administrador |
| `operador.labs` | Grello Labs | Operador |
| `admin.acme` | Acme Consultoria | Administrador |
| `operador.acme` | Acme Consultoria | Operador |

Para usar o Django Admin, crie um superusuário com `createsuperuser`. Um superusuário sem perfil
acessa o Admin normalmente, mas precisa de um perfil (criado pelo Admin) para usar as telas do
sistema.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `config/` | Configurações e roteamento raiz do projeto |
| `core/` | Organizações, perfis de acesso, isolamento por organização e permissões |
| `members/` | Domínio de membros da equipe |
| `projects/` | Domínio de projetos e sprints |
| `tasks/` | Domínio de tarefas, subtarefas e dependências |
| `dashboard/` | Métricas, gráficos, burndown e exportação CSV |
| `api/` | API REST (serializers, viewsets e permissões) |
| `templates/` | Template base, login e partials compartilhados |
| `static/` | Folha de estilos e scripts dos gráficos |
| `docker/` | Script de inicialização do container |
