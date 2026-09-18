"""
observabilidade_testes.py — Gera tráfego real, provoca uma falha controlada,
consulta o CloudWatch (métricas e Logs Insights) e escreve um relatório em
Markdown (relatorio_testes_observabilidade.md) relacionando cada cenário de
teste da Entrega 2 com o painel correspondente do dashboard.

Pré-requisitos:
    pip install requests boto3
    (o boto3 usa as mesmas credenciais já configuradas via `aws configure`)

Como usar (depois de fazer o deploy da Entrega 2 — ver DEPLOY-ENTREGA2.md):
    python observabilidade_testes.py

O script:
    1. Gera uso normal da aplicação pelo domínio (GET/POST/PATCH/DELETE em
       /todos) — percorre front-end→back-end→banco.
    2. Invoca o canário de disponibilidade (HealthCheckFunction) duas vezes
       manualmente, para não depender de esperar o agendamento de 5 min.
    3. Provoca uma falha controlada (GET /todos-falha-simulada) repetidas
       vezes.
    4. Espera a propagação das métricas no CloudWatch (~90s).
    5. Consulta, via CloudWatch, os dados que alimentam os 4 painéis:
       métricas nativas (API Gateway, DynamoDB), a métrica customizada de
       disponibilidade, e duas consultas de CloudWatch Logs Insights.
    6. Escreve relatorio_testes_observabilidade.md com timestamp (UTC e
       America/Sao_Paulo), período consultado e os valores/linhas reais
       obtidos — sem inventar nenhum dado.

Ajuste o dicionário CONFIG abaixo se algum nome de recurso mudar.
"""

import json
import time
from datetime import datetime, timedelta, timezone

import requests

try:
    import boto3
except ImportError:
    boto3 = None

CONFIG = {
    "api_url": "https://api.neshiku.com.br",
    "frontend_url": "https://app.neshiku.com.br",
    "aws_region": "us-east-2",
    "dynamo_table": "todos-table",
    "healthcheck_function_name_contains": "HealthCheckFunction",
    "todo_function_name_contains": "TodoFunction",
    "api_id": None,  # se None, o script descobre pelo nome da stack (sam-app)
    "normal_traffic_requests": 15,
    "simulated_failure_requests": 8,
    "wait_for_metrics_seconds": 90,
}

SP_TZ = timezone(timedelta(hours=-3))
report_lines = []


def log_section(title):
    print(f"\n=== {title} ===")
    report_lines.append(f"\n## {title}\n")


def log_line(text=""):
    print(text)
    report_lines.append(text)


def now_str():
    utc = datetime.now(timezone.utc)
    sp = utc.astimezone(SP_TZ)
    return (
        f"{utc.strftime('%Y-%m-%d %H:%M:%S')} UTC "
        f"({sp.strftime('%Y-%m-%d %H:%M:%S')} America/Sao_Paulo)"
    )


def discover_resources(session):
    """Descobre os nomes reais das funções Lambda pelo padrão do nome
    (o SAM gera nomes com sufixo aleatório, ex.: sam-app-TodoFunction-XXXX)."""
    lam = session.client("lambda", region_name=CONFIG["aws_region"])
    functions = lam.list_functions().get("Functions", [])
    todo_fn = next(
        (f["FunctionName"] for f in functions if CONFIG["todo_function_name_contains"] in f["FunctionName"]),
        None,
    )
    hc_fn = next(
        (f["FunctionName"] for f in functions if CONFIG["healthcheck_function_name_contains"] in f["FunctionName"]),
        None,
    )
    return todo_fn, hc_fn


def discover_api_id(session):
    apigw = session.client("apigatewayv2", region_name=CONFIG["aws_region"])
    apis = apigw.get_apis().get("Items", [])
    for api in apis:
        if "sam-app" in api.get("Name", "") or "Todo" in api.get("Name", ""):
            return api["ApiId"]
    return apis[0]["ApiId"] if apis else None


def gerar_trafego_normal():
    log_section("Cenário 1 — Uso normal pelo domínio (front-end → back-end → banco)")
    log_line(f"Início: {now_str()}")
    created_ids = []
    for i in range(CONFIG["normal_traffic_requests"]):
        r_get = requests.get(f"{CONFIG['api_url']}/todos", timeout=10)
        r_post = requests.post(
            f"{CONFIG['api_url']}/todos",
            json={"text": f"tarefa de teste observabilidade #{i}"},
            timeout=10,
        )
        if r_post.status_code == 201:
            created_ids.append(r_post.json()["id"])
        time.sleep(0.3)
    # marca e exclui algumas para exercitar PATCH e DELETE também
    for todo_id in created_ids[:5]:
        requests.patch(f"{CONFIG['api_url']}/todos/{todo_id}", timeout=10)
    for todo_id in created_ids:
        requests.delete(f"{CONFIG['api_url']}/todos/{todo_id}", timeout=10)
    log_line(
        f"{CONFIG['normal_traffic_requests']} GET + {CONFIG['normal_traffic_requests']} POST + "
        f"{min(5, len(created_ids))} PATCH + {len(created_ids)} DELETE em {CONFIG['api_url']}/todos"
    )
    log_line(f"Fim: {now_str()}")
    log_line(
        "Isso exercita GetTodos (Scan), PutTodo, UpdateTodo e DeleteTodo no DynamoDB "
        "pelo caminho real (domínio → Cloudflare → API Gateway → Lambda → DynamoDB)."
    )


