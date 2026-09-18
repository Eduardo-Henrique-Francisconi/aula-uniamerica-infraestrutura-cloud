# Relatório de testes — Observabilidade (Entrega 2)

**Gerado em:** 2026-09-18 18:04:35 UTC (2026-09-18 15:04:35 America/Sao_Paulo)
**Dashboard:** `todo-app-observabilidade` (CloudWatch, região `us-east-2`)

Todos os cenários abaixo rodam automaticamente (`python observabilidade_testes.py`), sem nenhum passo manual — inclusive o teste de failover do front-end e a captura das imagens do dashboard.

## Resumo

| # | Verificação | Resultado |
|---|---|---|
| 1 | Uso normal pelo domínio (front-end → back-end → banco) | PASS |
| 2 | Canário de disponibilidade (invocação manual) | PASS |
| 3 | Falha controlada (`GET /todos-falha-simulada` → sempre 500) | PASS |
| 4 | Failover do front-end com o canário rodando durante a queda | PASS |
| 5 | Métricas nativas do CloudWatch têm dado real | PASS |
| 6 | Logs Insights confirmam a falha controlada e o estado do banco | PASS |
| 7 | Capturas automáticas dos widgets do dashboard (GetMetricWidgetImage) | PASS |

**7/7 verificações passaram.**

## Validação painel a painel

| Painel | Cenário que o valida | Resultado esperado | Resultado observado |
|---|---|---|---|
| 1 — Disponibilidade | Cenários 2 e 4: canário invocado manualmente e de novo durante a queda do bucket primário | Duas checagens por execução (`frontend` e `api`) com `result=success`, e a série `AvailabilitySuccess` recebendo os pontos | PASS — ver verificações 2, 4 e 5 |
| 2 — Desempenho | Cenário 1: 15 GET + 15 POST + PATCH/DELETE pelo domínio | Métrica `Latency` publicada por rota, com pontos no período do teste | PASS — ver verificações 1 e 5 |
| 3 — Erros | Cenário 3: 8 chamadas à rota de falha simulada | 8 erros 5xx na rota `/todos-falha-simulada`, visíveis na série por rota e na tabela de causas | PASS — ver verificações 3 e 6 |
| 4 — Banco de Dados | Cenário 1: operações reais no DynamoDB (Scan, Put, Update, Delete) | Latência por operação e RCU/WCU consumidas com dados reais; tabela de falhas vazia (banco saudável) | PASS — ver verificações 1, 5 e 6 |

Um mesmo cenário valida mais de um painel porque o tráfego do Cenário 1 percorre a cadeia inteira (domínio → Cloudflare → API Gateway → Lambda → DynamoDB): a mesma requisição gera, ao mesmo tempo, a métrica de latência do API Gateway (Painel 2) e as métricas do DynamoDB (Painel 4).

## Rastreabilidade: do evento na aplicação até o painel

1. **Evento na aplicação** — uma requisição chega ao `TodoFunction`, que escreve uma linha JSON em `stdout` (exemplo mais abaixo).
2. **Coleta** — a AWS envia automaticamente o `stdout` do Lambda para o CloudWatch Logs, sem agente.
3. **Armazenamento** — a linha fica no log group `/aws/lambda/<função>`, com retenção de 30 dias.
4. **Consulta** — o widget roda a query de Logs Insights sobre esse log group (as mesmas queries reproduzidas na verificação 6).
5. **Painel** — o resultado aparece no dashboard `todo-app-observabilidade`; as imagens em `evidencias_observabilidade/` foram capturadas no período destes testes.

Em paralelo, a mesma requisição faz o API Gateway publicar `Latency`/`Count`/`5xxError` direto no CloudWatch Metrics, sem passar por log — por isso os Painéis 2 e 3 têm duas fontes.

## Detalhe (verificação a verificação)

### 1. Uso normal pelo domínio (front-end → back-end → banco) — PASS

Início: 2026-09-18 17:59:53 UTC (2026-09-18 14:59:53 America/Sao_Paulo) · Fim: 2026-09-18 18:00:30 UTC (2026-09-18 15:00:30 America/Sao_Paulo)
15 GET + 15 POST + 5 PATCH + 15 DELETE em `https://api.neshiku.com.br/todos`.
Requisições com status inesperado: 0.
Exercita GetTodos (Scan), PutTodo, UpdateTodo e DeleteTodo no DynamoDB pelo caminho real (domínio → Cloudflare → API Gateway → Lambda → DynamoDB).

