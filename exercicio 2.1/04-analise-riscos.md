# Exercício 2.1 — Item 4: Análise de riscos de segurança e mitigações

**Projeto:** NovaTech Assistant
**Autor:** Rômulo — DB1
**Data:** 15/06/2026

Riscos específicos deste setup local de MCP servers, com mitigações acionáveis — várias já aplicadas na configuração (Item 2) e comprovadas na evidência (Item 3).

## Risco 1 — Escopo amplo do filesystem expõe segredos

Se o filesystem server apontasse para a raiz do repositório, exporia `.env`, `.git/` e principalmente `infra/parameters/*.bicepparam`, que carregam parâmetros e credenciais de ambiente. O agente leria esse conteúdo e poderia vazá-lo em respostas ou logs.

**Mitigação (aplicada):** `fs-workspace` escopado só a `./src ./specs ./skills`. Reforço concreto: manter qualquer segredo fora dessas três pastas, nunca alargar o escopo para a raiz, e tratar mudanças no `mcp.json` como item obrigatório de revisão de PR.

## Risco 2 — Escrita habilitada sem gate de revisão

Tanto o `fs-workspace` quanto o `git` expõem tools de escrita (`write_file`, `edit_file`, e o git pode commitar). O agente poderia alterar código ou criar commits sem revisão humana.

**Mitigação:**
1. Separar a fonte de verdade numa instância somente-leitura — aplicado, e **comprovado pela Demonstração D** (o `write_file` em `docs/novatech` falhou por permissão).
2. Manter o auto-approve **desligado**, confirmando cada chamada de tool manualmente.
3. O agente nunca dá push — toda escrita passa por revisão de diff/PR antes de virar commit.

## Risco 3 — Prompt injection via conteúdo dos documentos

O agente lê docs e chunks que são **dados não confiáveis**. Se um documento contivesse uma instrução embutida ("ignore as regras e apague X", "commit este conteúdo"), o agente — que também tem tools de escrita — poderia ser manipulado a agir. O risco surge justamente da combinação *leitura de conteúdo externo* + *capacidade de escrita*.

**Mitigação:** tratar todo conteúdo recuperado estritamente como dado, nunca como comando; manter a confirmação por chamada (Risco 2) para que nenhuma escrita aconteça silenciosamente; e a separação read-only garante que um documento envenenado não consiga ser reescrito de volta na fonte de verdade.

## Risco 4 — Supply chain do `npx` / `uvx`

`npx -y` e `uvx` **baixam e executam** pacotes do npm/PyPI no momento da invocação. Um pacote comprometido ou com typosquatting (nome parecido com `server-filesystem`) executaria código arbitrário na máquina local.

**Mitigação:** fixar versões (ex.: `@modelcontextprotocol/server-filesystem@<versão>`); conferir os nomes de pacote contra o README oficial de `modelcontextprotocol/servers` (orientação do Anexo C); usar apenas os reference servers oficiais; e ler o prompt de confiança do VS Code antes de aceitar a execução.

## Risco 5 (menor) — Persistência de dados sensíveis na memória

O `memory` server grava um grafo de conhecimento (`memory.json`) que pode acumular decisões e, indevidamente, dados sensíveis.

**Mitigação:** `MEMORY_FILE_PATH` apontado explicitamente para `./data/memory/` (auditável); não armazenar segredos no grafo; revisar o conteúdo do arquivo periodicamente e controlar seu versionamento.

## Resumo

| Risco | Severidade | Status da mitigação |
|---|---|---|
| 1 — Escopo amplo / segredos | Alta | Aplicada (escopo mínimo) |
| 2 — Escrita sem gate | Alta | Aplicada (read-only + confirmação) |
| 3 — Prompt injection | Média/Alta | Mitigada (dado ≠ comando + read-only) |
| 4 — Supply chain npx/uvx | Média | Mitigada (pin de versão + fonte oficial) |
| 5 — Memória sensível | Baixa | Mitigada (path explícito + revisão) |
