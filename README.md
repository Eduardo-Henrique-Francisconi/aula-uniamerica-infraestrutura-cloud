# Todo App — Infraestrutura Serverless com Segurança e Observabilidade em Nuvem

Fork de [`aula-uniamerica-infraestrutura-cloud`](https://github.com/LaercioMLB/aula-uniamerica-infraestrutura-cloud) usado nas atividades de infraestrutura em nuvem da disciplina. O código da aplicação (Todo App — React no front-end, Express no back-end) não foi alterado em sua lógica de negócio; o trabalho do grupo foi construir a **infraestrutura serverless, a segurança e a observabilidade** em volta dela.

**Aplicação no ar:** front-end em https://app.neshiku.com.br · API em https://api.neshiku.com.br
**Domínio:** `neshiku.com.br` (Registro.br, DNS delegado para a Cloudflare)
**Conta AWS:** `005042706931`, região principal `us-east-2`

Este README é o ponto de entrada do repositório: explica o que cada parte do código faz e organiza os links para toda a documentação, em duas frentes — **Entrega 1** (infraestrutura: domínio, DNS, proxy reverso, redundância, segurança) e **Entrega 2** (observabilidade: dashboard, métricas, logs, testes).

---

## Arquitetura, em uma frase

```
Usuário → Cloudflare (DNS + proxy reverso + HTTPS)
            ├─ app.neshiku.com.br → CloudFront → S3 (2 buckets, com failover) — front-end
            └─ api.neshiku.com.br → API Gateway → Lambda → DynamoDB — back-end + banco
```

Front-end e back-end são 100% serverless (S3+CloudFront e Lambda+API Gateway), o banco (DynamoDB) não tem nenhum endpoint público, e todo acesso passa pela Cloudflare, que funciona como DNS e proxy reverso.

## 📐 Diagrama técnico da arquitetura

### **→ [Abrir o diagrama: `diagrama-arquitetura.html`](diagrama-arquitetura.html)**

**Como visualizar:** clicar no arquivo aqui no GitHub mostra o *código-fonte*, não o desenho. Para ver o diagrama, use o botão **Download raw file** (canto superior direito da página do arquivo) e abra o arquivo baixado com duplo clique no navegador. Ele é autossuficiente — não precisa de internet, servidor nem nada instalado.

Dentro dele há botões para **exportar tudo em PNG** (diagramas + legenda, a imagem é gerada na hora a partir do próprio arquivo, então edições aparecem automaticamente) e para **salvar em PDF**.

O diagrama está dividido em duas visões, com legenda comum:

| Parte | O que mostra |
|---|---|
| **Diagrama 1 — Aplicação** | Domínio, DNS e os destinos reais de cada registro, proxy reverso, front-end com as duas origens redundantes, back-end, banco de dados, portas e protocolos, os dois pontos de terminação TLS, e os fluxos permitidos e bloqueados — cada bloqueio indicando **onde exatamente** é decidido |
| **Diagrama 2 — Observabilidade** | O caminho completo do dado para as 4 fontes: componente que gera → coleta/encaminhamento → armazenamento/consulta → painel; e quem pode consultar os dados, com qual mecanismo de controle |
| **Legenda + guia de configuração** | Significado de cada tipo de seta, tabela de comunicações permitidas/bloqueadas com porta e protocolo, observações de fidelidade (inclusive o que não pôde ser comprovado), e uma tabela de **onde encontrar cada configuração** no console de cada ferramenta (Cloudflare, AWS, Registro.br), com o caminho de menus |

## Serviços e ferramentas utilizados, e por que foram escolhidos

| Camada | Serviço/ferramenta | Por que foi escolhido |
|---|---|---|
| Front-end | **Amazon S3** (2 buckets, `us-east-2` e `us-west-2`) + **Amazon CloudFront** | Hospedagem estática 100% serverless, sem servidor para gerenciar; dois buckets em regiões diferentes dão redundância geográfica real, e o CloudFront distribui/roteia entre eles automaticamente via Origin Group (failover em 403/404/500/502/503/504). |
| Back-end | **AWS Lambda** + **Amazon API Gateway** (HTTP API) | Modelo 100% serverless (paga por execução, escala sozinho, sem instância fixa para administrar), com o API Gateway como porta de entrada controlada — permite rotas explícitas, CORS restrito e métricas nativas por rota. |
| Banco de dados | **Amazon DynamoDB** | Banco gerenciado e serverless (sem instância, sem patch, sem capacidade fixa — `PAY_PER_REQUEST`), e por padrão **não tem endpoint público**: só é acessível via API assinada da AWS, o que já resolve boa parte do requisito de segurança do banco sem esforço extra. |
| DNS / Proxy reverso | **Cloudflare** (plano gratuito) | DNS gerenciado, proxy reverso com HTTPS automático na borda e Transform Rules gratuitas — usadas aqui para injetar o cabeçalho secreto que bloqueia acesso direto ao back-end. Funciona com domínio comprado em qualquer lugar, sem prender a escolha do domínio a um provedor de nuvem específico. |
| Domínio | **Registro.br** | Registrador oficial para domínios `.com.br`, processo simples e custo baixo de registro/gestão dos nameservers. |
| Certificados (origem AWS) | **AWS Certificate Manager (ACM)** | Necessário para o CloudFront e para o custom domain do API Gateway aceitarem o `Host` correto com HTTPS; validado por DNS, sem custo adicional. |
| Observabilidade | **Amazon CloudWatch** (Logs, Metrics, Logs Insights, Dashboard) | Toda a infraestrutura já é AWS, e o CloudWatch é o serviço nativo de observabilidade dela — API Gateway e DynamoDB já publicam métricas automaticamente nele, o Lambda já envia logs pra lá sem nenhum agente extra, e o Logs Insights permite consultar esses logs sem precisar de um banco de dados de logs separado. Fica dentro do free tier para o volume desta atividade e não abre nenhum novo ponto de acesso público (acesso só via login IAM da conta). |
| Agendamento do canário | **Amazon EventBridge** (regra agendada) | Serverless, nativo da AWS, dispensa um servidor/cron externo só para chamar a função de checagem a cada 5 minutos. |

A justificativa completa de cada escolha (com mais detalhe e comparações) está em `documentacao.md` (Seção 1, infraestrutura) e `documentacao-observabilidade.md` (Seção 1, observabilidade).

## Painéis do dashboard de observabilidade

O dashboard `todo-app-observabilidade` tem 4 painéis, cada um com um documento próprio de fundamentação completa (10 itens exigidos pela atividade — pergunta operacional, motivo da escolha, origem dos dados, consulta/cálculo, recorte temporal, forma de visualização, interpretação, critérios de atenção, ação decorrente, validação e limitações — mais o alcance do painel e como interpretar períodos sem dados):

| Painel | Pergunta operacional | Documento |
|---|---|---|
| 1 — Disponibilidade | O domínio (front-end e API) está acessível pelo domínio configurado? | [`paineis-observabilidade/painel-1-disponibilidade.md`](paineis-observabilidade/painel-1-disponibilidade.md) |
| 2 — Desempenho | Quais operações da API estão demorando mais, e em quais períodos? | [`paineis-observabilidade/painel-2-desempenho.md`](paineis-observabilidade/painel-2-desempenho.md) |
| 3 — Erros | Quais falhas estão ocorrendo, e qual parcela das requisições elas representam? | [`paineis-observabilidade/painel-3-erros.md`](paineis-observabilidade/painel-3-erros.md) |
| 4 — Banco de Dados | As operações do back-end com o DynamoDB estão funcionando, e com qual duração? | [`paineis-observabilidade/painel-4-banco-de-dados.md`](paineis-observabilidade/painel-4-banco-de-dados.md) |

Índice completo da pasta (com o mapa de onde ficam as evidências de cada painel): [`paineis-observabilidade/README.md`](paineis-observabilidade/README.md).

## O que tem em cada pasta

| Pasta/arquivo | O que é |
|---|---|
| `frontend/` | Código do Todo App em React (não alterado — herdado do repositório original). Build de produção enviado para os dois buckets S3. |
| `backend/` | Lambda (Express + `serverless-http`) + definição de toda a infraestrutura como código (`template.yaml`, AWS SAM). É aqui que vivem as rotas da API, os logs estruturados, o canário de disponibilidade e a definição do dashboard do CloudWatch. |
| `backend/healthcheck/` | Função Lambda do canário de disponibilidade (Entrega 2) — checa `app.neshiku.com.br` e `api.neshiku.com.br` a cada 5 minutos. |
| `paineis-observabilidade/` | Um documento por painel do dashboard (ver seção "Painéis do dashboard de observabilidade" acima). |
| `evidencias_observabilidade/` | Imagens (PNG) dos widgets do dashboard, capturadas automaticamente pelo script de testes. |
| `cloudfront/` | Scripts/functions do CloudFront relacionados à distribuição do front-end. |
| `banco-de-dados/`, `docker-compose.yaml` | **Não usados no deploy em nuvem** — são o setup de desenvolvimento local (Docker + MongoDB) herdado do repositório original antes do fork. A aplicação em produção usa DynamoDB, sem Docker. Mantidos só por serem parte do repositório-base. |
| `run_tests.py` / `relatorio_testes.md` | Script e relatório dos 7 testes exigidos pela **Entrega 1**. |
| `observabilidade_testes.py` / `relatorio_testes_observabilidade.md` | Script e relatório dos testes da **Entrega 2** — 100% automático (ver seção de testes abaixo). |

---

## 1. Documentação objetiva

O que foi usado, por quê, e como cada painel funciona — sem precisar ler o código para entender as decisões.

| Documento | Conteúdo |
|---|---|
| [`documentacao.md`](documentacao.md) | **Entrega 1.** Serviços de nuvem usados e por que foram escolhidos, como a segurança foi implementada, como funciona a redundância do front-end, como funciona o proxy reverso, como o domínio foi configurado, quais acessos foram permitidos/bloqueados. |
| [`documentacao-observabilidade.md`](documentacao-observabilidade.md) | **Entrega 2.** O que mudou na infraestrutura desde a Entrega 1, ferramenta de observabilidade escolhida e por quê, resumo dos 4 painéis, geração/coleta/retenção de logs, controle de acesso à observabilidade, ponteiro para o diagrama e para os testes. |
| [`paineis-observabilidade/`](paineis-observabilidade/README.md) | Fundamentação completa (10 itens) de cada um dos 4 painéis — ver a seção "Painéis do dashboard de observabilidade" acima para os links diretos. |
| 📐 **[`diagrama-arquitetura.html`](diagrama-arquitetura.html)** | **Diagrama técnico fiel à implementação** (fonte editável), com as duas visões — aplicação e observabilidade —, os nomes/IDs reais dos recursos, o guia de onde achar cada configuração no console de cada ferramenta, e as limitações declaradas. Como abrir e exportar: ver a seção [📐 Diagrama técnico da arquitetura](#-diagrama-técnico-da-arquitetura), acima. |
| [`relatorio_testes.md`](relatorio_testes.md) | Evidências dos 7 testes da Entrega 1 (comando executado + resposta obtida + PASS/FAIL, um por um). |
| [`relatorio_testes_observabilidade.md`](relatorio_testes_observabilidade.md) | Evidências dos testes da Entrega 2: tráfego real, canário, falha controlada, failover do front-end com o canário rodando durante a queda, e verificação de que as métricas/logs de cada painel têm dado real — tudo com veredito PASS/FAIL. |
| [`evidencias_observabilidade/`](evidencias_observabilidade/) | Capturas de tela reais dos widgets de métrica do dashboard, geradas automaticamente (não são prints manuais). |
| [`entrega-final.md`](entrega-final.md) / [`entrega-final-observabilidade.md`](entrega-final-observabilidade.md) | Checklist de cada entrega — o que foi exigido e o status de cada item. |

## 2. Configurações e código

Onde estão as alterações de instrumentação e a definição dos painéis/coleta — e como reproduzi-los.

A ferramenta de observabilidade escolhida foi o **Amazon CloudWatch**, e a peça mais importante desta seção é que **o dashboard inteiro é definido como código**, não configurado manualmente pelo console: o recurso `AWS::CloudWatch::Dashboard` dentro de `backend/template.yaml` contém o JSON completo de cada widget (métrica, consulta de Logs Insights, período, estatística). Isso significa que não há limitação de exportação — reproduzir os painéis é rodar `sam deploy`, não copiar passos manuais do console.

| Onde | O que tem lá |
|---|---|
| `backend/template.yaml` | **Fonte de verdade da infraestrutura e da observabilidade.** Rotas explícitas do API Gateway, `DetailedMetricsEnabled`, log groups com retenção, a função do canário (`HealthCheckFunction`) e seu agendamento (EventBridge), os 3 `AWS::Logs::MetricFilter` que viram os logs do canário em métricas, e o `AWS::CloudWatch::Dashboard` com a definição completa dos 4 painéis (todas as consultas/expressões de métrica e todas as queries de Logs Insights ficam ali, versionadas). |
| `backend/index.js` | Instrumentação do backend: logs estruturados em JSON (`http_request`, `db_operation`) e a rota `GET /todos-falha-simulada` usada no teste de falha controlada. |
| `backend/healthcheck/index.js` | Código do canário de disponibilidade — a única peça de observabilidade que não vem de métrica nativa de nenhum serviço gerenciado. |
| `backend/DEPLOY.md` | Passo a passo do deploy inicial da infraestrutura (Entrega 1). |
| `backend/DEPLOY-ENTREGA2.md` | Passo a passo do deploy das mudanças de observabilidade (Entrega 2) — o que mudou, comandos, troubleshooting, custo esperado. |
| `observabilidade_testes.py` | Roda os testes E reproduz a coleta de evidências sozinho: gera tráfego real, invoca o canário, provoca a falha controlada, testa o failover do front-end com o canário rodando durante a queda, verifica se as métricas/logs de cada painel têm dado real e baixa as imagens dos widgets via `GetMetricWidgetImage` — sem nenhum passo manual. |
| `run_tests.py` | Equivalente da Entrega 1: os 7 testes exigidos, com PASS/FAIL automático. |

### Como reproduzir

```powershell
cd backend
sam build
sam deploy --parameter-overrides OriginSecret=<segredo-atual> LogRetentionInDays=30
```

Isso já recria o dashboard, as métricas customizadas e os log groups do zero, exatamente como estão definidos em `template.yaml` (roteiro completo em `backend/DEPLOY-ENTREGA2.md`). Depois do deploy, `python observabilidade_testes.py` gera tráfego real e regenera `relatorio_testes_observabilidade.md` + `evidencias_observabilidade/` automaticamente.

---

## Status das entregas

| Entrega | Status |
|---|---|
| 1 — Infraestrutura | ✅ Concluída — 7/7 testes PASS (`relatorio_testes.md`) |
| 2 — Observabilidade | ✅ Deploy no ar, 4 painéis com dado real, 7/7 verificações automáticas PASS (`relatorio_testes_observabilidade.md`) |