### 2. Canário de disponibilidade (invocação manual) — PASS

Invocação 1 em 2026-09-18 18:00:42 UTC (2026-09-18 15:00:42 America/Sao_Paulo) → `{'checked': 2}`
Invocação 2 em 2026-09-18 18:00:47 UTC (2026-09-18 15:00:47 America/Sao_Paulo) → `{'checked': 2}`

`checked` deve ser 2 (frontend + api) em cada invocação.

### 3. Falha controlada (`GET /todos-falha-simulada` → sempre 500) — PASS

Início: 2026-09-18 18:00:52 UTC (2026-09-18 15:00:52 America/Sao_Paulo) · Fim: 2026-09-18 18:00:57 UTC (2026-09-18 15:00:57 America/Sao_Paulo)
Status recebidos: [500, 500, 500, 500, 500, 500, 500, 500]
Cada chamada gera 1 log `http_request` com `status_code=500` e `route="/todos-falha-simulada"` no TodoFunction, e é contada como `5xxError` nativo do API Gateway para essa rota.

### 4. Failover do front-end com o canário rodando durante a queda — PASS

Derrubando o bucket primário `todo-app-neshiku-frontend-1` (mv index.html → index.html.bak) em 2026-09-18 18:00:57 UTC (2026-09-18 15:00:57 America/Sao_Paulo)
`GET https://app.neshiku.com.br` durante a queda → status 200 (OK, serviu pelo bucket secundário)
Canário invocado durante a queda em 2026-09-18 18:01:10 UTC (2026-09-18 15:01:10 America/Sao_Paulo) → `{'checked': 2}`
Log do canário logo após a invocação: `{'@timestamp': '2026-09-18 18:01:11.072', 'target': 'frontend', 'result': 'success', 'http_status': '200', '@ptr': 'hotstore:MDA1MDQyNzA2OTMxOi9hd3MvbGFtYmRhL3NhbS1hcHAtSGVhbHRoQ2hlY2tGdW5jdGlvbi1CbGhRb0s4QmZqOFAfMTc4OTc1NDQ3OR8xNzg5NzU0NDc5ODcwHzY1MDAyNTg3ODE0NjAyOTAyNh8xHzE3ODk3NTQ0NzEwNzI='}`
Bucket primário restaurado com sucesso em 2026-09-18 18:01:31 UTC (2026-09-18 15:01:31 America/Sao_Paulo).

Resultado: front-end acessível durante a queda = True; canário confirmou `frontend`/`success` durante a queda = True.

### 5. Métricas nativas do CloudWatch têm dado real — PASS

Período consultado: 2026-09-18 17:43:01 a 2026-09-18 18:03:01 UTC (últimos 20 min)

| Verificação | Métrica | Total/valor | Datapoints |
|---|---|---|---|
| Disponibilidade — sucesso (api) | TodoApp/Availability/AvailabilitySuccess (Sum) | 10.00 | 4 |
| Disponibilidade — sucesso (frontend) | TodoApp/Availability/AvailabilitySuccess (Sum) | 10.00 | 4 |
| Erros — taxa agregada (5xxError) | AWS/ApiGateway/5xxError (Sum) | 0.00 | 0 |
| Banco de Dados — latência do Scan | AWS/DynamoDB/SuccessfulRequestLatency (Average) | 26.58 | 4 |
| Banco de Dados — capacidade lida (RCU) | AWS/DynamoDB/ConsumedReadCapacityUnits (Sum) | 100.00 | 4 |

### 6. Logs Insights confirmam a falha controlada e o estado do banco — PASS

**5xx por rota ao longo do tempo:**
| Período | Rota | Erros |
|---|---|---|
| 2026-09-18 17:45:00.000 | /todos-falha-simulada | 8 |
| 2026-09-18 18:00:00.000 | /todos-falha-simulada | 8 |

**Causas de erro (rotas/status >= 400):**
| Rota | Status | Ocorrências |
|---|---|---|
| /todos-falha-simulada | 500 | 16 |

**Falhas de acesso ao banco vistas pelo back-end:**
0 falhas — esperado (o cenário de falha controlada não passa pelo banco; banco saudável).

### 7. Capturas automáticas dos widgets do dashboard (GetMetricWidgetImage) — PASS

