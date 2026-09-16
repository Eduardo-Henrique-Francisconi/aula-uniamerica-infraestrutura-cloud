# Entrega — Aplicação Serverless com Segurança em Nuvem

**Grupo/Aluno:** NEKO
**Domínio:** neshiku.com.br

---

## ✅ Checklist — está tudo certo

| Item exigido | Status |
|---|---|
| Front-end serverless, redundante, HTTPS, domínio próprio | ✅ OK |
| Back-end serverless, não exposto direto, via API, proxy reverso | ✅ OK |
| Banco de dados gerenciado, sem acesso público, só o back-end acessa | ✅ OK |
| Domínio + DNS + proxy reverso configurados | ✅ OK |
| Segurança (regras claras, bloqueado por padrão) | ✅ OK |
| Diagrama da arquitetura | ✅ OK |
| Documentação curta | ✅ OK |
| Testes com evidências (7/7) | ✅ OK — todos passaram |

---

## Onde está cada coisa

| Peça exigida pela atividade | Onde está / o que é | Endereço |
|---|---|---|
| **Domínio** | Registrado no Registro.br | `neshiku.com.br` |
| **DNS** | Cloudflare (zona do domínio, nameservers delegados) | painel: dash.cloudflare.com → zona `neshiku.com.br` |
| **Proxy reverso** | Cloudflare (registros DNS "proxied" + Transform Rule que injeta o header secreto) | mesmo painel Cloudflare → DNS / Rules |
| **Front-end** | 2 buckets Amazon S3 (redundantes, privados) atrás de uma distribuição Amazon CloudFront | acesso público: `https://app.neshiku.com.br` |
| **Back-end / API** | AWS Lambda por trás de um Amazon API Gateway (HTTP API) | acesso público: `https://api.neshiku.com.br` |
| **Banco de dados** | Amazon DynamoDB, tabela `todos-table` — sem endpoint público | só acessível pela role do Lambda (não tem URL pública) |
| **Diagrama da arquitetura** | arquivo `diagrama-arquitetura.html` | anexar ao Blackboard |
| **Documentação curta** | arquivo `documentacao.md` | anexar ao Blackboard |
| **Evidência dos testes** | arquivo `relatorio_testes.md` (7/7 PASS, comando + saída de cada teste) | anexar ao Blackboard |
| **Código-fonte (fork)** | repositório no GitHub | https://github.com/Eduardo-Henrique-Francisconi/aula-uniamerica-infraestrutura-cloud |

---

## Por que escolhi cada nuvem/serviço

**AWS (para a aplicação em si — front-end, back-end e banco):**
- É o provedor com o free tier mais generoso para os serviços serverless que a atividade pede (Lambda, API Gateway, DynamoDB, S3, CloudFront praticamente não custam nada no volume de uso de uma atividade acadêmica).
- Tem exatamente um serviço gerenciado/serverless para cada camada exigida: Lambda (compute sem servidor), API Gateway (porta de entrada controlada da API), DynamoDB (banco NoSQL totalmente gerenciado, sem servidor pra administrar) e S3+CloudFront (hospedagem estática redundante com CDN global).
- Integração nativa entre os serviços (IAM Roles, Origin Access Control, certificados ACM) facilita implementar segurança "de fábrica" — por exemplo, o DynamoDB já nasce sem endpoint público, e os buckets S3 já nascem privados.

**Cloudflare (para DNS e proxy reverso):**
- Plano gratuito já inclui DNS gerenciado, proxy reverso (o "cloud laranja") e HTTPS automático na borda — exatamente o que a atividade pede, sem custo.
- As Transform Rules (também gratuitas) permitem implementar o controle de acesso "só passa quem vier pela Cloudflare" de forma simples, injetando um cabeçalho que o back-end exige — resolvendo o requisito de o back-end não poder ser acessado diretamente pela internet.
- Funciona com qualquer domínio comprado em qualquer lugar (bastou apontar os nameservers do Registro.br pra Cloudflare), então não prendeu a escolha de domínio a nenhum provedor de nuvem específico.

**Registro.br (para o domínio):**
- É o registrador oficial para domínios `.com.br`, com preço baixo e processo simples de registro e gestão dos nameservers.

---

## Texto pronto para colar na entrega

Copie o texto abaixo (ajuste o link do repositório) na caixa de entrega do Blackboard:

```
Aplicação Serverless com Segurança em Nuvem

Domínio utilizado: neshiku.com.br
Front-end: https://app.neshiku.com.br
Back-end/API: https://api.neshiku.com.br

Repositório (fork): https://github.com/Eduardo-Henrique-Francisconi/aula-uniamerica-infraestrutura-cloud

Por que essas nuvens:
- AWS para a aplicação (front-end, back-end e banco): free tier generoso e um
  serviço serverless gerenciado para cada camada (Lambda, API Gateway,
  DynamoDB, S3 + CloudFront), com segurança nativa (roles IAM restritas,
  buckets privados, banco sem endpoint público).
- Cloudflare para DNS e proxy reverso: plano gratuito já cobre DNS, proxy
  reverso e HTTPS automático, e as Transform Rules permitiram implementar o
  bloqueio de acesso direto ao back-end de forma simples.
- Registro.br para o domínio .com.br: registrador oficial, simples e barato.

Resumo da infraestrutura:
- Front-end: hospedado em dois buckets Amazon S3 (regiões us-east-2 e us-west-2),
  servidos via Amazon CloudFront com failover automático entre as duas origens.
  Acesso via HTTPS pelo domínio próprio (app.neshiku.com.br), com certificado
  emitido pela AWS Certificate Manager.
- Back-end: AWS Lambda (Node.js) por trás de um Amazon API Gateway (HTTP API),
  acessado via domínio próprio (api.neshiku.com.br). Não é acessível diretamente
  pela URL da AWS: qualquer chamada fora do proxy reverso é bloqueada com 403.
- Banco de dados: Amazon DynamoDB, sem endpoint público, acessível somente pela
  IAM Role restrita da função Lambda.
- DNS e proxy reverso: Cloudflare, responsável por rotear as requisições do
  domínio para o CloudFront (front-end) e para o API Gateway (back-end), aplicar
  HTTPS na borda e injetar um cabeçalho de autenticação exigido pelo back-end.
- Segurança: regra geral de "tudo bloqueado, exceto o necessário" aplicada em
  todas as camadas (back-end, banco de dados e buckets S3), com testes
  comprovando os bloqueios (ver relatorio_testes.md).

Anexos desta entrega:
1. diagrama-arquitetura.html — diagrama completo da arquitetura
2. documentacao.md — documentação explicando serviços, segurança, redundância,
   proxy reverso e configuração do domínio
3. relatorio_testes.md — evidências dos 7 testes exigidos (comando + resultado
   de cada um), todos com resultado PASS
```

---

## Arquivos para anexar na entrega

- `diagrama-arquitetura.html`
- `documentacao.md`
- `relatorio_testes.md`
