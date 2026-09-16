# Documentação — Infraestrutura Serverless com Segurança em Nuvem

**Aplicação:** Todo App (fork de `aula-uniamerica-infraestrutura-cloud`)
**Repositório:** https://github.com/Eduardo-Henrique-Francisconi/aula-uniamerica-infraestrutura-cloud
**Domínio:** neshiku.com.br
**Front-end:** https://app.neshiku.com.br
**Back-end/API:** https://api.neshiku.com.br

## 1. Serviços de nuvem utilizados e por que foram escolhidos

| Camada | Serviço | Motivo da escolha |
|---|---|---|
| Front-end | Amazon S3 (2 buckets, `us-east-2` e `us-west-2`) + Amazon CloudFront | Hospedagem estática serverless, sem servidor para gerenciar; dois buckets em regiões diferentes dão redundância geográfica real, e o CloudFront distribui/roteia entre eles |
| Back-end | AWS Lambda + Amazon API Gateway (HTTP API) | Modelo 100% serverless (paga por execução, escala automaticamente, sem servidor fixo), com o API Gateway atuando como porta de entrada controlada para a função |
| Banco de dados | Amazon DynamoDB | Banco gerenciado e serverless (sem instância para administrar), com billing `PAY_PER_REQUEST`, e sem endpoint público por padrão — acesso só é possível via API assinada da AWS |
| DNS / Proxy reverso | Cloudflare (plano gratuito) | DNS gerenciado, proxy reverso com HTTPS automático (certificado próprio da Cloudflare na borda) e Transform Rules gratuitas, usadas aqui para reforçar controle de acesso ao back-end |
| Domínio | Registro.br | Domínio `.com.br` próprio, com DNS delegado para os nameservers da Cloudflare |
| Certificados (origem AWS) | AWS Certificate Manager (ACM) | Necessário para o CloudFront e para o custom domain do API Gateway aceitarem o `Host` correto com HTTPS, validado via DNS |

Todos os serviços utilizados (Lambda, API Gateway, DynamoDB, S3, CloudFront) entram, na prática, no free tier da AWS para o volume de uso da atividade, e a Cloudflare foi usada no plano gratuito.

**Por que AWS para a aplicação (front-end, back-end e banco):** é o provedor com o free tier mais generoso para os serviços serverless exigidos, e tem exatamente um serviço gerenciado para cada camada pedida pela atividade — Lambda (compute sem servidor), API Gateway (porta de entrada controlada da API), DynamoDB (banco NoSQL totalmente gerenciado) e S3 + CloudFront (hospedagem estática redundante com CDN). A integração nativa entre esses serviços (IAM Roles, Origin Access Control, certificados ACM) também facilita implementar segurança "de fábrica": o DynamoDB já nasce sem endpoint público e os buckets S3 já nascem privados.

**Por que Cloudflare para DNS e proxy reverso:** o plano gratuito já cobre DNS gerenciado, proxy reverso e HTTPS automático na borda, exatamente o que a atividade exige, sem custo. As Transform Rules (também gratuitas) permitiram implementar o controle "só passa quem vier pela Cloudflare" de forma simples, injetando um cabeçalho que o back-end exige — resolvendo o requisito de o back-end não poder ficar exposto diretamente à internet. Além disso, a Cloudflare funciona com domínio comprado em qualquer lugar, não prendendo a escolha do domínio a um provedor de nuvem específico.

**Por que Registro.br para o domínio:** é o registrador oficial para domínios `.com.br`, com processo simples e custo baixo de registro e gestão dos nameservers.

## 2. Como a segurança foi implementada

A regra seguida foi: **tudo bloqueado, exceto o estritamente necessário para o funcionamento.**

- **HTTPS obrigatório em toda a borda pública.** O usuário sempre fala com a Cloudflare por HTTPS (443); a Cloudflare fala com o CloudFront e com o API Gateway também por HTTPS, usando certificados emitidos pelo AWS Certificate Manager (validados por DNS) tanto para `app.neshiku.com.br` (região `us-east-1`, exigência do CloudFront) quanto para `api.neshiku.com.br` (região `us-east-2`, mesma região da API).
- **Back-end não fica diretamente exposto.** O código do Lambda (`index.js`) exige um cabeçalho HTTP customizado, `X-Origin-Verify`, com um valor secreto. Uma **Transform Rule** configurada na Cloudflare injeta automaticamente esse cabeçalho em toda requisição que passa por `api.neshiku.com.br`. Qualquer chamada feita diretamente à URL bruta do API Gateway (`https://xxxx.execute-api.us-east-2.amazonaws.com`), pulando a Cloudflare, não tem esse cabeçalho e recebe **403 Forbidden**. Na prática, a Cloudflare funciona como o único portão de entrada autorizado ao back-end.
- **Banco de dados sem acesso público.** O DynamoDB não expõe porta ou IP público navegável: toda chamada à API da AWS precisa ser assinada (SigV4) com credenciais válidas. A única identidade com permissão de leitura/escrita na tabela `todos-table` é a **IAM Role da função Lambda**, criada com a policy gerenciada `DynamoDBCrudPolicy` do AWS SAM, restrita especificamente a essa tabela (não há permissão de administrador nem acesso a outras tabelas).
- **Front-end sem acesso direto aos buckets.** Os dois buckets S3 são privados (Block Public Access ativado); a única forma de ler os arquivos é através do **Origin Access Control (OAC)** do CloudFront, que autentica as requisições do CloudFront para o S3 internamente. Acessar a URL do bucket S3 diretamente é bloqueado.
- **CORS restrito** no API Gateway, liberando apenas os métodos usados pela aplicação (`GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS`).
- **Princípio do menor privilégio no IAM.** A função Lambda só tem a permissão mínima necessária (ler/escrever numa tabela específica do DynamoDB) — nenhuma outra permissão na conta AWS.

