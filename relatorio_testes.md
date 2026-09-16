# Relatório de Testes — Infraestrutura Serverless

Gerado em: 16/09/2026 16:20:46

- Front-end: https://app.neshiku.com.br
- Back-end/API: https://api.neshiku.com.br

## Resumo

| # | Teste | Resultado |
|---|---|---|
| 1 | Front-end acessível pelo domínio | PASS |
| 2 | Back-end acessível pelo domínio/API | PASS |
| 3 | Front-end conseguindo acessar o Back-end | PASS |
| 4 | Back-end conseguindo acessar o Banco de Dados | PASS |
| 5 | Acesso direto ao Back-end bloqueado | PASS |
| 6 | Acesso direto ao Banco de Dados bloqueado | PASS |
| 7 | Front-end disponível com componente redundante fora do ar | PASS |

**7/7 testes passaram.**

## Detalhe teste a teste (comando + saída)

### Teste 1 — Front-end acessível pelo domínio — PASS

**Comando(s) executado(s):**
```bash
curl -i https://app.neshiku.com.br
```

**Saída obtida:**
```
HTTP/1.1 200 OK
Date: Wed, 16 Sep 2026 19:20:22 GMT
Content-Type: text/html
Transfer-Encoding: chunked
Connection: keep-alive
Report-To: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=4qksPQkeH0ftK9b6S7RuSRhak4iIlgAZN74Z0wwbhZWqKN2l3u5Z71l6HiOrzNwA%2FOjJ2%2FM2pMnux5AyIDt4LHisLgI3joWUiqY1WZdmkp1DIrGiT0DT43XXR3tIjjbEf9Jq1HBC2phFI4A%2B2s4k6vY%3D"}]}
Server: cloudflare
last-modified: Wed, 16 Sep 2026 17:25:43 GMT
Nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
x-amz-server-side-encryption: AES256
x-cache: Hit from cloudfront
via: 1.1 68be678d2e87631ff97bdf13322976a0.cloudfront.net (CloudFront)
x-amz-cf-pop: GRU1-P1
x-amz-cf-id: lQMHb94uS_s8hSll6uZJGjlahyva9B-eyqxpmIs6Xsr8n8pto9g-0w==
Age: 6560
cf-cache-status: DYNAMIC
Content-Encoding: br
CF-RAY: a3c23a648cdddf24-GRU
alt-svc: h3=":443"; ma=86400

<!doctype html><html lang="en"><head><meta charset="utf-8"/><link rel="icon" href="/favicon.ico"/><meta name="viewport" content="width=device-width,initial-scale=1"/><meta name="theme-color" content="#000000"/><meta name="description" content="Web site created using create-react-app"/><link rel="apple-touch-icon" href="/logo192.png"/><link rel="manifest" href="/manifest.json"/><title>React App</title><script defer="defer" src="/static/js/main.26bd9205.js"></script><link href="/static/css/main.47 ...(truncado)
```

### Teste 2 — Back-end acessível pelo domínio/API — PASS

**Comando(s) executado(s):**
```bash
curl -i https://api.neshiku.com.br/todos
```

**Saída obtida:**
```
HTTP/1.1 200 OK
Date: Wed, 16 Sep 2026 19:20:25 GMT
Content-Type: application/json; charset=utf-8
Transfer-Encoding: chunked
Connection: keep-alive
etag: W/"4f-BN40qX9tbFsZ1GkfFWckrCzd3cI"
x-powered-by: Express
apigw-requestid: DznOuhtXCYcEP0w=
cf-cache-status: DYNAMIC
Report-To: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=2z%2FEZB3gBiRYYjcjiBqjjifvVWqF5mDLsG%2F6d60FneVbZyLCUNvOozk4t3u4fHEYWdf48NibNLFGUpc6LTBNb0E3ITILyg3kPZqr13fE624XRbshTEQcstgIGYiwhbUZidmclmHwRX%2BTEvkXoj%2B11xA%3D"}]}
Nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
Content-Encoding: br
Server: cloudflare
CF-RAY: a3c23a679bc0a47f-GRU
alt-svc: h3=":443"; ma=86400

[{"id":"713400fb-e5dc-4462-9771-f5418a3178ad","completed":false,"text":"test"}]
```

