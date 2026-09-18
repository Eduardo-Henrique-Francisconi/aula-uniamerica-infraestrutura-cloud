# Deploy da Entrega 2 — Observabilidade

Este arquivo é o roteiro para publicar as mudanças da Entrega 2 (logs
estruturados, canário de disponibilidade, métricas por rota e dashboard do
CloudWatch) na mesma stack já usada na Entrega 1 (`sam-app`, região
`us-east-2`). Não é necessário criar nada do zero — é uma atualização da
stack existente.

## O que mudou no `template.yaml` (e por quê)

1. **Rotas explícitas no API Gateway** (antes era um catch-all `/{proxy+}`).
   Sem isso, o CloudWatch não sabe separar "GET /todos" de "POST /todos" nas
   métricas nativas — tudo cairia numa única rota genérica. As rotas
   explícitas (`GET /todos`, `POST /todos`, `PATCH /todos/{id}`,
   `DELETE /todos/{id}`, `GET /todos-falha-simulada`) não mudam nada no
   comportamento do Express/Lambda — só fazem o API Gateway conhecer cada
   endpoint separadamente.
2. **`DefaultRouteSettings.DetailedMetricsEnabled: true`** no HTTP API —
   liga as métricas nativas por rota (Count, 4xxError, 5xxError, Latency).
3. **`TodoFunctionLogGroup`** — cria o log group do backend já com
   `RetentionInDays` (parâmetro `LogRetentionInDays`, padrão 30), em vez de
   deixar o Lambda criar um log group sem expiração.
4. **`HealthCheckFunction`** — função nova (canário de disponibilidade),
   `HealthCheckFunctionLogGroup` e o agendamento via EventBridge
   (`rate(5 minutes)`).
5. **3 `AWS::Logs::MetricFilter`** — transformam os logs do canário em
   métricas customizadas (`TodoApp/Availability`).
6. **`ObservabilityDashboard`** — o dashboard do CloudWatch com os 5
   painéis.

Nenhuma dessas mudanças altera o front-end, o DynamoDB ou os domínios já
configurados na Cloudflare — o `api.neshiku.com.br` continua apontando para
o mesmo `TodoHttpApi`.

## Passo a passo

Abra um terminal na pasta `backend/` do repositório (o mesmo de sempre):

```powershell
cd backend
sam build
```

Para o deploy, o `samconfig.toml` já guarda o nome da stack, a região e as
outras opções — mas **não guarda o `OriginSecret`** (ele é `NoEcho`, e
propositalmente não foi salvo em texto no arquivo versionado). Você precisa
informá-lo de novo neste deploy, com o **mesmo valor** que já está em uso
hoje. Duas formas de recuperar o valor atual, se não estiver anotado:

- **Console da AWS Lambda** → função `TodoFunction` (procure pelo nome que
  começa com `sam-app-TodoFunction-...`) → aba **Configuração** →
  **Variáveis de ambiente** → `ORIGIN_SECRET`.
- **Painel da Cloudflare** → zona `neshiku.com.br` → **Rules** → Transform
  Rule que injeta o cabeçalho `X-Origin-Verify` → veja o valor configurado
  na ação "Set static".

Com o valor em mãos, rode:

```powershell
sam deploy --parameter-overrides OriginSecret=SEU_VALOR_ATUAL LogRetentionInDays=30
```

(as demais opções — stack name `sam-app`, região `us-east-2`,
`CAPABILITY_IAM` — já vêm do `samconfig.toml`; o SAM vai mostrar o
changeset e pedir confirmação antes de aplicar, porque `confirm_changeset =
true`).

Se o deploy falhar em algum `AWS::Logs::MetricFilter` (mensagem sobre
propriedade `Unit` não reconhecida), remova a linha `Unit: Count` /
`Unit: Milliseconds` do `MetricTransformations` daquele filtro no
`template.yaml` e rode `sam build && sam deploy` novamente — é uma
propriedade opcional, só cosmética.

## Depois do deploy

A saída do `sam deploy` mostra `DashboardUrl` — abra esse link para ver o
dashboard `todo-app-observabilidade` já criado. Duas coisas levam um tempo
para aparecer:

- **Métricas por rota do API Gateway** (`DetailedMetricsEnabled`) — só
  aparecem depois da primeira requisição em cada rota *depois* do deploy.
  Gere tráfego (próxima seção) antes de olhar o dashboard.
- **Métricas de disponibilidade** — o canário roda a cada 5 minutos; espere
  pelo menos um ciclo (ou invoque manualmente uma vez para não esperar):

```powershell
aws lambda invoke --function-name <nome-da-HealthCheckFunction> --region us-east-2 out.json
```

(o nome exato aparece no console do Lambda ou em `aws lambda list-functions
--region us-east-2 --query "Functions[?contains(FunctionName,'HealthCheck')].FunctionName"`.)

## Gerar tráfego para popular os painéis

Um uso normal pela interface (`https://app.neshiku.com.br`) já gera dados
reais nos 5 painéis. Para garantir volume suficiente, também dá para bater
direto na API pelo domínio (mesmo caminho que o navegador usa):

```powershell
1..30 | ForEach-Object {
  Invoke-RestMethod -Uri "https://api.neshiku.com.br/todos" -Method GET | Out-Null
  Invoke-RestMethod -Uri "https://api.neshiku.com.br/todos" -Method POST -Body (@{text="tarefa de teste $_"} | ConvertTo-Json) -ContentType "application/json" | Out-Null
  Start-Sleep -Milliseconds 300
}
```

## Falha controlada para o painel de Erros

A rota `GET /todos-falha-simulada` foi criada só para isso — sempre devolve
`500` e grava um log `simulated_failure`. Gere algumas chamadas:

```powershell
1..10 | ForEach-Object { Invoke-WebRequest -Uri "https://api.neshiku.com.br/todos-falha-simulada" -SkipHttpErrorCheck | Out-Null }
```

Depois confirme no painel de Erros (widget "Erros 5xx por rota" e o widget
de log "Causas de erro") que o pico aparece, com `route =
"GET /todos-falha-simulada"`.

## Custo esperado

Tudo dentro do free tier para o volume desta atividade:
- EventBridge + Lambda do canário: ~8.640 execuções/mês (a cada 5 min),
  bem abaixo do free tier de 1 milhão de invocações/mês.
- Métricas customizadas: 6 séries (`AvailabilitySuccess`/`Failure`/`Latency`
  × 2 targets) — dentro das 10 métricas customizadas gratuitas por conta.
- Métricas nativas de API Gateway e DynamoDB: não têm custo adicional por
  estarem "detalhadas".
- CloudWatch Logs Insights: cobra por GB escaneado por consulta — irrelevante
  para o volume de logs desta atividade.
- Armazenamento dos logs: com `RetentionInDays: 30`, o volume gerado em
  poucos dias de teste fica em poucos KB/MB — custo desprezível.
