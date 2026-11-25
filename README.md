# Grello

**Grello** é um sistema de gestão de tarefas com subtarefas, dependências entre tarefas e
sprints, desenvolvido em Django (padrão MVT) com PostgreSQL para a disciplina de Laboratório de
Programação Full Stack. A P1 entregou o MVP; a P2 o transforma num mini-SaaS com várias
organizações, perfis de acesso, API REST e dashboard.

**Regra central:** uma tarefa não pode ser concluída enquanto qualquer tarefa da qual ela
depende — ou qualquer subtarefa dela — não estiver concluída. O sistema bloqueia a ação (nas telas,
no Admin e na API) e mostra exatamente quais pendências estão impedindo a conclusão.

- Documentação completa (arquitetura, modelagem, regras, API, métricas, segurança, desempenho,
  testes e roteiro de demonstração): [DOCUMENTATION.md](DOCUMENTATION.md)
- Pontos da P1 revisados para a P2: [MELHORIAS_P1.md](MELHORIAS_P1.md)

## Funcionalidades

- CRUD de projetos, sprints, membros, tarefas e subtarefas, com listagens paginadas
- Dependências entre tarefas do mesmo projeto, com detecção de ciclos
- Concluir e reabrir tarefas respeitando dependências e subtarefas, com o motivo do bloqueio
- Sprints de até 60 dias, com estado (planejada, em andamento, encerrada) e backlog
- Várias organizações na mesma base, cada uma vendo só os seus dados
- Login obrigatório, perfis de administrador e operador e limite de tentativas de login
- API REST com Django REST Framework em `/api/`
- Dashboard com KPIs, throughput, lead time, cycle time, entrega no prazo, velocity,
  burndown/burnup de sprint e exportação CSV

Stack: Python 3.13, Django 6.0.7, DRF 3.18.3, PostgreSQL 18, psycopg 3, Chart.js 4.6.2 (local),
gunicorn e WhiteNoise em produção.

## Como rodar com Docker (desenvolvimento)

Pré-requisito: Docker Desktop (ou Docker Engine com Compose v2).

```bash
cp .env.example .env                 # opcional; sem .env valem os padrões
docker compose up -d --build         # aplica as migrações ao subir
docker compose exec web python manage.py seed_demo
```

A aplicação fica em http://localhost:8000/. O código é montado dentro do container, então as
alterações recarregam sozinhas. Dentro do Compose, o serviço web sempre se conecta em `db:5432`,
independentemente do `DB_HOST`/`DB_PORT` do `.env`.

| Ação | Comando |
| --- | --- |
| Subir já carregando os dados de demonstração | `SEED_DEMO=1 docker compose up -d` |
| Recriar os dados de demonstração | `docker compose exec web python manage.py seed_demo --reset` |
| Ver os logs | `docker compose logs -f web` |
| Rodar os testes | `docker compose run --rm web python manage.py test` |
| Criar um superusuário | `docker compose exec web python manage.py createsuperuser` |
| Parar | `docker compose stop` |
| Derrubar (mantém os dados) | `docker compose down` |
| Derrubar e apagar o banco | `docker compose down -v` |

O PostgreSQL também fica exposto no host em `127.0.0.1:5433` (altere com `DB_HOST_PORT`), só nesse
endereço. No Windows, para conectar do host use `DB_HOST=127.0.0.1` e `DB_PORT=5433` — com
`localhost` o cliente pode tentar o IPv6 primeiro e travar.

## Produção

O `compose.prod.yml` sobe a imagem de produção (gunicorn + WhiteNoise, `DEBUG` desligado, banco sem
porta publicada e health check em `/health/`): copie `.env.prod.example` para `.env.prod`, defina
`DJANGO_SECRET_KEY`, `DB_PASSWORD` e o domínio, e rode
`docker compose -f compose.prod.yml --env-file .env.prod up -d --build`. Em produção real o serviço
fica atrás de um proxy reverso que termina o HTTPS. Detalhes e a lista de variáveis na
[seção 15 da documentação](DOCUMENTATION.md#15-como-rodar).

## Como rodar localmente

Pré-requisitos: Python 3.13 e PostgreSQL 14 ou superior (ou o PostgreSQL do Docker em
`127.0.0.1:5433`).

```bash
python -m venv .venv
.venv\Scripts\activate               # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env               # Linux/macOS: cp; ajuste as variáveis DB_*
```

Crie o banco (`CREATE DATABASE gestao_tarefas;`), aplique as migrações e suba o servidor:

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

A aplicação fica em http://127.0.0.1:8000/. Mantenha `DJANGO_DEBUG=True` no `.env` em
desenvolvimento: sem ele o sistema roda em modo de produção e exige `DJANGO_SECRET_KEY` e HTTPS.

## Dados de demonstração

O `seed_demo` cria duas organizações com projetos, sprints (a última em andamento), tarefas com
histórico de datas, subtarefas, dependências e tarefas bloqueadas, prontas para o roteiro de
demonstração da documentação e para alimentar o dashboard. Use `--reset` para recriar tudo. O
comando só roda com `DJANGO_DEBUG=True`. Todos os usuários têm a senha `demo1234`:

| Usuário | Organização | Papel |
| --- | --- | --- |
| `admin.labs` | Grello Labs | Administrador |
| `operador.labs` | Grello Labs | Operador |
| `admin.acme` | Acme Consultoria | Administrador |
| `operador.acme` | Acme Consultoria | Operador |

Para usar o Django Admin, crie um superusuário com `createsuperuser`. Um superusuário sem perfil
acessa o Admin normalmente, mas precisa de um perfil (criado pelo Admin) para usar as telas do
sistema.

## Testes e cobertura

São 348 testes automatizados, com 98% de cobertura de linhas.

```bash
pip install -r requirements-dev.txt
python manage.py test
coverage run manage.py test
coverage report
```

Com o banco do Docker de desenvolvimento, a partir do host: `DB_HOST=127.0.0.1 DB_PORT=5433 python
manage.py test`.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `config/` | Configurações e roteamento raiz do projeto |
| `core/` | Organizações, perfis de acesso, isolamento por organização, permissões, limite de login e health check |
| `members/` | Domínio de membros da equipe |
| `projects/` | Domínio de projetos e sprints |
| `tasks/` | Domínio de tarefas, subtarefas e dependências; comando `seed_demo` |
| `dashboard/` | Métricas, gráficos, burndown/burnup, API do dashboard e exportação CSV |
| `api/` | API REST (serializers, viewsets, permissões e paginação) |
| `templates/` | Template base, login, páginas de erro e partials compartilhados |
| `static/` | Folha de estilos, Chart.js e o script dos gráficos |
| `docker/` | Script de inicialização do container |
