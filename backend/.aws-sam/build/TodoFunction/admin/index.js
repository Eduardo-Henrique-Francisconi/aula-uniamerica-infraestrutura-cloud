const { CloudWatchClient, GetMetricWidgetImageCommand } = require('@aws-sdk/client-cloudwatch');
const {
  CloudWatchLogsClient,
  StartQueryCommand,
  GetQueryResultsCommand,
} = require('@aws-sdk/client-cloudwatch-logs');

// ---------------------------------------------------------------------------
// Painel administrativo protegido (Entrega 2) — GET /admin/dashboard
//
// Esta função é o que fica por trás de https://app.neshiku.com.br/admin.
// Ela NÃO serve HTML (isso é um arquivo estático no S3/CloudFront) — só
// devolve os dados já prontos (imagens dos widgets de métrica + linhas dos
// widgets de log) para a página montar os 5 painéis.
//
// Controle de acesso (item "quem pode consultar / qual mecanismo"):
//   1. A requisição só chega aqui se passar pela Cloudflare (mesma regra do
//      resto da API: cabeçalho X-Origin-Verify injetado pela Transform Rule).
//   2. Além disso, é exigido o cabeçalho X-Admin-Key, com um segredo próprio
//      (ADMIN_ACCESS_KEY, parâmetro NoEcho do SAM) — combinado só entre o
//      grupo e guardado num gerenciador de senhas (Bitwarden), nunca no
//      repositório. Sem os dois cabeçalhos corretos, a resposta é 403 e a
//      página de admin não mostra nada.
//
// Os widgets abaixo espelham EXATAMENTE os definidos em template.yaml
// (recurso ObservabilityDashboard) — mesmas métricas, mesmo período (3h),
// mesmas queries do Logs Insights. Se um for alterado, o outro deve
// acompanhar.
// ---------------------------------------------------------------------------

const cw = new CloudWatchClient({});
const logsClient = new CloudWatchLogsClient({});

const REGION = process.env.AWS_REGION;
// O ID da API NÃO vem de variável de ambiente (evita dependência circular no
// CloudFormation: esta função é alvo de uma rota dessa mesma API, então uma
// referência via !Ref no template criaria um ciclo "função espera API, API
// espera a permissão da função, permissão espera a função"). Em vez disso,
// o valor vem do próprio evento que o API Gateway manda em cada chamada.
const TABLE_NAME = process.env.TABLE_NAME;
const TODO_LOG_GROUP = process.env.TODO_FUNCTION_LOG_GROUP;
const ADMIN_ACCESS_KEY = process.env.ADMIN_ACCESS_KEY || '';
const ORIGIN_SECRET = process.env.ORIGIN_SECRET || '';

const TIMEZONE = '-03:00'; // America/Sao_Paulo (Brasil não usa horário de verão desde 2019)
const START = '-PT3H';
const END = 'PT0H';

function metricWidgetSpec({ title, view = 'timeSeries', stacked = false, stat, metrics, width, height }) {
  return {
    title,
    view,
    stacked,
    region: REGION,
    period: 300,
    stat,
    metrics,
    timezone: TIMEZONE,
    start: START,
    end: END,
    width,
    height,
  };
}

