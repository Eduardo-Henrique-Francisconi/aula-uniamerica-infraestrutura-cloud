# Documentação — Observabilidade (Entrega 2)

**Aplicação:** Todo App (mesma da Entrega 1)
**Domínio:** neshiku.com.br · **Front-end:** https://app.neshiku.com.br · **Back-end/API:** https://api.neshiku.com.br
**Ferramenta de observabilidade:** Amazon CloudWatch (Logs, Metrics, Logs Insights e Dashboard)
**Dashboard:** `todo-app-observabilidade`, região `us-east-2`, conta AWS 005042706931

Este documento complementa `documentacao.md` (que continua valendo para domínio,
segurança, redundância do front-end e proxy reverso) com a fundamentação exigida
pela Entrega 2: o que mudou na infraestrutura, os 4 painéis do dashboard e o
raciocínio completo (necessidade → dado coletado → consulta/cálculo →
visualização → interpretação → ação) de cada um deles.

**Nota sobre a versão final do dashboard.** Os painéis foram planejados
originalmente como 5, mas o "Uso da aplicação" (contagem bruta de requisições
por rota) foi incorporado como série auxiliar dentro do Painel 3 (a métrica
`Count` já aparece ali como denominador da taxa de erro) em vez de ganhar um
painel próprio — o volume por rota já fica implícito no Painel 2 (presença/
ausência de pontos de latência por rota) e um painel dedicado só a "quantas
vezes cada rota foi chamada" não acrescentava uma pergunta operacional nova
frente aos outros 4. O dashboard final tem, portanto, 4 painéis: Disponibilidade,
Desempenho, Erros e Banco de Dados — todos com fundamentação completa (10
itens) na Seção 2. Dois widgets também mudaram de fonte de dado depois dos
primeiros testes reais (ver nota no Painel 3 e no Painel 4 abaixo) porque a
métrica nativa `5xxError` do API Gateway, quando dimensionada por rota
(`Resource`+`Method`), não publicou nenhum datapoint mesmo com tráfego de erro
real confirmado — substituída por uma consulta aos próprios logs do backend,
que é uma fonte igualmente legítima (e mais rica, porque já traz a rota junto).

## 0. Continuidade da Entrega 1 — o que mudou

A aplicação, o domínio, o HTTPS, os serviços serverless, o proxy reverso
(Cloudflare), a redundância do front-end (2 buckets S3 + CloudFront Origin
Group) e a proteção do back-end/banco descritos em `documentacao.md`
**continuam exatamente os mesmos**. As únicas mudanças foram:

| Mudança | Onde | Por quê |
|---|---|---|
| Rotas explícitas no API Gateway (`GET /todos`, `POST /todos`, `PATCH /todos/{id}`, `DELETE /todos/{id}`) em vez de um catch-all `/{proxy+}` | `backend/template.yaml` | Sem rotas nomeadas, o CloudWatch não consegue publicar métricas separadas por operação — tudo cairia numa métrica genérica única |
| `DefaultRouteSettings.DetailedMetricsEnabled: true` no HTTP API | `backend/template.yaml` | Liga as métricas nativas por rota (Count, 4xx/5xxError, Latency) |
| Log group do backend com retenção explícita (30 dias) | `backend/template.yaml` | Por padrão o Lambda cria o log group sem expiração — custo e volume crescendo para sempre |
| Logs estruturados em JSON (requisição HTTP e chamada ao DynamoDB) | `backend/index.js` | Os logs do Lambda antes eram só o console.log padrão do Express/erros não estruturados — insuficientes para os painéis de erro/banco |
| Rota `GET /todos-falha-simulada` | `backend/index.js` | Existe só para o teste controlado de falha exigido pela atividade — sempre devolve 500 |
| Nova função `HealthCheckFunction` (canário) + agendamento a cada 5 min via EventBridge | `backend/healthcheck/` + `backend/template.yaml` | É o único dado que não existe nativamente em nenhum serviço gerenciado da conta: "o domínio está no ar?" |
| 3 Metric Filters (`AWS::Logs::MetricFilter`) | `backend/template.yaml` | Transformam os logs do canário em métricas do CloudWatch |
| Dashboard `todo-app-observabilidade` (`AWS::CloudWatch::Dashboard`) | `backend/template.yaml` | Os 4 painéis do dashboard |

Nenhuma dessas mudanças altera o comportamento visível da aplicação para o
usuário final, nem os domínios/certificados já configurados.

