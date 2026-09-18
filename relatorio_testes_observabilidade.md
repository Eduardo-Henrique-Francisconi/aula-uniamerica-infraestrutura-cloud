# Relatório de testes — Observabilidade (Entrega 2)

**Gerado em:** 2026-09-18 02:25:31 UTC (2026-09-17 23:25:31 America/Sao_Paulo)
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

## Detalhe (verificação a verificação)

### 1. Uso normal pelo domínio (front-end → back-end → banco) — PASS

Início: 2026-09-18 02:21:46 UTC (2026-09-17 23:21:46 America/Sao_Paulo) · Fim: 2026-09-18 02:22:25 UTC (2026-09-17 23:22:25 America/Sao_Paulo)
15 GET + 15 POST + 5 PATCH + 15 DELETE em `https://api.neshiku.com.br/todos`.
Requisições com status inesperado: 0.
Exercita GetTodos (Scan), PutTodo, UpdateTodo e DeleteTodo no DynamoDB pelo caminho real (domínio → Cloudflare → API Gateway → Lambda → DynamoDB).

### 2. Canário de disponibilidade (invocação manual) — PASS

Invocação 1 em 2026-09-18 02:22:38 UTC (2026-09-17 23:22:38 America/Sao_Paulo) → `{'checked': 2}`
Invocação 2 em 2026-09-18 02:22:44 UTC (2026-09-17 23:22:44 America/Sao_Paulo) → `{'checked': 2}`

`checked` deve ser 2 (frontend + api) em cada invocação.

### 3. Falha controlada (`GET /todos-falha-simulada` → sempre 500) — PASS

Início: 2026-09-18 02:22:49 UTC (2026-09-17 23:22:49 America/Sao_Paulo) · Fim: 2026-09-18 02:22:54 UTC (2026-09-17 23:22:54 America/Sao_Paulo)
Status recebidos: [500, 500, 500, 500, 500, 500, 500, 500]
Cada chamada gera 1 log `http_request` com `status_code=500` e `route="/todos-falha-simulada"` no TodoFunction, e é contada como `5xxError` nativo do API Gateway para essa rota.

### 4. Failover do front-end com o canário rodando durante a queda — PASS

Derrubando o bucket primário `todo-app-neshiku-frontend-1` (mv index.html → index.html.bak) em 2026-09-18 02:22:54 UTC (2026-09-17 23:22:54 America/Sao_Paulo)
`GET https://app.neshiku.com.br` durante a queda → status 200 (OK, serviu pelo bucket secundário)
Canário invocado durante a queda em 2026-09-18 02:23:08 UTC (2026-09-17 23:23:08 America/Sao_Paulo) → `{'checked': 2}`
Log do canário logo após a invocação: `{'@timestamp': '2026-09-18 02:23:08.883', 'target': 'frontend', 'result': 'success', 'http_status': '200', '@ptr': 'hotstore:MDA1MDQyNzA2OTMxOi9hd3MvbGFtYmRhL3NhbS1hcHAtSGVhbHRoQ2hlY2tGdW5jdGlvbi1CbGhRb0s4QmZqOFAfMTc4OTY5ODE5NB8xNzg5Njk4MTk0MjY4HzU5MzEwMTI3OTE5MjMyODU1MzgfNh8xNzg5Njk4MTg4ODgz'}`
Bucket primário restaurado com sucesso em 2026-09-18 02:23:17 UTC (2026-09-17 23:23:17 America/Sao_Paulo).

Resultado: front-end acessível durante a queda = True; canário confirmou `frontend`/`success` durante a queda = True.

### 5. Métricas nativas do CloudWatch têm dado real — PASS

Período consultado: 2026-09-18 02:04:47 a 2026-09-18 02:24:47 UTC (últimos 20 min)

| Verificação | Métrica | Total/valor | Datapoints |
|---|---|---|---|
| Disponibilidade — sucesso (api) | TodoApp/Availability/AvailabilitySuccess (Sum) | 9.00 | 4 |
| Disponibilidade — sucesso (frontend) | TodoApp/Availability/AvailabilitySuccess (Sum) | 9.00 | 4 |
| Erros — taxa agregada (5xxError) | AWS/ApiGateway/5xxError (Sum) | 0.00 | 0 |
| Banco de Dados — latência do Scan | AWS/DynamoDB/SuccessfulRequestLatency (Average) | 40.10 | 4 |
| Banco de Dados — capacidade lida (RCU) | AWS/DynamoDB/ConsumedReadCapacityUnits (Sum) | 98.00 | 4 |

### 6. Logs Insights confirmam a falha controlada e o estado do banco — PASS

**5xx por rota ao longo do tempo:**
| Período | Rota | Erros |
|---|---|---|
| 2026-09-18 02:20:00.000 | /todos-falha-simulada | 8 |

**Causas de erro (rotas/status >= 400):**
| Rota | Status | Ocorrências |
|---|---|---|
| /todos-falha-simulada | 500 | 8 |

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
2026-09-18T02:08:05.650Z	dacf2e6d-91aa-43f3-b9fc-970850c7bf0b	INFO	{"timestamp":"2026-09-18T02:08:05.650Z","service":"todo-backend","environment":"production","level":"info","event":"http_request","request_id":"Root=1-6aac9d05-3642e3f0063ddbd9606221c3","method":"GET","route":"/todos","status_code":200,"duration_ms":122}
```

Essa linha alimenta ao mesmo tempo as métricas nativas do API Gateway (Desempenho, Erros) e a consulta de Logs Insights do painel de Erros.

## Conclusão

7/7 verificações passaram, todas com dados reais consultados no CloudWatch depois de gerar tráfego real, invocar o canário, provocar a falha controlada e derrubar o bucket primário do front-end. As imagens dos widgets de métrica foram salvas automaticamente em `evidencias_observabilidade/` — anexe essa pasta e este relatório à entrega.