def invocar_canario(session, hc_fn):
    log_section("Cenário 2 — Canário de disponibilidade (invocação manual)")
    if not hc_fn or not session:
        log_line("AWS/boto3 não disponível — pulei a invocação manual; o agendamento (5 min) ainda gera dados.")
        return
    lam = session.client("lambda", region_name=CONFIG["aws_region"])
    for i in range(2):
        resp = lam.invoke(FunctionName=hc_fn, InvocationType="RequestResponse")
        payload = json.loads(resp["Payload"].read())
        log_line(f"Invocação {i + 1} de {hc_fn} em {now_str()} → resultado: {payload}")
        time.sleep(5)


def provocar_falha_controlada():
    log_section("Cenário 3 — Falha controlada (rota /todos-falha-simulada)")
    log_line(f"Início: {now_str()}")
    for _ in range(CONFIG["simulated_failure_requests"]):
        r = requests.get(f"{CONFIG['api_url']}/todos-falha-simulada", timeout=10)
        log_line(f"  status recebido: {r.status_code}")
    log_line(f"Fim: {now_str()}")
    log_line(
        "Cada chamada gera 1 log 'http_request' com status_code=500 e route="
        "\"GET /todos-falha-simulada\" no TodoFunction, e é contada como 5xxError "
        "nativo do API Gateway para essa rota."
    )


def consultar_metricas(session, api_id):
    log_section("Consulta ao CloudWatch Metrics (dados reais após os cenários acima)")
    if not session:
        log_line("boto3 não disponível — não foi possível consultar métricas automaticamente.")
        return
    cw = session.client("cloudwatch", region_name=CONFIG["aws_region"])
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=20)
    log_line(f"Período consultado: {start.strftime('%Y-%m-%d %H:%M:%S')} a {end.strftime('%Y-%m-%d %H:%M:%S')} UTC (últimos 20 min)")

    def get_sum(namespace, metric, dims, stat="Sum"):
        resp = cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric,
            Dimensions=dims,
            StartTime=start,
            EndTime=end,
            Period=300,
            Statistics=[stat],
        )
        points = sorted(resp.get("Datapoints", []), key=lambda d: d["Timestamp"])
        total = sum(p[stat] for p in points)
        return total, points

    # Nota: o widget "5xx por rota" do Painel 3 usa Logs Insights (ver
    # consultar_logs_insights), não a métrica nativa — a métrica 5xxError
    # dimensionada por Resource+Method nunca publicou datapoint nos testes
    # reais desta atividade (ver nota em documentacao-observabilidade.md).
    # Aqui verificamos a métrica agregada (sem dimensão de rota), que é a
    # fonte do widget "Taxa de erro agregada" e essa sim publica normalmente.
    checks = [
        ("Painel 1 — Disponibilidade", "TodoApp/Availability", "AvailabilitySuccess", [{"Name": "Target", "Value": "api"}]),
        ("Painel 1 — Disponibilidade", "TodoApp/Availability", "AvailabilitySuccess", [{"Name": "Target", "Value": "frontend"}]),
        ("Painel 3 — Erros (taxa agregada da API)", "AWS/ApiGateway", "5xxError", ([{"Name": "ApiId", "Value": api_id}, {"Name": "Stage", "Value": "$default"}] if api_id else [])),
        ("Painel 4 — Banco de Dados (latência)", "AWS/DynamoDB", "SuccessfulRequestLatency", [{"Name": "TableName", "Value": CONFIG["dynamo_table"]}, {"Name": "Operation", "Value": "Scan"}], "Average"),
        ("Painel 4 — Banco de Dados (capacidade consumida)", "AWS/DynamoDB", "ConsumedReadCapacityUnits", [{"Name": "TableName", "Value": CONFIG["dynamo_table"]}]),
    ]

    for item in checks:
        panel, namespace, metric, dims = item[0], item[1], item[2], item[3]
        stat = item[4] if len(item) > 4 else "Sum"
        if not dims:
            log_line(f"- [{panel}] {namespace}/{metric}: sem ApiId descoberto, pulei.")
            continue
        total, points = get_sum(namespace, metric, dims, stat)
        log_line(f"- [{panel}] {namespace}/{metric} ({stat}) — dimensões {dims}: total/valor agregado = {total:.2f}, {len(points)} datapoint(s)")
        for p in points:
            log_line(f"    {p['Timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')} → {p[stat]:.2f}")


