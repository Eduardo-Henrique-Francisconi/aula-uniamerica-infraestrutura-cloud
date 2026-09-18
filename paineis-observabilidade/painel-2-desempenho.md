# Painel 2 — Desempenho

**Aplicação:** Todo App · **Dashboard:** `todo-app-observabilidade` (CloudWatch, região `us-east-2`)
**API monitorada:** `api.neshiku.com.br` (API Gateway HTTP API `TodoHttpApi`)

---

## 1. Nome e pergunta operacional

**Desempenho** — quais operações da API estão demorando mais, e em quais períodos?

## 2. Motivo da escolha

A aplicação tem uma rota (`GET /todos`) que faz um `Scan` completo na tabela DynamoDB — uma operação cujo custo cresce com o volume de dados, ao contrário das operações por chave (`GetItem`/`UpdateItem`/`DeleteItem`). Sem medir latência por rota, um problema de desempenho só seria percebido quando o usuário já estivesse reclamando de lentidão, sem nenhuma pista de qual operação é a causa.

## 3. Origem dos dados

Métrica nativa `Latency` do Amazon API Gateway (namespace `AWS/ApiGateway`), publicada automaticamente pelo próprio serviço a cada requisição — nenhum código foi escrito no back-end para gerar esse dado. Ela só ficou granular **por rota** porque `backend/template.yaml` liga `DefaultRouteSettings.DetailedMetricsEnabled: true` no HTTP API e define rotas explícitas (`GET /todos`, `POST /todos`, `PATCH /todos/{id}`, `DELETE /todos/{id}`, `GET /todos-falha-simulada`) em vez de um catch-all `/{proxy+}` — sem rotas nomeadas, o API Gateway não consegue separar a métrica por operação.

## 4. Consulta e cálculo

Estatísticas `p50` (mediana) e `p95` (o pior caso "comum", ignorando os 5% mais extremos) da métrica `Latency`, uma série por combinação rota+percentil, unidade: milissegundos. Usamos percentil, e não média, porque a média esconde picos ocasionais — uma soma dividida pela contagem "dilui" um pico raro, enquanto o p95 o deixa visível.

## 5. Recorte temporal

Período de agregação de 5 minutos, janela padrão de 3 horas no dashboard, atualização conforme o tráfego chega (near real-time, com o atraso normal de publicação de métricas do CloudWatch, tipicamente 1–3 minutos).

## 6. Forma de visualização

Série temporal com uma linha por combinação rota+percentil — permite comparar visualmente, de forma direta, se `GET /todos` (que faz `Scan`) é consistentemente mais lento que as demais rotas, e se isso muda ao longo do tempo.

## 7. Interpretação

Esperado: `PATCH`/`DELETE`/operações por chave tendem a ser mais rápidas (acesso pontual no DynamoDB, por chave primária); `GET /todos` (Scan) e `POST /todos` (Put) tendem a ser um pouco mais lentas. Um afastamento grande entre p50 e p95 de uma mesma rota indica variabilidade (nem toda chamada tem o mesmo desempenho) — nesse caso vale olhar o Painel 4 (Banco de Dados) em paralelo, já que a maior parte do tempo de resposta tende a vir da chamada ao DynamoDB, não do próprio Lambda.

## 8. Critérios de atenção

Ainda não há um SLA formal definido para esta atividade acadêmica; como referência inicial, uma p95 acima de ~1000ms (1 segundo) para qualquer rota já é alto para operações tão simples num banco de item único/Scan pequeno, e motivaria investigação. **Limitação explícita:** esse número não vem de um estudo de carga real — é só o piso de "isso claramente não devia demorar tanto" para o tamanho atual da tabela; precisa ser revisto à medida que o volume de dados crescer e houver histórico suficiente para um limite estatístico de verdade.

## 9. Ação decorrente

Latência alta e crescente isolada em `GET /todos` é o primeiro sinal de que o `Scan` vai precisar ser substituído por uma consulta paginada ou por um índice, antes que a tabela cresça o suficiente para afetar a experiência do usuário. Latência alta e constante em **todas** as rotas (não só a que faz Scan) aponta para o Lambda em si (cold start, memória insuficiente) em vez do DynamoDB.

## 10. Validação e limitações

**Teste:** geração de ~15 requisições de cada tipo (GET/POST/PATCH/DELETE) pelo domínio, via o script automático `observabilidade_testes.py`.
**Resultado esperado:** a métrica `Latency` aparecer com pontos reais, por rota, no período do teste.
**Resultado observado:** confirmado — ver `relatorio_testes_observabilidade.md`; as 5 rotas explícitas aparecem com dado real no dashboard após o deploy.

**O que os dados não permitem concluir:** a métrica de latência do API Gateway mede o tempo entre a requisição chegar ao API Gateway e a resposta ser enviada — isso inclui o tempo de execução do Lambda **e** do DynamoDB juntos, mas não isola um do outro. Para separar "o Lambda está lento" de "o DynamoDB está lento", é preciso olhar o Painel 4 (Banco de Dados), que usa a métrica própria do DynamoDB.

## Alcance (o que este painel observa e o que não observa)

Observa: o tempo de resposta do API Gateway para as 5 rotas explícitas do backend, medido no lado do servidor (dentro da AWS). Não observa: o tempo de carregamento do front-end no navegador do usuário (renderização do React, tempo de download dos assets estáticos do CloudFront), nem a latência de rede entre o usuário e a Cloudflare — este painel só cobre a perna "back-end" do caminho completo `usuário → Cloudflare → CloudFront/API Gateway`.

## Como interpretar um período sem dados neste painel

Um período sem nenhum ponto para uma rota específica significa que **não houve nenhuma requisição àquela rota naquele intervalo** — não significa "latência zero" nem "erro". Isso é normal fora de um teste deliberado ou de uso ativo da aplicação (por exemplo, ninguém chamou `DELETE /todos/{id}` naquela janela de 5 minutos) e não deve ser interpretado como um problema.
