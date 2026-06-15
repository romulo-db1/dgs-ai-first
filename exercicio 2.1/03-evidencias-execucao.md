# Exercício 2.1 — Item 3: Evidência de execução via MCP

**Projeto:** NovaTech Assistant
**Autor:** Rômulo — DB1
**Data:** 15/06/2026

## Como a evidência foi produzida

Os servers foram subidos no VS Code (agent mode do GitHub Copilot) via `.vscode/mcp.json`, com status *running* confirmado em **MCP: List Servers**.

Observação importante sobre o método: os servers `fs-workspace`/`fs-knowledge`/`git` se sobrepõem ao acesso nativo do Copilot (que já lê arquivos do workspace e roda git). Por isso, deixado à própria escolha, o agente respondia usando ferramentas nativas — sem chamar o MCP. Para gerar evidência inequívoca de uso do MCP, cada chamada foi **forçada** referenciando a tool pelo nome com `#` no prompt e instruindo explicitamente a não usar o acesso nativo/terminal. Cada invocação foi confirmada manualmente (auto-approve desligado).

## Demonstrações e gabarito (Anexo B)

| # | Prompt usado (forçando MCP) | Server / tool esperada | Resultado esperado (gabarito Anexo B) |
|---|---|---|---|
| A — Ler doc | `#read_text_file` "Usando a tool read_text_file do MCP fs-knowledge (não o acesso nativo), leia a seção 3.1 da POL-001 em docs/novatech." | `fs-knowledge` / `read_text_file` | Prazo de **7 dias úteis** para devolução |
| B — Recuperar chunk | `#search_files` "Usando a tool search_files do MCP fs-knowledge, procure 'Gold' em data/retrieval-corpus e devolva o chunk do SLA do cliente Gold." | `fs-knowledge` / `search_files` | **SLA-2024-B** (resposta 2h / resolução 24h úteis); secundários: SLA-2024-A, SLA-2024-C |
| C — Git | `#git_log` "Usando git_log e git_status do MCP git — não use o terminal — mostre os últimos commits e a branch atual." | `git` / `git_log`, `git_status` | Lista de commits do repositório + branch atual |
| D — Prova do read-only | `#write_file` "Usando write_file do MCP fs-knowledge, tente criar docs/novatech/teste.txt." | `fs-knowledge` / `write_file` | **Falha por permissão** — comprova o read-only (least privilege) |

## Registro dos resultados

| # | Tool chamada (confirmar no print) | Passou? | Print |
|---|---|---|---|
| A | `fs-knowledge / read_text_file` | Sim | `evidencias/evidencia-1.png` |
| B | `fs-knowledge / search_files` | Sim | `evidencias/evidencia-2.png` |
| C | `git / git_log` + `git_status` | Sim | `evidencias/evidencia-3.png` |
| D | `fs-knowledge / write_file` (falha esperada) | Sim | `evidencias/evidencia-4.png` |

## Anexos

- `evidencias/evidencia-1.png`
- `evidencias/evidencia-2.png`
- `evidencias/evidencia-3.png`
- `evidencias/evidencia-4.png`