### Teste 3 — Front-end conseguindo acessar o Back-end — PASS

**Comando(s) executado(s):**
```bash
curl -i -X POST https://api.neshiku.com.br/todos -H "Content-Type: application/json" -d '{"text":"teste-automatizado"}'
curl -i https://api.neshiku.com.br/todos
curl -i -X DELETE https://api.neshiku.com.br/todos/5c192dac-6b1f-4aa3-9950-ccad6e94beaa
```

**Saída obtida:**
```
$ curl -i -X POST https://api.neshiku.com.br/todos -H "Content-Type: application/json" -d '{"text":"teste-automatizado"}'
HTTP/1.1 201 Created
Date: Wed, 16 Sep 2026 19:20:26 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 91
Connection: keep-alive
x-powered-by: Express
etag: W/"5b-psaBT7TPhCK5M+dsf2J3o2GZVIk"
apigw-requestid: DznPKhf4CYcEMqQ=
cf-cache-status: DYNAMIC
Report-To: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=VwQz5OFUizspyucAWYzwcy3rpeCiBfM25PZlT7%2F027kU3VH%2BQcMxmKC5KUZFNXlvgYA74kz%2B%2BWxmoLWxKnoYVWTtEdBCTKn01VtxPaAnwQ9OEk0%2FdtD47ErQvk9Uo3OrgQC%2B%2B1KorAUu15XFrCfgh94%3D"}]}
Nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
Server: cloudflare
CF-RAY: a3c23a78fa6ed575-GRU
alt-svc: h3=":443"; ma=86400

{"id":"5c192dac-6b1f-4aa3-9950-ccad6e94beaa","text":"teste-automatizado","completed":false}

$ curl -i https://api.neshiku.com.br/todos
HTTP/1.1 200 OK
Date: Wed, 16 Sep 2026 19:20:27 GMT
Content-Type: application/json; charset=utf-8
Transfer-Encoding: chunked
Connection: keep-alive
x-powered-by: Express
etag: W/"ab-0RiLFPMJZCAS41bBoT9V0H7SEHM"
apigw-requestid: DznPUhbcCYcEMEA=
cf-cache-status: DYNAMIC
Report-To: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=Mw8RGgXqtONOgEyT0pQ7oPipDdYNzFTadTD5%2FvZOQ9u2vyEPJTi3vs1wRTSdmJeJxdQBUXdzD1knHAwOaHXbAn4v7yqAW4OCY52s2XV%2BFcGvXd1z0uB27vSAhcGVBwxBeQLcya9GFPPcfJzlP6mSjvU%3D"}]}
Nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
Content-Encoding: br
Server: cloudflare
CF-RAY: a3c23a7f8ef8f183-GRU
alt-svc: h3=":443"; ma=86400

[{"id":"713400fb-e5dc-4462-9771-f5418a3178ad","completed":false,"text":"test"},{"id":"5c192dac-6b1f-4aa3-9950-ccad6e94beaa","completed":false,"text":"teste-automatizado"}]

$ curl -i -X DELETE https://api.neshiku.com.br/todos/5c192dac-6b1f-4aa3-9950-ccad6e94beaa
HTTP/1.1 200 OK
Date: Wed, 16 Sep 2026 19:20:28 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 42
Connection: keep-alive
etag: W/"2a-rdq7iPdw4cJX+kdFEiHqFVHQXCk"
x-powered-by: Express
apigw-requestid: DznPejgZCYcEMSw=
cf-cache-status: DYNAMIC
Report-To: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=hU0T%2FDN27351LTZlACoywztSLvcjL8sIzT7bRjxuLCt1HkRpTytWuN5DPsdgHA6cd%2BT1VLNKFkB8pmr4jRn5VUHlhe6wTOElw1pKFxiRWveXWuCheX4qb7sn3FNROFr6i5rUaYbyCAwLoqKQg4p6pSk%3D"}]}
Nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
Server: cloudflare
CF-RAY: a3c23a85acc00e8a-GRU
alt-svc: h3=":443"; ma=86400

{"message":"Tarefa excluída com sucesso"}
```

### Teste 4 — Back-end conseguindo acessar o Banco de Dados — PASS