function buildPanels(apiId) {
  return [
    {
      section: 'Painel 1 — Disponibilidade',
      question: 'A aplicação está acessível pelo domínio configurado?',
      widgets: [
        {
          id: 'disp-eventos',
          type: 'metric',
          spec: metricWidgetSpec({
            title: 'Checagens sintéticas — sucesso x falha (soma / 5 min)',
            stat: 'Sum',
            width: 600,
            height: 350,
            metrics: [
              ['TodoApp/Availability', 'AvailabilitySuccess', 'Target', 'frontend', { label: 'Front-end OK', color: '#2ca02c' }],
              ['TodoApp/Availability', 'AvailabilitySuccess', 'Target', 'api', { label: 'API OK', color: '#1f77b4' }],
              ['TodoApp/Availability', 'AvailabilityFailure', 'Target', 'frontend', { label: 'Front-end FALHA', color: '#d62728' }],
              ['TodoApp/Availability', 'AvailabilityFailure', 'Target', 'api', { label: 'API FALHA', color: '#ff7f0e' }],
            ],
          }),
        },
        {
          id: 'disp-latencia',
          type: 'metric',
          spec: metricWidgetSpec({
            title: 'Latência da checagem sintética (ms, média)',
            stat: 'Average',
            width: 600,
            height: 350,
            metrics: [
              ['TodoApp/Availability', 'AvailabilityLatency', 'Target', 'frontend', { label: 'Front-end' }],
              ['TodoApp/Availability', 'AvailabilityLatency', 'Target', 'api', { label: 'API' }],
            ],
          }),
        },
      ],
    },
    {
      section: 'Painel 2 — Desempenho',
      question: 'Quais operações estão demorando mais e em quais períodos?',
      widgets: [
        {
          id: 'desempenho-rotas',
          type: 'metric',
          spec: metricWidgetSpec({
            title: 'Latência por rota (API Gateway) — p50 e p95, ms',
            width: 1200,
            height: 350,
            metrics: [
              ['AWS/ApiGateway', 'Latency', 'ApiId', apiId,'Route', 'GET /todos', 'Stage', '$default', { stat: 'p50', label: 'GET /todos (p50)' }],
              ['AWS/ApiGateway', 'Latency', 'ApiId', apiId,'Route', 'GET /todos', 'Stage', '$default', { stat: 'p95', label: 'GET /todos (p95)' }],
              ['AWS/ApiGateway', 'Latency', 'ApiId', apiId,'Route', 'POST /todos', 'Stage', '$default', { stat: 'p50', label: 'POST /todos (p50)' }],
              ['AWS/ApiGateway', 'Latency', 'ApiId', apiId,'Route', 'POST /todos', 'Stage', '$default', { stat: 'p95', label: 'POST /todos (p95)' }],
              ['AWS/ApiGateway', 'Latency', 'ApiId', apiId,'Route', 'PATCH /todos/{id}', 'Stage', '$default', { stat: 'p95', label: 'PATCH /todos/{id} (p95)' }],
              ['AWS/ApiGateway', 'Latency', 'ApiId', apiId,'Route', 'DELETE /todos/{id}', 'Stage', '$default', { stat: 'p95', label: 'DELETE /todos/{id} (p95)' }],
            ],
          }),
        },
      ],
    },
    {
      section: 'Painel 3 — Erros',
      question: 'Quais falhas estão ocorrendo e qual parcela das requisições elas representam?',
      widgets: [
        {
          id: 'erros-taxa',
          type: 'metric',
          spec: metricWidgetSpec({
            title: 'Taxa de erro agregada da API (%)',
            stat: 'Sum',
            width: 400,
            height: 350,
            metrics: [
              ['AWS/ApiGateway', '5xxError', 'ApiId', apiId,'Stage', '$default', { id: 'e5', visible: false }],
              ['AWS/ApiGateway', '4xxError', 'ApiId', apiId,'Stage', '$default', { id: 'e4', visible: false }],
              ['AWS/ApiGateway', 'Count', 'ApiId', apiId,'Stage', '$default', { id: 'cnt', visible: false }],
              [{ expression: '100*(e5+e4)/cnt', label: 'Taxa de erro (%)', id: 'rate' }],
            ],
          }),
        },
        {
          id: 'erros-5xx-rota',
          type: 'metric',
          spec: metricWidgetSpec({
            title: 'Erros 5xx por rota (contagem)',
            stat: 'Sum',
            width: 400,
            height: 350,
            metrics: [
              ['AWS/ApiGateway', '5xxError', 'ApiId', apiId,'Route', 'GET /todos', 'Stage', '$default', { label: 'GET /todos' }],
              ['AWS/ApiGateway', '5xxError', 'ApiId', apiId,'Route', 'POST /todos', 'Stage', '$default', { label: 'POST /todos' }],
              ['AWS/ApiGateway', '5xxError', 'ApiId', apiId,'Route', 'PATCH /todos/{id}', 'Stage', '$default', { label: 'PATCH /todos/{id}' }],
              ['AWS/ApiGateway', '5xxError', 'ApiId', apiId,'Route', 'DELETE /todos/{id}', 'Stage', '$default', { label: 'DELETE /todos/{id}' }],
            ],
          }),
        },
        {
          id: 'erros-causas',
          type: 'log',
          title: 'Causas de erro (top, últimas 3h)',
          logGroupName: TODO_LOG_GROUP,
          query:
            "fields @timestamp, route, status_code, request_id\n| filter event = \"http_request\" and status_code >= 400\n| stats count() as ocorrencias by route, status_code\n| sort ocorrencias desc",
        },
      ],
    },
    {
      section: 'Painel 4 — Uso da aplicação',
      question: 'Quais funcionalidades são utilizadas e como o volume varia?',
      widgets: [
        {
          id: 'uso-rotas',
          type: 'metric',
          spec: metricWidgetSpec({
            title: 'Requisições por rota (contagem, soma / 5 min)',
            stat: 'Sum',
            stacked: true,
            width: 1200,
            height: 350,
            metrics: [
              ['AWS/ApiGateway', 'Count', 'ApiId', apiId,'Route', 'GET /todos', 'Stage', '$default', { label: 'Listar tarefas (GET)' }],
              ['AWS/ApiGateway', 'Count', 'ApiId', apiId,'Route', 'POST /todos', 'Stage', '$default', { label: 'Criar tarefa (POST)' }],
              ['AWS/ApiGateway', 'Count', 'ApiId', apiId,'Route', 'PATCH /todos/{id}', 'Stage', '$default', { label: 'Concluir tarefa (PATCH)' }],
              ['AWS/ApiGateway', 'Count', 'ApiId', apiId,'Route', 'DELETE /todos/{id}', 'Stage', '$default', { label: 'Excluir tarefa (DELETE)' }],
            ],
          }),
        },
      ],
    },
    {
      section: 'Painel 5 — Banco de Dados',
      question: 'As operações do back-end com o banco estão funcionando e com qual duração?',
      widgets: [
        {
          id: 'banco-latencia',
          type: 'metric',
          spec: metricWidgetSpec({
            title: 'Latência das operações no DynamoDB (ms, média)',
            stat: 'Average',
            width: 400,
            height: 350,
            metrics: [
              ['AWS/DynamoDB', 'SuccessfulRequestLatency', 'TableName', TABLE_NAME, 'Operation', 'Scan', { label: 'Scan (GET /todos)' }],
              ['AWS/DynamoDB', 'SuccessfulRequestLatency', 'TableName', TABLE_NAME, 'Operation', 'PutItem', { label: 'PutItem (POST /todos)' }],
              ['AWS/DynamoDB', 'SuccessfulRequestLatency', 'TableName', TABLE_NAME, 'Operation', 'GetItem', { label: 'GetItem' }],
              ['AWS/DynamoDB', 'SuccessfulRequestLatency', 'TableName', TABLE_NAME, 'Operation', 'UpdateItem', { label: 'UpdateItem (PATCH)' }],
              ['AWS/DynamoDB', 'SuccessfulRequestLatency', 'TableName', TABLE_NAME, 'Operation', 'DeleteItem', { label: 'DeleteItem' }],
            ],
          }),
        },
        {
          id: 'banco-falhas-nativas',
          type: 'metric',
          spec: metricWidgetSpec({
            title: 'Falhas nativas do DynamoDB (throttling / erros)',
            stat: 'Sum',
            width: 400,
            height: 350,
            metrics: [
              ['AWS/DynamoDB', 'ThrottledRequests', 'TableName', TABLE_NAME, { label: 'Throttled' }],
              ['AWS/DynamoDB', 'SystemErrors', 'TableName', TABLE_NAME, { label: 'Erros de sistema (AWS)' }],
              ['AWS/DynamoDB', 'UserErrors', 'TableName', TABLE_NAME, { label: 'Erros de uso (cliente)' }],
            ],
          }),
        },
        {
          id: 'banco-falhas-backend',
          type: 'log',
          title: 'Falhas de acesso ao banco vistas pelo back-end (últimas 3h)',
          logGroupName: TODO_LOG_GROUP,
          query:
            'fields (@timestamp - 3h) as horario_brasilia, operation, error_type, error_message, duration_ms\n| filter event = "db_operation" and result = "failure"\n| sort horario_brasilia desc\n| limit 50',
        },
      ],
    },
  ];
}

