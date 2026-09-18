# Painel 1 — Disponibilidade

**Aplicação:** Todo App · **Dashboard:** `todo-app-observabilidade` (CloudWatch, região `us-east-2`)
**Domínios monitorados:** `app.neshiku.com.br` (front-end) e `api.neshiku.com.br` (API)

---

## 1. Nome e pergunta operacional

**Disponibilidade** — a aplicação está acessível pelo domínio configurado, tanto o front-end (`app.neshiku.com.br`) quanto a API (`api.neshiku.com.br`)?

## 2. Motivo da escolha

É o requisito mais básico da atividade: se o domínio não responde, nada mais importa. E é o único painel cujo dado **não existe nativamente** em nenhum serviço gerenciado da conta — API Gateway e CloudFront só sabem responder "quantas requisições eu recebi", não "alguém de fora conseguiu me alcançar pelo domínio público agora, do jeito que um usuário faria". Sem essa checagem ativa, uma indisponibilidade só seria percebida se um usuário reclamasse.

## 3. Origem dos dados

Função `HealthCheckFunction` (Lambda), disparada pelo EventBridge (regra agendada `todo-app-healthcheck-schedule`) a cada 5 minutos. Ela faz uma requisição HTTPS real a `https://app.neshiku.com.br/` e outra a `https://api.neshiku.com.br/todos` — os mesmos domínios que um usuário usaria, passando pela Cloudflare da mesma forma (o header `X-Origin-Verify` é injetado pela Transform Rule, não pelo código do canário, então a checagem não precisa conhecer o segredo).

Cada checagem grava uma linha JSON no CloudWatch Logs (log group da `HealthCheckFunction`) com os campos `target` (`frontend` ou `api`), `result` (`success`/`failure`), `http_status` e `latency_ms`. Três Metric Filters (`AWS::Logs::MetricFilter`, definidos em `backend/template.yaml`) convertem essas linhas em métricas customizadas no namespace `TodoApp/Availability`: `AvailabilitySuccess`, `AvailabilityFailure` e `AvailabilityLatency`, todas dimensionadas por `Target`.

## 4. Consulta e cálculo

O primeiro widget soma (`Sum`) `AvailabilitySuccess` e `AvailabilityFailure` por período de 5 minutos, uma série por `Target` — unidade: contagem de checagens. Um segundo widget mostra a média (`Average`) de `AvailabilityLatency` no mesmo período, em milissegundos.

Não há uma **taxa** calculada aqui, de propósito: como a checagem só roda a cada 5 min, cada período de agregação tem no máximo 1 amostra — uma taxa (%) oscilaria só entre 0% e 100%, sem significado estatístico (não existe "meio sucesso"). Por isso o painel mostra sucesso/falha como contagem simples, não como percentual.

## 5. Recorte temporal

Janela padrão de 3 horas no dashboard (ajustável pelo leitor), período de agregação de 5 minutos (igual ao intervalo do agendamento do canário), atualização a cada nova execução (a cada 5 min). Fuso: o CloudWatch mostra os horários no fuso do navegador de quem está olhando; os logs internos são gravados em UTC (`timestamp` em ISO-8601 UTC).

## 6. Forma de visualização

Série temporal (linha), porque a pergunta é "como isso se comportou ao longo do tempo" — uma tabela não deixaria visível, de forma rápida, um período curto de indisponibilidade no meio de uma janela de horas.

## 7. Interpretação

Comportamento esperado: `AvailabilitySuccess` presente e constante em todo período de 5 min, para os dois `Target`s, com `AvailabilityFailure` em zero e `AvailabilityLatency` estável.

## 8. Critérios de atenção

Qualquer valor de `AvailabilityFailure` maior que zero já é motivo de investigação — o alvo esperado é 100% de sucesso, sempre. Para latência, ainda não há histórico longo suficiente de uso real para definir um limite estatisticamente justificado (ex.: um p95 histórico); por ora o critério é qualitativo — um salto muito acima da faixa observada nos testes (ver Seção 10 abaixo) já indica algo mudando na borda (Cloudflare) ou na origem (CloudFront/API Gateway).

## 9. Ação decorrente

Uma falha de `frontend` indica investigar CloudFront → Cloudflare → os dois buckets S3, nessa ordem (checar o console do CloudFront e o estado dos dois buckets de origem). Uma falha de `api` indica checar API Gateway → Lambda → DynamoDB nessa ordem — a checagem da API percorre a cadeia inteira, já que `GET /todos` faz um `Scan` real no banco, então uma falha na API pode ter origem no banco também.

## 10. Validação e limitações

**Teste:** invocação manual da `HealthCheckFunction` (fora do agendamento normal), confirmando a linha de log e o ponto correspondente na métrica logo em seguida.
**Resultado esperado:** duas linhas de log (`target=frontend` e `target=api`), ambas com `result=success`, e os pontos correspondentes aparecendo em `AvailabilitySuccess` no dashboard.
**Resultado observado:** confirmado — ver `relatorio_testes_observabilidade.md`, verificação "Canário de disponibilidade".

Um segundo teste (automático, no script `observabilidade_testes.py`) derruba deliberadamente o bucket S3 primário do front-end e invoca o canário durante a queda, confirmando pelo próprio log que `target=frontend` continua `success` (porque o CloudFront já fez failover para o bucket secundário) — essa é a evidência de que o painel **não** acusaria indisponibilidade durante um failover real e correto.

**O que os dados não permitem concluir:** o canário roda de uma única região/localização (não é um teste multi-região como um serviço de monitoramento comercial pago). Ele comprova que o domínio responde a partir da rede da AWS na região `us-east-2` — não prova que todos os pontos da internet conseguem alcançar o domínio (um bloqueio de rede regional em outro país, por exemplo, não seria detectado por este painel).

## Alcance (o que este painel observa e o que não observa)

Observa: se os dois domínios públicos respondem HTTP com sucesso, a cada 5 minutos, a partir da região `us-east-2` da AWS. A checagem da API cobre a cadeia inteira até o banco (porque `GET /todos` faz `Scan`), mas só essa rota — não testa `POST`/`PATCH`/`DELETE` (essas ficam cobertas indiretamente pelo Painel 2/3, quando há tráfego real). Não observa: desempenho percebido no navegador do usuário final, disponibilidade vista de outras regiões geográficas, nem falhas que durem menos que o intervalo entre checagens (uma indisponibilidade de alguns segundos entre duas execuções do canário pode não ser capturada).

## Como interpretar um período sem dados neste painel

Um "buraco" no gráfico — nenhum ponto, nem de sucesso nem de falha, em um período de 5 minutos — significa que **o canário não rodou** naquele intervalo (por exemplo: erro na própria função `HealthCheckFunction`, ou o agendamento do EventBridge desabilitado). Isso é **diferente** de uma falha real e não deve ser lido como "a aplicação caiu": nesse caso é preciso checar o log group da `HealthCheckFunction` para diferenciar as duas situações — ausência de coleta não é a mesma coisa que uma falha confirmada.
