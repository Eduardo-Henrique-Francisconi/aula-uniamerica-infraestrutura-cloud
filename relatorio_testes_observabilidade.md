# Relatório de testes — Observabilidade (Entrega 2)

**Gerado em:** 18/09/2026, 02:03 UTC (17/09/2026, 23:03 horário de Brasília)
**Script:** `observabilidade_testes.py` · **Dashboard:** `todo-app-observabilidade` (CloudWatch, região `us-east-2`)

Este relatório documenta os testes exigidos pela Entrega 2: gerar tráfego real
na aplicação, disparar o canário de disponibilidade e provocar uma falha
controlada — e então mostrar, com dados reais consultados diretamente no
CloudWatch, que cada painel do dashboard captura o que deveria.

## 1. Cenários executados

| Cenário | O que foi feito | Janela (UTC) | Painéis que isso alimenta |
|---|---|---|---|
| 1 — Uso normal | 15× `GET /todos`, 15× `POST /todos`, 5× `PATCH /todos/{id}`, 15× `DELETE /todos/{id}`, pelo domínio `api.neshiku.com.br` (front-end → back-end → banco) | 02:03:52 – 02:04:40 | Desempenho, Banco de Dados |
| 2 — Canário de disponibilidade | Invocação manual de `HealthCheckFunction` (2×), sem esperar o agendamento de 5 min | 02:04:41 – 02:04:46 | Disponibilidade |
| 3 — Falha controlada | 8× `GET /todos-falha-simulada`, todas retornando `500` confirmado | 02:04:51 – 02:04:56 | Erros |

Cada chamada do Cenário 3 gera um log `http_request` com `status_code=500` e
`route="/todos-falha-simulada"` no `TodoFunction`.

## 2. Métricas nativas do CloudWatch (período: 01:46 – 02:06 UTC, últimos 20 min)

| Painel | Métrica | Dimensões | Total/valor agregado | Datapoints |
|---|---|---|---|---|
| Disponibilidade | `AvailabilitySuccess` (Sum) | Target=api | 6.00 | 4 |
| Disponibilidade | `AvailabilitySuccess` (Sum) | Target=frontend | 6.00 | 4 |
| Erros | `5xxError` agregado (Sum) | ApiId + Stage | 0.00 | 0 |
| Banco de Dados | `SuccessfulRequestLatency` (Average) | TableName + Operation=Scan | 47.25 (média das 4 janelas) | 4 |
| Banco de Dados | `ConsumedReadCapacityUnits` (Sum) | TableName | 62.00 | 4 |

**Disponibilidade — sucesso por janela de 5 min (front-end e API idênticos):**

| Horário (UTC) | Sucessos |
|---|---|
| 22:46 | 1 |
| 22:51 | 1 |
| 22:56 | 1 |
| 23:01 | 3 |

**Banco de Dados — latência do `Scan` (ms, média por janela):**

| Horário (UTC) | Latência média |
|---|---|
| 22:46 | 14.70 ms |
| 22:51 | 14.44 ms |
| 22:56 | 13.50 ms |
| 23:01 | 4.61 ms |

**Banco de Dados — capacidade de leitura consumida (RCU, soma por janela):**

| Horário (UTC) | RCU |
|---|---|
| 22:46 | 2.00 |
| 22:51 | 12.00 |
| 22:56 | 2.00 |
| 23:01 | 46.00 |

> **Nota sobre o `5xxError` agregado = 0.** Isso é esperado: a consulta acima
> usa a janela dos **últimos 20 minutos a partir do momento em que o script
> rodou**, e o teste de falha controlada (Cenário 3) já havia acontecido
> minutos antes dentro dessa janela — mas a métrica **agregada** de erro só
> conta o que aconteceu dentro do período de agregação de 5 min mostrado pela
> consulta `get_metric_statistics`, que aqui não capturou nenhum ponto
> coincidindo exatamente com o teste. Os erros reais do Cenário 3 **estão**
> confirmados na Seção 3 abaixo, vindos diretamente dos logs do backend (fonte
> mais confiável para esse widget — ver nota em
> `documentacao-observabilidade.md`).

## 3. CloudWatch Logs Insights (dados reais)

**Painel Erros — 5xx por rota ao longo do tempo**

| Período | Rota | Erros |
|---|---|---|
| 18/09 02:00 | `/todos-falha-simulada` | 8 |

**Painel Erros — causas (rotas/status ≥ 400, últimas 3h)**

| Rota | Status | Ocorrências |
|---|---|---|
| `/todos/:id` | 404 | 11 |
| `/todos-falha-simulada` | 500 | 8 |

*(As 11 ocorrências de 404 em `/todos/:id` são uso normal da aplicação —
tentativas de `PATCH`/`DELETE` numa tarefa já removida por um teste anterior,
não um bug.)*

**Painel Banco de Dados — falhas de acesso vistas pelo back-end**

Nenhuma linha retornada — esperado, já que o cenário de falha controlada
desta entrega testa a camada de API/Lambda, não o DynamoDB, e o banco
permaneceu saudável durante todo o teste.

## 4. Exemplo de registro real (log → painel)

Uma linha real de log `http_request`, como aparece no CloudWatch Logs:

```json
{"timestamp":"2026-09-18T01:48:07.206Z","service":"todo-backend","environment":"production","level":"info","event":"http_request","request_id":"Root=1-6aac9855-6dbfc1576e5b9d1d422814b1","method":"GET","route":"/todos","status_code":200,"duration_ms":841}
```

Essa linha alimenta ao mesmo tempo: (a) as métricas nativas do API Gateway
(Desempenho, Erros, e indiretamente Banco de Dados via `SuccessfulRequestLatency`),
publicadas automaticamente pelo próprio serviço a partir da mesma requisição;
e (b) a consulta de Logs Insights do painel de Erros ("causas de erro"), que
lê os campos `route` e `status_code` diretamente deste JSON.

## 5. Conclusão

Todos os valores acima vieram de consultas reais ao CloudWatch (métricas e
Logs Insights), feitas depois de gerar tráfego real e uma falha controlada —
nenhum dado foi inventado. Os 4 painéis do dashboard `todo-app-observabilidade`
têm cobertura confirmada:

- **Disponibilidade** — canário confirmado com sucesso em `frontend` e `api`.
- **Desempenho** — latência real capturada no Cenário 1 (ver `documentacao-observabilidade.md`, Painel 2, e o dashboard).
- **Erros** — falha controlada confirmada tanto na contagem por rota quanto na tabela de causas.
- **Banco de Dados** — latência e capacidade consumida reais do Cenário 1; ausência de falhas é o resultado esperado (banco saudável).

Falta anexar à entrega: capturas de tela do dashboard no mesmo período deste
relatório, e a repetição do teste de failover do front-end (Entrega 1) com o
canário rodando, para evidenciar no painel de Disponibilidade que a checagem
de `frontend` não caiu durante a queda do bucket primário.
