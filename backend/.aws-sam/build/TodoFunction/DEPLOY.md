# Deploy do backend (Lambda + API Gateway + DynamoDB)

## Pré-requisitos (instalar na sua máquina, uma vez só)

1. **AWS CLI**: https://docs.aws.amazon.com/pt_br/cli/latest/userguide/getting-started-install.html
2. **AWS SAM CLI**: https://docs.aws.amazon.com/pt_br/serverless-application-model/latest/developerguide/install-sam-cli.html
3. Depois de instalar o AWS CLI, rode `aws configure` e informe a Access Key / Secret Key do seu usuário IAM (crie um usuário IAM com permissões de administrador só para esse projeto, não use o usuário root da conta).

## Deploy

Dentro da pasta `backend/`:

```bash
npm install
sam build
sam deploy --guided
```

No `sam deploy --guided`, responda:
- **Stack Name**: `todo-backend` (ou o nome que preferir)
- **AWS Region**: escolha uma região próxima (ex: `us-east-1` ou `sa-east-1`)
- **Confirm changes before deploy**: Y
- **Allow SAM CLI IAM role creation**: Y (ele precisa criar a role do Lambda com permissão só na tabela DynamoDB)
- **Save arguments to configuration file**: Y (assim da próxima vez basta rodar `sam deploy`)

Ao final, o SAM mostra o **ApiUrl** de saída — algo como:

```
https://abc123xyz.execute-api.us-east-1.amazonaws.com
```

Guarde essa URL — é o endereço real da API na AWS. Teste rápido:

```bash
curl https://abc123xyz.execute-api.us-east-1.amazonaws.com/todos
```

Deve retornar `[]` (lista vazia, a tabela nova ainda não tem dados).

## Próximo passo

Essa URL do API Gateway ainda **não** é o domínio final (`api.neshiku.com.br`). O próximo passo é apontar um registro CNAME na Cloudflare (`api` → esse hostname do execute-api), com o proxy da Cloudflare ativado (nuvem laranja) — isso já entrega HTTPS automático e faz o papel de proxy reverso exigido pela atividade. Fazemos isso depois que o front-end (CloudFront) também estiver no ar, para configurar os dois domínios de uma vez.