## 1. Ferramenta de observabilidade escolhida e por quê

**Amazon CloudWatch**, pelos seguintes motivos:

- Toda a infraestrutura já é AWS (Lambda, API Gateway, DynamoDB, S3,
  CloudFront) — o CloudWatch é o serviço nativo de observabilidade dessa
  nuvem, sem precisar contratar/configurar uma ferramenta externa nem abrir
  uma nova conta em outro provedor.
- **API Gateway e DynamoDB já publicam métricas no CloudWatch automaticamente**
  (sem nenhuma configuração extra, além de ligar as métricas detalhadas por
  rota no API Gateway) — ou seja, 3 dos 4 painéis usam dado que a AWS já gera
  e já publica por conta própria.
- **CloudWatch Logs recebe automaticamente tudo que o Lambda escreve em
  `stdout`** — não foi necessário instalar/configurar nenhum agente de coleta
  de logs.
- **CloudWatch Logs Insights** permite consultar esses logs com uma linguagem
  de consulta parecida com SQL (sem precisar de um banco separado para logs),
  incluindo diretamente como widget do dashboard.
- **Custo**: dentro do free tier para o volume desta atividade (detalhado em
  `backend/DEPLOY-ENTREGA2.md`, seção "Custo esperado").
- **Sem novo ponto de acesso público**: o CloudWatch é acessado só pela
  mesma conta AWS/console já usado para o resto da infraestrutura — não abre
  uma nova superfície de exposição na internet.

A única peça que **não** existe nativamente em nenhum serviço gerenciado é
"o domínio está respondendo, do ponto de vista de um usuário real?" — por
isso foi criada a função `HealthCheckFunction` (um canário simples, feito à
mão), descrita no Painel 1.

## 2. Painéis — fundamentação completa (100%)

> A fundamentação completa e detalhada de cada painel (os 10 itens exigidos,
> mais o alcance de cada um e como interpretar períodos sem dados) está em
> documentos individuais na pasta [`paineis-observabilidade/`](paineis-observabilidade/README.md).
> O resumo abaixo cobre os mesmos 10 itens de forma mais compacta, para
> leitura rápida; use os arquivos da pasta como referência canônica.

### Painel 1 — Disponibilidade

**Nome e pergunta operacional.** "Disponibilidade" — a aplicação está
acessível pelo domínio configurado, tanto o front-end (`app.neshiku.com.br`)
quanto a API (`api.neshiku.com.br`)?

**Motivo da escolha.** É o requisito mais básico da atividade (domínio
funcionando) e o único item que nenhum serviço gerenciado da conta expõe
como métrica nativa — API Gateway e CloudFront só sabem dizer "quantas
requisições eu recebi", não "alguém de fora conseguiu me alcançar pelo
domínio público agora".

**Origem dos dados.** Função `HealthCheckFunction` (Lambda), disparada pelo
EventBridge (regra agendada `todo-app-healthcheck-schedule`) a cada 5 minutos. Ela faz uma requisição HTTPS real a
`https://app.neshiku.com.br/` e outra a `https://api.neshiku.com.br/todos`
— os mesmos domínios que um usuário usaria, passando pela Cloudflare da
mesma forma (o header `X-Origin-Verify` é injetado pela Transform Rule, não
pelo código do canário). Cada checagem grava uma linha JSON no CloudWatch
Logs (log group `HealthCheckFunction`) com os campos `target` (`frontend` ou
`api`), `result` (`success`/`failure`), `http_status` e `latency_ms`. Três
Metric Filters convertem essas linhas em métricas customizadas no namespace
`TodoApp/Availability`: `AvailabilitySuccess`, `AvailabilityFailure` e
`AvailabilityLatency`, todas dimensionadas por `Target`.

**Consulta e cálculo.** O widget soma (`Sum`) `AvailabilitySuccess` e
`AvailabilityFailure` por período de 5 minutos, uma série por `Target`. Um
segundo widget mostra a média (`Average`) de `AvailabilityLatency` no mesmo
período. Não há uma "taxa" calculada aqui de propósito: como a checagem só
roda a cada 5 min, cada período tem no máximo 1 amostra — uma taxa (%)
oscilaria só entre 0% e 100%, sem significado estatístico. Por isso o painel
mostra sucesso/falha como contagem simples.

**Recorte temporal.** Janela padrão de 3 horas no dashboard (ajustável),
período de agregação de 5 minutos (igual ao intervalo do agendamento),
atualização a cada nova execução do canário (a cada 5 min). Fuso: o
CloudWatch mostra os horários no fuso do navegador de quem está olhando; os
logs internos são gravados em UTC (`timestamp` em ISO-8601 UTC).

