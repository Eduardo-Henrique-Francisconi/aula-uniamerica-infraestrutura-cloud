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

// Rota para obter todas as tarefas (GET)
app.get('/todos', async (req, res) => {
  try {
    const data = await ddb.send(new ScanCommand({ TableName: TABLE_NAME }));
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
    await ddb.send(new PutCommand({ TableName: TABLE_NAME, Item: todo }));
    res.status(201).json(todo);
  } catch (err) {
    res.status(400).json({ message: err.message });
  }
});

// Rota para marcar uma tarefa como concluída (PATCH)
app.patch('/todos/:id', async (req, res) => {
  try {
    const existing = await ddb.send(
      new GetCommand({ TableName: TABLE_NAME, Key: { id: req.params.id } })
    );

    if (!existing.Item) {
      return res.status(404).json({ message: 'Tarefa não encontrada' });
    }

    const updated = await ddb.send(
      new UpdateCommand({
        TableName: TABLE_NAME,
        Key: { id: req.params.id },
        UpdateExpression: 'SET completed = :c',
        ExpressionAttributeValues: { ':c': !existing.Item.completed },
        ReturnValues: 'ALL_NEW',
      })
    );

    res.json(updated.Attributes);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// Rota para excluir uma tarefa (DELETE)
app.delete('/todos/:id', async (req, res) => {
  try {
    const existing = await ddb.send(
      new GetCommand({ TableName: TABLE_NAME, Key: { id: req.params.id } })
    );

    if (!existing.Item) {
      return res.status(404).json({ message: 'Tarefa não encontrada' });
    }

    await ddb.send(
      new DeleteCommand({ TableName: TABLE_NAME, Key: { id: req.params.id } })
    );

    res.json({ message: 'Tarefa excluída com sucesso' });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
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
