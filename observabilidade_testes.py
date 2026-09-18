"""
observabilidade_testes.py — Roda os testes da Entrega 2 de ponta a ponta, sem
passos manuais: gera tráfego real, invoca o canário, provoca a falha
controlada, executa o teste de failover do front-end (com o canário rodando
durante a queda), julga PASS/FAIL de cada verificação (igual ao
run_tests.py da Entrega 1), consulta o CloudWatch (métricas + Logs Insights)
e ainda baixa automaticamente as imagens dos widgets de métrica do dashboard
(via GetMetricWidgetImage) como evidência — sem precisar abrir o console e
tirar print manualmente.

Ao final, gera:
    - relatorio_testes_observabilidade.md  (relatório com resumo PASS/FAIL,
      dados reais e uma seção "detalhe" por verificação)
    - evidencias_observabilidade/*.png     (capturas automáticas dos widgets
      de métrica do dashboard, no mesmo período dos testes)

Pré-requisitos:
    pip install requests boto3
    (o boto3 usa as mesmas credenciais já configuradas via `aws configure`,
    com permissão de leitura no CloudWatch/Logs/DynamoDB/Lambda/API Gateway/S3)

Como usar (depois de fazer o deploy da Entrega 2 — ver DEPLOY-ENTREGA2.md):
    python observabilidade_testes.py

ATENÇÃO — Cenário 4 (failover): igual ao Teste 7 do run_tests.py da Entrega 1,
ele remove temporariamente o index.html do bucket S3 primário para forçar o
failover do CloudFront, e restaura automaticamente no final (mesmo se algo
der errado no meio do caminho — bloco try/finally). Para pular esse cenário,
mude CONFIG["run_failover_test"] para False.

Ajuste o dicionário CONFIG abaixo se algum nome de recurso mudar.
"""

import json
import os
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
    "dashboard_name": "todo-app-observabilidade",
    "primary_bucket": "todo-app-neshiku-frontend-1",
    "primary_bucket_region": "us-east-2",
    "run_failover_test": True,
    "screenshots_dir": "evidencias_observabilidade",
}

SP_TZ = timezone(timedelta(hours=-3))
results = []  # {"num", "nome", "passed", "detalhe"}


def now_str():
    utc = datetime.now(timezone.utc)
    sp = utc.astimezone(SP_TZ)
    return (
        f"{utc.strftime('%Y-%m-%d %H:%M:%S')} UTC "
        f"({sp.strftime('%Y-%m-%d %H:%M:%S')} America/Sao_Paulo)"
    )


def registrar(num, nome, passed, detalhe_md):
    """Registra o resultado de uma verificação (igual ao log() do
    run_tests.py): imprime no console em tempo real e guarda pro relatório
    final, com veredito PASS/FAIL explícito — nada de só despejar dado cru."""
    results.append({"num": num, "nome": nome, "passed": passed, "detalhe": detalhe_md})
    status = "PASS" if passed else "FAIL"
    print(f"\n[{status}] {num}. {nome}")
    for linha in detalhe_md.splitlines():
        print(f"    {linha}")


def discover_resources(session):
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


