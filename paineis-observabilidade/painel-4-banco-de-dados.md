# Painel 4 — Banco de Dados

**Aplicação:** Todo App · **Dashboard:** `todo-app-observabilidade` (CloudWatch, região `us-east-2`)
**Banco monitorado:** DynamoDB `todos-table` + logs do Lambda `TodoFunction`

---

## 1. Nome e pergunta operacional

**Banco de Dados** — as operações do back-end com o DynamoDB estão funcionando, e com qual duração?

## 2. Motivo da escolha

O banco é o componente mais "escondido" da arquitetura (sem acesso público — só a role IAM do Lambda pode lê-lo/escrevê-lo). Sem um painel dedicado, uma lentidão ou falha ali ficaria misturada dentro do tempo total de resposta da API (Painel 2), sem dar para saber se o problema é no Lambda ou no banco em si.

## 3. Origem dos dados

Duas fontes combinadas:

1. Métricas nativas do DynamoDB (namespace `AWS/DynamoDB`) — `SuccessfulRequestLatency` (dimensionada por `Operation`: `Scan`, `PutItem`, `GetItem`, `UpdateItem`, `DeleteItem`) e `ConsumedReadCapacityUnits`/`ConsumedWriteCapacityUnits` (dimensionadas por `TableName`) —, publicadas automaticamente pelo próprio DynamoDB, sem nenhum código no backend.
2. Os logs `db_operation` gerados pelo `TodoFunction` a cada chamada ao DynamoDB (campos `operation`, `result`, `duration_ms`, e em caso de falha `error_type`/`error_message`), consultados via Logs Insights para ver o detalhe do que o **back-end** observou — não só o que o serviço gerenciado relata.

**Nota sobre uma mudança de fonte de dado.** O segundo widget media originalmente `ThrottledRequests`/`SystemErrors`/`UserErrors` — métricas nativas de falha do DynamoDB. Como o banco esteve saudável durante todos os testes (nenhuma dessas falhas de fato ocorreu, e não há como simulá-las de forma controlada sem degradar a tabela de propósito), esse widget ficava sempre vazio — o que é o comportamento correto, mas não serve como demonstração visual de que o painel está funcionando. Foi trocado por `ConsumedReadCapacityUnits`/`ConsumedWriteCapacityUnits`, que são publicadas a cada operação **bem-sucedida** (não só em falha) e por isso sempre têm dado real quando há tráfego. O widget de falhas nativas continua coberto, na prática, pelo terceiro widget (logs `db_operation` com `result = "failure"`), que é a fonte mais rica de qualquer forma — traz tipo e mensagem do erro, não só uma contagem.

## 4. Consulta e cálculo

**Widget 1:** média (`Average`) de `SuccessfulRequestLatency` por `Operation`, em milissegundos (a própria métrica da AWS já vem nessa unidade).

**Widget 2:** soma (`Sum`) de `ConsumedReadCapacityUnits` e `ConsumedWriteCapacityUnits` por período de 5 minutos — unidade de capacidade consumida no modo `PAY_PER_REQUEST`, usada aqui como indicador indireto de volume de leitura/escrita no banco.

**Widget 3 (Logs Insights):**

```
fields @timestamp, operation, error_type, error_message, duration_ms
| filter event = "db_operation" and result = "failure"
| sort @timestamp desc
| limit 50
```

## 5. Recorte temporal

Período de agregação de 5 minutos para os widgets de métrica; a consulta de Logs Insights cobre a janela escolhida no dashboard (padrão 3h), listando as falhas mais recentes primeiro.

## 6. Forma de visualização

Série temporal para latência (compara as 5 operações ao longo do tempo) e para a capacidade consumida; tabela para as falhas vistas pelo back-end, porque o interessante aqui é o detalhe de cada ocorrência (tipo e mensagem do erro), não uma tendência agregada.

## 7. Interpretação