**Forma de visualização.** Série temporal (linha), porque a pergunta é
"como isso se comportou ao longo do tempo" — uma tabela não deixaria visível
um período de indisponibilidade tão rápido quanto um gráfico.

**Interpretação.** Comportamento esperado: `AvailabilitySuccess` presente e
constante em todo período de 5 min, para os dois `Target`s, com
`AvailabilityFailure` em zero e `AvailabilityLatency` estável. Um "buraco"
sem nenhum ponto (nem sucesso nem falha) significa que o **canário não
rodou** naquele período (ex.: erro na própria função, ou EventBridge
desabilitado) — isso é diferente de uma falha real e não deve ser lido como
"a aplicação caiu"; é preciso checar o log group do `HealthCheckFunction`
para diferenciar as duas situações.

**Critérios de atenção.** Qualquer valor de `AvailabilityFailure` maior que
zero já é motivo de investigação (o alvo esperado é 100% de sucesso). Para
latência, ainda não há um histórico longo suficiente de uso real para
definir um limite estatisticamente justificado (ex.: p95 histórico); por
ora, o critério é qualitativo — um salto muito acima da faixa observada nos
testes (ver Seção 6) já indica algo mudando na borda (Cloudflare) ou na
origem (CloudFront/API Gateway).

**Ação decorrente.** Uma falha de `frontend` indica investigar
CloudFront/Cloudflare/os dois buckets S3 (checar o Painel de redundância
descrito no Diagrama 1/2 e o console do CloudFront). Uma falha de `api`
indica checar API Gateway → Lambda → DynamoDB nessa ordem (o teste da API
percorre a cadeia inteira, incluindo um `Scan` no banco).

**Validação e limitações.** Testado invocando a função manualmente (fora do
agendamento) e confirmando a linha de log e o ponto correspondente na
métrica (ver `relatorio_testes_observabilidade.md`, Cenário 2). Limitação:
o canário roda de uma única região/localização (não é um teste multi-região
como um serviço de monitoramento comercial) — ele comprova que o domínio
responde a partir da rede da AWS na região `us-east-2`, não de todos os
pontos da internet.

### Painel 2 — Desempenho

**Nome e pergunta operacional.** "Desempenho" — quais operações da API
estão demorando mais, e em quais períodos?

**Motivo da escolha.** A aplicação já teve, na Entrega 1, uma rota (`GET
/todos`) que faz um `Scan` completo na tabela — uma operação que piora com
o crescimento dos dados. Sem medir latência por rota, um problema de
desempenho só seria percebido quando o usuário já estivesse reclamando.

**Origem dos dados.** Métrica nativa `Latency` do Amazon API Gateway
(namespace `AWS/ApiGateway`), publicada automaticamente pelo próprio
serviço a cada requisição, sem nenhum código no back-end. Ficou granular
por rota porque o `template.yaml` liga `DetailedMetricsEnabled: true` e
define rotas explícitas (`GET /todos`, `POST /todos`, `PATCH /todos/{id}`,
`DELETE /todos/{id}`) em vez do catch-all anterior.

**Consulta e cálculo.** Estatísticas `p50` (mediana) e `p95` (pior caso
"comum", ignorando os 5% mais extremos) da métrica `Latency`, uma série por
rota, unidade: milissegundos. Percentil, e não média, porque a média
esconde picos ocasionais (uma soma dividida pela contagem "dilui" um pico
raro; o p95 mostra ele).

**Recorte temporal.** Período de agregação de 5 minutos, janela padrão de 3
horas, atualização conforme o tráfego chega (near real-time, com o atraso
normal de publicação de métricas do CloudWatch, tipicamente 1–3 min).

**Forma de visualização.** Série temporal com uma linha por combinação
rota+percentil — permite comparar visualmente se `GET /todos` (que faz
`Scan`) é consistentemente mais lento que as demais.

**Interpretação.** Esperado: `PATCH`/`DELETE`/`GET`-por-id tendem a ser mais
rápidos (operações pontuais no DynamoDB, por chave); `GET /todos` (Scan) e
`POST /todos` (Put) tendem a ser um pouco mais lentos. Um afastamento grande
entre p50 e p95 de uma mesma rota indica variabilidade (nem toda chamada
está com o mesmo desempenho) — vale olhar o painel de Banco de Dados em
paralelo, já que a maior parte do tempo de resposta tende a ser a chamada ao
DynamoDB.