## 3. Como funciona a redundância do Front-end

O front-end é hospedado em **dois buckets S3 idênticos, em regiões diferentes da AWS** (`us-east-2` e `us-west-2`), cada um contendo uma cópia completa do build de produção do React.

Na frente dos dois buckets fica uma distribuição do **Amazon CloudFront** configurada com um **Origin Group**: o bucket de `us-east-2` é a origem primária e o de `us-west-2` é a origem secundária. O CloudFront está configurado para considerar a origem primária "falha" sempre que ela responder com os códigos `403`, `404`, `500`, `502`, `503` ou `504`, e nesse caso repassa automaticamente a requisição para a origem secundária, sem que o usuário perceba qualquer interrupção.

Esse comportamento foi testado na prática: o arquivo `index.html` do bucket primário foi temporariamente renomeado (simulando uma falha), e o site em `https://app.neshiku.com.br` continuou respondendo normalmente (`200 OK`), servido pela origem secundária. Depois o arquivo original foi restaurado.

## 4. Como funciona o proxy reverso

A **Cloudflare** atua como proxy reverso para as duas partes públicas da aplicação:

- Os registros DNS `app` (aponta para o domínio do CloudFront) e `api` (aponta para o domínio regional do API Gateway) estão configurados como **"proxied"** (nuvem laranja) na Cloudflare, em vez de "DNS only". Isso significa que o tráfego não vai direto do navegador do usuário para a AWS — ele passa primeiro pela borda da Cloudflare, que termina a conexão HTTPS do cliente, aplica suas regras (incluindo a injeção do cabeçalho `X-Origin-Verify` nas requisições para a API) e só então encaminha a requisição para o destino real na AWS.
- Isso cumpre o papel de proxy reverso exigido pela atividade: o usuário nunca enxerga ou usa diretamente os endereços da AWS (`*.cloudfront.net` ou `*.execute-api.amazonaws.com`) — apenas os domínios `app.neshiku.com.br` e `api.neshiku.com.br`.
- Registros DNS adicionais, do tipo CNAME e sem proxy ("DNS only"), foram usados apenas durante a etapa de validação dos certificados ACM (exigência da própria AWS para emitir os certificados).

## 5. Como o domínio foi configurado

1. Domínio `neshiku.com.br` registrado no Registro.br.
2. Nameservers do domínio alterados no Registro.br para os nameservers da Cloudflare (`ashton.ns.cloudflare.com` e `itzel.ns.cloudflare.com`), delegando a zona DNS inteira para a Cloudflare.
3. Na Cloudflare, criados os registros:
   - `app.neshiku.com.br` → CNAME para o domínio da distribuição CloudFront, com proxy ativado.
   - `api.neshiku.com.br` → CNAME para o domínio regional (target domain name) do custom domain do API Gateway, com proxy ativado.
4. No lado da AWS, foram criados os **custom domain names**, tanto no CloudFront (Alternate Domain Name / CNAME `app.neshiku.com.br` + certificado ACM) quanto no API Gateway (custom domain `api.neshiku.com.br` + certificado ACM + mapeamento para a API), pois tanto o CloudFront quanto o API Gateway rejeitam requisições cujo cabeçalho `Host` não corresponda a um domínio que eles reconheçam — um CNAME "solto" apontando para o hostname padrão da AWS não seria suficiente.

## 6. Quais acessos foram permitidos e bloqueados

**Permitidos:**
- Usuário → `app.neshiku.com.br` (HTTPS/443) → Cloudflare → CloudFront → S3 (via OAC).
- Navegador (front-end) → `api.neshiku.com.br` (HTTPS/443, com `X-Origin-Verify` injetado pela Cloudflare) → API Gateway → Lambda.
- Lambda → DynamoDB (API interna da AWS, assinada via SigV4, permitida apenas pela IAM Role restrita da função).

**Bloqueados:**
- Internet → URL crua do API Gateway (`*.execute-api.amazonaws.com`), sem passar pela Cloudflare → **403 Forbidden** (falta o cabeçalho secreto).
- Internet → Amazon DynamoDB diretamente → rejeitado, sem endpoint público e sem credencial IAM assinada.
- Internet → buckets S3 diretamente (sem passar pelo CloudFront) → bloqueado pelo "Block Public Access" e pela política que só libera leitura ao Origin Access Control do CloudFront.

## 7. Evidências dos testes realizados

| # | Teste | Resultado |
|---|---|---|
| 1 | Acesso ao Front-end pelo domínio | `https://app.neshiku.com.br` responde 200 OK e carrega a aplicação |
| 2 | Acesso ao Back-end pelo domínio/API | `Invoke-WebRequest https://api.neshiku.com.br/todos` responde 200 OK |
| 3 | Front-end acessando o Back-end | Adicionar/marcar/excluir tarefa pela interface funciona de ponta a ponta |
| 4 | Back-end acessando o Banco de Dados | Tarefa criada pela aplicação confirmada via `aws dynamodb scan --table-name todos-table`, aparecendo como item real da tabela |
| 5 | Acesso direto ao Back-end bloqueado | Chamada direta à URL do API Gateway retorna `403 Forbidden` ("Acesso direto não permitido") |
| 6 | Acesso direto ao Banco de Dados bloqueado | Chamada HTTP direta ao endpoint do DynamoDB, sem assinatura SigV4, é rejeitada pela AWS |
| 7 | Disponibilidade com um componente redundante fora do ar | Com o `index.html` do bucket primário indisponível, o site continuou respondendo 200 OK via failover para o bucket secundário |

(Prints e saídas de terminal de cada teste devem ser anexados junto com esta documentação na entrega final.)
