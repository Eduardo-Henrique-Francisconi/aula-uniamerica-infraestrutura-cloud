const serverless = require('serverless-http');
const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const { randomUUID } = require('crypto');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const {
  DynamoDBDocumentClient,
  ScanCommand,
  PutCommand,
  GetCommand,
  UpdateCommand,
  DeleteCommand,
} = require('@aws-sdk/lib-dynamodb');

// Inicializando o app Express
const app = express();

// Cliente do DynamoDB (as credenciais vêm da role do Lambda em produção;
// localmente, vêm do seu `aws configure`)
const client = new DynamoDBClient({});
const ddb = DynamoDBDocumentClient.from(client);
const TABLE_NAME = process.env.TABLE_NAME || 'todos-table';
const SERVICE_NAME = 'todo-backend';
const ENVIRONMENT = process.env.ENVIRONMENT || 'production';

// ---------------------------------------------------------------------------
// Observabilidade — logging estruturado (JSON, uma linha por evento)
//
// Todo log vai para o CloudWatch Logs automaticamente (stdout do Lambda).
// Dois tipos de evento são gerados:
//   - "http_request": uma linha por requisição HTTP atendida pelo Express,
//     com rota, método, status e duração.
//   - "db_operation": uma linha por chamada ao DynamoDB, com a operação,
//     sucesso/falha e duração — usada tanto para diagnosticar erros quanto
//     para complementar as métricas nativas do DynamoDB no painel de banco.
//
// Nenhum dado sensível (senha, token, string de conexão) é logado.
// ---------------------------------------------------------------------------
function log(fields) {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(), // UTC (padrão do Date#toISOString)
    service: SERVICE_NAME,
    environment: ENVIRONMENT,
    ...fields,
  }));
}

// Executa uma chamada ao DynamoDB medindo duração e registrando sucesso/falha.
// `operation` é um nome estável (ex.: "ScanTodos") usado como dimensão nas
// métricas derivadas dos logs e nas consultas do CloudWatch Logs Insights.
async function timedDb(operation, requestId, fn) {
  const start = Date.now();
  try {
    const result = await fn();
    log({
      level: 'info',
      event: 'db_operation',
      request_id: requestId,
      operation,
      result: 'success',
      duration_ms: Date.now() - start,
    });
    return result;
  } catch (err) {
    log({
      level: 'error',
      event: 'db_operation',
      request_id: requestId,
      operation,
      result: 'failure',
      duration_ms: Date.now() - start,
      error_type: err.name,
      error_message: err.message,
    });
    throw err;
  }
}

// Middleware para habilitar CORS e processar JSON
app.use(cors());
app.use(bodyParser.json());

// Middleware para verificar o cabeçalho 'x-origin-verify' em todas as requisições
const ORIGIN_SECRET = process.env.ORIGIN_SECRET || '';
app.use((req, res, next) => {
  if (!ORIGIN_SECRET || req.headers['x-origin-verify'] !== ORIGIN_SECRET) {
    return res.status(403).json({ message: 'Acesso direto não permitido. Use o domínio oficial.' });
  }
  next();
});

// Middleware de log estruturado de requisição — captura toda requisição que
// passou pela verificação de origem, com o status/duração da resposta.
// req.route.path só existe depois que o Express casa a rota (fica disponível
// no momento de "finish"), por isso pegamos req.path como fallback.
app.use((req, res, next) => {
  const start = Date.now();
  req.requestId = req.headers['x-amzn-trace-id'] || randomUUID();
  res.on('finish', () => {
    const durationMs = Date.now() - start;
    const route = req.route ? `${req.baseUrl}${req.route.path}` : req.path;
    log({
      level: res.statusCode >= 500 ? 'error' : (res.statusCode >= 400 ? 'warn' : 'info'),
      event: 'http_request',
      request_id: req.requestId,
      method: req.method,
      route,
      status_code: res.statusCode,
      duration_ms: durationMs,
    });
  });
  next();
});

// Rota para obter todas as tarefas (GET)
app.get('/todos', async (req, res) => {
  try {
    const data = await timedDb('ScanTodos', req.requestId, () =>
      ddb.send(new ScanCommand({ TableName: TABLE_NAME }))
    );
    res.json(data.Items || []);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// Rota para adicionar uma nova tarefa (POST)
app.post('/todos', async (req, res) => {
  const { text } = req.body;

  if (!text) {
    return res.status(400).json({ message: 'O campo "text" é obrigatório' });
  }

  const todo = {
    id: randomUUID(),
    text,
    completed: false,
  };

  try {
    await timedDb('PutTodo', req.requestId, () =>
      ddb.send(new PutCommand({ TableName: TABLE_NAME, Item: todo }))
    );
    res.status(201).json(todo);
  } catch (err) {
    res.status(400).json({ message: err.message });
  }
});

// Rota para marcar uma tarefa como concluída (PATCH)
app.patch('/todos/:id', async (req, res) => {
  try {
    const existing = await timedDb('GetTodo', req.requestId, () =>
      ddb.send(new GetCommand({ TableName: TABLE_NAME, Key: { id: req.params.id } }))
    );

    if (!existing.Item) {
      return res.status(404).json({ message: 'Tarefa não encontrada' });
    }

    const updated = await timedDb('UpdateTodo', req.requestId, () =>
      ddb.send(
        new UpdateCommand({
          TableName: TABLE_NAME,
          Key: { id: req.params.id },
          UpdateExpression: 'SET completed = :c',
          ExpressionAttributeValues: { ':c': !existing.Item.completed },
          ReturnValues: 'ALL_NEW',
        })
      )
    );

    res.json(updated.Attributes);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// Rota para excluir uma tarefa (DELETE)
app.delete('/todos/:id', async (req, res) => {
  try {
    const existing = await timedDb('GetTodo', req.requestId, () =>
      ddb.send(new GetCommand({ TableName: TABLE_NAME, Key: { id: req.params.id } }))
    );

    if (!existing.Item) {
      return res.status(404).json({ message: 'Tarefa não encontrada' });
    }

    await timedDb('DeleteTodo', req.requestId, () =>
      ddb.send(new DeleteCommand({ TableName: TABLE_NAME, Key: { id: req.params.id } }))
    );

    res.json({ message: 'Tarefa excluída com sucesso' });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// Rota de teste para gerar falhas controladas (usada nos testes da Entrega 2
// para provocar um erro real e comprovar que ele aparece no painel de erros).
// Não expõe nenhum dado sensível — só devolve um erro 500 propositalmente.
app.get('/todos-falha-simulada', async (req, res) => {
  log({
    level: 'error',
    event: 'simulated_failure',
    request_id: req.requestId,
    route: '/todos-falha-simulada',
  });
  res.status(500).json({ message: 'Falha simulada para teste do painel de erros' });
});

// Handler que o Lambda chama (via API Gateway)
module.exports.handler = serverless(app);

// Permite rodar localmente com "node index.js" para testar antes de fazer deploy
// (precisa ter credenciais AWS configuradas e a tabela já criada)
if (require.main === module) {
  const port = 5000;
  app.listen(port, () => {
    console.log(`Servidor local rodando na porta ${port}`);
  });
}
