# Melhorias da P1

Revisão da entrega P1 do **Grello** antes de iniciar a P2. Cada item descreve uma fragilidade
encontrada no MVP e como ela é tratada na etapa avançada: tudo que a API e o dashboard
expuserem herda o que o model já faz, então os pontos frágeis precisam ser corrigidos antes.

| # | Item | Situação |
| - | ---- | -------- |
| 1 | Sem autenticação nem controle de acesso | Corrigido na P2 |
| 2 | E-mail de membro único no banco inteiro | Corrigido na P2 |
| 3 | Nenhum teste automatizado | Corrigido na P2 |
| 4 | Configuração insegura por padrão | Pendente (Fase 5) |
| 5 | Listagens sem paginação | Pendente (Fase 6) |

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

**Plano:** inverter os padrões (`DEBUG` falso e erro ao iniciar sem `SECRET_KEY` fora do modo de
desenvolvimento) e ativar as configurações de segurança do Django na etapa de segurança e testes.

## 5. Listagens sem paginação

As listagens de projetos, tarefas e membros carregam todos os registros de uma vez. Com o volume
de um trabalho acadêmico não faz diferença, mas a API e o crescimento das organizações tornam isso
um problema.

**Plano:** `paginate_by` nas `ListView` e paginação padrão na API, na etapa de polimento.