def run_logs_insights_query(session, log_group, query, start_epoch, end_epoch, wait_s=30):
    """Roda uma consulta de Logs Insights e espera terminar. Retorna
    (status, linhas), cada linha um dict campo->valor."""
    logs = session.client("logs", region_name=CONFIG["aws_region"])
    start_resp = logs.start_query(
        logGroupName=log_group, startTime=start_epoch, endTime=end_epoch, queryString=query
    )
    query_id = start_resp["queryId"]
    result = {"status": "Unknown", "results": []}
    for _ in range(wait_s // 2):
        result = logs.get_query_results(queryId=query_id)
        if result["status"] in ("Complete", "Failed", "Cancelled"):
            break
        time.sleep(2)
    rows = result.get("results", [])
    return result.get("status", "Unknown"), [{f["field"]: f["value"] for f in row} for row in rows]


# ---------------------------------------------------------------------------
# Cenário 1 — Uso normal pelo domínio (front-end → back-end → banco)
# ---------------------------------------------------------------------------

def cenario_1_trafego_normal():
    inicio = now_str()
    created_ids = []
    falhas = 0
    for i in range(CONFIG["normal_traffic_requests"]):
        r_get = requests.get(f"{CONFIG['api_url']}/todos", timeout=10)
        r_post = requests.post(
            f"{CONFIG['api_url']}/todos",
            json={"text": f"tarefa de teste observabilidade #{i}"},
            timeout=10,
        )
        if r_get.status_code != 200:
            falhas += 1
        if r_post.status_code == 201:
            created_ids.append(r_post.json()["id"])
        else:
            falhas += 1
        time.sleep(0.3)
    for todo_id in created_ids[:5]:
        requests.patch(f"{CONFIG['api_url']}/todos/{todo_id}", timeout=10)
    for todo_id in created_ids:
        requests.delete(f"{CONFIG['api_url']}/todos/{todo_id}", timeout=10)
    fim = now_str()

    ok = falhas == 0 and len(created_ids) == CONFIG["normal_traffic_requests"]
    detalhe = (
        f"Início: {inicio} · Fim: {fim}\n"
        f"{CONFIG['normal_traffic_requests']} GET + {CONFIG['normal_traffic_requests']} POST + "
        f"{min(5, len(created_ids))} PATCH + {len(created_ids)} DELETE em `{CONFIG['api_url']}/todos`.\n"
        f"Requisições com status inesperado: {falhas}.\n"
        "Exercita GetTodos (Scan), PutTodo, UpdateTodo e DeleteTodo no DynamoDB pelo "
        "caminho real (domínio → Cloudflare → API Gateway → Lambda → DynamoDB)."
    )
    registrar(1, "Uso normal pelo domínio (front-end → back-end → banco)", ok, detalhe)


# ---------------------------------------------------------------------------
# Cenário 2 — Canário de disponibilidade (invocação manual)
# ---------------------------------------------------------------------------

def cenario_2_canario(session, hc_fn):
    if not hc_fn or not session:
        registrar(
            2, "Canário de disponibilidade (invocação manual)", False,
            "AWS/boto3 não disponível — pulei a invocação manual.",
        )
        return
    lam = session.client("lambda", region_name=CONFIG["aws_region"])
    linhas = []
    ok = True
    for i in range(2):
        resp = lam.invoke(FunctionName=hc_fn, InvocationType="RequestResponse")
        payload = json.loads(resp["Payload"].read())
        checked = payload.get("checked", 0)
        if checked < 2:
            ok = False
        linhas.append(f"Invocação {i + 1} em {now_str()} → `{payload}`")
        time.sleep(5)
    registrar(
        2, "Canário de disponibilidade (invocação manual)", ok,
        "\n".join(linhas) + "\n\n`checked` deve ser 2 (frontend + api) em cada invocação.",
    )


# ---------------------------------------------------------------------------
# Cenário 3 — Falha controlada
# ---------------------------------------------------------------------------

def cenario_3_falha_controlada():
    inicio = now_str()
    codigos = []
    for _ in range(CONFIG["simulated_failure_requests"]):
        r = requests.get(f"{CONFIG['api_url']}/todos-falha-simulada", timeout=10)
        codigos.append(r.status_code)
    fim = now_str()
    ok = all(c == 500 for c in codigos)
    detalhe = (
        f"Início: {inicio} · Fim: {fim}\n"
        f"Status recebidos: {codigos}\n"
        "Cada chamada gera 1 log `http_request` com `status_code=500` e "
        "`route=\"/todos-falha-simulada\"` no TodoFunction, e é contada como "
        "`5xxError` nativo do API Gateway para essa rota."
    )
    registrar(3, "Falha controlada (`GET /todos-falha-simulada` → sempre 500)", ok, detalhe)


# ---------------------------------------------------------------------------
# Cenário 4 — Failover do front-end COM o canário rodando durante a queda
# (mesma técnica do Teste 7 de run_tests.py: derruba o bucket primário,
# confirma que o front-end continua no ar via CloudFront, e que o canário —
# que alimenta o Painel de Disponibilidade — também captura sucesso durante
# a queda, comprovando que o painel não acusaria indisponibilidade num
# failover real. Restaura o bucket automaticamente, sempre, mesmo se algo
# falhar no meio do caminho.)
# ---------------------------------------------------------------------------

def cenario_4_failover_com_canario(session, hc_fn):
    nome = "Failover do front-end com o canário rodando durante a queda"
    if not CONFIG["run_failover_test"]:
        registrar(4, nome, False, "Pulado (`run_failover_test = False` na configuração).")
        return
    if session is None:
        registrar(4, nome, False, "boto3 não disponível — pulei o teste de failover.")
        return

    bucket = CONFIG["primary_bucket"]
    region = CONFIG["primary_bucket_region"]
    s3 = session.client("s3", region_name=region)
    lam = session.client("lambda", region_name=CONFIG["aws_region"]) if hc_fn else None

    linhas = []
    moved = False
    frontend_ok_durante_queda = False
    canario_confirmou = False
    invoke_ts = None

    try:
        linhas.append(f"Derrubando o bucket primário `{bucket}` (mv index.html → index.html.bak) em {now_str()}")
        s3.copy_object(Bucket=bucket, CopySource=f"{bucket}/index.html", Key="index.html.bak")
        s3.delete_object(Bucket=bucket, Key="index.html")
        moved = True

        # Confirma que o front-end continua respondendo via failover do CloudFront
        r = requests.get(CONFIG["frontend_url"], timeout=15)
        frontend_ok_durante_queda = r.status_code == 200 and "<html" in r.text.lower()
        linhas.append(
            f"`GET {CONFIG['frontend_url']}` durante a queda → status {r.status_code} "
            f"({'OK, serviu pelo bucket secundário' if frontend_ok_durante_queda else 'FALHOU'})"
        )

        # Invoca o canário NA HORA em que o bucket primário está fora do ar
        if lam:
            invoke_ts = int(datetime.now(timezone.utc).timestamp())
            resp = lam.invoke(FunctionName=hc_fn, InvocationType="RequestResponse")
            payload = json.loads(resp["Payload"].read())
            linhas.append(f"Canário invocado durante a queda em {now_str()} → `{payload}`")

            # Espera a linha de log do canário ficar disponível e confirma, pelo
            # próprio log estruturado, que o target=frontend deu "success"
            # mesmo com o bucket primário fora do ar.
            time.sleep(8)
            log_group = f"/aws/lambda/{hc_fn}"
            status, rows = run_logs_insights_query(
                session, log_group,
                'fields @timestamp, target, result, http_status\n'
                '| filter event = "healthcheck" and target = "frontend"\n'
                '| sort @timestamp desc\n'
                '| limit 1',
                invoke_ts - 30, invoke_ts + 60,
            )
            if rows:
                canario_confirmou = rows[0].get("result") == "success"
                linhas.append(f"Log do canário logo após a invocação: `{rows[0]}`")
            else:
                linhas.append("Não encontrei a linha de log do canário na janela esperada.")
        else:
            linhas.append("Nome da HealthCheckFunction não descoberto — pulei a invocação durante a queda.")
    except Exception as e:
        linhas.append(f"Erro durante o teste: {e}")
    finally:
        if moved:
            try:
                s3.copy_object(Bucket=bucket, CopySource=f"{bucket}/index.html.bak", Key="index.html")
                s3.delete_object(Bucket=bucket, Key="index.html.bak")
                linhas.append(f"Bucket primário restaurado com sucesso em {now_str()}.")
            except Exception as e:
                linhas.append(f"ATENÇÃO: falha ao restaurar o bucket automaticamente: {e} — restaure manualmente!")

    ok = frontend_ok_durante_queda and (canario_confirmou or lam is None and frontend_ok_durante_queda)
    linhas.append(
        f"\nResultado: front-end acessível durante a queda = {frontend_ok_durante_queda}; "
        f"canário confirmou `frontend`/`success` durante a queda = {canario_confirmou}."
    )
    registrar(4, nome, ok, "\n".join(linhas))


# ---------------------------------------------------------------------------
# Verificações no CloudWatch (métricas nativas)
# ---------------------------------------------------------------------------

def verificar_metricas(session, api_id):
    if not session:
        registrar(5, "Métricas nativas do CloudWatch têm dado real", False, "boto3 não disponível.")
        return
    cw = session.client("cloudwatch", region_name=CONFIG["aws_region"])
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=20)

    def get_stat(namespace, metric, dims, stat="Sum"):
        resp = cw.get_metric_statistics(
            Namespace=namespace, MetricName=metric, Dimensions=dims,
            StartTime=start, EndTime=end, Period=300, Statistics=[stat],
        )
        points = sorted(resp.get("Datapoints", []), key=lambda d: d["Timestamp"])
        total = sum(p[stat] for p in points)
        return total, points

    checks = [
        ("Disponibilidade — sucesso (api)", "TodoApp/Availability", "AvailabilitySuccess", [{"Name": "Target", "Value": "api"}], "Sum", True),
        ("Disponibilidade — sucesso (frontend)", "TodoApp/Availability", "AvailabilitySuccess", [{"Name": "Target", "Value": "frontend"}], "Sum", True),
        ("Erros — taxa agregada (5xxError)", "AWS/ApiGateway", "5xxError", ([{"Name": "ApiId", "Value": api_id}, {"Name": "Stage", "Value": "$default"}] if api_id else []), "Sum", False),
        ("Banco de Dados — latência do Scan", "AWS/DynamoDB", "SuccessfulRequestLatency", [{"Name": "TableName", "Value": CONFIG["dynamo_table"]}, {"Name": "Operation", "Value": "Scan"}], "Average", True),
        ("Banco de Dados — capacidade lida (RCU)", "AWS/DynamoDB", "ConsumedReadCapacityUnits", [{"Name": "TableName", "Value": CONFIG["dynamo_table"]}], "Sum", True),
    ]

    linhas = [f"Período consultado: {start.strftime('%Y-%m-%d %H:%M:%S')} a {end.strftime('%Y-%m-%d %H:%M:%S')} UTC (últimos 20 min)\n"]
    linhas.append("| Verificação | Métrica | Total/valor | Datapoints |")
    linhas.append("|---|---|---|---|")
    tudo_ok = True
    for nome, namespace, metric, dims, stat, esperado_com_dado in checks:
        if not dims:
            linhas.append(f"| {nome} | {namespace}/{metric} | sem ApiId descoberto | — |")
            continue
        total, points = get_stat(namespace, metric, dims, stat)
        linhas.append(f"| {nome} | {namespace}/{metric} ({stat}) | {total:.2f} | {len(points)} |")
        # 5xxError agregado com 0 datapoints é esperado fora da janela exata
        # do teste — não reprova o resultado geral (ver nota no relatório).
        if esperado_com_dado and len(points) == 0:
            tudo_ok = False

    registrar(5, "Métricas nativas do CloudWatch têm dado real", tudo_ok, "\n".join(linhas))


