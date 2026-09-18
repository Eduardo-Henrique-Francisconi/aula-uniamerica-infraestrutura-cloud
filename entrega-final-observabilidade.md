# Entrega 2 — Observabilidade

**Grupo/Aluno:** NEKO
**Continuação de:** `entrega-final.md` (Entrega 1 — infraestrutura funcionando)
**Prazo:** 18/09

---

## ✅ Checklist

| Item exigido | Status |
|---|---|
| Continuidade da Entrega 1 (domínio, HTTPS, serverless, proxy reverso, redundância, proteção do back-end/banco) | ✅ Mantido sem alteração |
| Diagrama técnico fiel (aplicação + observabilidade) | ✅ `diagrama-arquitetura.html` (Diagrama 1 + Diagrama 2) |
| Pelo menos 4 painéis com dados reais | ✅ 4 painéis definidos em `backend/template.yaml` (`ObservabilityDashboard`), confirmados com dados reais no dashboard após o deploy |
| Fundamentação de 100% dos painéis (10 itens cada) | ✅ `documentacao-observabilidade.md`, Seção 2 |
| Logs estruturados e adaptações necessárias | ✅ `backend/index.js`, `backend/healthcheck/index.js` — documentado na Seção 3 |
| Controle de acesso à observabilidade | ✅ Seção 4 (só IAM da conta, sem endpoint público) |
| Deploy da stack atualizada | ✅ **Concluído** — `sam build && sam deploy` rodados com sucesso, dashboard confirmado com dados reais em todos os widgets |
| Testes e evidências | ⏳ **Falta rodar a versão final** — `observabilidade_testes.py` foi reescrito para rodar tudo sozinho (inclusive o teste de failover e as capturas de tela do dashboard); falta só executar `python observabilidade_testes.py` uma vez |

---

## O que já está pronto (arquivos no repositório)

| Arquivo | O que é |
|---|---|
| `backend/index.js` | Backend com logs estruturados (`http_request`, `db_operation`) + rota de falha simulada |
| `backend/healthcheck/index.js` + `package.json` | Canário de disponibilidade (nova função Lambda) |
| `backend/template.yaml` | Rotas explícitas, métricas detalhadas, log groups com retenção, Metric Filters, Dashboard (4 painéis) |
| `backend/DEPLOY-ENTREGA2.md` | Roteiro passo a passo do deploy (o que mudou, comandos, troubleshooting, custo) |
| `diagrama-arquitetura.html` | Diagrama 1 (aplicação, atualizado) + Diagrama 2 (observabilidade) + legenda unificada |
| `documentacao-observabilidade.md` | Documentação completa: o que mudou, ferramenta escolhida, fundamentação dos 4 painéis, logs, acesso, testes |
| `observabilidade_testes.py` | Script 100% automático: gera tráfego real, invoca o canário, provoca a falha controlada, **executa o teste de failover do front-end com o canário rodando durante a queda**, julga PASS/FAIL de cada verificação, consulta o CloudWatch e **baixa sozinho as imagens dos widgets do dashboard** (`GetMetricWidgetImage`) — nenhum passo manual, nenhuma captura de tela na mão |
| `relatorio_testes_observabilidade.md` | Gerado pelo script — resumo PASS/FAIL + detalhe de cada verificação com dados reais. A versão atual no repositório foi organizada manualmente a partir de uma rodada anterior (3 dos 7 cenários); rodar o script reescrito substitui esse arquivo por um relatório completo e automático |

## O que falta fazer

1. Rodar `python observabilidade_testes.py` uma vez (com `aws configure` já feito). Ele sozinho: gera tráfego, invoca o canário, provoca a falha controlada, derruba e restaura o bucket primário do front-end (testando o failover com o canário rodando durante a queda), julga PASS/FAIL de cada verificação, escreve `relatorio_testes_observabilidade.md` e salva as imagens dos widgets do dashboard em `evidencias_observabilidade/`.
2. Anexar `relatorio_testes_observabilidade.md` e a pasta `evidencias_observabilidade/` a esta entrega.

## Status do deploy

O `sam build && sam deploy` já foi rodado com sucesso (roteiro em
`backend/DEPLOY-ENTREGA2.md`). O dashboard `todo-app-observabilidade` está no
ar com os 4 painéis mostrando dados reais, incluindo os dois widgets que
precisaram trocar de fonte de dado (ver nota no início de
`documentacao-observabilidade.md`). O que falta agora é só a etapa 8 da
atividade: rodar a versão final e automática de `observabilidade_testes.py`
(item 1 acima) — ela já cobre testes e evidências (incluindo a captura das
imagens) numa única execução, sem passo manual nenhum.
