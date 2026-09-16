# Gestão de Tarefas

Sistema de gestão de tarefas com subtarefas e dependências entre tarefas, desenvolvido em
Django puro (padrão MVT) com PostgreSQL, para a disciplina de Laboratório de Programação
Full Stack.

**Regra central:** uma tarefa não pode ser concluída enquanto qualquer tarefa da qual ela
depende — ou qualquer subtarefa dela — não estiver concluída. O sistema bloqueia a ação e
mostra exatamente quais pendências estão impedindo a conclusão.

A documentação completa de arquitetura, modelagem e implementação está em
[DOCUMENTATION.md](DOCUMENTATION.md).

## Funcionalidades

- CRUD de projetos, membros, tarefas e subtarefas
- Definição de dependências entre tarefas do mesmo projeto
- Ação de concluir tarefa com validação das dependências e das subtarefas em aberto
- Ação de reabrir tarefa, respeitando a mesma ordem
- Listagem de tarefas com filtros e indicação visual das tarefas bloqueadas
- Detecção de ciclos no grafo de dependências

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

O comando `seed_demo` é opcional e cria um projeto de demonstração já com dependências e
tarefas bloqueadas, pronto para percorrer o roteiro de teste da documentação.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `config/` | Configurações e roteamento raiz do projeto |
| `members/` | Domínio de membros da equipe |
| `projects/` | Domínio de projetos |
| `tasks/` | Domínio de tarefas, subtarefas e dependências |
| `templates/` | Template base e partials compartilhados |
| `static/` | Folha de estilos da aplicação |