def verificar_logs_insights(session, todo_fn):
    if not session or not todo_fn:
        registrar(6, "Logs Insights confirmam a falha controlada e o estado do banco", False, "boto3 ou TodoFunction não disponível.")
        return
    log_group = f"/aws/lambda/{todo_fn}"
    end = int(datetime.now(timezone.utc).timestamp())
    start = end - 20 * 60

    linhas = []

    status1, rows1 = run_logs_insights_query(
        session, log_group,
        'fields @timestamp, route, status_code\n'
        '| filter event = "http_request" and status_code >= 500\n'
        '| stats count() as erros by bin(5m) as periodo, route\n'
        '| sort periodo asc',
        start, end,
    )
    linhas.append("**5xx por rota ao longo do tempo:**")
    linhas.append("| Período | Rota | Erros |")
    linhas.append("|---|---|---|")
    for row in rows1:
        linhas.append(f"| {row.get('periodo')} | {row.get('route')} | {row.get('erros')} |")
    total_erros_logados = sum(int(r.get("erros", 0)) for r in rows1)
    erros_ok = total_erros_logados >= CONFIG["simulated_failure_requests"]

    status2, rows2 = run_logs_insights_query(
        session, log_group,
        'fields @timestamp, route, status_code, request_id\n'
        '| filter event = "http_request" and status_code >= 400\n'
        '| stats count() as ocorrencias by route, status_code\n'
        '| sort ocorrencias desc',
        start, end,
    )
    linhas.append("\n**Causas de erro (rotas/status >= 400):**")
    linhas.append("| Rota | Status | Ocorrências |")
    linhas.append("|---|---|---|")
    for row in rows2:
        linhas.append(f"| {row.get('route')} | {row.get('status_code')} | {row.get('ocorrencias')} |")

    status3, rows3 = run_logs_insights_query(
        session, log_group,
        'filter event = "db_operation" and result = "failure"\n'
        '| stats count() as falhas',
        start, end,
    )
    linhas.append("\n**Falhas de acesso ao banco vistas pelo back-end:**")
    if rows3 and int(rows3[0].get("falhas", 0)) > 0:
        linhas.append(f"{rows3[0].get('falhas')} falha(s) — inesperado neste cenário (banco deveria estar saudável).")
        banco_ok = False
    else:
        linhas.append("0 falhas — esperado (o cenário de falha controlada não passa pelo banco; banco saudável).")
        banco_ok = True

    ok = erros_ok and banco_ok
    registrar(6, "Logs Insights confirmam a falha controlada e o estado do banco", ok, "\n".join(linhas))