**Critérios de atenção.** Ainda não há um SLA formal definido para esta
atividade acadêmica; como referência inicial, uma p95 acima de ~1000ms (1s)
para qualquer rota já é alto para operações tão simples num banco de
item único/Scan pequeno, e motivaria investigação. Esse número não vem de
um estudo de carga — é só o piso de "isso claramente não devia demorar
tanto" para o tamanho atual da tabela; deve ser revisto à medida que o
volume de dados crescer.

**Ação decorrente.** Latência alta e crescente em `GET /todos` é o primeiro
sinal de que o `Scan` vai precisar ser substituído por uma consulta
paginada ou por um índice, à medida que a tabela cresce. Latência alta e
constante em todas as rotas aponta para o Lambda (cold start, memória
insuficiente) em vez do DynamoDB.

**Validação e limitações.** Testado gerando ~15 requisições de cada tipo
(Cenário 1 do roteiro de testes) e confirmando que a métrica `Latency`
aparece com pontos reais por rota no período do teste. Limitação: a métrica
de latência do API Gateway mede o tempo entre a requisição chegar ao API
Gateway e a resposta ser enviada — inclui o tempo de execução do Lambda e do
DynamoDB, mas não isola um do outro (para isso, veja o Painel 4, que usa a
métrica própria do DynamoDB).

### Painel 3 — Erros

**Nome e pergunta operacional.** "Erros" — quais falhas estão ocorrendo, e
qual parcela das requisições elas representam?

**Motivo da escolha.** É o indicador mais direto de "algo está quebrado" —
sem ele, um erro só é percebido se um usuário avisar. Também é o painel
usado para comprovar o cenário de falha controlada exigido pela atividade.

**Origem dos dados.** Duas fontes combinadas: (1) as métricas nativas
`4xxError`/`5xxError`/`Count` do API Gateway (`AWS/ApiGateway`), agregadas
para toda a API, usadas na taxa de erro; (2) os logs estruturados
`http_request` do `TodoFunction` (campos `route` e `status_code`),
consultados via CloudWatch Logs Insights tanto para a série de 5xx por
rota ao longo do tempo quanto para a tabela de causas — informação que a
métrica nativa, por si só, não separa por rota nem por causa.

**Nota sobre uma mudança de fonte de dado.** O widget "5xx por rota" foi
inicialmente implementado com a métrica nativa `5xxError` dimensionada por
`Resource`+`Method` (o equivalente nativo do "por rota" no API Gateway HTTP
API). Nos testes reais (Cenário 3, chamadas repetidas a
`/todos-falha-simulada` retornando 500 confirmado via status HTTP), essa
combinação específica de métrica+dimensões nunca publicou nenhum datapoint,
mesmo consultando a API do CloudWatch diretamente (sem passar pelo catálogo
de `list-metrics`, que tem um atraso de propagação próprio) — ao contrário
da métrica `Latency` com as mesmas dimensões, que funcionou normalmente. Não
foi possível confirmar a causa exata (suspeita: atraso/particularidade da
AWS na publicação de `5xxError` para uma combinação nova de dimensões). Como
o backend já registra a mesma informação (rota + status) em log estruturado,
o widget foi trocado para uma consulta de Logs Insights — fonte igualmente
legítima e, neste caso, mais confiável.

**Consulta e cálculo.** Widget 1 (taxa agregada): `100 * (Sum(5xxError) +
Sum(4xxError)) / Sum(Count)`, uma expressão de métrica calculada sobre toda
a API — unidade: porcentagem, numerador = requisições com erro, denominador
= total de requisições no mesmo período. Widget 2 (5xx por rota ao longo do
tempo, Logs Insights):

```
fields @timestamp, route, status_code
| filter event = "http_request" and status_code >= 500
| stats count() as erros by bin(5m) as periodo, route
| sort periodo asc
```

Widget 3 (causas, Logs Insights):

```
fields @timestamp, route, status_code, request_id
| filter event = "http_request" and status_code >= 400
| stats count() as ocorrencias by route, status_code
| sort ocorrencias desc
```

**Recorte temporal.** Período de agregação de 5 minutos para o widget de
métrica (taxa agregada); as duas consultas de Logs Insights rodam sobre a
janela de tempo escolhida no dashboard (padrão 3h) no momento em que o
painel é aberto/atualizado — a de "5xx por rota ao longo do tempo" agrupa
essa janela em blocos de 5 min (`bin(5m)`) para parecer uma série temporal
normal; a de "causas" é uma "foto" agregada da janela inteira, sem quebra
por tempo.