def consultar_logs_insights(session, todo_fn):
    log_section("Consulta ao CloudWatch Logs Insights (dados reais)")
    if not session or not todo_fn:
        log_line("boto3 não disponível ou função não encontrada — pulei.")
        return
    logs = session.client("logs", region_name=CONFIG["aws_region"])
    log_group = f"/aws/lambda/{todo_fn}"
    end = int(datetime.now(timezone.utc).timestamp())
    start = end - 20 * 60

    queries = {
        "Painel 3 — 5xx por rota ao longo do tempo": (
            'fields @timestamp, route, status_code\n'
            '| filter event = "http_request" and status_code >= 500\n'
            '| stats count() as erros by bin(5m) as periodo, route\n'
            '| sort periodo asc'
        ),
        "Painel 3 — Causas de erro (top rotas/status >= 400)": (
            'fields @timestamp, route, status_code, request_id\n'
            '| filter event = "http_request" and status_code >= 400\n'
            '| stats count() as ocorrencias by route, status_code\n'
            '| sort ocorrencias desc'
        ),
        "Painel 4 — Falhas do back-end no acesso ao banco": (
            'fields @timestamp, operation, error_type, error_message, duration_ms\n'
            '| filter event = "db_operation" and result = "failure"\n'
            '| sort @timestamp desc\n'
            '| limit 50'
        ),
    }

    for title, query in queries.items():
        log_line(f"\n**{title}**")
        log_line(f"Log group: `{log_group}` · consulta:\n```\n{query}\n```")
        start_resp = logs.start_query(
            logGroupName=log_group, startTime=start, endTime=end, queryString=query
        )
        query_id = start_resp["queryId"]
        for _ in range(15):
            result = logs.get_query_results(queryId=query_id)
            if result["status"] in ("Complete", "Failed", "Cancelled"):
                break
            time.sleep(2)
        rows = result.get("results", [])
        log_line(f"Status: {result['status']} · {len(rows)} linha(s) retornada(s):")
        for row in rows[:10]:
            fields = {f["field"]: f["value"] for f in row}
            log_line(f"  {fields}")


def exemplo_de_registro(session, todo_fn):
    log_section("Exemplo de registro real (para relacionar log ↔ painel)")
    if not session or not todo_fn:
        log_line("boto3 não disponível — não foi possível buscar um exemplo real.")
        return
    logs = session.client("logs", region_name=CONFIG["aws_region"])
    log_group = f"/aws/lambda/{todo_fn}"
    end = int(datetime.now(timezone.utc).timestamp() * 1000)
    start = end - 20 * 60 * 1000
    resp = logs.filter_log_events(
        logGroupName=log_group,
        startTime=start,
        endTime=end,
        filterPattern='{ $.event = "http_request" }',
        limit=1,
    )
    events = resp.get("events", [])
    if events:
        log_line("Linha de log real (http_request), como aparece no CloudWatch Logs:")
        log_line(f"```json\n{events[0]['message'].strip()}\n```")
        log_line(
            "Essa linha alimenta: (a) as métricas nativas do API Gateway (Painéis 2/3/4, "
            "publicadas pelo próprio serviço a partir da mesma requisição) e (b) a consulta "
            "de Logs Insights do Painel 3 (\"Causas de erro\"), que lê os campos route e "
            "status_code diretamente deste JSON."
        )
    else:
        log_line("Nenhum evento encontrado no período — gere tráfego e rode o script novamente.")


def main():
    log_line(f"# Relatório de testes — Observabilidade (Entrega 2)\n")
    log_line(f"Gerado em: {now_str()}\n")

    session = boto3.Session() if boto3 else None
    todo_fn, hc_fn = (None, None)
    api_id = CONFIG["api_id"]
    if session:
        try:
            todo_fn, hc_fn = discover_resources(session)
            if not api_id:
                api_id = discover_api_id(session)
        except Exception as e:
            log_line(f"Aviso: não consegui descobrir os recursos automaticamente via boto3 ({e}).")

    gerar_trafego_normal()
    invocar_canario(session, hc_fn)
    provocar_falha_controlada()

    log_section("Aguardando propagação das métricas no CloudWatch")
    log_line(f"Aguardando {CONFIG['wait_for_metrics_seconds']}s...")
    time.sleep(CONFIG["wait_for_metrics_seconds"])

    consultar_metricas(session, api_id)
    consultar_logs_insights(session, todo_fn)
    exemplo_de_registro(session, todo_fn)

    log_section("Conclusão")
    log_line(
        "Os valores acima foram obtidos consultando o CloudWatch (métricas e Logs "
        "Insights) depois de gerar tráfego real e uma falha controlada — não são "
        "dados fictícios. Complemente este relatório com capturas de tela do "
        "dashboard `todo-app-observabilidade` no mesmo período, para a entrega final."
    )

    with open("relatorio_testes_observabilidade.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print("\nRelatório salvo em relatorio_testes_observabilidade.md")


if __name__ == "__main__":
    main()