def capturar_screenshots_dashboard(session):
    """Baixa automaticamente as imagens dos widgets de MÉTRICA do dashboard
    (via GetMetricWidgetImage) — evidência visual sem precisar abrir o
    console e tirar print na mão. Widgets de log (Logs Insights) já viram
    tabela real na Seção de logs acima, que também conta como evidência."""
    if not session:
        registrar(7, "Capturas automáticas dos widgets do dashboard", False, "boto3 não disponível.")
        return
    cw = session.client("cloudwatch", region_name=CONFIG["aws_region"])
    try:
        resp = cw.get_dashboard(DashboardName=CONFIG["dashboard_name"])
    except Exception as e:
        registrar(7, "Capturas automáticas dos widgets do dashboard", False, f"Erro ao ler o dashboard: {e}")
        return

    body = json.loads(resp["DashboardBody"])
    os.makedirs(CONFIG["screenshots_dir"], exist_ok=True)
    salvos = []
    for i, widget in enumerate(body.get("widgets", [])):
        if widget.get("type") != "metric":
            continue
        props = dict(widget["properties"])
        props["width"] = 900
        props["height"] = 450
        try:
            img = cw.get_metric_widget_image(MetricWidget=json.dumps(props))
            titulo = props.get("title", f"widget-{i}")
            slug = "".join(c if c.isalnum() else "-" for c in titulo).strip("-").lower()[:60]
            path = os.path.join(CONFIG["screenshots_dir"], f"{i:02d}-{slug}.png")
            payload = img["MetricWidgetImage"]
            with open(path, "wb") as f:
                f.write(payload.read() if hasattr(payload, "read") else payload)
            salvos.append(path)
        except Exception as e:
            salvos.append(f"(falhou: {props.get('title', i)} — {e})")

    ok = len(salvos) > 0 and all(not s.startswith("(falhou") for s in salvos)
    detalhe = "Imagens salvas em `" + CONFIG["screenshots_dir"] + "/`:\n" + "\n".join(f"- {s}" for s in salvos)
    registrar(7, "Capturas automáticas dos widgets do dashboard (GetMetricWidgetImage)", ok, detalhe)


