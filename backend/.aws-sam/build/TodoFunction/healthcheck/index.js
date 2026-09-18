const https = require('https');
const { URL } = require('url');

// ---------------------------------------------------------------------------
// Canário de disponibilidade (checagem sintética)
//
// Esta função é a única peça nova de infraestrutura criada especificamente
// para o painel de "Disponibilidade". Ela é chamada periodicamente pelo
// EventBridge Scheduler (ver template.yaml, evento "ScheduledCheck") e faz,
// a cada execução, uma requisição HTTPS real contra os MESMOS domínios que
// um usuário usaria:
//
//   - FRONTEND_URL -> https://app.neshiku.com.br/         (front-end)
//   - API_URL      -> https://api.neshiku.com.br/todos    (back-end + banco)
//
// Como as duas chamadas passam pela Cloudflare (proxy reverso) da mesma
// forma que o tráfego real do usuário, o cabeçalho X-Origin-Verify é
// injetado automaticamente pela Transform Rule — a checagem da API não
// precisa (e não deve) conhecer o segredo. Isso também significa que a
// checagem da API valida a cadeia inteira: Cloudflare -> API Gateway ->
// Lambda -> DynamoDB (GET /todos faz um Scan na tabela), então uma falha
// aqui pode indicar tanto problema de API quanto de banco.
//
// Cada checagem gera exatamente UMA linha de log JSON, com o resultado
// (sucesso/falha), o código HTTP e a latência observada. Um Metric Filter
// no CloudWatch Logs (definido no template.yaml) transforma essas linhas
// nas métricas customizadas AvailabilitySuccess / AvailabilityFailure /
// AvailabilityLatency, dimensionadas por "target".
// ---------------------------------------------------------------------------

const SERVICE_NAME = 'todo-healthcheck';
const ENVIRONMENT = process.env.ENVIRONMENT || 'production';
const TIMEOUT_MS = 8000;

function log(fields) {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    service: SERVICE_NAME,
    environment: ENVIRONMENT,
    ...fields,
  }));
}

function checkUrl(target, rawUrl) {
  return new Promise((resolve) => {
    const start = Date.now();
    let url;
    try {
      url = new URL(rawUrl);
    } catch (err) {
      resolve({
        target,
        url: rawUrl,
        result: 'failure',
        http_status: null,
        latency_ms: Date.now() - start,
        error_message: `URL inválida: ${err.message}`,
      });
      return;
    }

    const req = https.get(
      {
        hostname: url.hostname,
        path: url.pathname + url.search,
        protocol: url.protocol,
        timeout: TIMEOUT_MS,
        headers: { 'User-Agent': 'todo-app-healthcheck/1.0' },
      },
      (res) => {
        // Drena o corpo da resposta para liberar o socket, mas não precisamos
        // do conteúdo — só do status e da latência.
        res.on('data', () => {});
        res.on('end', () => {
          const ok = res.statusCode >= 200 && res.statusCode < 400;
          resolve({
            target,
            url: rawUrl,
            result: ok ? 'success' : 'failure',
            http_status: res.statusCode,
            latency_ms: Date.now() - start,
            error_message: null,
          });
        });
      }
    );

    req.on('timeout', () => {
      req.destroy();
      resolve({
        target,
        url: rawUrl,
        result: 'failure',
        http_status: null,
        latency_ms: Date.now() - start,
        error_message: `Timeout após ${TIMEOUT_MS}ms`,
      });
    });

    req.on('error', (err) => {
      resolve({
        target,
        url: rawUrl,
        result: 'failure',
        http_status: null,
        latency_ms: Date.now() - start,
        error_message: err.message,
      });
    });
  });
}

exports.handler = async () => {
  const targets = [
    { target: 'frontend', url: process.env.FRONTEND_URL },
    { target: 'api', url: process.env.API_URL },
  ].filter((t) => !!t.url);

  const results = await Promise.all(
    targets.map((t) => checkUrl(t.target, t.url))
  );

  for (const checkResult of results) {
    log({
      level: checkResult.result === 'success' ? 'info' : 'error',
      event: 'healthcheck',
      ...checkResult,
    });
  }

  return { checked: results.length };
};
