# Relatório referente as Features solicitadas para conclusão da entrega da P1 de Laboratório Fullstack

## Feature 1 
- Já havia implementado esta Feature no projeto, a pesquisa por filtro que eu fiz não utiliza um campo de busca por texto, ela da ao usuário um campo com os projetos disponiveis que ele pode selecionar e tambem o status da `task`. O usuario seleciona o projeto que deseja e, se quiser, o status das ``tasks`` referentes aquele projeto e clica em filtrar, então é feito um ``.get`` com o id do projeto e status da task e entrega os dados relevantes da task como nome da task, nome de quem foi designado para ela, status, prazo de entrega, dependencia, etc, alem de dar a opção tambem de concluir/reabrir, editar ou excluir a tarefa.

## Feature 2
- Segui a recomendação e fiz um método ``clean()`` no ``forms.py`` das ``tasks`` que compara a data que o projeto foi criado com a data do prazo de conclusão da tarefa. Caso a data de conclusão da ``task`` seja menor do que a data de criação do ``project``, a criação é bloqueada e uma mensagem de erro aparece para o usuário.