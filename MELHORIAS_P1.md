# Melhorias da P1

Revisão da entrega P1 do **Grello** antes de iniciar a P2. Cada item descreve uma fragilidade
encontrada no MVP e como ela é tratada na etapa avançada: tudo que a API e o dashboard
expuserem herda o que o model já faz, então os pontos frágeis precisam ser corrigidos antes.

| # | Item | Situação |
| - | ---- | -------- |
| 1 | Sem autenticação nem controle de acesso | Corrigido na P2 |
| 2 | E-mail de membro único no banco inteiro | Corrigido na P2 |
| 3 | Nenhum teste automatizado | Corrigido na P2 |
| 4 | Configuração insegura por padrão | Corrigido na P2 |
| 5 | Listagens sem paginação | Corrigido na P2 |

## 1. Sem autenticação nem controle de acesso

Qualquer pessoa com acesso à aplicação podia criar, editar e excluir qualquer registro, e todas
as consultas usavam `.objects.all()`. Num sistema com várias organizações, isso significaria uma
organização enxergando os dados da outra.

**Correção:** login obrigatório em todas as telas (`LoginRequiredMiddleware`), model
`Organization` com FK em `Project` e `Member`, `Profile` ligando cada usuário a uma organização e a
um papel (administrador ou operador), e todas as views e formulários filtrando pela organização
do usuário logado.

## 2. E-mail de membro único no banco inteiro

`Member.email` tinha `unique=True`. Com várias organizações, a segunda empresa não conseguiria
cadastrar uma pessoa cujo e-mail já existisse em outra.

**Correção:** `UniqueConstraint(organization, email)` no banco e a checagem de duplicado no
`clean_email()` do `MemberForm`, já que a organização não faz parte do formulário.

## 3. Nenhum teste automatizado

As seis regras de bloqueio da conclusão eram verificadas apenas pelo roteiro manual da
documentação. Qualquer mudança nos models (como a FK de organização) poderia quebrá-las sem aviso.

**Correção:** suíte de testes com as regras da P1, o isolamento entre organizações, os papéis, a
API e as métricas do dashboard.

## 4. Configuração insegura por padrão

`DJANGO_DEBUG` assume `True` e `DJANGO_SECRET_KEY` tem um valor de desenvolvimento quando a
variável não está definida. Esquecer o `.env` em produção deixaria o sistema com o modo debug
ligado e uma chave conhecida.

**Correção:** `DEBUG` agora é falso quando a variável não está definida, e o sistema se recusa a
iniciar sem `DJANGO_SECRET_KEY` fora do modo de desenvolvimento. Em produção, os cookies só
trafegam por HTTPS, o HTTP é redirecionado para HTTPS e o HSTS pode ser ligado por variável de
ambiente. O `manage.py check --deploy` passa sem avisos com a configuração de produção, e
testes automatizados garantem esse comportamento. O Docker Compose, que é de desenvolvimento,
continua com `DEBUG` ligado por padrão.

## 5. Listagens sem paginação

As listagens de projetos, tarefas e membros carregam todos os registros de uma vez. Com o volume
de um trabalho acadêmico não faz diferença, mas a API e o crescimento das organizações tornam isso
um problema.

**Correção:** as listas de projetos (12 por página), membros (20) e tarefas (25) são paginadas,
mantendo os filtros nos links de página, e uma página inválida mostra a primeira ou a última em
vez de dar erro. A API devolve as listas no formato `{"count", "next", "previous", "results"}`,
com 50 itens por padrão e `?page_size=` até 200.