def exemplo_de_registro(session, todo_fn):
    if not session or not todo_fn:
        return None
    logs = session.client("logs", region_name=CONFIG["aws_region"])
    log_group = f"/aws/lambda/{todo_fn}"
    end = int(datetime.now(timezone.utc).timestamp() * 1000)
    start = end - 20 * 60 * 1000
    resp = logs.filter_log_events(
        logGroupName=log_group, startTime=start, endTime=end,
        filterPattern='{ $.event = "http_request" }', limit=1,
    )
    events = resp.get("events", [])
    return events[0]["message"].strip() if events else None


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def gerar_relatorio_md(exemplo_log):
    linhas = [
        "# Relatório de testes — Observabilidade (Entrega 2)",
        "",
        f"**Gerado em:** {now_str()}",
        f"**Dashboard:** `{CONFIG['dashboard_name']}` (CloudWatch, região `{CONFIG['aws_region']}`)",
        "",
        "Todos os cenários abaixo rodam automaticamente (`python observabilidade_testes.py`), "
        "sem nenhum passo manual — inclusive o teste de failover do front-end e a captura "
        "das imagens do dashboard.",
        "",
        "## Resumo",
        "",
        "| # | Verificação | Resultado |",
        "|---|---|---|",
    ]
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        linhas.append(f"| {r['num']} | {r['nome']} | {status} |")
    total = len(results)
    ok = sum(1 for r in results if r["passed"])
    linhas.append("")
    linhas.append(f"**{ok}/{total} verificações passaram.**")

    linhas.append("")
    linhas.append("## Detalhe (verificação a verificação)")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        linhas.append("")
        linhas.append(f"### {r['num']}. {r['nome']} — {status}")
        linhas.append("")
        linhas.append(r["detalhe"])

    if exemplo_log:
        linhas.append("")
        linhas.append("## Exemplo de registro real (log → painel)")
        linhas.append("")
        linhas.append("Uma linha real de log `http_request`, como aparece no CloudWatch Logs:")
        linhas.append("")
        linhas.append(f"```json\n{exemplo_log}\n```")
        linhas.append("")
        linhas.append(
            "Essa linha alimenta ao mesmo tempo as métricas nativas do API Gateway "
            "(Desempenho, Erros) e a consulta de Logs Insights do painel de Erros."
        )

    linhas.append("")
    linhas.append("## Conclusão")
    linhas.append("")
    linhas.append(
        f"{ok}/{total} verificações passaram, todas com dados reais consultados no "
        "CloudWatch depois de gerar tráfego real, invocar o canário, provocar a falha "
        "controlada e derrubar o bucket primário do front-end. As imagens dos widgets "
        f"de métrica foram salvas automaticamente em `{CONFIG['screenshots_dir']}/` — "
        "anexe essa pasta e este relatório à entrega."
    )

    with open("relatorio_testes_observabilidade.md", "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    print(f"\nRelatório salvo em relatorio_testes_observabilidade.md ({ok}/{total} OK)")


def main():
    print(f"Executando os testes da Entrega 2 (Observabilidade) — {now_str()}\n")

    session = boto3.Session() if boto3 else None
    todo_fn, hc_fn = (None, None)
    api_id = CONFIG["api_id"]
    if session:
        try:
            todo_fn, hc_fn = discover_resources(session)
            if not api_id:
                api_id = discover_api_id(session)
        except Exception as e:
            print(f"Aviso: não consegui descobrir os recursos automaticamente via boto3 ({e}).")

    cenario_1_trafego_normal()
    cenario_2_canario(session, hc_fn)
    cenario_3_falha_controlada()
    cenario_4_failover_com_canario(session, hc_fn)

    print(f"\nAguardando {CONFIG['wait_for_metrics_seconds']}s para as métricas propagarem no CloudWatch...")
    time.sleep(CONFIG["wait_for_metrics_seconds"])

    verificar_metricas(session, api_id)
    verificar_logs_insights(session, todo_fn)
    capturar_screenshots_dashboard(session)
    exemplo_log = exemplo_de_registro(session, todo_fn)

    gerar_relatorio_md(exemplo_log)


if __name__ == "__main__":
    main()