async function renderMetricWidget(widget) {
  const cmd = new GetMetricWidgetImageCommand({
    MetricWidget: JSON.stringify(widget.spec),
    OutputFormat: 'png',
  });
  const result = await cw.send(cmd);
  const bytes = await result.MetricWidgetImage.transformToByteArray();
  const base64 = Buffer.from(bytes).toString('base64');
  return {
    id: widget.id,
    type: 'image',
    title: widget.spec.title,
    image: `data:image/png;base64,${base64}`,
  };
}

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runLogQuery(widget) {
  const end = Math.floor(Date.now() / 1000);
  const start = end - 3 * 60 * 60; // últimas 3h, mesma janela dos widgets de métrica

  const { queryId } = await logsClient.send(
    new StartQueryCommand({
      logGroupName: widget.logGroupName,
      startTime: start,
      endTime: end,
      queryString: widget.query,
      limit: 50,
    })
  );

  // Logs Insights é assíncrono: aguarda a conclusão com polling limitado
  // (a função tem 25s de timeout — no máximo ~9 tentativas de 2s aqui).
  let status = 'Running';
  let results = [];
  for (let attempt = 0; attempt < 9 && (status === 'Running' || status === 'Scheduled'); attempt += 1) {
    await sleep(2000);
    const resp = await logsClient.send(new GetQueryResultsCommand({ queryId }));
    status = resp.status;
    results = resp.results || [];
  }

  const columns = results.length > 0 ? results[0].map((f) => f.field) : [];
  const rows = results.map((row) => Object.fromEntries(row.map((f) => [f.field, f.value])));

  return {
    id: widget.id,
    type: 'table',
    title: widget.title,
    status,
    columns,
    rows,
  };
}

