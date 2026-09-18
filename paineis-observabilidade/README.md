# Fundamentação dos painéis — dashboard `todo-app-observabilidade`

Um documento por painel, cada um cobrindo os 10 itens exigidos pela atividade
(nome e pergunta operacional, motivo da escolha, origem dos dados, consulta e
cálculo, recorte temporal, forma de visualização, interpretação, critérios de
atenção, ação decorrente, validação e limitações), além de duas seções
extras em cada arquivo: **alcance** (o que o painel observa e o que fica de
fora) e **como interpretar um período sem dados** (para não confundir
ausência de coleta com ausência de erro/funcionamento normal).

| Painel | Pergunta operacional | Arquivo |
|---|---|---|
| 1 — Disponibilidade | O domínio (front-end e API) está acessível pelo domínio configurado? | [`painel-1-disponibilidade.md`](painel-1-disponibilidade.md) |
| 2 — Desempenho | Quais operações da API estão demorando mais, e em quais períodos? | [`painel-2-desempenho.md`](painel-2-desempenho.md) |
| 3 — Erros | Quais falhas estão ocorrendo, e qual parcela das requisições elas representam? | [`painel-3-erros.md`](painel-3-erros.md) |
| 4 — Banco de Dados | As operações do back-end com o DynamoDB estão funcionando, e com qual duração? | [`painel-4-banco-de-dados.md`](painel-4-banco-de-dados.md) |

Esta pasta é a fundamentação canônica de cada painel — o resumo que aparece
na Seção 2 de `../documentacao-observabilidade.md` remete pra cá para o
detalhe completo. As evidências reais de teste de cada painel estão em
`../relatorio_testes_observabilidade.md` e `../evidencias_observabilidade/`
(gerados automaticamente por `../observabilidade_testes.py`).