**Forma de visualização.** Série temporal para a taxa agregada e para os 5xx
por rota ao longo do tempo (ver tendência e localizar onde os erros de
servidor se concentram); tabela (Logs Insights) para a lista de causas — uma
tabela é melhor aqui porque a pergunta é "quais", não "quando".

**Interpretação.** Esperado: taxa de erro perto de 0% na maior parte do
tempo, subindo apenas quando há uma falha real (como no teste do Cenário 3)
ou um erro de uso genuíno (ex.: `POST /todos` sem o campo `text`, que
devolve 400 — esperado e não é um "bug"). Um pico isolado que desaparece
sozinho tende a ser transitório; um platô alto e constante indica uma
regressão no código ou uma dependência (DynamoDB, Cloudflare) com problema.

**Critérios de atenção.** Qualquer 5xx real (erro do servidor) é motivo de
olhar a causa — o objetivo é 0% de 5xx fora de testes deliberados. Para
4xx, como parte é uso normal da aplicação (campo obrigatório faltando,
tarefa não encontrada), o critério de atenção é uma **mudança de padrão**
(um 4xx que nunca ocorria e passa a ocorrer com frequência), não um número
fixo — ainda não há dado histórico suficiente para um limite quantitativo
confiável.

**Ação decorrente.** Um pico de 5xx concentrado numa rota → olhar o Painel 4
(o erro provavelmente vem do DynamoDB) e os logs `db_operation` com
`result = "failure"`. Um pico de 5xx espalhado por todas as rotas → suspeitar
do runtime do Lambda ou de throttling de conta.

**Validação e limitações.** Validado com o Cenário 3 do roteiro de testes
(chamadas repetidas a `GET /todos-falha-simulada`): o pico apareceu tanto no
widget de "5xx por rota" quanto na consulta de causas, com `route = "GET
/todos-falha-simulada"` e `status_code = 500` (ver
`relatorio_testes_observabilidade.md`). Limitação: a consulta de causas
olha só os logs do `TodoFunction` — um erro de infraestrutura antes do
Lambda ser executado (ex.: o próprio API Gateway rejeitando a requisição)
não geraria uma linha nesse log, só a métrica nativa de erro do API Gateway.

### Painel 4 — Banco de Dados

**Nome e pergunta operacional.** "Banco de Dados" — as operações do
back-end com o DynamoDB estão funcionando, e com qual duração?

**Motivo da escolha.** O banco é o componente mais "escondido" da
arquitetura (sem acesso público, só o Lambda o acessa) — sem um painel
dedicado, uma lentidão ou falha ali ficaria misturada dentro do tempo total
de resposta da API (Painel 2), sem dar para saber se o problema é no
Lambda ou no banco.

**Origem dos dados.** Duas fontes combinadas: (1) métricas nativas do
DynamoDB (`AWS/DynamoDB`) — `SuccessfulRequestLatency` (dimensionada por
`Operation`: `Scan`, `PutItem`, `GetItem`, `UpdateItem`, `DeleteItem`) e
`ConsumedReadCapacityUnits`/`ConsumedWriteCapacityUnits` (dimensionadas por
`TableName`) —, publicadas automaticamente pelo próprio DynamoDB; (2) os
logs `db_operation` gerados pelo `TodoFunction` a cada chamada ao DynamoDB
(campos `operation`, `result`, `duration_ms`, e em caso de falha
`error_type`/`error_message`), consultados via Logs Insights para ver o
detalhe do que o **back-end** observou (não só o que o serviço gerenciado
relata).

**Nota sobre uma mudança de fonte de dado.** O widget 2 media originalmente
`ThrottledRequests`/`SystemErrors`/`UserErrors` — métricas nativas de falha
do DynamoDB. Como o banco esteve saudável durante todos os testes (nenhuma
dessas falhas de fato ocorreu, e não há como simulá-las de forma controlada
sem degradar a tabela de propósito), esse widget ficava sempre vazio — o que
é o comportamento correto, mas não serve como demonstração visual de que o
painel está funcionando. Foi trocado por `ConsumedReadCapacityUnits`/
`ConsumedWriteCapacityUnits`, que são publicadas a cada operação bem-sucedida
(não só em falha) e por isso sempre têm dado real quando há tráfego — o
widget de falhas nativas continua coberto, na prática, pelo Widget 3 (logs
`db_operation` com `result = "failure"`), que é a fonte mais rica de
qualquer forma (traz tipo e mensagem do erro, não só a contagem).