Imagens salvas em `evidencias_observabilidade/`:
- evidencias_observabilidade\01-checagens-sintéticas---sucesso-x-falha--soma-por-período-de-.png
- evidencias_observabilidade\02-latência-da-checagem-sintética--ms--média-por-período.png
- evidencias_observabilidade\04-latência-por-rota--api-gateway----p50-e-p95--ms.png
- evidencias_observabilidade\06-taxa-de-erro-agregada-da-api.png
- evidencias_observabilidade\10-latência-das-operações-no-dynamodb--ms--média.png
- evidencias_observabilidade\11-capacidade-consumida-no-dynamodb--rcu---wcu.png

## Exemplo de registro real (log → painel)

Uma linha real de log `http_request`, como aparece no CloudWatch Logs:

```json
2026-09-18T17:46:47.601Z	30dbebdc-c0c1-4175-b8ea-d983c80dd3d7	INFO	{"timestamp":"2026-09-18T17:46:47.601Z","service":"todo-backend","environment":"production","level":"info","event":"http_request","request_id":"Root=1-6aad7907-4a7c814c6c3b94f7748f0d60","method":"GET","route":"/todos","status_code":200,"duration_ms":181}
```

Essa linha alimenta ao mesmo tempo as métricas nativas do API Gateway (Desempenho, Erros) e a consulta de Logs Insights do painel de Erros.

## Inventário do ambiente (conferência do diagrama)

Consultado diretamente na AWS no momento deste relatório. Serve para conferir, recurso a recurso, que o diagrama representa o ambiente que está no ar. Não é um teste, e por isso não entra na contagem de verificações acima.

| Elemento | Onde aparece no diagrama | Valor real na AWS |
|---|---|---|
| Distribuicao CloudFront | caixa Amazon CloudFront | `E107CAQRHXIBU9` |
| Dominio do CloudFront | destino do CNAME app | `d2q2k05w0uyq82.cloudfront.net` |
| Alternate domain | app.neshiku.com.br | `app.neshiku.com.br` |
| Origens configuradas | os dois buckets S3 | `todo-app-neshiku-frontend-2.s3.us-west-2.amazonaws.com, todo-app-neshiku-frontend-1.s3.us-east-2.amazonaws.com-mu49zjaihyw` |
| Origin groups (failover) | mecanismo de distribuicao | `1 grupo(s)` |
| API Gateway (ApiId) | caixa Amazon API Gateway | `vfb3b537c6` |
| Rotas explicitas | 5 rotas explicitas | `GET /todos-falha-simulada · GET /todos · PATCH /todos/{id} · POST /todos · DELETE /todos/{id}` |
| Custom domain da API | api.neshiku.com.br | `api.neshiku.com.br` |
| Target do CNAME api | destino do CNAME api | `d-rzvh9g1a2d.execute-api.us-east-2.amazonaws.com` |
| Lambda do back-end | caixas AWS Lambda | `sam-app-TodoFunction-ZBJ9ee0dV1L9` |
| Lambda do canario | caixas AWS Lambda | `sam-app-HealthCheckFunction-BlhQoK8Bfj8P` |
| Tabela DynamoDB | caixa Amazon DynamoDB | `todos-table` |
| Modo de cobranca | PAY_PER_REQUEST | `PAY_PER_REQUEST` |
| Chave primaria | PK: id (String) | `id (HASH)` |
| Bucket primario | caixas Amazon S3 | `todo-app-neshiku-frontend-1 — regiao us-east-2 — Block Public Access: ativo` |
| Bucket secundario | caixas Amazon S3 | `todo-app-neshiku-frontend-2 — regiao us-west-2 — Block Public Access: ativo` |
| Agendamento do canario | caixa Amazon EventBridge | `todo-app-healthcheck-schedule — rate(5 minutes) — estado ENABLED` |
| Log group do back-end | caixas CloudWatch Logs | `/aws/lambda/sam-app-TodoFunction-ZBJ9ee0dV1L9 — retencao: 30 dias` |
| Log group do canario | caixas CloudWatch Logs | `/aws/lambda/sam-app-HealthCheckFunction-BlhQoK8Bfj8P — retencao: 30 dias` |
| Dashboard | caixa CloudWatch Dashboard | `todo-app-observabilidade` |
| Paineis publicados | os 4 paineis | `Painel 1 — Disponibilidade · Painel 2 — Desempenho · Painel 3 — Erros · Painel 4 — Banco de Dados` |

## Conclusão

7/7 verificações passaram, todas com dados reais consultados no CloudWatch depois de gerar tráfego real, invocar o canário, provocar a falha controlada e derrubar o bucket primário do front-end. As imagens dos widgets de métrica foram salvas automaticamente em `evidencias_observabilidade/` — anexe essa pasta e este relatório à entrega.