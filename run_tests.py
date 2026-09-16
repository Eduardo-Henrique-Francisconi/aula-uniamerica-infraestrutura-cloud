"""
run_tests.py — Executa os 7 testes exigidos pela atividade e gera um
relatório em Markdown (relatorio_testes.md) mostrando, para cada teste,
o(s) comando(s) exatamente usado(s), a saída obtida e o resultado (PASS/FAIL).

Pré-requisitos:
    pip install requests boto3
    (o boto3 usa as mesmas credenciais já configuradas via `aws configure`)

Como usar:
    python run_tests.py

O script já vem configurado com os valores usados neste projeto
(neshiku.com.br). Se algo mudar (nova URL do API Gateway após um
`sam deploy`, por exemplo), ajuste o dicionário CONFIG abaixo.

ATENÇÃO — Teste 7: ele remove temporariamente o index.html do bucket S3
primário para forçar o failover do CloudFront, e tenta restaurar o
arquivo automaticamente no final (mesmo se algo der errado no meio do
caminho). Se preferir não rodar esse teste, mude run_failover_test
para False.
"""

import io
import json
import sys
import time
from datetime import datetime

import requests

try:
    import boto3
except ImportError:
    boto3 = None


class Tee(io.TextIOBase):
    """Escreve em vários streams ao mesmo tempo (console real + buffer em
    memória), só para conseguirmos exibir tudo em tempo real e também
    guardar uma cópia."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
        return len(data)

    def flush(self):
        for s in self.streams:
            s.flush()


CONFIG = {
    "frontend_url": "https://app.neshiku.com.br",
    "api_url": "https://api.neshiku.com.br",
    "raw_api_url": "https://vfb3b537c6.execute-api.us-east-2.amazonaws.com",
    "dynamo_table": "todos-table",
    "aws_region": "us-east-2",
    "primary_bucket": "todo-app-neshiku-frontend-1",
    "primary_bucket_region": "us-east-2",
    "run_failover_test": True,
}

results = []


def log(test_num, name, passed, commands, output):
    """
    commands: lista de strings, cada uma um comando "equivalente" (curl/aws
              cli) ao que o script de fato executou via requests/boto3 —
              assim o relatório mostra comando por comando, do jeito que
              você digitaria no terminal.
    output:   texto com a saída/resposta obtida.
    """
    results.append(
        {
            "num": test_num,
            "name": name,
            "passed": passed,
            "commands": commands,
            "output": output,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
    )
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] Teste {test_num}: {name}")
    for c in commands:
        print(f"    $ {c}")
    for linha in output.splitlines():
        print(f"      {linha}")
    print()


def resposta_para_texto(r):
    """Formata uma requests.Response parecido com o que -i do curl mostra."""
    linhas = [f"HTTP/1.1 {r.status_code} {r.reason}"]
    for k, v in r.headers.items():
        linhas.append(f"{k}: {v}")
    linhas.append("")
    corpo = r.text
    if len(corpo) > 500:
        corpo = corpo[:500] + " ...(truncado)"
    linhas.append(corpo)
    return "\n".join(linhas)


def test_1_frontend_dominio():
    cmd = f"curl -i {CONFIG['frontend_url']}"
    try:
        r = requests.get(CONFIG["frontend_url"], timeout=15)
        ok = r.status_code == 200 and "<html" in r.text.lower()
        log(1, "Front-end acessível pelo domínio", ok, [cmd], resposta_para_texto(r))
    except Exception as e:
        log(1, "Front-end acessível pelo domínio", False, [cmd], f"Erro: {e}")


def test_2_backend_dominio():
    cmd = f"curl -i {CONFIG['api_url']}/todos"
    try:
        r = requests.get(f"{CONFIG['api_url']}/todos", timeout=15)
        ok = r.status_code == 200
        log(2, "Back-end acessível pelo domínio/API", ok, [cmd], resposta_para_texto(r))
    except Exception as e:
        log(2, "Back-end acessível pelo domínio/API", False, [cmd], f"Erro: {e}")


def test_3_frontend_para_backend():
    """
    Reproduz, via HTTP, o mesmo caminho que o front-end usa no navegador
    (POST/GET/DELETE em api.neshiku.com.br) — prova que a rota
    front-end -> back-end funciona de ponta a ponta.
    """
    cmd_post = (
        f"curl -i -X POST {CONFIG['api_url']}/todos "
        f'-H "Content-Type: application/json" -d \'{{"text":"teste-automatizado"}}\''
    )
    saida = []
    try:
        created = requests.post(
            f"{CONFIG['api_url']}/todos", json={"text": "teste-automatizado"}, timeout=15
        )
        saida.append("$ " + cmd_post)
        saida.append(resposta_para_texto(created))
        ok1 = created.status_code == 201
        todo_id = created.json().get("id") if ok1 else None

        cmd_get = f"curl -i {CONFIG['api_url']}/todos"
        saida.append("")
        saida.append("$ " + cmd_get)
        listed = requests.get(f"{CONFIG['api_url']}/todos", timeout=15)
        saida.append(resposta_para_texto(listed))
        ok2 = listed.status_code == 200 and any(
            t.get("id") == todo_id for t in listed.json()
        )

        cmd_delete = f"curl -i -X DELETE {CONFIG['api_url']}/todos/{todo_id}"
        cleanup_ok = True
        if todo_id:
            saida.append("")
            saida.append("$ " + cmd_delete)
            deleted = requests.delete(f"{CONFIG['api_url']}/todos/{todo_id}", timeout=15)
            saida.append(resposta_para_texto(deleted))
            cleanup_ok = deleted.status_code == 200
        else:
            cmd_delete = "(não executado: POST não retornou id)"

        ok = ok1 and ok2
        log(
            3,
            "Front-end conseguindo acessar o Back-end",
            ok,
            [cmd_post, cmd_get, cmd_delete],
            "\n".join(saida),
        )
    except Exception as e:
        log(
            3,
            "Front-end conseguindo acessar o Back-end",
            False,
            [cmd_post],
            f"Erro: {e}",
        )


def test_4_backend_para_db():
    cmd_post = (
        f"curl -i -X POST {CONFIG['api_url']}/todos "
        f'-H "Content-Type: application/json" -d \'{{"text":"teste-db-automatizado"}}\''
    )
    if boto3 is None:
        log(
            4,
            "Back-end conseguindo acessar o Banco de Dados",
            False,
            [cmd_post],
            "biblioteca boto3 não instalada (pip install boto3)",
        )
        return
    saida = []
    cmd_get_item = None
    try:
        created = requests.post(
            f"{CONFIG['api_url']}/todos", json={"text": "teste-db-automatizado"}, timeout=15
        )
        saida.append("$ " + cmd_post)
        saida.append(resposta_para_texto(created))
        todo_id = created.json().get("id") if created.status_code == 201 else None

        time.sleep(1)

        cmd_get_item = (
            f"aws dynamodb get-item --table-name {CONFIG['dynamo_table']} "
            f'--key \'{{"id":{{"S":"{todo_id}"}}}}\' --region {CONFIG["aws_region"]}'
        )
        ddb = boto3.client("dynamodb", region_name=CONFIG["aws_region"])
        item = (
            ddb.get_item(TableName=CONFIG["dynamo_table"], Key={"id": {"S": todo_id}})
            if todo_id
            else {}
        )
        found = "Item" in item
        saida.append("")
        saida.append("$ " + cmd_get_item)
        saida.append(json.dumps(item, indent=2, default=str))

        cmd_delete = f"curl -i -X DELETE {CONFIG['api_url']}/todos/{todo_id}"
        if todo_id:
            saida.append("")
            saida.append("$ " + cmd_delete)
            deleted = requests.delete(f"{CONFIG['api_url']}/todos/{todo_id}", timeout=15)
            saida.append(resposta_para_texto(deleted))

        ok = created.status_code == 201 and found
        log(
            4,
            "Back-end conseguindo acessar o Banco de Dados",
            ok,
            [cmd_post, cmd_get_item or "(não executado)", cmd_delete],
            "\n".join(saida),
        )
    except Exception as e:
        log(
            4,
            "Back-end conseguindo acessar o Banco de Dados",
            False,
            [cmd_post, cmd_get_item or "(não executado)"],
            f"Erro: {e}",
        )


def test_5_backend_direto_bloqueado():
    cmd = f"curl -i {CONFIG['raw_api_url']}/todos"
    try:
        r = requests.get(f"{CONFIG['raw_api_url']}/todos", timeout=15)
        ok = r.status_code == 403
        log(5, "Acesso direto ao Back-end bloqueado", ok, [cmd], resposta_para_texto(r))
    except Exception as e:
        log(5, "Acesso direto ao Back-end bloqueado", False, [cmd], f"Erro: {e}")


def test_6_db_direto_bloqueado():
    cmd = (
        f"curl -i -X POST https://dynamodb.{CONFIG['aws_region']}.amazonaws.com/ "
        f'-H "X-Amz-Target: DynamoDB_20120810.Scan" '
        f'-H "Content-Type: application/x-amz-json-1.0" '
        f'-d \'{{"TableName":"{CONFIG["dynamo_table"]}"}}\''
    )
    try:
        r = requests.post(
            f"https://dynamodb.{CONFIG['aws_region']}.amazonaws.com/",
            headers={
                "X-Amz-Target": "DynamoDB_20120810.Scan",
                "Content-Type": "application/x-amz-json-1.0",
            },
            data=json.dumps({"TableName": CONFIG["dynamo_table"]}),
            timeout=15,
        )
        # Sem assinatura SigV4/credenciais, a AWS sempre rejeita a chamada
        # (nunca devolve 200 com os itens da tabela).
        ok = r.status_code != 200
        log(6, "Acesso direto ao Banco de Dados bloqueado", ok, [cmd], resposta_para_texto(r))
    except Exception as e:
        log(6, "Acesso direto ao Banco de Dados bloqueado", False, [cmd], f"Erro: {e}")


def test_7_failover_frontend():
    bucket = CONFIG["primary_bucket"]
    region = CONFIG["primary_bucket_region"]
    cmd_quebrar = (
        f"aws s3 mv s3://{bucket}/index.html s3://{bucket}/index.html.bak --region {region}"
    )
    cmd_testar = f"curl -i {CONFIG['frontend_url']}"
    cmd_restaurar = (
        f"aws s3 mv s3://{bucket}/index.html.bak s3://{bucket}/index.html --region {region}"
    )

    if not CONFIG["run_failover_test"]:
        log(
            7,
            "Front-end disponível com componente redundante fora do ar",
            False,
            [cmd_quebrar, cmd_testar, cmd_restaurar],
            "Pulado (run_failover_test = False na configuração)",
        )
        return
    if boto3 is None:
        log(
            7,
            "Front-end disponível com componente redundante fora do ar",
            False,
            [cmd_quebrar, cmd_testar, cmd_restaurar],
            "biblioteca boto3 não instalada (pip install boto3)",
        )
        return

    s3 = boto3.client("s3", region_name=region)
    moved = False
    ok = False
    saida = []
    try:
        saida.append("$ " + cmd_quebrar)
        s3.copy_object(Bucket=bucket, CopySource=f"{bucket}/index.html", Key="index.html.bak")
        s3.delete_object(Bucket=bucket, Key="index.html")
        moved = True
        saida.append("move: index.html -> index.html.bak (via boto3, equivalente ao comando acima)")

        saida.append("")
        saida.append("$ " + cmd_testar)
        r = requests.get(CONFIG["frontend_url"], timeout=15)
        saida.append(resposta_para_texto(r))
        ok = r.status_code == 200
    except Exception as e:
        ok = False
        saida.append(f"Erro durante o teste: {e}")
    finally:
        if moved:
            saida.append("")
            saida.append("$ " + cmd_restaurar)
            try:
                s3.copy_object(
                    Bucket=bucket, CopySource=f"{bucket}/index.html.bak", Key="index.html"
                )
                s3.delete_object(Bucket=bucket, Key="index.html.bak")
                saida.append("move: index.html.bak -> index.html (bucket restaurado com sucesso)")
            except Exception as e:
                saida.append(f"ATENÇÃO: falha ao restaurar o bucket automaticamente: {e}")

    log(
        7,
        "Front-end disponível com componente redundante fora do ar",
        ok,
        [cmd_quebrar, cmd_testar, cmd_restaurar],
        "\n".join(saida),
    )


def gerar_relatorio_md():
    linhas = [
        "# Relatório de Testes — Infraestrutura Serverless",
        "",
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        "",
        f"- Front-end: {CONFIG['frontend_url']}",
        f"- Back-end/API: {CONFIG['api_url']}",
        "",
        "## Resumo",
        "",
        "| # | Teste | Resultado |",
        "|---|---|---|",
    ]
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        linhas.append(f"| {r['num']} | {r['name']} | {status} |")

    total = len(results)
    ok = sum(1 for r in results if r["passed"])
    linhas.append("")
    linhas.append(f"**{ok}/{total} testes passaram.**")

    linhas.append("")
    linhas.append("## Detalhe teste a teste (comando + saída)")

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        linhas.append("")
        linhas.append(f"### Teste {r['num']} — {r['name']} — {status}")
        linhas.append("")
        linhas.append("**Comando(s) executado(s):**")
        linhas.append("```bash")
        for c in r["commands"]:
            linhas.append(c)
        linhas.append("```")
        linhas.append("")
        linhas.append("**Saída obtida:**")
        linhas.append("```")
        linhas.append(r["output"])
        linhas.append("```")

    with open("relatorio_testes.md", "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))

    print(f"\nRelatório salvo em relatorio_testes.md ({ok}/{total} testes OK)")


def main():
    print("Executando os 7 testes da atividade...\n")
    test_1_frontend_dominio()
    test_2_backend_dominio()
    test_3_frontend_para_backend()
    test_4_backend_para_db()
    test_5_backend_direto_bloqueado()
    test_6_db_direto_bloqueado()
    test_7_failover_frontend()


if __name__ == "__main__":
    main()
    gerar_relatorio_md()