**Consulta e cálculo.** Widget 1: média (`Average`) de
`SuccessfulRequestLatency` por `Operation`, em milissegundos (a própria
métrica da AWS já vem nessa unidade). Widget 2: soma (`Sum`) de
`ConsumedReadCapacityUnits` e `ConsumedWriteCapacityUnits` por período de 5
minutos — unidade de capacidade consumida no modo `PAY_PER_REQUEST`, serve
como indicador indireto de volume de leitura/escrita no banco. Widget 3
(Logs Insights):

```
fields @timestamp, operation, error_type, error_message, duration_ms
| filter event = "db_operation" and result = "failure"
| sort @timestamp desc
| limit 50
```

**Recorte temporal.** Período de agregação de 5 minutos para os widgets de
métrica; a consulta de Logs Insights cobre a janela escolhida no dashboard
(padrão 3h), listando as falhas mais recentes primeiro.

**Forma de visualização.** Série temporal para latência (comparar as 5
operações ao longo do tempo) e para as falhas nativas; tabela para as
falhas vistas pelo back-end, porque o interessante aqui é o detalhe de cada
ocorrência (tipo e mensagem do erro), não uma tendência agregada.

**Interpretação.** Esperado: latência baixa e estável para operações por
chave (`GetItem`, `UpdateItem`, `DeleteItem`, `PutItem`) e um pouco mais alta
para `Scan` (que percorre a tabela inteira); RCU/WCU consumidas acompanhando
o volume de tráfego gerado no período (picos coincidindo com rajadas de
teste, voltando a zero quando não há tráfego). A tabela 3 (logs) deve
permanecer vazia em operação normal — ver nota abaixo.

**Critérios de atenção.** Um crescimento constante de RCU/WCU sem um
aumento correspondente de tráfego (Painel Erros/Desempenho) sugere leitura
ineficiente (ex.: `Scan` repetido sem necessidade). Qualquer linha na
tabela de falhas do Widget 3 já é motivo de investigação — em operação
normal ela deve ficar vazia. Para latência, aplica-se a mesma ressalva do
Painel 2: ainda não há histórico suficiente para um limite estatístico;
qualquer valor consistentemente acima da faixa observada nos testes (Seção
6) já é um sinal.

**Ação decorrente.** Latência crescente isolada em `Scan` → é o sintoma
esperado de a tabela crescer sem paginação/índice — planejar a mudança do
`GET /todos` antes que isso afete a experiência. RCU consumida crescendo
sem tráfego correspondente → suspeitar de um `Scan` acionado repetidamente
(ex.: front-end chamando `GET /todos` em loop, mesmo problema descrito no
Painel de Erros/Desempenho). Uma linha na tabela de falhas com o mesmo
`error_type` recorrente → é um bug no código que monta a chave/expressão da
operação (ex.: `UpdateExpression`), não um problema de infraestrutura.

**Validação e limitações.** Validado gerando tráfego real que passa pelas 4
operações no DynamoDB (Cenário 1) e conferindo, no mesmo período, tanto a
métrica nativa `SuccessfulRequestLatency` por `Operation` quanto os picos
reais de `ConsumedReadCapacityUnits`/`ConsumedWriteCapacityUnits`
correspondentes às rajadas de teste, além dos logs `db_operation` com
`result = "success"` (ver relatório). O cenário de falha controlada desta
entrega (Painel 3) não passa pelo banco de propósito — ele testa a camada
de API/Lambda, não o DynamoDB — então este painel não teve uma falha real
induzida nos testes; a tabela de falhas (Widget 3) permanecer vazia é o
resultado esperado (banco saudável), e as métricas de sucesso (latência,
capacidade consumida, `result = "success"`) já comprovam que a
leitura/escrita real está funcionando de ponta a ponta. Limitação: como a
tabela é pequena, a latência observada tende a ser uniformemente baixa — o
painel ainda não foi exercitado sob um volume de dados grande o suficiente
para mostrar diferença real entre `Scan` e as operações por chave.

## 3. Logs — geração, coleta, armazenamento, retenção e consulta

