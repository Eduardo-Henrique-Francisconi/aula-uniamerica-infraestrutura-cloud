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
| Testes e evidências | ⏳ **Quase pronto** — `observabilidade_testes.py` já rodou e gerou `relatorio_testes_observabilidade.md` com dados reais dos 3 cenários; falta só tirar as capturas de tela do dashboard e repetir o teste de failover do front-end com o canário rodando |

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
| `observabilidade_testes.py` | Script que gera tráfego real + falha controlada e consulta o CloudWatch (métricas e Logs Insights), gerando `relatorio_testes_observabilidade.md` |
| `relatorio_testes_observabilidade.md` | ✅ Já gerado — relatório com os 3 cenários de teste e os dados reais consultados no CloudWatch |

## O que falta fazer

1. **Capturas de tela**: abrir o `DashboardUrl` que o `sam deploy` mostrou no final do deploy, e tirar prints dos 4 painéis com dados (no mesmo período do relatório).
2. **Teste de redundância combinado**: repetir o teste de failover do front-end (Entrega 1) enquanto o canário está rodando, para mostrar no painel de Disponibilidade que a checagem do front-end não caiu durante a falha do bucket primário.
3. Anexar `relatorio_testes_observabilidade.md` e as capturas de tela a esta entrega.

## Status do deploy

O `sam build && sam deploy` já foi rodado com sucesso (roteiro em
`backend/DEPLOY-ENTREGA2.md`). O dashboard `todo-app-observabilidade` está no
ar com os 4 painéis mostrando dados reais, incluindo os dois widgets que
precisaram trocar de fonte de dado (ver nota no início de
`documentacao-observabilidade.md`). Os testes (`observabilidade_testes.py`)
já rodaram e geraram o relatório. O que falta agora é só a etapa 8 da
atividade: as capturas de tela e o teste de failover combinado (itens 1–3
acima).