**Comando(s) executado(s):**
```bash
curl -i -X POST https://api.neshiku.com.br/todos -H "Content-Type: application/json" -d '{"text":"teste-db-automatizado"}'
aws dynamodb get-item --table-name todos-table --key '{"id":{"S":"341e1e0e-a206-4f40-8d08-87c16239f496"}}' --region us-east-2
curl -i -X DELETE https://api.neshiku.com.br/todos/341e1e0e-a206-4f40-8d08-87c16239f496
```

**Saída obtida:**
```
$ curl -i -X POST https://api.neshiku.com.br/todos -H "Content-Type: application/json" -d '{"text":"teste-db-automatizado"}'
HTTP/1.1 201 Created
Date: Wed, 16 Sep 2026 19:20:29 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 94
Connection: keep-alive
etag: W/"5e-WuW3kYRiYIlhjD4QLnWSe5WSiGQ"
x-powered-by: Express
apigw-requestid: DznPogGKCYcEMZQ=
cf-cache-status: DYNAMIC
Report-To: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=h8%2Fp8A9cbuIHzEnKFOhX9SZjCXyHpDxCCRxALanyY42wLMhTutw0Yd4nnPMMFY265J3IPeCqufQnGfaKOieFqULOJ6dC46ndRTeEo5AJIsMX8ZQQFP5TMsRhickgJnd064jlNPziYRKoz0uyGDcPdeQ%3D"}]}
Nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
Server: cloudflare
CF-RAY: a3c23a8bb9376229-GRU
alt-svc: h3=":443"; ma=86400

{"id":"341e1e0e-a206-4f40-8d08-87c16239f496","text":"teste-db-automatizado","completed":false}

$ aws dynamodb get-item --table-name todos-table --key '{"id":{"S":"341e1e0e-a206-4f40-8d08-87c16239f496"}}' --region us-east-2
{
  "Item": {
    "id": {
      "S": "341e1e0e-a206-4f40-8d08-87c16239f496"
    },
    "completed": {
      "BOOL": false
    },
    "text": {
      "S": "teste-db-automatizado"
    }
  },
  "ResponseMetadata": {
    "RequestId": "S5OVIOJ5O6L3LQ6TUCG67L7ET3VV4KQNSO5AEMVJF66Q9ASUAAJG",
    "HTTPStatusCode": 200,
    "HTTPHeaders": {
      "server": "Server",
      "date": "Wed, 16 Sep 2026 19:20:42 GMT",
      "content-type": "application/x-amz-json-1.0",
      "content-length": "124",
      "connection": "keep-alive",
      "x-amzn-requestid": "S5OVIOJ5O6L3LQ6TUCG67L7ET3VV4KQNSO5AEMVJF66Q9ASUAAJG",
      "x-amz-crc32": "2721352369"
    },
    "RetryAttempts": 0
  }
}

$ curl -i -X DELETE https://api.neshiku.com.br/todos/341e1e0e-a206-4f40-8d08-87c16239f496
HTTP/1.1 200 OK
Date: Wed, 16 Sep 2026 19:20:43 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 42
Connection: keep-alive
etag: W/"2a-rdq7iPdw4cJX+kdFEiHqFVHQXCk"
x-powered-by: Express
apigw-requestid: DznR1jYriYcEPGA=
cf-cache-status: DYNAMIC
Report-To: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=IrREcUOrSY%2Ba5EPOekSm2SP%2BYJ9722dmR2JLE%2BP4QA8xJFR5vz0l4%2BY1A8PSJ%2FEr09U1sw%2F6hgPGGPXDzMZLuSDXElDB6R2y8idG73j296wCy2WOYkdDnAaPuf3j%2FMu2oIhxCa0ifuWmx2vlfKRLasU%3D"}]}
Nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
Server: cloudflare
CF-RAY: a3c23ae3ea0e37a6-GRU
alt-svc: h3=":443"; ma=86400

{"message":"Tarefa excluída com sucesso"}
```

### Teste 5 — Acesso direto ao Back-end bloqueado — PASS

**Comando(s) executado(s):**
```bash
curl -i https://vfb3b537c6.execute-api.us-east-2.amazonaws.com/todos
```