async function renderWidget(widget) {
  try {
    if (widget.type === 'metric') {
      return await renderMetricWidget(widget);
    }
    return await runLogQuery(widget);
  } catch (err) {
    return {
      id: widget.id,
      type: 'error',
      title: widget.spec ? widget.spec.title : widget.title,
      message: err.message,
    };
  }
}

exports.handler = async (event) => {
  const headers = event.headers || {};
  const originOk = ORIGIN_SECRET && headers['x-origin-verify'] === ORIGIN_SECRET;
  const adminOk = ADMIN_ACCESS_KEY && headers['x-admin-key'] === ADMIN_ACCESS_KEY;

  if (!originOk || !adminOk) {
    return {
      statusCode: 403,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'Acesso negado. Verifique a chave de acesso (X-Admin-Key).' }),
    };
  }

  const apiId = (event.requestContext && event.requestContext.apiId) || '';
  const panelDefs = buildPanels(apiId);

  const panels = await Promise.all(
    panelDefs.map(async (panel) => ({
      section: panel.section,
      question: panel.question,
      widgets: await Promise.all(panel.widgets.map(renderWidget)),
    }))
  );

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      generatedAt: new Date().toISOString(),
      timezoneDisplay: 'America/Sao_Paulo (UTC-03:00)',
      windowHours: 3,
      panels,
    }),
  };
};
