# Deploy da página protegida `/admin` (observabilidade com chave de acesso)

Este roteiro cobre a peça nova pedida depois do `DEPLOY-ENTREGA2.md`: uma
página em **`https://app.neshiku.com.br/admin`** que mostra os mesmos 5
painéis do CloudWatch, mas sem exigir login na AWS — só uma **chave de
acesso** (guardada no Bitwarden do grupo), enviada como cabeçalho
`X-Admin-Key`.

## O que foi adicionado

| Peça | Onde | Para quê |
|---|---|---|
| `backend/admin/index.js` + `package.json` | nova função Lambda `AdminDashboardFunction` | Confere a chave, consulta o CloudWatch (imagens dos gráficos + tabelas de log) e devolve tudo em JSON |
| Rota `GET /admin/dashboard` | `backend/template.yaml` | Exposta no mesmo `api.neshiku.com.br` de sempre (herda a proteção da Cloudflare) |
| Parâmetro `AdminAccessKey` (NoEcho) | `backend/template.yaml` | A chave em si — nunca fica salva em texto no repositório |
| `frontend/public/admin/index.html` | página estática, sem build especial | Pede a chave, chama a API e desenha os painéis |
| `cloudfront/admin-url-rewrite.js` + `cloudfront_attach_function.py` | raiz do repositório | Faz `/admin` (sem `.html`) funcionar no CloudFront |

Como funciona o controle de acesso, resumido: a chave nunca é commitada em
lugar nenhum; ela vive só como parâmetro `NoEcho` do SAM (fica guardada
dentro da AWS, criptografada) e como variável de ambiente da função. Vocês
guardam a mesma chave no Bitwarden (ou outro gerenciador) para poder digitar
na página quando precisarem consultar os painéis. Sem a chave certa, a API
responde `403` e a página não mostra nada — é exatamente o mesmo padrão já
usado para bloquear acesso direto ao backend (`ORIGIN_SECRET`), só que numa
segunda camada, específica da observabilidade.

## Passo a passo

### 1. Gerar a chave de acesso

No PowerShell, gere algo aleatório e forte (não precisa ser bonito, só
imprevisível):

```powershell
-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 40 | % {[char]$_})
```

Copie o resultado e salve **imediatamente** no Bitwarden (ex.: item "Todo App
— Admin Observabilidade"), com o link `https://app.neshiku.com.br/admin`
junto. Não cole essa chave em nenhum arquivo do repositório.

### 2. Deploy do backend (SAM)

```powershell
cd backend
sam build
sam deploy --parameter-overrides OriginSecret=SEU_ORIGIN_SECRET_ATUAL LogRetentionInDays=30 AdminAccessKey=A_CHAVE_QUE_VOCE_ACABOU_DE_GERAR
```

(o `OriginSecret` é o mesmo valor já em uso — ver `DEPLOY-ENTREGA2.md` para
onde consultá-lo se não estiver anotado).

### 3. Publicar a CloudFront Function que faz `/admin` funcionar

O CloudFront só serve `index.html` automaticamente na raiz do domínio; para
`/admin` funcionar sem precisar digitar `/admin/index.html`, é preciso uma
CloudFront Function pequena que já está escrita (`cloudfront/admin-url-rewrite.js`)
e um script que a publica e associa à distribuição (`cloudfront_attach_function.py`,
na raiz do repositório):

```powershell
cd ..   # volta pra raiz do repositório
pip install boto3 --break-system-packages   # se ainda não tiver
python cloudfront_attach_function.py
```

O script identifica sozinho a distribuição pelo domínio `app.neshiku.com.br`,
publica a function e a associa ao comportamento padrão (evento
`viewer-request`), além de invalidar o cache de `/admin*`. Se ele não achar a
distribuição automaticamente, ele imprime o passo manual equivalente pelo
console.

Aguarde a distribuição voltar para o status **Deployed** no console do
CloudFront antes de testar (normalmente poucos minutos).

### 4. Publicar o front-end (inclui a página `/admin`)

Mesmo processo de sempre — o build do React já inclui `public/admin/index.html`
automaticamente:

```powershell
cd frontend
npm run build
aws s3 sync build/ s3://todo-app-neshiku-frontend-1 --delete
aws s3 sync build/ s3://todo-app-neshiku-frontend-2 --delete
```

### 5. Testar

1. Abra `https://app.neshiku.com.br/admin`.
2. Cole a chave salva no Bitwarden.
3. Confirme que os 5 painéis carregam com dados reais (pode levar alguns
   segundos — a página consulta métricas e faz consultas do Logs Insights na
   hora).
4. Teste também o bloqueio: tente uma chave errada (deve aparecer "chave
   inválida" e nada de dado sensível) e tente chamar a API diretamente sem
   passar pela Cloudflare (deve dar `403` por causa do `ORIGIN_SECRET`, antes
   mesmo de checar a chave de admin).

## Custo

`GetMetricWidgetImage` e Logs Insights têm custo por chamada/GB escaneado,
mas irrelevante no volume desta atividade (poucas dezenas de acessos à
página). A função `AdminDashboardFunction` só roda quando alguém abre a
página — sem uso, sem custo (mesmo modelo serverless do resto da aplicação).