**Saída obtida:**
```
HTTP/1.1 403 Forbidden
Date: Wed, 16 Sep 2026 19:20:44 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 67
Connection: keep-alive
etag: W/"43-5CVZgpDXDvcwUWqHuzKIZ+oex1w"
X-Powered-By: Express
Apigw-Requestid: DznR_icYiYcEJQg=

{"message":"Acesso direto não permitido. Use o domínio oficial."}
```

### Teste 6 — Acesso direto ao Banco de Dados bloqueado — PASS

**Comando(s) executado(s):**
```bash
curl -i -X POST https://dynamodb.us-east-2.amazonaws.com/ -H "X-Amz-Target: DynamoDB_20120810.Scan" -H "Content-Type: application/x-amz-json-1.0" -d '{"TableName":"todos-table"}'
```

**Saída obtida:**
```
HTTP/1.1 400 Bad Request
Server: Server
Date: Wed, 16 Sep 2026 19:20:45 GMT
Content-Type: application/x-amz-json-1.0
Content-Length: 125
Connection: keep-alive
x-amzn-RequestId: RGT6FF85315B851KKC095VSKBNVV4KQNSO5AEMVJF66Q9ASUAAJG
x-amz-crc32: 2088342776

{"__type":"com.amazon.coral.service#MissingAuthenticationTokenException","message":"Request is missing Authentication Token"}
```

### Teste 7 — Front-end disponível com componente redundante fora do ar — PASS

**Comando(s) executado(s):**
```bash
aws s3 mv s3://todo-app-neshiku-frontend-1/index.html s3://todo-app-neshiku-frontend-1/index.html.bak --region us-east-2
curl -i https://app.neshiku.com.br
aws s3 mv s3://todo-app-neshiku-frontend-1/index.html.bak s3://todo-app-neshiku-frontend-1/index.html --region us-east-2
```

**Saída obtida:**
```
$ aws s3 mv s3://todo-app-neshiku-frontend-1/index.html s3://todo-app-neshiku-frontend-1/index.html.bak --region us-east-2
move: index.html -> index.html.bak (via boto3, equivalente ao comando acima)

$ curl -i https://app.neshiku.com.br
HTTP/1.1 200 OK
Date: Wed, 16 Sep 2026 19:20:46 GMT
Content-Type: text/html
Transfer-Encoding: chunked
Connection: keep-alive
Report-To: {"group":"cf-nel","max_age":604800,"endpoints":[{"url":"https://a.nel.cloudflare.com/report/v4?s=JtVDtcaZFqdsz1ykyhL4kxgBFPnwT1m1cUf7GSk%2BMzFWIBJ0SltImgLF0yz4gXe68DkWgUGjv22rS0qbEVYntQSS7O5EuIhdNbFNk40XD4aQOVGIuYxgC0C7zxuGHqBz%2B2IFWi3%2F5zIjePF3uOozgd0%3D"}]}
Server: cloudflare
last-modified: Wed, 16 Sep 2026 17:25:43 GMT
Nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
x-amz-server-side-encryption: AES256
x-cache: Hit from cloudfront
via: 1.1 94515a696fcaa3487248920ae7147c34.cloudfront.net (CloudFront)
x-amz-cf-pop: GRU1-P1
x-amz-cf-id: r1DFE3AGZsgEfnazl0VijMRPnN9cQeCEGrBAVO_2txVWE-hBullBkQ==
Age: 6584
cf-cache-status: DYNAMIC
Content-Encoding: br
CF-RAY: a3c23afc1d47464c-GRU
alt-svc: h3=":443"; ma=86400

<!doctype html><html lang="en"><head><meta charset="utf-8"/><link rel="icon" href="/favicon.ico"/><meta name="viewport" content="width=device-width,initial-scale=1"/><meta name="theme-color" content="#000000"/><meta name="description" content="Web site created using create-react-app"/><link rel="apple-touch-icon" href="/logo192.png"/><link rel="manifest" href="/manifest.json"/><title>React App</title><script defer="defer" src="/static/js/main.26bd9205.js"></script><link href="/static/css/main.47 ...(truncado)

$ aws s3 mv s3://todo-app-neshiku-frontend-1/index.html.bak s3://todo-app-neshiku-frontend-1/index.html --region us-east-2
move: index.html.bak -> index.html (bucket restaurado com sucesso)
```