Esperado: latência baixa e estável para operações por chave (`GetItem`, `UpdateItem`, `DeleteItem`, `PutItem`) e um pouco mais alta para `Scan` (que percorre a tabela inteira); RCU/WCU consumidas acompanhando o volume de tráfego gerado no período (picos coincidindo com rajadas de uso, voltando a zero quando não há tráfego). A tabela de falhas (Widget 3) deve permanecer vazia em operação normal — ver a seção de períodos sem dados, abaixo, para a diferença entre "vazio esperado" e "ausência de coleta".

## 8. Critérios de atenção

Um crescimento constante de RCU/WCU sem um aumento correspondente de tráfego (visível nos Painéis 2/3) sugere leitura ineficiente — por exemplo, um `Scan` sendo acionado repetidamente sem necessidade. Qualquer linha na tabela de falhas do Widget 3 já é motivo de investigação — em operação normal ela deve ficar vazia. Para latência, aplica-se a mesma ressalva do Painel 2: ainda não há histórico suficiente para um limite estatístico confiável; qualquer valor consistentemente acima da faixa observada nos testes (ver item 10) já é um sinal de atenção.

## 9. Ação decorrente

Latência crescente isolada em `Scan` → é o sintoma esperado de a tabela crescer sem paginação/índice — planejar a mudança do `GET /todos` antes que isso afete a experiência do usuário. RCU consumida crescendo sem tráfego correspondente → suspeitar de um `Scan` acionado repetidamente (por exemplo, o front-end chamando `GET /todos` em loop — mesmo problema que seria visto no Painel 2/3). Uma linha na tabela de falhas com o mesmo `error_type` recorrente → é um bug no código que monta a chave/expressão da operação (ex.: `UpdateExpression`), não um problema de infraestrutura.

## 10. Validação e limitações

**Teste:** tráfego real passando pelas 4 operações no DynamoDB (Scan, PutItem, UpdateItem, DeleteItem), via o script automático `observabilidade_testes.py`.
**Resultado esperado:** a métrica `SuccessfulRequestLatency` por `Operation` e os picos de `ConsumedReadCapacityUnits`/`ConsumedWriteCapacityUnits` aparecerem coincidindo com as rajadas de teste, junto com logs `db_operation` com `result = "success"`.
**Resultado observado:** confirmado — ver `relatorio_testes_observabilidade.md`.

O cenário de falha controlada desta entrega (usado no Painel 3) não passa pelo banco de propósito — ele testa a camada de API/Lambda, não o DynamoDB — então este painel não teve uma falha real induzida nos testes; a tabela de falhas (Widget 3) permanecer vazia é o resultado esperado (banco saudável).

**O que os dados não permitem concluir:** como a tabela é pequena, a latência observada tende a ser uniformemente baixa — o painel ainda não foi exercitado sob um volume de dados grande o suficiente para mostrar diferença real entre `Scan` e as operações por chave. Também não há, nos testes realizados, nenhuma falha real de banco (throttling, erro de sistema) — a ausência dessas falhas nos dados não comprova que o painel as capturaria corretamente se elas ocorressem, apenas que a consulta está correta e roda sem erro.

## Alcance (o que este painel observa e o que não observa)

Observa: apenas as chamadas que o Lambda `TodoFunction` faz ao DynamoDB através do AWS SDK — latência, capacidade consumida e falhas vistas do lado do backend. Não observa: nenhuma operação feita fora do Lambda (não há nenhuma via de acesso fora dele — a tabela não tem endpoint público, então não existe "outro caminho" a monitorar), nem métricas administrativas internas do DynamoDB (particionamento, replicação) que não afetem diretamente a latência ou a capacidade consumida percebida pelo backend.

## Como interpretar um período sem dados neste painel

É preciso diferenciar dois casos, que têm leituras opostas:

- **Widgets 1 e 2 (latência e capacidade) sem nenhum ponto:** significa que não houve nenhuma operação no DynamoDB naquele período — normal fora de um teste ou de uso ativo, não indica problema.
- **Widget 3 (tabela de falhas) vazio:** aqui "vazio" é o **resultado bom esperado** — significa que o back-end não registrou nenhuma falha de acesso ao banco no período consultado. Não confundir com "sem coleta": a consulta sempre roda e sempre retornaria linhas se houvesse falhas reais; a ausência de linhas é, ela mesma, a evidência de que o banco está saudável.