| | TodoFunction (backend) | HealthCheckFunction (canário) |
|---|---|---|
| **Onde são gerados** | `backend/index.js`, em cada requisição HTTP (`console.log` de uma linha JSON) e em cada chamada ao DynamoDB | `backend/healthcheck/index.js`, uma linha JSON por checagem (front-end e API) |
| **Como são coletados** | Automaticamente: tudo que um Lambda escreve em `stdout` é enviado pela própria AWS para o CloudWatch Logs, sem agente/configuração extra | Igual — mesmo mecanismo nativo do Lambda |
| **Onde ficam armazenados** | CloudWatch Logs, log group `/aws/lambda/<nome-da-TodoFunction>` | CloudWatch Logs, log group `/aws/lambda/<nome-da-HealthCheckFunction>` |
| **Retenção** | 30 dias (`RetentionInDays`, parâmetro `LogRetentionInDays` do `template.yaml`) | 30 dias (idem) |
| **Como são consultados** | CloudWatch Logs Insights (consultas embutidas nos Painéis 3 e 4 do dashboard, e sob demanda no console) | Metric Filters (transformam em métrica automaticamente) + Logs Insights sob demanda |

**Formato dos logs (JSON estruturado), campos por tipo de evento:**

- `http_request` (uma linha por requisição HTTP atendida pelo backend):
  `timestamp` (ISO-8601, UTC), `service` (`todo-backend`), `environment`,
  `level` (`info`/`warn`/`error`, derivado do `status_code`), `event`
  (`http_request`), `request_id` (correlação — vem do header
  `x-amzn-trace-id` quando presente, senão um UUID gerado), `method`,
  `route` (padrão da rota, ex. `/todos/:id`, não o valor real do id),
  `status_code`, `duration_ms`.
- `db_operation` (uma linha por chamada ao DynamoDB): os mesmos
  `timestamp`/`service`/`environment`/`level`, mais `event` (`db_operation`),
  `request_id` (o mesmo da requisição HTTP que originou a chamada —
  permite relacionar as duas linhas), `operation` (nome estável, ex.
  `ScanTodos`, `PutTodo`), `result` (`success`/`failure`), `duration_ms`,
  e em caso de falha: `error_type` e `error_message`.
- `healthcheck` (uma linha por checagem do canário): `timestamp`,
  `service` (`todo-healthcheck`), `environment`, `level`, `event`
  (`healthcheck`), `target` (`frontend`/`api`), `url`, `result`
  (`success`/`failure`), `http_status`, `latency_ms`, `error_message`
  (quando a chamada falha antes de receber uma resposta HTTP, ex. timeout).

Nenhum log grava senha, token, string de conexão ou dado pessoal — os únicos
dados de negócio nos logs são o texto de rotas (padrão, sem valores de
id) e mensagens de erro técnicas.

**Exemplo real de registro e sua relação com um painel:** ver
`relatorio_testes_observabilidade.md`, seção "Exemplo de registro real" —
o script `observabilidade_testes.py` busca uma linha `http_request` real
gerada pelos próprios testes e mostra como ela alimenta, ao mesmo tempo, a
métrica nativa do API Gateway (Painéis 2/3/4) e a consulta de Logs Insights
do Painel 3.

**Suficiência dos dados existentes:** os logs padrão que a aplicação já
produzia na Entrega 1 (mensagens de erro genéricas do Express, sem
estrutura) não eram suficientes para os Painéis 3 e 4 — não davam para
filtrar/agrupar por rota, status ou operação. Por isso o backend foi
adaptado (Seção 0). Já os Painéis 1, 2 e 4 dependem de métricas nativas de
serviços gerenciados (API Gateway, DynamoDB) que **já existiam** — só
precisaram ser "ligadas" (`DetailedMetricsEnabled`) ou, no caso da
disponibilidade, não existiam em nenhum lugar e motivaram a função nova.

## 4. Controle de acesso aos dados de observabilidade

O dashboard, os logs e as métricas do CloudWatch **não têm nenhum endpoint
público** — são consultados exclusivamente por quem faz login no Console da
AWS com um usuário/role IAM da conta 005042706931 com permissão de leitura
no CloudWatch (`cloudwatch:GetDashboard`, `cloudwatch:GetMetricData`,
`logs:GetQueryResults`/`logs:StartQuery` e afins). Não existe usuário
anônimo nem link compartilhável sem autenticação. Isso segue a mesma regra
geral da atividade ("tudo bloqueado, exceto o necessário"): o CloudWatch fica
por trás do mesmo perímetro de identidade (IAM) que protege o resto da
conta, sem abrir uma nova superfície pública.

