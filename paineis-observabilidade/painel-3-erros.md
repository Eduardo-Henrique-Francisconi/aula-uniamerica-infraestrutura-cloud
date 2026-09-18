# Painel 3 — Erros

**Aplicação:** Todo App · **Dashboard:** `todo-app-observabilidade` (CloudWatch, região `us-east-2`)
**API monitorada:** `api.neshiku.com.br` (API Gateway HTTP API `TodoHttpApi` + logs do Lambda `TodoFunction`)

---

## 1. Nome e pergunta operacional

**Erros** — quais falhas estão ocorrendo na API, e qual parcela das requisições elas representam?

## 2. Motivo da escolha

É o indicador mais direto de "algo está quebrado" — sem ele, um erro só é percebido se um usuário avisar. Também é o painel usado para comprovar o cenário de falha controlada exigido pela atividade (a rota `GET /todos-falha-simulada`, que sempre retorna 500).

## 3. Origem dos dados

Duas fontes combinadas:

1. As métricas nativas `4xxError`/`5xxError`/`Count` do API Gateway (namespace `AWS/ApiGateway`), agregadas para toda a API — usadas na taxa de erro geral, publicadas automaticamente pelo serviço.
2. Os logs estruturados `http_request` do `TodoFunction` (campos `route` e `status_code`), consultados via CloudWatch Logs Insights, tanto para a série de 5xx por rota ao longo do tempo quanto para a tabela de causas — informação que a métrica nativa, por si só, não separa por rota nem por causa.

**Nota sobre uma mudança de fonte de dado.** O widget "5xx por rota" foi inicialmente implementado com a métrica nativa `5xxError` dimensionada por `Resource`+`Method` (o equivalente nativo do "por rota" no API Gateway HTTP API). Nos testes reais (chamadas repetidas a `/todos-falha-simulada`, com 500 confirmado via status HTTP), essa combinação específica de métrica+dimensões nunca publicou nenhum datapoint — mesmo consultando a API do CloudWatch diretamente, sem passar pelo catálogo de `list-metrics` (que tem um atraso de propagação próprio) — ao contrário da métrica `Latency` com as mesmas dimensões, que funcionou normalmente. Não foi possível confirmar a causa exata (suspeita: atraso ou particularidade da AWS na publicação de `5xxError` para uma combinação nova de dimensões). Como o backend já registra a mesma informação (rota + status) em log estruturado, o widget foi trocado para uma consulta de Logs Insights — fonte igualmente legítima e, neste caso, mais confiável.

## 4. Consulta e cálculo

**Widget 1 (taxa agregada):** `100 * (Sum(5xxError) + Sum(4xxError)) / Sum(Count)` — uma expressão de métrica calculada sobre toda a API. Unidade: porcentagem. Numerador: soma das requisições com erro (cliente + servidor) no período. Denominador: total de requisições no mesmo período.

**Widget 2 (5xx por rota ao longo do tempo, Logs Insights):**

```
fields @timestamp, route, status_code
| filter event = "http_request" and status_code >= 500
| stats count() as erros by bin(5m) as periodo, route
| sort periodo asc
```

**Widget 3 (causas, Logs Insights):**

```
fields @timestamp, route, status_code, request_id
| filter event = "http_request" and status_code >= 400
| stats count() as ocorrencias by route, status_code
| sort ocorrencias desc
```

## 5. Recorte temporal

Período de agregação de 5 minutos para o widget de métrica (taxa agregada). As duas consultas de Logs Insights rodam sobre a janela de tempo escolhida no dashboard (padrão 3h) no momento em que o painel é aberto/atualizado — a de "5xx por rota ao longo do tempo" agrupa essa janela em blocos de 5 min (`bin(5m)`) para se comportar como uma série temporal; a de "causas" é uma "foto" agregada da janela inteira, sem quebra por tempo.

## 6. Forma de visualização

Série temporal para a taxa agregada e para os 5xx por rota ao longo do tempo (para ver tendência e localizar onde os erros de servidor se concentram); tabela (Logs Insights) para a lista de causas — uma tabela é melhor aqui porque a pergunta é "quais", não "quando".

## 7. Interpretação

Esperado: taxa de erro perto de 0% na maior parte do tempo, subindo apenas quando há uma falha real (como no teste de falha controlada) ou um erro de uso genuíno (ex.: `POST /todos` sem o campo `text`, que devolve 400 — esperado, e não é um "bug"). Um pico isolado que desaparece sozinho tende a ser transitório; um platô alto e constante indica uma regressão no código ou uma dependência (DynamoDB, Cloudflare) com problema real.

## 8. Critérios de atenção

Qualquer `5xx` real (erro de servidor) é motivo de olhar a causa — o objetivo é 0% de 5xx fora de testes deliberados. Para `4xx`, como parte é uso normal da aplicação (campo obrigatório faltando, tarefa não encontrada), o critério de atenção é uma **mudança de padrão** (um 4xx que nunca ocorria e passa a ocorrer com frequência), não um número fixo — ainda não há dado histórico suficiente para um limite quantitativo confiável nesta atividade acadêmica.

## 9. Ação decorrente

Um pico de 5xx concentrado numa única rota → olhar o Painel 4 (o erro provavelmente vem do DynamoDB) e os logs `db_operation` com `result = "failure"`. Um pico de 5xx espalhado por todas as rotas → suspeitar do runtime do Lambda (erro de configuração, falta de memória) ou de throttling de conta, não de uma rota específica.

## 10. Validação e limitações

**Teste:** 8 chamadas repetidas a `GET /todos-falha-simulada` (rota que sempre devolve 500), via o script automático `observabilidade_testes.py`.
**Resultado esperado:** as 8 chamadas aparecerem tanto no widget "5xx por rota" quanto na consulta de causas, com `route = "/todos-falha-simulada"` e `status_code = 500`.
**Resultado observado:** confirmado — ver `relatorio_testes_observabilidade.md`: 8 erros contabilizados na consulta de "5xx por rota", e a mesma rota/status aparecendo na tabela de causas.

**O que os dados não permitem concluir:** a consulta de causas olha só os logs do `TodoFunction` — um erro de infraestrutura que aconteça **antes** do Lambda ser executado (por exemplo, o próprio API Gateway rejeitando a requisição por throttling de conta) não geraria uma linha nesse log, só a métrica nativa de erro do API Gateway (Widget 1). Por isso os dois widgets são complementares, não substituíveis um pelo outro.

## Alcance (o que este painel observa e o que não observa)

Observa: erros HTTP (4xx/5xx) que chegam ao Lambda `TodoFunction` através do API Gateway, e a taxa agregada de erro de toda a API. Não observa: erros de JavaScript que ocorram só no navegador do usuário (exceções do lado do cliente, no React), nem eventuais bloqueios feitos pela Cloudflare antes da requisição chegar ao API Gateway — esses não passam pelo `TodoFunction` e não aparecem em nenhum dos três widgets.

## Como interpretar um período sem dados neste painel

Aqui é preciso um cuidado extra em relação aos outros painéis: quando **não há nenhuma requisição** num período de 5 minutos, o denominador da taxa de erro (`Count`) é zero — nesse caso o widget de taxa agregada não mostra "0%", mostra **ausência de ponto**, porque uma divisão por zero não produz um valor plotável. Isso não significa "0% de erro" nem "sistema com problema": significa apenas que não houve tráfego naquele intervalo. Já um "buraco" no widget de "5xx por rota" ou na tabela de causas, quando há tráfego normal acontecendo, é o resultado esperado (sem 5xx/4xx no período) — não indica falha de coleta.
