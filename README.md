# Gestão de Tarefas

Sistema de gestão de tarefas com subtarefas e dependências entre tarefas, desenvolvido
em Django puro (MVT) com PostgreSQL, para a disciplina de Laboratório de Programação
Full Stack.

A documentação completa de arquitetura está em [DOCUMENTATION.md](DOCUMENTATION.md).

## Como rodar localmente

Pré-requisitos: Python 3.13 e PostgreSQL 14 ou superior em execução.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
```

Edite o `.env` com as credenciais do seu PostgreSQL e crie o banco:

```sql
CREATE DATABASE gestao_tarefas;
```

Aplique as migrações e suba o servidor:

```bash
python manage.py migrate
python manage.py runserver
```

A aplicação fica disponível em http://127.0.0.1:8000/.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `config/` | Configurações e roteamento raiz do projeto |
| `members/` | Domínio de membros da equipe |
| `projects/` | Domínio de projetos |
| `tasks/` | Domínio de tarefas, subtarefas e dependências |
| `templates/` | Template base e partials compartilhados |
| `static/` | Folha de estilos da aplicação |