## 5. Diagrama

Ver `diagrama-arquitetura.html` — **Diagrama 1** (aplicação, atualizado com
as rotas explícitas no API Gateway) e **Diagrama 2** (observabilidade: para
cada uma das 4 fontes de dados, o caminho completo Componente → Coleta →
Armazenamento/consulta → Painel, com legenda distinguindo fluxo de
aplicação, fluxo de observabilidade, fluxo bloqueado e resolução
DNS/agendamento). O próprio arquivo HTML é o arquivo-fonte editável (SVG
inline, sem dependências externas).

## 6. Testes e evidências

Ver `backend/DEPLOY-ENTREGA2.md` (como publicar as mudanças) e
`observabilidade_testes.py` — script **100% automático**, sem nenhum passo
manual: roda todos os cenários abaixo (incluindo o teste de failover do
front-end com o canário rodando durante a queda), julga PASS/FAIL de cada
verificação, escreve `relatorio_testes_observabilidade.md` com os dados reais
obtidos do CloudWatch e ainda baixa sozinho, via `GetMetricWidgetImage`, as
imagens dos widgets de métrica do dashboard (pasta `evidencias_observabilidade/`)
— não é preciso abrir o console e tirar print na mão.

Cenários cobertos pelo script, e o painel que cada um valida:

1. **Uso normal pelo domínio** (GET/POST/PATCH/DELETE em `/todos`, ponta a
   ponta front-end→back-end→banco) → gera dados reais para os Painéis
   Desempenho e Banco de Dados.
2. **Canário de disponibilidade** (invocação manual, sem esperar os 5 min do
   agendamento) → gera dados reais para o Painel Disponibilidade.
3. **Falha controlada** (`GET /todos-falha-simulada`, sempre 500) → gera
   dados reais para o Painel Erros (taxa e causas).
4. **Failover do front-end com o canário rodando durante a queda** —
   remove temporariamente o `index.html` do bucket primário (mesma técnica
   do Teste 7 de `run_tests.py`, Entrega 1), confirma que o front-end
   continua respondendo via failover do CloudFront, invoca o canário nesse
   exato momento e confirma, pelo próprio log do canário, que `target=frontend`
   registrou `success` durante a queda — depois restaura o bucket
   automaticamente (mesmo se algo falhar no meio do caminho). Essa é a
   evidência indireta da redundância no Painel Disponibilidade, sem precisar
   de um painel dedicado a isso.

Depois de rodar o script (após o deploy — ver `DEPLOY-ENTREGA2.md`), anexe
a esta entrega os dois artefatos que ele gera sozinho:

- `relatorio_testes_observabilidade.md` — resumo PASS/FAIL de cada
  verificação, com timestamp, período consultado e os valores reais obtidos.
- `evidencias_observabilidade/` — imagens (PNG) dos widgets de métrica do
  dashboard, capturadas automaticamente no mesmo período do teste.

**Como interpretar um período sem dados nos painéis:** um período sem
nenhum ponto (não é "zero", é a ausência total do ponto) significa que a
fonte de dado não gerou/publicou nada naquele intervalo — não é o mesmo que
"sem erros" ou "funcionando normalmente". Para o Painel 1, um buraco
significa o canário não rodou (ver Seção 2, Painel 1). Para os Painéis 2/3/4
(métricas do API Gateway), um buraco significa que não houve nenhuma
requisição naquela rota naquele período — o que é normal fora de um teste
ou de uso ativo, e não indica problema.

## 7. Para a entrega

- **Serviços utilizados nesta etapa:** Amazon CloudWatch (Logs, Metrics,
  Logs Insights, Dashboard), Amazon EventBridge — regra agendada (dispara o
  canário), AWS Lambda (função nova `HealthCheckFunction`) — todos dentro da
  mesma conta/região da Entrega 1 (`us-east-2`).
- **Repositório:** https://github.com/Eduardo-Henrique-Francisconi/aula-uniamerica-infraestrutura-cloud
  (código de instrumentação em `backend/index.js`, `backend/healthcheck/`,
  definição das métricas/dashboard em `backend/template.yaml`).
- **Endereço da aplicação:** https://app.neshiku.com.br (front-end),
  https://api.neshiku.com.br (API).
- **Ferramenta de observabilidade:** console da AWS → CloudWatch → Dashboards
  → `todo-app-observabilidade` (região `us-east-2`) — acesso autenticado,
  sem credenciais incluídas nesta documentação nem no repositório.
